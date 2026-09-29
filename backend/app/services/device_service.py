"""Leesbare toestelnamen (zie DeviceModel)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DeviceModel
from app.services.common import now_utc


def set_device_name(db: Session, *, device_id: str, name: str) -> None:
    """Een lege naam wist de naam: het toestel valt dan terug op zijn code."""
    name = name.strip()
    device = db.get(DeviceModel, device_id)
    if not name:
        if device is not None:
            db.delete(device)
    elif device is None:
        db.add(DeviceModel(device_id=device_id, name=name, updated_at=now_utc()))
    elif device.name != name:
        device.name = name
        device.updated_at = now_utc()
    db.commit()


def device_names(db: Session) -> dict[str, str]:
    return {device.device_id: device.name for device in db.execute(select(DeviceModel)).scalars()}
