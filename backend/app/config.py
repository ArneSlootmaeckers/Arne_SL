"""Application configuration, loaded from a single config.yaml file."""
from __future__ import annotations

from dataclasses import dataclass, field
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
    # Met standaardwaarde: een config.yaml van vóór deze velden blijft werken.
    # Poort voor de pc zelf (enkel 127.0.0.1, gewone http): het netwerk
    # gebruikt https op `port`.
    local_port: int = 8001
    # Map met het zelfgemaakte https-certificaat (relatief t.o.v. backend/).
    tls_dir: str = "../data/tls"
    # Bijkomende netwerken (bv. "203.0.113.0/24") die de server mogen
    # bereiken. Normaal leeg: enkel adressen van het eigen netwerk (geen
    # internetadressen) worden toegelaten, zie network_service.
    extra_allowed_networks: list[str] = field(default_factory=list)
    # Lemon-kiosk (zie app/services/lemon_service.py). Enkel dit adres mag
    # spelers doorsturen; leeg = koppeling uit.
    lemon_kiosk_host: str = ""
    lemon_kiosk_port: int = 4100
    # Fallback: deze server vraagt de spelers zelf op bij de kiosk.
    lemon_poll_enabled: bool = False
    lemon_poll_interval_seconds: float = 2

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
