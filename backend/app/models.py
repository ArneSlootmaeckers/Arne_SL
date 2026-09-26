"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class WristbandModel(Base):
    __tablename__ = "wristbands"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)


class EmployeeModel(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    pincode_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class DailyStatusModel(Base):
    """One row per wristband per calendar day (Europe/Brussels). A row's absence,
    or a row whose status_date is not today, both mean NOG_NIET_GESPRONGEN —
    see app.domain.status.effective_status, the single source of truth for that rule.
    """

    __tablename__ = "daily_status"
    __table_args__ = (UniqueConstraint("wristband_id", "status_date", name="uq_wristband_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wristband_id: Mapped[str] = mapped_column(ForeignKey("wristbands.id"))
    status_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_by_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PendingScanModel(Base):
    """At most one open scan per device, enforcing "één scan = één oordeel"."""

    __tablename__ = "pending_scans"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    wristband_id: Mapped[str] = mapped_column(ForeignKey("wristbands.id"))
    status_snapshot: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime)
    event_type: Mapped[str] = mapped_column(String(40))
    wristband_id: Mapped[str | None] = mapped_column(
        ForeignKey("wristbands.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(64))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="{}")


class SessionModel(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_activity_at: Mapped[datetime] = mapped_column(UTCDateTime)
