"""FastAPI application factory.

Kept as a factory (rather than a module-level `app`) so tests can build an
isolated app against a temporary database and short timeouts, without any
import-time side effects on the real config.yaml / data file.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import ipaddress
import logging
from pathlib import Path

import httpx

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, load_settings
from app.database import create_session_factory
from app.hardware.gate_controller import create_gate_controller
from app.services.errors import (
    DeviceNotFoundError,
    DeviceNotPairedError,
    DomainServiceError,
    DuplicatePincodeError,
    InvalidPairingCodeError,
    InvalidPincodeError,
    NoPendingScanError,
    PermissionDeniedError,
    SessionExpiredError,
    TooManyAttemptsError,
    WeakPincodeError,
    WrongResolutionPathError,
)
from app.services.employee_service import anonymise_accounts
from app.services.lemon_service import InvalidLemonDataError, LemonInbox, fetch_players
from app.services.log_service import purge_old_events
from app.services.maintenance_service import create_backup, purge_old_backups
from app.services.network_service import is_local_client
from app.services.rate_limit import AttemptLimiter
from app.services.scan_service import reap_expired_pending_scans

logger = logging.getLogger("maintenance")

_ERROR_STATUS_CODES: dict[type[DomainServiceError], int] = {
    NoPendingScanError: 409,
    WrongResolutionPathError: 400,
    InvalidPincodeError: 401,
    SessionExpiredError: 401,
    PermissionDeniedError: 403,
    DuplicatePincodeError: 409,
    WeakPincodeError: 400,
    TooManyAttemptsError: 429,
    DeviceNotPairedError: 401,
    InvalidLemonDataError: 400,
    InvalidPairingCodeError: 400,
    DeviceNotFoundError: 404,
}

_REAPER_INTERVAL_SECONDS = 5.0
_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


def _frontend_version() -> str:
    """Vingerafdruk van alle schermbestanden: verandert enkel na een update.
    Een open scherm dat een andere waarde terugkrijgt van /api/health draait
    nog oude code en herlaadt zichzelf (zie frontend/shared/api.js)."""
    digest = hashlib.sha256()
    if _FRONTEND_DIR.is_dir():
        for path in sorted(p for p in _FRONTEND_DIR.rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(_FRONTEND_DIR)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


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


def _record_lemon_session(app: FastAPI, session) -> None:
    # Openen, schrijven en sluiten in dezelfde thread: wordt de lus bij het
    # afsluiten geannuleerd, dan werkt deze thread nog netjes af in plaats
    # van dat de verbinding onder hem gesloten wordt.
    from app.api.routes_lemon import record_new_session

    db = app.state.session_factory()
    try:
        record_new_session(db, session, source="lemon-kiosk")
    finally:
        db.close()


async def _poll_lemon_kiosk_periodically(app: FastAPI, settings: Settings) -> None:
    """GET-fallback: vraagt de spelers zelf op bij de kiosk. Een fout wordt
    enkel kort gemeld (op Beheer -> Systeem), nooit met de inhoud van het
    antwoord erbij."""
    inbox: LemonInbox = app.state.lemon_inbox
    with httpx.Client(timeout=2.0, trust_env=False) as client:
        while True:
            try:
                payload = await asyncio.to_thread(
                    fetch_players, client, host=settings.lemon_kiosk_host, port=settings.lemon_kiosk_port
                )
                session = inbox.receive(payload, via="get")
                inbox.poll_error = None
            except InvalidLemonDataError as exc:
                inbox.poll_error = str(exc)
                session = None
            except Exception as exc:  # de lus mag nooit stilletjes stoppen
                # Enkel het soort fout: een foutmelding kan ontvangen gegevens bevatten.
                logger.warning("Ophalen bij de Lemon-kiosk mislukt (%s)", type(exc).__name__)
                inbox.poll_error = "Onverwachte fout bij het ophalen."
                session = None
            if session is not None:
                await asyncio.to_thread(_record_lemon_session, app, session)
            await asyncio.sleep(settings.lemon_poll_interval_seconds)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.session_factory = create_session_factory(settings.database_url)
        app.state.gate_controller = create_gate_controller(settings.gate_controller)
        # Geen personeelsgegevens: namen van vroegere, persoonlijke accounts
        # worden vervangen door het label van hun groep.
        db = app.state.session_factory()
        try:
            anonymise_accounts(db)
        finally:
            db.close()

        tasks = [
            asyncio.create_task(_reap_expired_scans_periodically(app)),
            asyncio.create_task(_run_maintenance_periodically(app, settings)),
        ]
        if settings.lemon_poll_enabled and settings.lemon_kiosk_host:
            tasks.append(asyncio.create_task(_poll_lemon_kiosk_periodically(app, settings)))
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Toelatingssysteem veiligheidssprong", lifespan=lifespan)
    app.state.frontend_version = _frontend_version()
    # Na 5 foute pincodes of koppelcodes vanaf hetzelfde adres: 5 minuten geblokkeerd.
    app.state.login_limiter = AttemptLimiter()
    app.state.pairing_limiter = AttemptLimiter()
    # Laatste sessie van de Lemon-kiosk: enkel in het geheugen (namen!).
    app.state.lemon_inbox = LemonInbox()

    def _make_handler(status_code: int):
        async def _handler(request: Request, exc: DomainServiceError) -> JSONResponse:
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})

        return _handler

    for exc_class, status_code in _ERROR_STATUS_CODES.items():
        app.add_exception_handler(exc_class, _make_handler(status_code))

    # Zonder Cache-Control mag een browser/WebView een oude app.js blijven
    # gebruiken na een update, en een oude pagina met een nieuwe server laat
    # scans meteen weer verdwijnen. "no-cache" = altijd even navragen (een
    # goedkope 304 via de ETag als er niets veranderd is).
    @app.middleware("http")
    async def _no_stale_frontend(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-cache")
        return response

    # Als laatste toegevoegd = als eerste uitgevoerd: een verzoek vanaf een
    # internetadres komt nergens anders meer aan (ook niet aan de
    # schermbestanden). Tweede slot naast de firewall op de pc. Een fout in
    # extra_allowed_networks laat de server meteen bij het starten stoppen.
    extra_allowed_networks = [ipaddress.ip_network(network) for network in settings.extra_allowed_networks]

    @app.middleware("http")
    async def _only_local_network(request: Request, call_next):
        host = request.client.host if request.client else None
        if not is_local_client(host, extra_allowed_networks):
            return JSONResponse(status_code=403, content={"detail": "Enkel bereikbaar vanaf het eigen netwerk."})
        return await call_next(request)

    from app.api.routes_admin import router as admin_router
    from app.api.routes_auth import router as auth_router
    from app.api.routes_gate import router as gate_router
    from app.api.routes_health import router as health_router
    from app.api.routes_host import router as host_router
    from app.api.routes_lemon import router as lemon_router

    app.include_router(health_router)
    app.include_router(host_router)
    app.include_router(gate_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(lemon_router)

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
