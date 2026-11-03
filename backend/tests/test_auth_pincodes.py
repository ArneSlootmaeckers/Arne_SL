"""Pincode login, session inactivity timeout, and role-based access (section 3.3)."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import EmployeeModel
from app.security import hash_pincode
from app.services.common import now_utc


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


def _headers(client, pincode: str) -> dict:
    return {"Authorization": f"Bearer {client.post('/api/auth/login', json={'pincode': pincode}).json()['token']}"}


def test_only_the_admin_manages_pincodes(client, supervisor_employee, student_employee):
    for pincode in ("5678", "2468"):
        headers = _headers(client, pincode)
        assert client.get("/api/admin/pincodes", headers=headers).status_code == 403
        assert client.put("/api/admin/pincodes/student", json={"pincode": "999999"}, headers=headers).status_code == 403


def test_admin_sets_and_disables_a_group_pincode(client, admin_employee):
    headers = _headers(client, "1234")

    response = client.put("/api/admin/pincodes/student", json={"pincode": "999999"}, headers=headers)
    assert response.status_code == 200
    login = client.post("/api/auth/login", json={"pincode": "999999"}).json()
    assert (login["role"], login["name"]) == ("student", "Studenten")

    groups = {g["role"]: g for g in client.get("/api/admin/pincodes", headers=headers).json()}
    assert [g["label"] for g in groups.values()] == ["Beheerder", "Vaste medewerkers", "Studenten"]
    assert groups["student"]["active"] is True and groups["supervisor"]["active"] is False

    assert client.delete("/api/admin/pincodes/student", headers=headers).status_code == 200
    assert client.post("/api/auth/login", json={"pincode": "999999"}).status_code == 401

    events = [e["event_type"] for e in client.get("/api/admin/logs", headers=headers).json()]
    assert "PINCODE_INGESTELD" in events and "GROEP_UITGEZET" in events


def test_the_admin_group_cannot_be_disabled(client, admin_employee):
    response = client.delete("/api/admin/pincodes/admin", headers=_headers(client, "1234"))
    assert response.status_code == 403
    assert client.post("/api/auth/login", json={"pincode": "1234"}).status_code == 200


def test_unknown_group_is_rejected(client, admin_employee):
    headers = _headers(client, "1234")
    assert client.put("/api/admin/pincodes/stagiair", json={"pincode": "999999"}, headers=headers).status_code == 422


def test_one_pincode_per_group_replaces_older_accounts(client, admin_employee, supervisor_employee, db_session):
    # Een vroegere, tweede persoonlijke pincode in dezelfde groep.
    db_session.add(
        EmployeeModel(name="Vaste medewerkers", pincode_hash=hash_pincode("8765"), role="supervisor",
                      active=True, created_at=now_utc())
    )
    db_session.commit()

    client.put("/api/admin/pincodes/supervisor", json={"pincode": "567890"}, headers=_headers(client, "1234"))

    assert client.post("/api/auth/login", json={"pincode": "567890"}).status_code == 200
    assert client.post("/api/auth/login", json={"pincode": "5678"}).status_code == 401
    assert client.post("/api/auth/login", json={"pincode": "8765"}).status_code == 401


def test_two_groups_cannot_share_a_pincode(client, admin_employee):
    headers = _headers(client, "1234")
    assert client.put("/api/admin/pincodes/supervisor", json={"pincode": "246810"}, headers=headers).status_code == 200
    response = client.put("/api/admin/pincodes/student", json={"pincode": "246810"}, headers=headers)
    assert response.status_code == 409


def test_new_pincode_must_have_six_characters(client, admin_employee):
    headers = _headers(client, "1234")
    response = client.put("/api/admin/pincodes/student", json={"pincode": "12345"}, headers=headers)
    assert response.status_code == 400
    assert "6" in response.json()["detail"]


def test_login_flags_a_short_existing_pincode(client, admin_employee):
    # Pincodes van vóór de minimumlengte blijven werken, maar worden gemeld.
    assert client.post("/api/auth/login", json={"pincode": "1234"}).json()["short_pincode"] is True

    client.put("/api/admin/pincodes/admin", json={"pincode": "123456"}, headers=_headers(client, "1234"))
    assert client.post("/api/auth/login", json={"pincode": "1234"}).status_code == 401
    assert client.post("/api/auth/login", json={"pincode": "123456"}).json()["short_pincode"] is False


def test_names_of_old_personal_accounts_are_removed_at_startup(test_settings):
    # Geen personeelsgegevens: een naam uit een vroegere versie verdwijnt bij de volgende start.
    with TestClient(create_app(test_settings), client=("192.168.1.20", 50000)) as first:
        db = first.app.state.session_factory()
        db.add(EmployeeModel(name="Jan Peeters", pincode_hash=hash_pincode("123456"), role="supervisor",
                             active=True, created_at=now_utc()))
        db.commit()
        db.close()

    with TestClient(create_app(test_settings), client=("192.168.1.20", 50000)) as second:
        db = second.app.state.session_factory()
        assert [e.name for e in db.query(EmployeeModel).all()] == ["Vaste medewerkers"]
        db.close()
        assert second.post("/api/auth/login", json={"pincode": "123456"}).json()["name"] == "Vaste medewerkers"


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
    client.app.state.login_limiter.reset("192.168.1.20")
    client.app.state.login_limiter._blocked_until.clear()

    token = client.post("/api/auth/login", json={"pincode": "1234"}).json()["token"]
    logs = client.get("/api/admin/logs", headers={"Authorization": f"Bearer {token}"}).json()
    assert any(event["event_type"] == "INLOGGEN_GEBLOKKEERD" for event in logs)
