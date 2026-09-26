"""Pincode login, session inactivity timeout, and role-based access (section 3.3)."""
from __future__ import annotations

import time


def test_login_with_correct_pincode_succeeds(client, admin_employee):
    response = client.post("/api/auth/login", json={"pincode": "1234"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    assert "token" in body


def test_login_with_wrong_pincode_fails(client, admin_employee):
    response = client.post("/api/auth/login", json={"pincode": "0000"})
    assert response.status_code == 401


def test_login_with_revoked_pincode_fails(client, admin_employee, db_session):
    admin_employee.active = False
    db_session.merge(admin_employee)
    db_session.commit()

    response = client.post("/api/auth/login", json={"pincode": "1234"})
    assert response.status_code == 401


def test_me_requires_a_valid_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_employee_for_valid_token(client, admin_employee):
    login = client.post("/api/auth/login", json={"pincode": "1234"})
    token = login.json()["token"]
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_session_expires_after_inactivity(client, admin_employee):
    login = client.post("/api/auth/login", json={"pincode": "1234"})
    token = login.json()["token"]
    time.sleep(2.2)  # test_settings.session_inactivity_timeout_seconds == 2
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_supervisor_cannot_manage_employees(client, supervisor_employee):
    login = client.post("/api/auth/login", json={"pincode": "5678"})
    token = login.json()["token"]
    response = client.get("/api/admin/employees", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_can_create_and_revoke_employee(client, admin_employee):
    login = client.post("/api/auth/login", json={"pincode": "1234"})
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    create = client.post(
        "/api/admin/employees",
        json={"name": "Nieuwe Host", "pincode": "9999", "role": "supervisor"},
        headers=headers,
    )
    assert create.status_code == 200
    new_id = create.json()["id"]

    assert client.post("/api/auth/login", json={"pincode": "9999"}).status_code == 200

    revoke = client.patch(f"/api/admin/employees/{new_id}", json={"active": False}, headers=headers)
    assert revoke.status_code == 200

    assert client.post("/api/auth/login", json={"pincode": "9999"}).status_code == 401


def test_duplicate_pincode_is_rejected(client, admin_employee):
    login = client.post("/api/auth/login", json={"pincode": "1234"})
    token = login.json()["token"]
    response = client.post(
        "/api/admin/employees",
        json={"name": "Dubbel", "pincode": "1234", "role": "supervisor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
