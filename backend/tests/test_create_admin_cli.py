"""create_admin.py's non-interactive mode (--name/--pincode), used by the
Windows installer to create the first admin without any prompts."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import create_admin
from app.config import Settings
from app.database import create_session_factory
from app.models import EmployeeModel


@pytest.fixture
def cli_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(
        timezone="Europe/Brussels",
        port=8000,
        scan_timeout_seconds=60,
        session_inactivity_timeout_seconds=120,
        log_retention_days=365,
        polling_interval_seconds=3,
        cushion_sensor_enabled=False,
        gate_controller="dummy",
        database_path=str(tmp_path / "test.db"),
        maintenance_interval_hours=24,
        backup_dir=str(tmp_path / "backups"),
        backup_retention_days=30,
    )
    monkeypatch.setattr(create_admin, "load_settings", lambda: settings)
    return settings


def test_non_interactive_creates_admin(cli_settings: Settings, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "--name", "Installer Admin", "--pincode", "13579"])
    create_admin.main()

    db = create_session_factory(cli_settings.database_url)()
    try:
        employee = db.query(EmployeeModel).filter_by(name="Installer Admin").one()
        assert employee.role == "admin"
        assert employee.active is True
    finally:
        db.close()


def test_non_interactive_rejects_short_pincode(cli_settings: Settings, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "--name", "Kort", "--pincode", "12"])
    with pytest.raises(SystemExit):
        create_admin.main()


def test_non_interactive_rejects_empty_name(cli_settings: Settings, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "--name", "  ", "--pincode", "1234"])
    with pytest.raises(SystemExit):
        create_admin.main()


def test_non_interactive_rejects_duplicate_pincode(cli_settings: Settings, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "--name", "Eerste", "--pincode", "24680"])
    create_admin.main()

    monkeypatch.setattr(sys, "argv", ["create_admin.py", "--name", "Tweede", "--pincode", "24680"])
    with pytest.raises(SystemExit):
        create_admin.main()
