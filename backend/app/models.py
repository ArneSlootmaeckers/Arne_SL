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


class DeviceModel(Base):
    """Leesbare naam per toestel (bv. "Host 1"), ingesteld op de telefoon zelf.
    Enkel voor weergave: de logs en openstaande scans blijven de unieke
    device_id gebruiken, zodat twee toestellen met dezelfde naam elkaar nooit
    in de weg zitten."""

    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class PairedDeviceModel(Base):
    """Een hosttoestel dat een beheerder één keer goedgekeurd heeft. Enkel
    gekoppelde toestellen mogen scannen en oordelen; het toestel bewijst wie
    het is met een geheime sleutel (zie pairing_service). De server bewaart
    daarvan enkel een hash: wie de database kan lezen, kan zich daarmee nog
    niet als toestel voordoen."""

    __tablename__ = "paired_devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    paired_at: Mapped[datetime] = mapped_column(UTCDateTime)
    paired_by_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)


class PairingCodeModel(Base):
    """Eenmalige koppelcode die een beheerder aanmaakt om één toestel te koppelen."""

    __tablename__ = "pairing_codes"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))


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
