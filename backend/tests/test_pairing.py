"""Toestellen koppelen: enkel een toestel dat een beheerder goedgekeurd heeft,
mag scannen en oordelen. Zonder geldige toestelsleutel kan niemand op het
netwerk een bandje als geslaagd laten markeren."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from app import tls
from app.models import PairingCodeModel, PendingScanModel
from tests.devices import paired


def _login(client, pincode: str = "1234") -> dict:
    token = client.post("/api/auth/login", json={"pincode": pincode}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _new_code(client, headers) -> str:
    response = client.post("/api/admin/pairing-codes", headers=headers)
    assert response.status_code == 200
    return response.json()["code"]


def _pair(client, code: str, name: str = "Host 1"):
    return client.post("/api/host/pair", json={"code": code, "name": name})


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/host/scan", {"wristband_id": "B001"}),
        ("post", "/api/host/verdict", {"verdict": "GROEN"}),
        ("post", "/api/host/practice-ack", None),
        ("post", "/api/host/cancel", None),
        ("put", "/api/host/device-name", {"name": "Host 1"}),
        ("get", "/api/host/device", None),
        ("post", "/api/gate/scan", {"wristband_id": "B001"}),
    ],
)
def test_host_actions_require_a_paired_device(client, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401
    assert getattr(client, method)(path, headers={"X-Device-Token": "verzonnen"}, **kwargs).status_code == 401


def test_pairing_with_a_code_from_an_admin(client, admin_employee):
    code = _new_code(client, _login(client))
    assert len(code) == 6 and code.isdigit()

    response = _pair(client, code, "Ingang")
    assert response.status_code == 200
    headers = {"X-Device-Token": response.json()["token"]}

    device = client.get("/api/host/device", headers=headers).json()
    assert device == {"device_id": response.json()["device_id"], "name": "Ingang"}
    assert client.post("/api/host/scan", json={"wristband_id": "B001"}, headers=headers).status_code == 200


def test_device_id_comes_from_the_token_not_from_the_request(client, admin_employee):
    headers = paired(client, "host-1")
    client.post("/api/host/scan", json={"wristband_id": "B001", "device_id": "iemand-anders"}, headers=headers)

    logs = client.get("/api/admin/logs", headers=_login(client)).json()
    assert next(e for e in logs if e["event_type"] == "SCAN")["source"] == "host-1"


def test_pairing_code_works_only_once(client, admin_employee):
    code = _new_code(client, _login(client))
    assert _pair(client, code).status_code == 200
    assert _pair(client, code).status_code == 400


def test_expired_pairing_code_is_rejected(client, admin_employee, db_session):
    code = _new_code(client, _login(client))
    row = db_session.get(PairingCodeModel, code)
    row.expires_at = row.expires_at - timedelta(minutes=11)
    db_session.commit()

    assert _pair(client, code).status_code == 400


def test_only_admins_create_pairing_codes(client, supervisor_employee):
    assert client.post("/api/admin/pairing-codes").status_code == 401
    assert client.post("/api/admin/pairing-codes", headers=_login(client, "5678")).status_code == 403


def test_pairing_is_blocked_after_five_wrong_codes(client, admin_employee):
    code = _new_code(client, _login(client))
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert _pair(client, wrong).status_code == 400

    # Ook de juiste code werkt nu even niet: raden heeft geen zin.
    assert _pair(client, code).status_code == 429


def test_unpaired_device_is_refused_immediately(client, admin_employee, db_session):
    headers = paired(client, "host-1")
    client.post("/api/host/scan", json={"wristband_id": "B001"}, headers=headers)
    admin = _login(client)

    devices = client.get("/api/admin/devices", headers=admin).json()
    assert [d["device_id"] for d in devices] == ["host-1"]

    assert client.delete("/api/admin/devices/host-1", headers=admin).status_code == 200
    assert client.post("/api/host/verdict", json={"verdict": "GROEN"}, headers=headers).status_code == 401
    assert client.get("/api/admin/devices", headers=admin).json() == []
    assert client.delete("/api/admin/devices/host-1", headers=admin).status_code == 404

    events = [e["event_type"] for e in client.get("/api/admin/logs", headers=admin).json()]
    assert "TOESTEL_ONTKOPPELD" in events
    # Een openstaande scan van het ontkoppelde toestel vervalt mee.
    assert db_session.get(PendingScanModel, "host-1") is None


def test_pairing_is_logged(client, admin_employee):
    admin = _login(client)
    response = _pair(client, _new_code(client, admin))
    _pair(client, "000000")  # de enige code is al gebruikt

    events = {e["event_type"]: e for e in client.get("/api/admin/logs", headers=admin).json()}
    assert events["TOESTEL_GEKOPPELD"]["source"] == response.json()["device_id"]
    assert events["TOESTEL_GEKOPPELD"]["device_name"] == "Host 1"
    assert "KOPPELCODE_AANGEMAAKT" in events
    assert "KOPPELEN_MISLUKT" in events


def test_network_info_shows_certificate_fingerprint(client, admin_employee, test_settings):
    tls.ensure_certificate(Path(test_settings.tls_dir))
    info = client.get("/api/admin/network", headers=_login(client)).json()
    assert info["certificate_fingerprint"] == tls.certificate_fingerprint(Path(test_settings.tls_dir))
    assert len(info["certificate_fingerprint"].split(" ")) == 4
