"""Access check for the high-platform gate."""
from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.domain.calendar import local_today
from app.domain.status import Status, can_jump_high_platform
from app.hardware.gate_controller import GateController
from app.services.common import get_or_create_wristband, log_event, now_utc, read_effective_status

_DENY_REASONS = {
    Status.NOG_NIET_GESPRONGEN: "Eerst testsprong doen op het startplatform",
    Status.HERKANSING: "Nog één poging op het startplatform",
    Status.NIET_GESLAAGD: "Vandaag niet meer toegestaan",
}


def check_gate_access(
    db: Session,
    *,
    wristband_id: str,
    device_id: str,
    tz: ZoneInfo,
    gate_controller: GateController,
) -> tuple[bool, Status, str | None]:
    today = local_today(now_utc(), tz)

    get_or_create_wristband(db, wristband_id)
    status, _ = read_effective_status(db, wristband_id, today)
    allowed = can_jump_high_platform(status)
    reason = None if allowed else _DENY_REASONS[status]

    gate_controller.trigger_access(allowed, wristband_id=wristband_id)
    log_event(
        db, event_type="TOEGANG_HOOG_PLATFORM", wristband_id=wristband_id, source=device_id,
        detail={"toegestaan": allowed, "status": status.value},
    )
    db.commit()
    return allowed, status, reason
