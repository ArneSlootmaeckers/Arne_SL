"""Manual status overrides by supervisors/admins are logged with old/new status,
reason and the acting employee (section 3.3 / 5)."""
from __future__ import annotations

import json


def test_manual_override_changes_status_and_is_logged(client, supervisor_employee, db_session):
    login = client.post("/api/auth/login", json={"pincode": "5678"})
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/admin/wristbands/M001/status",
        json={"status": "GESLAAGD", "reason": "Host vergat te scannen"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "GESLAAGD"

    from app.models import EventModel

    events = db_session.query(EventModel).filter_by(event_type="HANDMATIGE_WIJZIGING").all()
    assert len(events) == 1
    detail = json.loads(events[0].detail)
    assert detail["nieuwe_status"] == "GESLAAGD"
    assert detail["reden"] == "Host vergat te scannen"
    assert events[0].employee_id == supervisor_employee.id


def test_manual_override_to_niet_geslaagd_then_blocks_gate(client, supervisor_employee):
    login = client.post("/api/auth/login", json={"pincode": "5678"})
    token = login.json()["token"]
    client.post(
        "/api/admin/wristbands/M002/status",
        json={"status": "NIET_GESLAAGD", "reason": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    gate_response = client.post("/api/gate/scan", json={"wristband_id": "M002", "device_id": "gate-1"})
    assert gate_response.json()["allowed"] is False


def test_manual_override_requires_authentication(client):
    response = client.post("/api/admin/wristbands/M003/status", json={"status": "GESLAAGD"})
    assert response.status_code == 401
