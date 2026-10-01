"""Scan and verdict handling for the testsprong host screen.

Wires the pure domain rules (app.domain.status) to the database, keeping at
most one open scan per device and logging every step.

Een oordeel (1e/2e poging) heeft geen tijdslimiet: de host mag er zo lang
over doen als nodig. Scant de host intussen een nieuw bandje, dan vervangt
die scan de openstaande: het vorige bandje kreeg geen oordeel en behoudt
dus gewoon zijn status (gelogd als GEANNULEERD).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.calendar import local_today
from app.domain.status import Status, Verdict, apply_verdict
from app.models import DailyStatusModel, PendingScanModel
from app.services.common import get_or_create_wristband, log_event, now_utc, read_effective_status
from app.services.errors import NoPendingScanError, WrongResolutionPathError

# A scan opens a pending interaction: NOG_NIET_GESPRONGEN/HERKANSING wait for
# a verdict, GESLAAGD for a practice-jump acknowledgement. NIET_GESLAAGD needs
# neither, so it opens nothing.
_PENDING_STATUSES = {Status.NOG_NIET_GESPRONGEN, Status.HERKANSING, Status.GESLAAGD}
_VERDICT_STATUSES = {Status.NOG_NIET_GESPRONGEN, Status.HERKANSING}
_VERDICT_STATUS_VALUES = {s.value for s in _VERDICT_STATUSES}


@dataclass(frozen=True)
class ScanResult:
    wristband_id: str
    status: Status
    requires_verdict: bool
    requires_practice_ack: bool
    expires_at: datetime | None


def _expires(pending: PendingScanModel) -> bool:
    """Enkel een oefensprong verloopt (vangnet als het toestel uitvalt voor de
    automatische bevestiging); een scan die op een oordeel wacht nooit."""
    return pending.status_snapshot not in _VERDICT_STATUS_VALUES


def _expire_if_stale(db: Session, device_id: str) -> PendingScanModel | None:
    """Return the device's pending scan if still valid, otherwise clear+log it and return None."""
    pending = db.get(PendingScanModel, device_id)
    if pending is not None and _expires(pending) and pending.expires_at <= now_utc():
        log_event(db, event_type="TIME_OUT", wristband_id=pending.wristband_id, source=device_id)
        db.delete(pending)
        db.flush()
        return None
    return pending


def _close_for_new_scan(db: Session, pending: PendingScanModel) -> None:
    if pending.status_snapshot in _VERDICT_STATUS_VALUES:
        log_event(
            db, event_type="GEANNULEERD", wristband_id=pending.wristband_id, source=pending.device_id,
            detail={"reden": "nieuwe scan zonder oordeel"},
        )
    else:
        # Het hostscherm bevestigt een oefensprong anders zelf na enkele
        # seconden; een nieuwe scan in die tijd telt dus als bevestigd.
        log_event(db, event_type="OEFENSPRONG", wristband_id=pending.wristband_id, source=pending.device_id)
    db.delete(pending)
    db.flush()


def register_scan(
    db: Session, *, wristband_id: str, device_id: str, timeout_seconds: int, tz: ZoneInfo
) -> ScanResult:
    now = now_utc()
    today = local_today(now, tz)

    previous = _expire_if_stale(db, device_id)
    if previous is not None:
        _close_for_new_scan(db, previous)

    get_or_create_wristband(db, wristband_id)
    status, _ = read_effective_status(db, wristband_id, today)
    log_event(
        db, event_type="SCAN", wristband_id=wristband_id, source=device_id,
        detail={"status": status.value},
    )

    if status not in _PENDING_STATUSES:
        db.commit()
        return ScanResult(wristband_id, status, False, False, None)

    # De kolom is verplicht, maar wordt bij een oordeel-scan genegeerd (zie _expires).
    expires_at = now + timedelta(seconds=timeout_seconds)
    db.add(PendingScanModel(
        device_id=device_id, wristband_id=wristband_id,
        status_snapshot=status.value, created_at=now, expires_at=expires_at,
    ))
    db.commit()

    requires_verdict = status in _VERDICT_STATUSES
    return ScanResult(
        wristband_id=wristband_id,
        status=status,
        requires_verdict=requires_verdict,
        requires_practice_ack=(status is Status.GESLAAGD),
        expires_at=None if requires_verdict else expires_at,
    )


@dataclass(frozen=True)
class VerdictOutcome:
    wristband_id: str
    new_status: Status


def submit_verdict(db: Session, *, device_id: str, verdict: Verdict, tz: ZoneInfo) -> VerdictOutcome:
    now = now_utc()
    today = local_today(now, tz)

    pending = _expire_if_stale(db, device_id)
    if pending is None:
        db.commit()
        raise NoPendingScanError("Geen openstaande scan (of deze is verlopen).")
    if pending.status_snapshot not in _VERDICT_STATUS_VALUES:
        raise WrongResolutionPathError(
            "Dit bandje wacht niet op een oordeel; gebruik de bevestigingsknop."
        )

    wristband_id = pending.wristband_id
    status, row = read_effective_status(db, wristband_id, today)
    result = apply_verdict(status, verdict)

    if row is None:
        row = DailyStatusModel(wristband_id=wristband_id, status_date=today)
        db.add(row)
    row.status = result.new_status.value
    row.updated_at = now
    row.updated_by_employee_id = None
    row.reason = None

    db.delete(pending)
    log_event(
        db, event_type="OORDEEL", wristband_id=wristband_id, source=device_id,
        detail={
            "verdict": verdict.value,
            "oude_status": status.value,
            "nieuwe_status": result.new_status.value,
        },
    )
    db.commit()
    return VerdictOutcome(wristband_id=wristband_id, new_status=result.new_status)


def submit_practice_ack(db: Session, *, device_id: str) -> None:
    pending = _expire_if_stale(db, device_id)
    if pending is None:
        db.commit()
        raise NoPendingScanError("Geen openstaande scan (of deze is verlopen).")
    if pending.status_snapshot != Status.GESLAAGD.value:
        raise WrongResolutionPathError("Dit bandje heeft een oordeel nodig (groen/rood).")

    wristband_id = pending.wristband_id
    db.delete(pending)
    log_event(db, event_type="OEFENSPRONG", wristband_id=wristband_id, source=device_id)
    db.commit()


def cancel_scan(db: Session, *, device_id: str) -> None:
    """Discard the device's pending scan without any status change — for when
    the visitor scanned but didn't actually jump (changed their mind, called
    away, ...).
    """
    pending = _expire_if_stale(db, device_id)
    if pending is None:
        db.commit()
        raise NoPendingScanError("Geen openstaande scan (of deze is verlopen).")

    wristband_id = pending.wristband_id
    db.delete(pending)
    log_event(db, event_type="GEANNULEERD", wristband_id=wristband_id, source=device_id)
    db.commit()


def reap_expired_pending_scans(db: Session) -> int:
    """Background sweep so a time-out gets logged promptly even without a next scan."""
    now = now_utc()
    expired = list(
        db.execute(
            select(PendingScanModel).where(
                PendingScanModel.expires_at <= now,
                PendingScanModel.status_snapshot.not_in(_VERDICT_STATUS_VALUES),
            )
        ).scalars()
    )
    for pending in expired:
        log_event(db, event_type="TIME_OUT", wristband_id=pending.wristband_id, source=pending.device_id)
        db.delete(pending)
    if expired:
        db.commit()
    return len(expired)
