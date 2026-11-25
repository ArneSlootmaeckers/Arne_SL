"""Ontvangt de spelers van de Lemon-kiosk (zie app/services/lemon_service.py).

De kiosk kan niet gekoppeld worden zoals een telefoon; enkel het IP-adres
van de kiosk (Beheer -> Systeem, of lemon_kiosk_host in config.yaml) mag
hier spelers doorsturen.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.dependencies import client_address, get_db, get_settings
from app.services.common import log_event
from app.services.errors import PermissionDeniedError
from app.services.lemon_service import InvalidLemonDataError, parse_session

router = APIRouter(prefix="/api/lemon", tags=["lemon"])
logger = logging.getLogger("lemon")


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
    inbox = request.app.state.lemon_inbox
    sender = client_address(request)

    def refuse(result: str, error: Exception) -> Exception:
        # Zichtbaar op Beheer -> Systeem en in het logbestand van de server,
        # zonder iets van de ontvangen gegevens.
        inbox.record_attempt(via="post", sender=sender, result=result, ok=False)
        logger.warning("Lemon-kiosk: verzoek van %s niet verwerkt: %s", sender, result)
        return error

    if not settings.lemon_kiosk_host:
        raise refuse(
            "Geweigerd: geen kiosk ingesteld (Beheer -> Systeem)",
            PermissionDeniedError("Geen Lemon-kiosk ingesteld."),
        )
    if sender != settings.lemon_kiosk_host:
        raise refuse(
            f"Geweigerd: komt van {sender}, de ingestelde kiosk is {settings.lemon_kiosk_host}",
            PermissionDeniedError("Enkel de ingestelde Lemon-kiosk mag spelers doorsturen."),
        )
    try:
        payload = await request.json()
    except ValueError:
        raise refuse("Ongeldige gegevens: geen JSON", InvalidLemonDataError("Ongeldige sessie van de kiosk.")) from None

    try:
        _, players = parse_session(payload)
        session = inbox.receive(payload, via="post")
    except InvalidLemonDataError as exc:
        raise refuse(f"Ongeldige gegevens ({getattr(exc, 'hint', '')})", exc) from None

    if session is not None:
        inbox.record_attempt(via="post", sender=sender, result=f"Ontvangen: {len(players)} speler(s)", ok=True)
        # Database-werk niet op de event loop (zoals de gewone routes).
        await run_in_threadpool(record_new_session, db, session, source="lemon-kiosk")
    elif not players:
        inbox.record_attempt(via="post", sender=sender, result="Ontvangen, maar zonder spelers", ok=True)
    else:
        inbox.record_attempt(via="post", sender=sender, result="Al ontvangen (zelfde sessie)", ok=True)
    return {"ok": True}
