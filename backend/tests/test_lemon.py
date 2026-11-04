"""Koppeling met de Lemon-kiosk. Afspraak met IT: enkel de UUID van een
speler mag bewaard worden; naam, geboortedatum en avatar mogen enkel
tijdelijk op het hostscherm getoond worden en nergens weggeschreven."""
from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import lemon_service
from app.services.lemon_service import InvalidLemonDataError, LemonInbox
from tests.devices import paired

KIOSK_IP = "192.168.1.50"
PLAYER_ID = "21552882-bcff-4abf-801a-08a47e64caa6"


def _session(session_id: str = "9a13cc83-d56d-4456-aaf6-821156e780af", **player) -> dict:
    """Zelfde vorm als het voorbeeld van Lemon."""
    return {
        "sessionId": session_id,
        "language": "NL",
        "players": [{
            "id": PLAYER_ID,
            "firstName": "Voornaam",
            "lastName": "Achternaam",
            "teamId": "1",
            "placeId": "1",
            "birthdate": "2000-01-01",
            "avatarUrl": "https://avatars.example/abc.jpg",
            "avatarColor": "#facb0d",
            "playerLevel": 2,
            **player,
        }],
        "options": None,
    }


@pytest.fixture
def lemon_settings(test_settings):
    return dataclasses.replace(test_settings, lemon_kiosk_host=KIOSK_IP)


@pytest.fixture
def lemon_client(lemon_settings):
    with TestClient(create_app(lemon_settings), client=("192.168.1.20", 50000)) as client:
        yield client


@pytest.fixture
def lemon_admin(lemon_client, admin_employee):
    # admin_employee schrijft in dezelfde testdatabase (zelfde test_settings).
    return lemon_client


def _kiosk(client) -> TestClient:
    # Zelfde app, ander afzenderadres (zonder de app opnieuw op te starten).
    return TestClient(client.app, client=(KIOSK_IP, 50000))


def _admin(client) -> dict:
    token = client.post("/api/auth/login", json={"pincode": "1234"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_kiosk_post_reaches_the_host_screen(lemon_client):
    assert _kiosk(lemon_client).post("/api/lemon/session", json=_session()).status_code == 200

    body = lemon_client.get("/api/host/lemon/session", headers=paired(lemon_client, "host-1")).json()
    assert body["enabled"] is True
    [player] = body["session"]["players"]
    # Enkel voornaam en de eerste letter van de achternaam; geen geboortedatum.
    assert player == {
        "id": PLAYER_ID, "first_name": "Voornaam", "last_initial": "A",
        "avatar_url": "https://avatars.example/abc.jpg", "avatar_color": "#facb0d",
    }


def test_only_the_configured_kiosk_may_post(lemon_client, test_settings):
    assert lemon_client.post("/api/lemon/session", json=_session()).status_code == 403

    with TestClient(create_app(test_settings), client=(KIOSK_IP, 50000)) as not_configured:
        assert not_configured.post("/api/lemon/session", json=_session()).status_code == 403


def test_host_screen_needs_a_paired_device(lemon_client):
    assert lemon_client.get("/api/host/lemon/session").status_code == 401


def test_invalid_data_is_refused_without_echoing_it(lemon_client):
    response = _kiosk(lemon_client).post("/api/lemon/session", json=_session(id="geen-uuid"))
    assert response.status_code == 400
    assert "Voornaam" not in response.text and "Achternaam" not in response.text

    garbage = _kiosk(lemon_client).post(
        "/api/lemon/session", content=b"{niet json", headers={"Content-Type": "application/json"}
    )
    assert garbage.status_code == 400


def test_unsafe_avatar_and_color_are_dropped():
    _, [player] = lemon_service.parse_session(_session(avatarUrl="javascript:alert(1)", avatarColor="red;x"))
    assert player.avatar_url is None and player.avatar_color is None


def test_same_session_twice_counts_once(lemon_admin):
    kiosk = _kiosk(lemon_admin)
    kiosk.post("/api/lemon/session", json=_session())
    kiosk.post("/api/lemon/session", json=_session())

    events = lemon_admin.get("/api/admin/logs?event_type=LEMON_SESSIE", headers=_admin(lemon_admin)).json()
    assert len(events) == 1
    assert events[0]["detail"] == {"spelers": 1, "via": "post"}


def test_no_personal_data_is_ever_written(lemon_admin, lemon_settings, caplog, capsys):
    """De kern van de afspraak: na een volledige sessie (kiosk, scan, oordeel,
    logs bekijken) staat de naam nergens: niet in de database, niet in de
    logs, niet in de console."""
    caplog.set_level(logging.DEBUG)
    client = lemon_admin
    _kiosk(client).post("/api/lemon/session", json=_session())
    host = paired(client, "host-1")
    client.get("/api/host/lemon/session", headers=host)
    client.post("/api/host/scan", json={"wristband_id": PLAYER_ID}, headers=host)
    client.post("/api/host/verdict", json={"verdict": "GROEN"}, headers=host)
    logs = client.get("/api/admin/logs", headers=_admin(client)).text
    status = client.get("/api/admin/lemon", headers=_admin(client)).text

    database = b"".join(path.read_bytes() for path in Path(lemon_settings.database_path).parent.glob("test.db*"))
    printed = capsys.readouterr()
    for secret in ("Voornaam", "Achternaam", "2000-01-01", "avatars.example", "9a13cc83"):
        assert secret.encode() not in database, secret
        assert secret not in logs and secret not in status, secret
        assert secret not in caplog.text and secret not in printed.out and secret not in printed.err, secret

    # De UUID mag wel: daarmee worden de pogingen en het resultaat bijgehouden.
    assert PLAYER_ID.encode() in database
    assert client.get(f"/api/admin/wristbands/{PLAYER_ID}", headers=_admin(client)).json()["status"] == "GESLAAGD"


def test_names_disappear_from_memory_after_the_session():
    clock = [0.0]
    inbox = LemonInbox(ttl_seconds=60, clock=lambda: clock[0])
    inbox.receive(_session(), via="post")
    assert inbox.current() is not None
    clock[0] = 61
    assert inbox.current() is None


def test_session_without_players_is_ignored():
    inbox = LemonInbox()
    assert inbox.receive({"sessionId": "x", "players": []}, via="post") is None
    assert inbox.current() is None


def test_get_fallback_reads_the_kiosk():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"http://{KIOSK_IP}:4100/players"
        return httpx.Response(200, json=_session())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        payload = lemon_service.fetch_players(client, host=KIOSK_IP, port=4100)
    assert lemon_service.parse_session(payload)[1][0].id == PLAYER_ID


def test_get_fallback_errors_never_contain_the_answer():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="Voornaam!"))) as client:
        with pytest.raises(InvalidLemonDataError) as error:
            lemon_service.fetch_players(client, host=KIOSK_IP, port=4100)
    assert "Voornaam" not in str(error.value)

    def unreachable(request):
        raise httpx.ConnectError("geen verbinding")

    with httpx.Client(transport=httpx.MockTransport(unreachable)) as client:
        with pytest.raises(InvalidLemonDataError, match="niet bereikbaar"):
            lemon_service.fetch_players(client, host=KIOSK_IP, port=4100)


def test_verdict_on_one_phone_closes_the_player_on_the_other(lemon_client):
    # Een kioskspeler verschijnt op elk hostscherm: hij mag maar één keer beoordeeld worden.
    host1, host2 = paired(lemon_client, "host-1"), paired(lemon_client, "host-2")
    for host in (host1, host2):
        lemon_client.post("/api/host/scan", json={"wristband_id": PLAYER_ID}, headers=host)

    assert lemon_client.post("/api/host/verdict", json={"verdict": "ROOD"}, headers=host1).status_code == 200
    assert lemon_client.post("/api/host/verdict", json={"verdict": "ROOD"}, headers=host2).status_code == 409


def test_admin_status_and_test_player(lemon_admin):
    client = lemon_admin
    admin = _admin(client)
    assert client.get("/api/admin/lemon", headers=admin).json()["last_session"] is None

    assert client.post("/api/admin/lemon/test-session", headers=admin).status_code == 200
    status = client.get("/api/admin/lemon", headers=admin).json()
    assert status["kiosk_host"] == KIOSK_IP and status["poll_enabled"] is False
    assert status["last_session"]["via"] == "test" and status["last_session"]["players"] == 1

    session = client.get("/api/host/lemon/session", headers=paired(client, "host-1")).json()["session"]
    assert session["players"][0]["first_name"] == "Testspeler"


def test_lemon_admin_routes_are_for_the_admin_only(lemon_client, supervisor_employee):
    token = lemon_client.post("/api/auth/login", json={"pincode": "5678"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert lemon_client.get("/api/admin/lemon", headers=headers).status_code == 403
    assert lemon_client.post("/api/admin/lemon/test-session", headers=headers).status_code == 403


def test_get_fallback_runs_when_enabled(lemon_settings, monkeypatch):
    import time

    import app.main as main

    calls = []

    def fake_fetch(client, *, host, port):
        calls.append((host, port))
        return _session()

    monkeypatch.setattr(main, "fetch_players", fake_fetch)
    settings = dataclasses.replace(lemon_settings, lemon_poll_enabled=True, lemon_poll_interval_seconds=0.05)
    with TestClient(create_app(settings), client=("192.168.1.20", 50000)) as client:
        deadline = time.monotonic() + 3
        while client.app.state.lemon_inbox.current() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        session = client.app.state.lemon_inbox.current()

    assert calls[0] == (KIOSK_IP, 4100)
    assert session is not None and session.via == "get"


def test_get_fallback_stays_off_by_default(lemon_settings, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "fetch_players", lambda *a, **k: pytest.fail("GET mag niet draaien"))
    with TestClient(create_app(lemon_settings), client=("192.168.1.20", 50000)) as client:
        client.get("/api/health")
