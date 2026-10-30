"""Hosttoestellen koppelen: een beheerder maakt een eenmalige koppelcode aan,
de telefoon ruilt die in voor een eigen geheime sleutel, en stuurt die
sleutel daarna mee bij elke scan en elk oordeel.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import PairedDeviceModel, PairingCodeModel, PendingScanModel
from app.services import device_service
from app.services.common import log_event, now_utc
from app.services.errors import DeviceNotFoundError, DeviceNotPairedError, InvalidPairingCodeError

PAIRING_CODE_VALID_MINUTES = 10
PAIRING_CODE_LENGTH = 6
# "Laatst gezien" hoeft niet op de seconde juist te zijn: zo schrijft niet
# elke scan ook nog eens naar de database.
_LAST_SEEN_RESOLUTION = timedelta(minutes=1)


@dataclass(frozen=True)
class PairingCode:
    code: str
    expires_at: datetime


@dataclass(frozen=True)
class PairedDevice:
    device_id: str
    token: str


def hash_device_token(token: str) -> str:
    # Een sleutel van 32 willekeurige bytes is niet te raden: een snelle
    # hash volstaat (bcrypt is enkel nodig voor korte geheimen zoals pincodes).
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_pairing_code(db: Session, *, employee_id: int) -> PairingCode:
    now = now_utc()
    db.execute(delete(PairingCodeModel).where(PairingCodeModel.expires_at <= now))
    while True:
        code = f"{secrets.randbelow(10**PAIRING_CODE_LENGTH):0{PAIRING_CODE_LENGTH}d}"
        if db.get(PairingCodeModel, code) is None:
            break
    expires_at = now + timedelta(minutes=PAIRING_CODE_VALID_MINUTES)
    db.add(PairingCodeModel(code=code, created_at=now, expires_at=expires_at, created_by_employee_id=employee_id))
    log_event(db, event_type="KOPPELCODE_AANGEMAAKT", source="admin", employee_id=employee_id)
    db.commit()
    return PairingCode(code=code, expires_at=expires_at)


def pair_device(db: Session, *, code: str, name: str, client: str | None = None) -> PairedDevice:
    """Ruilt een geldige koppelcode in (eenmalig) voor een nieuw toestel + sleutel."""
    now = now_utc()
    pairing_code = db.get(PairingCodeModel, code.strip())
    if pairing_code is None or pairing_code.expires_at <= now:
        log_event(db, event_type="KOPPELEN_MISLUKT", source="host", detail={"ip": client})
        db.commit()
        raise InvalidPairingCodeError("Onjuiste of verlopen koppelcode. Vraag een nieuwe code aan een beheerder.")

    device_id = f"toestel-{secrets.token_hex(4)}"
    while db.get(PairedDeviceModel, device_id) is not None:
        device_id = f"toestel-{secrets.token_hex(4)}"
    token = secrets.token_urlsafe(32)

    db.delete(pairing_code)
    db.add(
        PairedDeviceModel(
            device_id=device_id, token_hash=hash_device_token(token), paired_at=now,
            paired_by_employee_id=pairing_code.created_by_employee_id, last_seen_at=now,
        )
    )
    log_event(
        db, event_type="TOESTEL_GEKOPPELD", source=device_id,
        employee_id=pairing_code.created_by_employee_id, detail={"ip": client},
    )
    db.commit()
    # Na de commit: set_device_name commit zelf ook.
    device_service.set_device_name(db, device_id=device_id, name=name)
    return PairedDevice(device_id=device_id, token=token)


def authenticate_device(db: Session, *, token: str) -> PairedDeviceModel:
    device = db.execute(
        select(PairedDeviceModel).where(PairedDeviceModel.token_hash == hash_device_token(token))
    ).scalar_one_or_none()
    if device is None:
        raise DeviceNotPairedError("Dit toestel is niet (meer) gekoppeld. Vraag een koppelcode aan een beheerder.")
    now = now_utc()
    if now - device.last_seen_at >= _LAST_SEEN_RESOLUTION:
        device.last_seen_at = now
        db.commit()
    return device


def list_paired_devices(db: Session) -> list[dict]:
    names = device_service.device_names(db)
    devices = db.execute(select(PairedDeviceModel).order_by(PairedDeviceModel.paired_at)).scalars()
    return [
        {
            "device_id": device.device_id,
            "name": names.get(device.device_id),
            "paired_at": device.paired_at,
            "last_seen_at": device.last_seen_at,
        }
        for device in devices
    ]


def unpair_device(db: Session, *, device_id: str, employee_id: int) -> None:
    """Het toestel kan meteen niets meer; een openstaande scan vervalt mee."""
    device = db.get(PairedDeviceModel, device_id)
    if device is None:
        raise DeviceNotFoundError("Toestel niet gevonden.")
    name = device_service.device_names(db).get(device_id)
    db.delete(device)
    db.execute(delete(PendingScanModel).where(PendingScanModel.device_id == device_id))
    log_event(
        db, event_type="TOESTEL_ONTKOPPELD", source="admin", employee_id=employee_id,
        detail={"toestel": device_id, "naam": name},
    )
    db.commit()
