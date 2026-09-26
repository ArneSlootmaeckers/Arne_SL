"""Database setup: SQLite with WAL mode and BEGIN IMMEDIATE transactions.

BEGIN IMMEDIATE makes every transaction take SQLite's write lock as soon as it
starts reading, not just when it first writes. That is what prevents two
concurrent verdicts for the same wristband from both reading the old status
and racing to write conflicting new ones: SQLite blocks the second
transaction until the first commits or rolls back (see services/scan_service.py).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Stores a timezone-aware UTC datetime as a naive UTC value (SQLite has no
    timezone-aware storage) and always returns it as timezone-aware on read,
    so callers never have to worry about naive/aware mismatches.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Expected a timezone-aware datetime")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    # A generous busy timeout: since every transaction takes the write lock via
    # BEGIN IMMEDIATE, concurrent requests are expected to briefly queue rather
    # than fail outright (the default 5s is too tight once bcrypt-backed pincode
    # checks stretch a transaction out).
    engine = create_engine(database_url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _disable_pysqlite_autobegin(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def _begin_immediate(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    from app import models  # noqa: F401  (registers tables on Base.metadata)

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
