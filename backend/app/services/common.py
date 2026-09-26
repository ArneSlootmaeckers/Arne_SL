"""Shared helpers used by multiple services: event logging, wristband lookup,
and reading a wristband's effective status for "today".
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.status import Status, effective_status
from app.models import DailyStatusModel, EventModel, WristbandModel


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def log_event(
    db: Session,
    *,
    event_type: str,
    source: str,
    wristband_id: str | None = None,
    employee_id: int | None = None,
    detail: dict | None = None,
) -> None:
    db.add(
        EventModel(
            timestamp=now_utc(),
            event_type=event_type,
            wristband_id=wristband_id,
            source=source,
            employee_id=employee_id,
            detail=json.dumps(detail or {}),
        )
    )


def get_or_create_wristband(db: Session, wristband_id: str) -> WristbandModel:
    band = db.get(WristbandModel, wristband_id)
    if band is None:
        band = WristbandModel(id=wristband_id, first_seen_at=now_utc())
        db.add(band)
        db.flush()
    return band


def read_effective_status(
    db: Session, wristband_id: str, today: date
) -> tuple[Status, DailyStatusModel | None]:
    row = db.execute(
        select(DailyStatusModel).where(
            DailyStatusModel.wristband_id == wristband_id,
            DailyStatusModel.status_date == today,
        )
    ).scalar_one_or_none()
    stored_status = Status(row.status) if row else None
    stored_date = row.status_date if row else None
    return effective_status(stored_status, stored_date, today), row
