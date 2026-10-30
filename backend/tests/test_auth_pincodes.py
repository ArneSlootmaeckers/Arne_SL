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
        json={"name": "Nieuwe Host", "pincode": "999999", "role": "supervisor"},
        headers=headers,
    )
    assert create.status_code == 200
    new_id = create.json()["id"]

    assert client.post("/api/auth/login", json={"pincode": "999999"}).status_code == 200

    revoke = client.patch(f"/api/admin/employees/{new_id}", json={"active": False}, headers=headers)
    assert revoke.status_code == 200

    assert client.post("/api/auth/login", json={"pincode": "999999"}).status_code == 401


def test_duplicate_pincode_is_rejected(client, admin_employee):
    login = client.post("/api/auth/login", json={"pincode": "1234"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    first = {"name": "Eerste", "pincode": "246810", "role": "supervisor"}
    assert client.post("/api/admin/employees", json=first, headers=headers).status_code == 200
    response = client.post(
        "/api/admin/employees",
        json={"name": "Dubbel", "pincode": "246810", "role": "supervisor"},
        headers=headers,
    )
    assert response.status_code == 409


def test_new_pincode_must_have_six_characters(client, admin_employee):
    login = client.post("/api/auth/login", json={"pincode": "1234"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    create = client.post(
        "/api/admin/employees", json={"name": "Kort", "pincode": "12345", "role": "supervisor"}, headers=headers
    )
    assert create.status_code == 400
    assert "6" in create.json()["detail"]

    change = client.patch(f"/api/admin/employees/{admin_employee.id}", json={"new_pincode": "4321"}, headers=headers)
    assert change.status_code == 400


def test_login_flags_a_short_existing_pincode(client, admin_employee):
    # Pincodes van vóór de minimumlengte blijven werken, maar worden gemeld.
    assert client.post("/api/auth/login", json={"pincode": "1234"}).json()["short_pincode"] is True

    headers = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'pincode': '1234'}).json()['token']}"}
    client.patch(f"/api/admin/employees/{admin_employee.id}", json={"new_pincode": "123456"}, headers=headers)
    assert client.post("/api/auth/login", json={"pincode": "123456"}).json()["short_pincode"] is False


def test_login_is_blocked_after_five_wrong_pincodes(client, admin_employee):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"pincode": "000000"}).status_code == 401

    # Ook de juiste pincode wordt nu geweigerd, tot de blokkering voorbij is.
    blocked = client.post("/api/auth/login", json={"pincode": "1234"})
    assert blocked.status_code == 429
    assert "minuten" in blocked.json()["detail"]


def test_successful_login_resets_the_wrong_pincode_count(client, admin_employee):
    for _ in range(4):
        client.post("/api/auth/login", json={"pincode": "000000"})
    assert client.post("/api/auth/login", json={"pincode": "1234"}).status_code == 200
    for _ in range(4):
        client.post("/api/auth/login", json={"pincode": "000000"})
    assert client.post("/api/auth/login", json={"pincode": "1234"}).status_code == 200


def test_blocking_is_logged(client, admin_employee):
    for _ in range(5):
        client.post("/api/auth/login", json={"pincode": "000000"})
    client.app.state.login_limiter.reset("testclient")
    client.app.state.login_limiter._blocked_until.clear()

    token = client.post("/api/auth/login", json={"pincode": "1234"}).json()["token"]
    logs = client.get("/api/admin/logs", headers={"Authorization": f"Bearer {token}"}).json()
    assert any(event["event_type"] == "INLOGGEN_GEBLOKKEERD" for event in logs)
