"""Pure date/timezone helpers for the Europe/Brussels day boundary.

Uses the standard-library zoneinfo database (a local, deterministic lookup —
not network I/O), so the day-rollover rule stays correct across DST
transitions without an active reset job.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

BRUSSELS_TZ = ZoneInfo("Europe/Brussels")


def local_today(now_utc: datetime, tz: ZoneInfo = BRUSSELS_TZ) -> date:
    """Convert a timezone-aware UTC instant to the local (Brussels) calendar date."""
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    return now_utc.astimezone(tz).date()
