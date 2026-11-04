"""Ontvangt de spelers van de Lemon-kiosk (zie app/services/lemon_service.py).

De kiosk kan niet gekoppeld worden zoals een telefoon; enkel het IP-adres
dat in config.yaml als lemon_kiosk_host staat, mag hier spelers doorsturen.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.dependencies import client_address, get_db, get_settings
from app.services.common import log_event
from app.services.errors import PermissionDeniedError
from app.services.lemon_service import InvalidLemonDataError

router = APIRouter(prefix="/api/lemon", tags=["lemon"])


def record_new_session(db: Session, session, *, source: str) -> None:
    """Logt dat er spelers binnenkwamen: enkel het aantal en de weg, geen
    namen (en geen sessie-ID: enkel de UUID van een speler mag bewaard worden)."""
    log_event(
        db, event_type="LEMON_SESSIE", source=source,
        detail={"spelers": len(session.players), "via": session.via},
    )
    db.commit()


@router.post("/session")
async def receive_session(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.lemon_kiosk_host:
        raise PermissionDeniedError("Geen Lemon-kiosk ingesteld (lemon_kiosk_host in config.yaml).")
    if client_address(request) != settings.lemon_kiosk_host:
        raise PermissionDeniedError("Enkel de ingestelde Lemon-kiosk mag spelers doorsturen.")
    try:
        payload = await request.json()
    except ValueError:
        raise InvalidLemonDataError("Ongeldige sessie van de kiosk.") from None

    session = request.app.state.lemon_inbox.receive(payload, via="post")
    if session is not None:
        # Database-werk niet op de event loop (zoals de gewone routes).
        await run_in_threadpool(record_new_session, db, session, source="lemon-kiosk")
    return {"ok": True}
