"""High-platform gate API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db, get_gate_controller, get_settings
from app.hardware.gate_controller import GateController
from app.schemas import GateScanRequest, GateScanResponse
from app.services import gate_service

router = APIRouter(prefix="/api/gate", tags=["gate"])


@router.post("/scan", response_model=GateScanResponse)
def gate_scan(
    payload: GateScanRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    gate_controller: GateController = Depends(get_gate_controller),
) -> GateScanResponse:
    allowed, status, reason = gate_service.check_gate_access(
        db,
        wristband_id=payload.wristband_id,
        device_id=payload.device_id,
        tz=settings.tz,
        gate_controller=gate_controller,
    )
    return GateScanResponse(wristband_id=payload.wristband_id, status=status, allowed=allowed, reason=reason)
