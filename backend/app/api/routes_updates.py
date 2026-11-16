"""Updates op het beheerscherm (Systeem -> Updates), enkel voor de beheerder.

Controleren, automatisch bijwerken aan/uit, en met één klik de nieuwste
stabiele versie of beta installeren (zie app/services/update_service.py).
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db, get_settings, require_role
from app.models import EmployeeModel
from app.services import update_service
from app.services.common import log_event, now_utc
from app.services.update_service import UpdateError, UpdateStore
from app.version import APP_VERSION

router = APIRouter(prefix="/api/admin/updates", tags=["updates"])


class UpdateSettingsRequest(BaseModel):
    auto_install: bool


class InstallRequest(BaseModel):
    channel: Literal["stable", "beta"]


def _store(settings: Settings) -> UpdateStore:
    return UpdateStore(update_service.updates_dir_for(settings.database_path))


def _check(request: Request, settings: Settings) -> tuple:
    """Haalt de releases op en onthoudt het resultaat (enkel in het geheugen)."""
    try:
        with request.app.state.update_http_client() as client:
            stable, beta = update_service.latest_releases(update_service.fetch_releases(client, settings.update_repo))
        request.app.state.update_check = {"checked_at": now_utc(), "stable": stable, "beta": beta, "error": None}
    except UpdateError as exc:
        request.app.state.update_check = {"checked_at": now_utc(), "stable": None, "beta": None, "error": str(exc)}
        stable = beta = None
    return stable, beta


def _offer(release) -> dict | None:
    if release is None:
        return None
    return {**release.as_dict(), "newer": update_service.is_newer(release.version, APP_VERSION)}


def _overview(request: Request, settings: Settings) -> dict:
    check = request.app.state.update_check
    store = _store(settings)
    return {
        "current_version": APP_VERSION,
        "repo": settings.update_repo,
        "auto_install": store.auto_install(),
        "dev_checkout": update_service.is_dev_checkout(request.app.state.install_root),
        "can_restart": getattr(request.app.state, "uvicorn_server", None) is not None,
        "last_result": store.last_result(),
        "check": None if check is None else {
            "checked_at": check["checked_at"],
            "error": check["error"],
            "stable": _offer(check["stable"]),
            "beta": _offer(check["beta"]),
        },
    }


@router.get("")
def update_status(
    request: Request,
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin")),
) -> dict:
    return _overview(request, settings)


@router.post("/check")
def check_for_updates(
    request: Request,
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin")),
) -> dict:
    _check(request, settings)
    return _overview(request, settings)


@router.put("/settings")
def set_update_settings(
    payload: UpdateSettingsRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    employee: EmployeeModel = Depends(require_role("admin")),
) -> dict:
    _store(settings).set_auto_install(payload.auto_install)
    log_event(
        db, event_type="UPDATE_INSTELLING", source="admin", employee_id=employee.id,
        detail={"automatisch": payload.auto_install},
    )
    db.commit()
    return _overview(request, settings)


@router.post("/install")
def install_update(
    payload: InstallRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    employee: EmployeeModel = Depends(require_role("admin")),
) -> dict:
    """Downloadt de gekozen versie, zet ze klaar en herstart de server; bij
    het opstarten installeert run.py ze (zie update_service)."""
    server = getattr(request.app.state, "uvicorn_server", None)
    if server is None:
        raise HTTPException(status_code=503, detail="Kan niet herstarten: de server is niet gestart via run.py.")
    install_root = request.app.state.install_root
    if update_service.is_dev_checkout(install_root):
        raise HTTPException(status_code=409, detail="Dit is een ontwikkelkopie (git): werk die bij met git pull.")

    stable, beta = _check(request, settings)
    error = request.app.state.update_check["error"]
    if error:
        raise HTTPException(status_code=502, detail=error)
    release = stable if payload.channel == "stable" else beta
    if release is None or not update_service.is_newer(release.version, APP_VERSION):
        raise HTTPException(status_code=409, detail="Er is geen nieuwere versie om te installeren.")

    store = _store(settings)
    try:
        with request.app.state.update_http_client() as client:
            staged = update_service.download_and_stage(client, release, store.dir)
    except UpdateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    store.set_pending(release.version, staged, payload.channel)

    log_event(
        db, event_type="UPDATE_GESTART", source="admin", employee_id=employee.id,
        detail={"van": APP_VERSION, "naar": release.version, "kanaal": payload.channel},
    )
    db.commit()
    request.app.state.restart_for_update = True
    server.should_exit = True
    return {"ok": True, "version": release.version}
