"""Event log querying, CSV export and retention cleanup."""
from __future__ import annotations

import csv
import io
import json
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.calendar import local_day_utc_range
from app.models import EventModel
from app.services.common import now_utc


def query_events(
    db: Session,
    *,
    tz: ZoneInfo,
    event_date: date | None = None,
    wristband_id: str | None = None,
    employee_id: int | None = None,
    event_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[EventModel]:
    stmt = select(EventModel).order_by(EventModel.timestamp.desc())
    if wristband_id is not None:
        stmt = stmt.where(EventModel.wristband_id == wristband_id)
    if employee_id is not None:
        stmt = stmt.where(EventModel.employee_id == employee_id)
    if event_type is not None:
        stmt = stmt.where(EventModel.event_type == event_type)
    if event_date is not None:
        start_utc, end_utc = local_day_utc_range(event_date, tz)
        stmt = stmt.where(EventModel.timestamp >= start_utc, EventModel.timestamp < end_utc)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.execute(stmt).scalars())


def event_to_dict(event: EventModel, device_names: dict[str, str]) -> dict:
    return {
        "id": event.id,
        "timestamp": event.timestamp,
        "event_type": event.event_type,
        "wristband_id": event.wristband_id,
        "source": event.source,
        "device_name": device_names.get(event.source),
        "employee_id": event.employee_id,
        "detail": json.loads(event.detail) if event.detail else {},
    }


def events_to_csv(events: list[EventModel], device_names: dict[str, str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "tijdstip_utc", "type", "bandje_id", "bron", "toestelnaam", "medewerker_id", "detail"]
    )
    for event in events:
        writer.writerow([
            event.id, event.timestamp.isoformat(), event.event_type,
            event.wristband_id or "", event.source, device_names.get(event.source, ""),
            event.employee_id or "", event.detail,
        ])
    return buffer.getvalue()


def purge_old_events(db: Session, retention_days: int) -> int:
    from datetime import timedelta

    cutoff = now_utc() - timedelta(days=retention_days)
    old_events = list(db.execute(select(EventModel).where(EventModel.timestamp < cutoff)).scalars())
    for event in old_events:
        db.delete(event)
    if old_events:
        db.commit()
    return len(old_events)
