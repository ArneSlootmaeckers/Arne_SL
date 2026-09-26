"""Daily overview aggregation for the admin screen.

"Gemiddelde tijd tussen twee sprongen" is interpreted as the throughput of
the low platform: the average gap between consecutive SCAN events that day,
across all wristbands.
"""
from __future__ import annotations

import json
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.calendar import local_day_utc_range
from app.models import EventModel


def daily_report(db: Session, *, report_date: date, tz: ZoneInfo) -> dict:
    start_utc, end_utc = local_day_utc_range(report_date, tz)
    stmt = (
        select(EventModel)
        .where(
            EventModel.timestamp >= start_utc,
            EventModel.timestamp < end_utc,
            EventModel.event_type.in_(["OORDEEL", "OEFENSPRONG", "SCAN"]),
        )
        .order_by(EventModel.timestamp)
    )
    events = list(db.execute(stmt).scalars())

    geslaagd = herkansing = niet_geslaagd = oefensprongen = 0
    scan_timestamps = []
    for event in events:
        detail = json.loads(event.detail) if event.detail else {}
        if event.event_type == "OORDEEL":
            nieuwe_status = detail.get("nieuwe_status")
            if nieuwe_status == "GESLAAGD":
                geslaagd += 1
            elif nieuwe_status == "HERKANSING":
                herkansing += 1
            elif nieuwe_status == "NIET_GESLAAGD":
                niet_geslaagd += 1
        elif event.event_type == "OEFENSPRONG":
            oefensprongen += 1
        elif event.event_type == "SCAN":
            scan_timestamps.append(event.timestamp)

    scan_timestamps.sort()
    gaps = [(b - a).total_seconds() for a, b in zip(scan_timestamps, scan_timestamps[1:])]
    gemiddelde = sum(gaps) / len(gaps) if gaps else None

    return {
        "date": report_date.isoformat(),
        "totaal_testsprongen": geslaagd + herkansing + niet_geslaagd,
        "geslaagd": geslaagd,
        "herkansing": herkansing,
        "niet_geslaagd": niet_geslaagd,
        "oefensprongen": oefensprongen,
        "gemiddelde_tijd_tussen_sprongen_seconden": gemiddelde,
    }
