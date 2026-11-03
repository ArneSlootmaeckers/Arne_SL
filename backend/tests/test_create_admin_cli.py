"""create_admin.py's non-interactive mode (--pincode), used by the Windows
installer to set the beheerder's pincode without any prompts."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import create_admin
from app.config import Settings
from app.database import create_session_factory
from app.models import EmployeeModel
from app.security import verify_pincode


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


def _beheerders(settings: Settings) -> list[EmployeeModel]:
    db = create_session_factory(settings.database_url)()
    try:
        return db.query(EmployeeModel).filter_by(role="admin").all()
    finally:
        db.close()


def test_non_interactive_sets_admin_pincode(cli_settings: Settings, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "--pincode", "135790"])
    create_admin.main()

    [account] = _beheerders(cli_settings)
    assert account.name == "Beheerder"  # geen persoonsnaam
    assert account.active is True
    assert verify_pincode("135790", account.pincode_hash)


def test_running_again_replaces_the_admin_pincode(cli_settings: Settings, monkeypatch: pytest.MonkeyPatch):
    # Zo raakt de beheerder weer binnen als niemand de pincode nog weet.
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "--pincode", "135790"])
    create_admin.main()
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "--pincode", "246800"])
    create_admin.main()

    [account] = [a for a in _beheerders(cli_settings) if a.active]
    assert verify_pincode("246800", account.pincode_hash)


def test_non_interactive_rejects_short_pincode(cli_settings: Settings, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "--pincode", "12345"])
    with pytest.raises(SystemExit):
        create_admin.main()
    assert _beheerders(cli_settings) == []
