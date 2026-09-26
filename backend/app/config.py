"""Application configuration, loaded from a single config.yaml file."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


@dataclass(frozen=True)
class Settings:
    timezone: str
    port: int
    scan_timeout_seconds: int
    session_inactivity_timeout_seconds: int
    log_retention_days: int
    polling_interval_seconds: int
    cushion_sensor_enabled: bool
    gate_controller: str
    database_path: str
    maintenance_interval_hours: int
    backup_dir: str
    backup_retention_days: int

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


def load_settings(path: Path = DEFAULT_CONFIG_PATH) -> Settings:
    with open(path, "r", encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file)
    return Settings(**raw)
