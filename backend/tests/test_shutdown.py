"""Admin screen's "applicatie afsluiten"-knop: zet uvicorn's should_exit-vlag
in plaats van een OS-signaal te sturen (dat geeft op Windows geen nette
shutdown). Enkel voor admins, en gelogd."""
from __future__ import annotations


class _FakeUvicornServer:
    def __init__(self) -> None:
        self.should_exit = False


def test_shutdown_requires_authentication(client):
    response = client.post("/api/admin/shutdown")
    assert response.status_code == 401


def test_shutdown_requires_admin_role(client, supervisor_employee):
    login = client.post("/api/auth/login", json={"pincode": "5678"})
    token = login.json()["token"]

    response = client.post("/api/admin/shutdown", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_shutdown_without_server_reference_returns_503(client, admin_employee):
    # The TestClient app was never launched via run.py, so app.state has no
    # uvicorn_server — exactly the state a plain "uvicorn asgi:app" run would
    # be in too.
    login = client.post("/api/auth/login", json={"pincode": "1234"})
    token = login.json()["token"]

    response = client.post("/api/admin/shutdown", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 503


def test_shutdown_sets_should_exit_and_logs(client, admin_employee, db_session):
    fake_server = _FakeUvicornServer()
    client.app.state.uvicorn_server = fake_server

    login = client.post("/api/auth/login", json={"pincode": "1234"})
    token = login.json()["token"]

    response = client.post("/api/admin/shutdown", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert fake_server.should_exit is True

    from app.models import EventModel

    events = db_session.query(EventModel).filter_by(event_type="SYSTEEM_AFSLUITEN").all()
    assert len(events) == 1
    assert events[0].employee_id == admin_employee.id
