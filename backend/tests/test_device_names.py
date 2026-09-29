"""Toestelnamen: een telefoon kan zichzelf een leesbare naam geven ("Host 1"),
die het beheerscherm naast de technische toestel-code in de logs toont.
De code blijft de sleutel: twee toestellen met dezelfde naam blijven apart."""
from __future__ import annotations


def _admin_headers(client) -> dict:
    token = client.post("/api/auth/login", json={"pincode": "1234"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _set_name(client, device_id: str, name: str):
    return client.put("/api/host/device-name", json={"device_id": device_id, "name": name})


def _scan(client, device_id: str, wristband_id: str = "B001"):
    return client.post("/api/host/scan", json={"wristband_id": wristband_id, "device_id": device_id})


def _logs(client, headers) -> list[dict]:
    return client.get("/api/admin/logs", headers=headers).json()


def test_logs_show_device_name(client, admin_employee):
    assert _set_name(client, "toestel-abc", "  Host 1  ").status_code == 200
    _scan(client, "toestel-abc")

    scan_event = next(e for e in _logs(client, _admin_headers(client)) if e["event_type"] == "SCAN")
    assert scan_event["source"] == "toestel-abc"
    assert scan_event["device_name"] == "Host 1"


def test_unnamed_device_has_no_name(client, admin_employee):
    _scan(client, "toestel-xyz")

    scan_event = next(e for e in _logs(client, _admin_headers(client)) if e["event_type"] == "SCAN")
    assert scan_event["device_name"] is None


def test_rename_and_clear(client, admin_employee):
    _set_name(client, "toestel-abc", "Host 1")
    _set_name(client, "toestel-abc", "Ingang")
    _scan(client, "toestel-abc")
    headers = _admin_headers(client)
    assert next(e for e in _logs(client, headers) if e["event_type"] == "SCAN")["device_name"] == "Ingang"

    _set_name(client, "toestel-abc", "")
    assert next(e for e in _logs(client, headers) if e["event_type"] == "SCAN")["device_name"] is None


def test_same_name_on_two_devices_keeps_scans_separate(client):
    _set_name(client, "toestel-a", "Host")
    _set_name(client, "toestel-b", "Host")

    assert _scan(client, "toestel-a", "B001").status_code == 200
    # Het andere toestel heeft zijn eigen openstaande scan, ondanks dezelfde naam.
    assert _scan(client, "toestel-b", "B002").status_code == 200


def test_root_redirect_keeps_query_string(client):
    # De Android-app opent "/?toestel=..."; die naam mag niet verloren gaan.
    response = client.get("/?toestel=Host+1", follow_redirects=False)
    assert response.headers["location"] == "/host/?toestel=Host+1"
    assert client.get("/", follow_redirects=False).headers["location"] == "/host/"


def test_name_too_long_is_rejected(client):
    assert _set_name(client, "toestel-abc", "x" * 41).status_code == 422


def test_csv_export_contains_device_name(client, admin_employee):
    _set_name(client, "toestel-abc", "Host 1")
    _scan(client, "toestel-abc")

    csv_text = client.get("/api/admin/logs/export.csv", headers=_admin_headers(client)).text
    header, *rows = csv_text.strip().splitlines()
    assert "toestelnaam" in header.split(",")
    assert any("toestel-abc,Host 1" in row for row in rows)
