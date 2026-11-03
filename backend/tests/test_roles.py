"""Wat elke groep mag op het beheerscherm: studenten enkel een bandje
opzoeken, vaste medewerkers ook corrigeren en logs/dagoverzicht bekijken,
de beheerder alles."""
from __future__ import annotations

import pytest

from tests.devices import paired


def _headers(client, pincode: str) -> dict:
    token = client.post("/api/auth/login", json={"pincode": pincode}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


ADMIN_ONLY = [
    ("get", "/api/admin/pincodes"),
    ("get", "/api/admin/network"),
    ("get", "/api/admin/devices"),
    ("post", "/api/admin/pairing-codes"),
    ("post", "/api/admin/logs/purge"),
]
STAFF_ONLY = [
    ("get", "/api/admin/logs"),
    ("get", "/api/admin/logs/export.csv"),
    ("get", "/api/admin/report?report_date=2026-11-04"),
]


def test_student_can_look_up_a_wristband_with_todays_history(client, student_employee):
    client.post("/api/host/scan", json={"wristband_id": "S001"}, headers=paired(client, "host-1"))
    headers = _headers(client, "2468")

    assert client.get("/api/admin/wristbands/S001", headers=headers).json()["status"] == "NOG_NIET_GESPRONGEN"
    history = client.get("/api/admin/wristbands/S001/history", headers=headers)
    assert history.status_code == 200
    assert [e["event_type"] for e in history.json()] == ["SCAN"]


def test_student_cannot_change_a_status(client, student_employee):
    response = client.post(
        "/api/admin/wristbands/S001/status", json={"status": "GESLAAGD"}, headers=_headers(client, "2468")
    )
    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path"), STAFF_ONLY + ADMIN_ONLY)
def test_student_cannot_see_logs_report_or_system(client, student_employee, method, path):
    assert getattr(client, method)(path, headers=_headers(client, "2468")).status_code == 403


@pytest.mark.parametrize(("method", "path"), STAFF_ONLY)
def test_permanent_staff_see_logs_and_report(client, supervisor_employee, method, path):
    assert getattr(client, method)(path, headers=_headers(client, "5678")).status_code == 200


@pytest.mark.parametrize(("method", "path"), ADMIN_ONLY)
def test_permanent_staff_cannot_manage_the_system(client, supervisor_employee, method, path):
    assert getattr(client, method)(path, headers=_headers(client, "5678")).status_code == 403


def test_permanent_staff_can_correct_a_status(client, supervisor_employee):
    response = client.post(
        "/api/admin/wristbands/S001/status", json={"status": "GESLAAGD", "reason": "test"},
        headers=_headers(client, "5678"),
    )
    assert response.status_code == 200


def test_logs_show_which_group_did_something(client, admin_employee, supervisor_employee):
    client.post(
        "/api/admin/wristbands/S001/status", json={"status": "GESLAAGD"}, headers=_headers(client, "5678")
    )
    admin = _headers(client, "1234")

    events = client.get("/api/admin/logs?role=supervisor", headers=admin).json()
    assert {e["event_type"] for e in events} == {"INLOGGEN", "HANDMATIGE_WIJZIGING"}
    assert {e["group"] for e in events} == {"Vaste medewerkers"}

    csv_text = client.get("/api/admin/logs/export.csv?role=supervisor", headers=admin).text
    assert "groep" in csv_text.splitlines()[0].split(",")
    assert "Vaste medewerkers" in csv_text
