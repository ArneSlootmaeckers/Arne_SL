"""Host screen API (low platform): scan, verdict, practice acknowledgement."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db, get_settings
from app.schemas import PracticeAckRequest, ScanRequest, ScanResponse, VerdictRequest
from app.services import scan_service

router = APIRouter(prefix="/api/host", tags=["host"])


@router.post("/scan", response_model=ScanResponse)
def scan(
    payload: ScanRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> ScanResponse:
    result = scan_service.register_scan(
        db,
        wristband_id=payload.wristband_id,
        device_id=payload.device_id,
        timeout_seconds=settings.scan_timeout_seconds,
        tz=settings.tz,
    )
    return ScanResponse(
        wristband_id=result.wristband_id,
        status=result.status,
        requires_verdict=result.requires_verdict,
        requires_practice_ack=result.requires_practice_ack,
        expires_at=result.expires_at,
    )


@router.post("/verdict")
def submit_verdict(
    payload: VerdictRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict:
    new_status = scan_service.submit_verdict(
        db, device_id=payload.device_id, verdict=payload.verdict, tz=settings.tz
    )
    return {"status": new_status}


@router.post("/practice-ack")
def practice_ack(payload: PracticeAckRequest, db: Session = Depends(get_db)) -> dict:
    scan_service.submit_practice_ack(db, device_id=payload.device_id)
    return {"ok": True}
