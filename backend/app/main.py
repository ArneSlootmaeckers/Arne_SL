"""FastAPI application factory.

Kept as a factory (rather than a module-level `app`) so tests can build an
isolated app against a temporary database and short timeouts, without any
import-time side effects on the real config.yaml / data file.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, load_settings
from app.database import create_session_factory
from app.hardware.gate_controller import create_gate_controller
from app.services.errors import (
    DomainServiceError,
    DuplicatePincodeError,
    EmployeeNotFoundError,
    InvalidPincodeError,
    NoPendingScanError,
    PermissionDeniedError,
    SessionExpiredError,
    WrongResolutionPathError,
)
from app.services.log_service import purge_old_events
from app.services.maintenance_service import create_backup, purge_old_backups
from app.services.scan_service import reap_expired_pending_scans

logger = logging.getLogger("maintenance")

_ERROR_STATUS_CODES: dict[type[DomainServiceError], int] = {
    NoPendingScanError: 409,
    WrongResolutionPathError: 400,
    InvalidPincodeError: 401,
    SessionExpiredError: 401,
    PermissionDeniedError: 403,
    DuplicatePincodeError: 409,
    EmployeeNotFoundError: 404,
}

_REAPER_INTERVAL_SECONDS = 5.0
_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


async def _reap_expired_scans_periodically(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(_REAPER_INTERVAL_SECONDS)
        db = app.state.session_factory()
        try:
            # Run off the event loop: this is a blocking DB call, and the sync
            # API routes already run in Starlette's thread pool, not on the
            # loop — keeping this here too avoids stalling everything else
            # (and stalling it is also what stops asyncio from cancelling
            # this task promptly on shutdown).
            await asyncio.to_thread(reap_expired_pending_scans, db)
        finally:
            db.close()


async def _run_maintenance_periodically(app: FastAPI, settings: Settings) -> None:
    """Purges old logs and takes a database back-up, immediately at startup
    and then every `maintenance_interval_hours`. A failed backup/purge is
    logged but never crashes this loop — there's always a next attempt.
    """
    backup_dir = Path(settings.backup_dir)
    interval_seconds = settings.maintenance_interval_hours * 3600

    while True:
        db = app.state.session_factory()
        try:
            await asyncio.to_thread(purge_old_events, db, settings.log_retention_days)
        except Exception:
            logger.exception("Opruimen van oude logs is mislukt")
        finally:
            db.close()

        try:
            await asyncio.to_thread(create_backup, settings.database_path, backup_dir)
            await asyncio.to_thread(purge_old_backups, backup_dir, settings.backup_retention_days)
        except Exception:
            logger.exception("Automatische back-up is mislukt")

        await asyncio.sleep(interval_seconds)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.session_factory = create_session_factory(settings.database_url)
        app.state.gate_controller = create_gate_controller(settings.gate_controller)

        reaper_task = asyncio.create_task(_reap_expired_scans_periodically(app))
        maintenance_task = asyncio.create_task(_run_maintenance_periodically(app, settings))
        try:
            yield
        finally:
            reaper_task.cancel()
            maintenance_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reaper_task
            with contextlib.suppress(asyncio.CancelledError):
                await maintenance_task

    app = FastAPI(title="Toelatingssysteem veiligheidssprong", lifespan=lifespan)

    def _make_handler(status_code: int):
        async def _handler(request: Request, exc: DomainServiceError) -> JSONResponse:
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})

        return _handler

    for exc_class, status_code in _ERROR_STATUS_CODES.items():
        app.add_exception_handler(exc_class, _make_handler(status_code))

    from app.api.routes_admin import router as admin_router
    from app.api.routes_auth import router as auth_router
    from app.api.routes_gate import router as gate_router
    from app.api.routes_health import router as health_router
    from app.api.routes_host import router as host_router

    app.include_router(health_router)
    app.include_router(host_router)
    app.include_router(gate_router)
    app.include_router(auth_router)
    app.include_router(admin_router)

    # Each screen is a plain static site; mount whichever ones exist yet
    # plus the assets they share.
    if (_FRONTEND_DIR / "shared").is_dir():
        app.mount("/shared", StaticFiles(directory=_FRONTEND_DIR / "shared"), name="shared")
    for screen in ("host", "admin"):
        screen_dir = _FRONTEND_DIR / screen
        if screen_dir.is_dir():
            app.mount(f"/{screen}", StaticFiles(directory=screen_dir, html=True), name=screen)

    # Browsers request this path directly regardless of a page's <link> tag.
    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> FileResponse:
        return FileResponse(_FRONTEND_DIR / "shared" / "icons" / "favicon.ico")

    # The app always opens on the host screen — no separate chooser page.
    @app.get("/", include_in_schema=False)
    def root(request: Request) -> RedirectResponse:
        # Querystring meegeven: de Android-app opent "/?toestel=Host+1".
        query = request.url.query
        return RedirectResponse(url=f"/host/?{query}" if query else "/host/")

    return app
