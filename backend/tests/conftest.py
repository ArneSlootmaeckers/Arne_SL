"""Shared pytest fixtures: an isolated FastAPI app + TestClient per test,
backed by a throwaway SQLite file, with short timeouts so time-out and
inactivity behaviour is testable without waiting for the real 60s/120s
production defaults.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import EmployeeModel
from app.security import hash_pincode
from app.services.common import now_utc


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        timezone="Europe/Brussels",
        port=8000,
        scan_timeout_seconds=1,
        session_inactivity_timeout_seconds=2,
        log_retention_days=365,
        polling_interval_seconds=3,
        cushion_sensor_enabled=False,
        gate_controller="dummy",
        database_path=str(tmp_path / "test.db"),
        maintenance_interval_hours=24,
        backup_dir=str(tmp_path / "backups"),
        backup_retention_days=30,
    )


@pytest.fixture
def client(test_settings: Settings):
    app = create_app(test_settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session(client: TestClient):
    """A raw DB session on the same database as `client`, for setup/assertions."""
    session = client.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_employee(db_session) -> EmployeeModel:
    employee = EmployeeModel(
        name="Test Admin", pincode_hash=hash_pincode("1234"), role="admin",
        active=True, created_at=now_utc(),
    )
    db_session.add(employee)
    db_session.commit()
    return employee


@pytest.fixture
def supervisor_employee(db_session) -> EmployeeModel:
    employee = EmployeeModel(
        name="Test Supervisor", pincode_hash=hash_pincode("5678"), role="supervisor",
        active=True, created_at=now_utc(),
    )
    db_session.add(employee)
    db_session.commit()
    return employee
