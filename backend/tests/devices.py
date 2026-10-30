"""Testhulp: een gekoppeld toestel met een vast, voorspelbaar id, zonder
telkens de hele koppelprocedure te doorlopen (die heeft eigen testen in
test_pairing.py)."""
from __future__ import annotations

from app.models import PairedDeviceModel
from app.services.common import now_utc
from app.services.pairing_service import hash_device_token


def paired(client, device_id: str) -> dict:
    """Headers voor toestel `device_id`; koppelt het eerst als dat nog niet zo is."""
    token = f"testsleutel-{device_id}"
    db = client.app.state.session_factory()
    try:
        if db.get(PairedDeviceModel, device_id) is None:
            now = now_utc()
            db.add(
                PairedDeviceModel(
                    device_id=device_id, token_hash=hash_device_token(token), paired_at=now, last_seen_at=now
                )
            )
            db.commit()
    finally:
        db.close()
    return {"X-Device-Token": token}
