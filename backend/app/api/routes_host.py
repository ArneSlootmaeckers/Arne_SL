"""Host screen API (testsprong + Ski Jump-toegang in één scherm): scan,
verdict, practice acknowledgement.

Zodra een scan of oordeel de status op GESLAAGD of NIET_GESLAAGD zet (of
al zo'n status oplevert bij het scannen), doet dit meteen ook de Ski
Jump-toegangscontrole — inclusief het aansturen van het hekje en de
TOEGANG_SKI_JUMP-log — zodat de host niet naar een apart scherm hoeft.

Alles behalve /pair vereist een gekoppeld toestel (zie require_paired_device):
zonder geldige toestelsleutel kan niemand op het netwerk een bandje als
geslaagd laten markeren.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import (
    client_address,
    get_db,
    get_gate_controller,
    get_pairing_limiter,
    get_settings,
    require_paired_device,
)
from app.domain.status import Status
from app.hardware.gate_controller import GateController
from app.models import PairedDeviceModel
from app.schemas import (
    DeviceNameRequest,
    PairRequest,
    PairResponse,
    ScanRequest,
    ScanResponse,
    VerdictRequest,
    VerdictResponse,
)
from app.services import device_service, gate_service, lemon_service, pairing_service, scan_service
from app.services.common import log_event
from app.services.errors import InvalidPairingCodeError
from app.services.rate_limit import AttemptLimiter

router = APIRouter(prefix="/api/host", tags=["host"])
logger = logging.getLogger(__name__)

_FINAL_STATUSES = (Status.GESLAAGD, Status.NIET_GESLAAGD)


def _stop_player_at_kiosk(inbox, settings: Settings, payload: dict) -> None:
    """Na het antwoord aan het hostscherm: de host wacht hier niet op. Een
    fout wordt enkel kort gemeld (Beheer -> Systeem), zonder inhoud."""
    try:
        with httpx.Client(timeout=2.0, trust_env=False) as client:
            lemon_service.send_scores(
                client, host=settings.lemon_kiosk_host, port=settings.lemon_kiosk_port, payload=payload
            )
        inbox.scores_error = None
    except lemon_service.InvalidLemonDataError as exc:
        inbox.scores_error = str(exc)
    except Exception as exc:
        logger.warning("Stopbericht naar de Lemon-kiosk mislukt (%s)", type(exc).__name__)
        inbox.scores_error = "Onverwachte fout bij het stopbericht."


@router.post("/pair", response_model=PairResponse)
def pair(
    payload: PairRequest,
    request: Request,
    db: Session = Depends(get_db),
    limiter: AttemptLimiter = Depends(get_pairing_limiter),
) -> PairResponse:
    client = client_address(request)
    limiter.check(client)
    try:
        paired = pairing_service.pair_device(db, code=payload.code, name=payload.name, client=client)
    except InvalidPairingCodeError:
        if limiter.record_failure(client):
            log_event(db, event_type="KOPPELEN_GEBLOKKEERD", source="host", detail={"ip": client})
            db.commit()
        raise
    limiter.reset(client)
    return PairResponse(device_id=paired.device_id, token=paired.token)


@router.get("/lemon/session")
def current_lemon_session(
    request: Request,
    settings: Settings = Depends(get_settings),
    _: PairedDeviceModel = Depends(require_paired_device),
) -> dict:
    """De spelers die net aan de kiosk gestart zijn, om op het hostscherm te
    tonen. Enkel voor gekoppelde toestellen: hier staan namen in (enkel de
    voornaam en de eerste letter van de achternaam)."""
    inbox = request.app.state.lemon_inbox
    session = inbox.current()
    return {
        "enabled": bool(settings.lemon_kiosk_host),
        "session": None if session is None else {
            "key": session.key,
            "age_seconds": round(inbox.age_seconds(session), 1),
            "players": [
                {
                    "id": player.id,
                    "first_name": player.first_name,
                    "last_initial": player.last_initial,
                    "avatar_url": player.avatar_url,
                    "avatar_color": player.avatar_color,
                }
                for player in session.players
            ],
        },
    }


@router.get("/device")
def current_device(
    db: Session = Depends(get_db), device: PairedDeviceModel = Depends(require_paired_device)
) -> dict:
    """Laat het hostscherm bij het openen nagaan of zijn sleutel nog geldig is."""
    return {"device_id": device.device_id, "name": device_service.device_names(db).get(device.device_id)}


@router.post("/scan", response_model=ScanResponse)
def scan(
    payload: ScanRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    gate_controller: GateController = Depends(get_gate_controller),
    device: PairedDeviceModel = Depends(require_paired_device),
) -> ScanResponse:
    result = scan_service.register_scan(
        db,
        wristband_id=payload.wristband_id,
        device_id=device.device_id,
        timeout_seconds=settings.scan_timeout_seconds,
        tz=settings.tz,
    )

    ski_jump_toegestaan = None
    ski_jump_reden = None
    if result.status in _FINAL_STATUSES:
        ski_jump_toegestaan, _, ski_jump_reden = gate_service.check_gate_access(
            db,
            wristband_id=result.wristband_id,
            device_id=device.device_id,
            tz=settings.tz,
            gate_controller=gate_controller,
        )

    return ScanResponse(
        wristband_id=result.wristband_id,
        status=result.status,
        requires_verdict=result.requires_verdict,
        requires_practice_ack=result.requires_practice_ack,
        expires_at=result.expires_at,
        ski_jump_toegestaan=ski_jump_toegestaan,
        ski_jump_reden=ski_jump_reden,
    )


@router.post("/verdict", response_model=VerdictResponse)
def submit_verdict(
    payload: VerdictRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    gate_controller: GateController = Depends(get_gate_controller),
    device: PairedDeviceModel = Depends(require_paired_device),
) -> VerdictResponse:
    outcome = scan_service.submit_verdict(
        db, device_id=device.device_id, verdict=payload.verdict, tz=settings.tz
    )

    ski_jump_toegestaan = None
    ski_jump_reden = None
    if outcome.new_status in _FINAL_STATUSES:
        ski_jump_toegestaan, _, ski_jump_reden = gate_service.check_gate_access(
            db,
            wristband_id=outcome.wristband_id,
            device_id=device.device_id,
            tz=settings.tz,
            gate_controller=gate_controller,
        )

    # Kwam deze speler van de kiosk, dan krijgt Lemon (bij groen én rood)
    # een stopbericht: sessie + deze ene speler, geen score, geen resultaat.
    inbox = request.app.state.lemon_inbox
    session_id = inbox.take_session_id(outcome.wristband_id)
    if session_id is not None and settings.lemon_kiosk_host:
        background.add_task(
            _stop_player_at_kiosk, inbox, settings,
            lemon_service.scores_payload(
                session_id, outcome.wristband_id, game_mode_code=settings.lemon_game_mode_code
            ),
        )

    return VerdictResponse(
        status=outcome.new_status, ski_jump_toegestaan=ski_jump_toegestaan, ski_jump_reden=ski_jump_reden
    )


@router.post("/practice-ack")
def practice_ack(
    db: Session = Depends(get_db), device: PairedDeviceModel = Depends(require_paired_device)
) -> dict:
    scan_service.submit_practice_ack(db, device_id=device.device_id)
    return {"ok": True}


@router.post("/cancel")
def cancel_scan(
    db: Session = Depends(get_db), device: PairedDeviceModel = Depends(require_paired_device)
) -> dict:
    scan_service.cancel_scan(db, device_id=device.device_id)
    return {"ok": True}


@router.put("/device-name")
def set_device_name(
    payload: DeviceNameRequest,
    db: Session = Depends(get_db),
    device: PairedDeviceModel = Depends(require_paired_device),
) -> dict:
    device_service.set_device_name(db, device_id=device.device_id, name=payload.name)
    return {"ok": True}
