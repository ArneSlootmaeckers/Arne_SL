"""Host screen API (testsprong + Ski Jump-toegang in één scherm): scan,
verdict, practice acknowledgement.

Zodra een scan of oordeel de status op GESLAAGD of NIET_GESLAAGD zet (of
al zo'n status oplevert bij het scannen), doet dit meteen ook de Ski
Jump-toegangscontrole — inclusief het aansturen van het hekje en de
TOEGANG_SKI_JUMP-log — zodat de host niet naar een apart scherm hoeft.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db, get_gate_controller, get_settings
from app.domain.status import Status
from app.hardware.gate_controller import GateController
from app.schemas import DeviceRequest, ScanRequest, ScanResponse, VerdictRequest, VerdictResponse
from app.services import gate_service, scan_service

router = APIRouter(prefix="/api/host", tags=["host"])

_FINAL_STATUSES = (Status.GESLAAGD, Status.NIET_GESLAAGD)


@router.post("/scan", response_model=ScanResponse)
def scan(
    payload: ScanRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    gate_controller: GateController = Depends(get_gate_controller),
) -> ScanResponse:
    result = scan_service.register_scan(
        db,
        wristband_id=payload.wristband_id,
        device_id=payload.device_id,
        timeout_seconds=settings.scan_timeout_seconds,
        tz=settings.tz,
    )

    ski_jump_toegestaan = None
    ski_jump_reden = None
    if result.status in _FINAL_STATUSES:
        ski_jump_toegestaan, _, ski_jump_reden = gate_service.check_gate_access(
            db,
            wristband_id=result.wristband_id,
            device_id=payload.device_id,
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
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    gate_controller: GateController = Depends(get_gate_controller),
) -> VerdictResponse:
    outcome = scan_service.submit_verdict(
        db, device_id=payload.device_id, verdict=payload.verdict, tz=settings.tz
    )

    ski_jump_toegestaan = None
    ski_jump_reden = None
    if outcome.new_status in _FINAL_STATUSES:
        ski_jump_toegestaan, _, ski_jump_reden = gate_service.check_gate_access(
            db,
            wristband_id=outcome.wristband_id,
            device_id=payload.device_id,
            tz=settings.tz,
            gate_controller=gate_controller,
        )

    return VerdictResponse(
        status=outcome.new_status, ski_jump_toegestaan=ski_jump_toegestaan, ski_jump_reden=ski_jump_reden
    )


@router.post("/practice-ack")
def practice_ack(payload: DeviceRequest, db: Session = Depends(get_db)) -> dict:
    scan_service.submit_practice_ack(db, device_id=payload.device_id)
    return {"ok": True}


@router.post("/cancel")
def cancel_scan(payload: DeviceRequest, db: Session = Depends(get_db)) -> dict:
    scan_service.cancel_scan(db, device_id=payload.device_id)
    return {"ok": True}
