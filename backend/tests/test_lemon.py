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
    _kiosk(lemon_client).post("/api/lemon/session", json=_session())
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


# --- Stopbericht naar de kiosk na het oordeel (POST <kiosk>:4100/scores) ---

@pytest.fixture
def sent_scores(monkeypatch):
    sent = []
    monkeypatch.setattr(
        lemon_service, "send_scores",
        lambda client, *, host, port, payload: sent.append((host, port, payload)),
    )
    return sent


@pytest.mark.parametrize("verdict", ["GROEN", "ROOD"])
def test_verdict_stops_the_player_at_the_kiosk(lemon_client, sent_scores, verdict):
    _kiosk(lemon_client).post("/api/lemon/session", json=_session())
    host = paired(lemon_client, "host-1")
    lemon_client.post("/api/host/scan", json={"wristband_id": PLAYER_ID}, headers=host)
    assert lemon_client.post("/api/host/verdict", json={"verdict": verdict}, headers=host).status_code == 200

    # Eén speler, geen score en geen resultaat (of iemand mag springen gaat nooit naar Lemon).
    assert sent_scores == [(KIOSK_IP, 4100, {
        "sessionId": "9a13cc83-d56d-4456-aaf6-821156e780af",
        "gameModeCode": "10",
        "players": [{"id": PLAYER_ID}],
    })]


def test_only_the_judged_player_is_sent_once(lemon_client, sent_scores):
    other = "305b1224-f528-4704-a8a0-5adaefcdd397"
    payload = _session()
    payload["players"].append({**payload["players"][0], "id": other})
    _kiosk(lemon_client).post("/api/lemon/session", json=payload)
    host = paired(lemon_client, "host-1")

    lemon_client.post("/api/host/scan", json={"wristband_id": PLAYER_ID}, headers=host)
    lemon_client.post("/api/host/verdict", json={"verdict": "ROOD"}, headers=host)
    # Opnieuw openen zonder nieuwe kioskscan kan niet: maar één stopbericht.
    assert lemon_client.post("/api/host/scan", json={"wristband_id": PLAYER_ID}, headers=host).status_code == 403
    assert [s[2]["players"] for s in sent_scores] == [[{"id": PLAYER_ID}]]

    lemon_client.post("/api/host/scan", json={"wristband_id": other}, headers=host)
    lemon_client.post("/api/host/verdict", json={"verdict": "GROEN"}, headers=host)
    assert [s[2]["players"] for s in sent_scores] == [[{"id": PLAYER_ID}], [{"id": other}]]


def test_no_stop_message_for_the_test_player(lemon_admin, sent_scores):
    client = lemon_admin
    host = paired(client, "host-1")
    client.post("/api/admin/lemon/test-session", headers=_admin(client))
    test_id = client.get("/api/host/lemon/session", headers=host).json()["session"]["players"][0]["id"]
    client.post("/api/host/scan", json={"wristband_id": test_id}, headers=host)
    client.post("/api/host/verdict", json={"verdict": "GROEN"}, headers=host)
    assert sent_scores == []


def test_send_scores_posts_to_the_kiosk_and_hides_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and str(request.url) == f"http://{KIOSK_IP}:4100/scores"
        return httpx.Response(200)

    payload = lemon_service.scores_payload("s1", PLAYER_ID, game_mode_code="10")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        lemon_service.send_scores(client, host=KIOSK_IP, port=4100, payload=payload)

    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="Voornaam"))) as client:
        with pytest.raises(InvalidLemonDataError) as error:
            lemon_service.send_scores(client, host=KIOSK_IP, port=4100, payload=payload)
    assert "Voornaam" not in str(error.value) and "s1" not in str(error.value)


def test_failed_stop_message_shows_on_admin_status(lemon_admin, monkeypatch):
    def fail(client, *, host, port, payload):
        raise InvalidLemonDataError("Stopbericht naar de kiosk mislukt.")

    monkeypatch.setattr(lemon_service, "send_scores", fail)
    client = lemon_admin
    _kiosk(client).post("/api/lemon/session", json=_session())
    host = paired(client, "host-1")
    client.post("/api/host/scan", json={"wristband_id": PLAYER_ID}, headers=host)
    assert client.post("/api/host/verdict", json={"verdict": "GROEN"}, headers=host).status_code == 200
    assert client.get("/api/admin/lemon", headers=_admin(client)).json()["scores_error"] == "Stopbericht naar de kiosk mislukt."


# --- Laatste contact met de kiosk (Beheer -> Systeem) -----------------------

def _attempts(client) -> list[dict]:
    return client.get("/api/admin/lemon", headers=_admin(client)).json()["attempts"]


def test_refused_attempts_show_where_they_came_from(lemon_admin):
    lemon_admin.post("/api/lemon/session", json=_session())  # van 192.168.1.20, niet de kiosk
    [attempt] = _attempts(lemon_admin)
    assert attempt["ok"] is False and attempt["via"] == "post" and attempt["sender"] == "192.168.1.20"
    assert "192.168.1.20" in attempt["result"] and KIOSK_IP in attempt["result"]


def test_missing_kiosk_setting_is_shown(client, admin_employee):
    kiosk = TestClient(client.app, client=(KIOSK_IP, 50000))
    assert kiosk.post("/api/lemon/session", json=_session()).status_code == 403
    [attempt] = _attempts(client)
    assert "geen kiosk ingesteld" in attempt["result"]


def test_invalid_data_names_the_field_but_never_the_values(lemon_admin):
    _kiosk(lemon_admin).post("/api/lemon/session", json=_session(id="Voornaam-geen-uuid"))
    _kiosk(lemon_admin).post("/api/lemon/session", json={"players": []})
    newest, oldest = _attempts(lemon_admin)
    assert "players.0.id" in oldest["result"] and "Voornaam" not in oldest["result"]
    assert "sessionId" in newest["result"]


def test_accepted_duplicate_and_empty_sessions_are_shown(lemon_admin):
    kiosk = _kiosk(lemon_admin)
    kiosk.post("/api/lemon/session", json=_session())
    kiosk.post("/api/lemon/session", json=_session())
    kiosk.post("/api/lemon/session", json={"sessionId": "leeg", "players": []})
    assert [a["result"] for a in _attempts(lemon_admin)] == [
        "Ontvangen, maar zonder spelers",
        "Al ontvangen (zelfde sessie)",
        "Ontvangen: 1 speler(s)",
    ]
    assert all(a["sender"] == KIOSK_IP and a["ok"] for a in _attempts(lemon_admin))
    assert "Voornaam" not in str(_attempts(lemon_admin))


def test_get_fallback_errors_are_shown_once(lemon_settings, monkeypatch):
    import time

    import app.main as main

    def unreachable(client, *, host, port):
        raise InvalidLemonDataError("Kiosk niet bereikbaar.")

    monkeypatch.setattr(main, "fetch_players", unreachable)
    settings = dataclasses.replace(lemon_settings, lemon_poll_enabled=True, lemon_poll_interval_seconds=0.02)
    with TestClient(create_app(settings), client=("192.168.1.20", 50000)) as client:
        time.sleep(0.3)  # vele pogingen, telkens dezelfde fout
        attempts = client.app.state.lemon_inbox.attempts()

    assert len(attempts) == 1
    assert attempts[0]["via"] == "get" and attempts[0]["sender"] == f"{KIOSK_IP}:4100"
    assert attempts[0]["result"] == "Kiosk niet bereikbaar." and attempts[0]["ok"] is False


# --- Kiosk instellen op Beheer -> Systeem ------------------------------------

def _save_kiosk(client, headers=None, **fields):
    body = {"kiosk_host": KIOSK_IP, "kiosk_port": 4100, "poll_enabled": False, **fields}
    return client.put("/api/admin/lemon/settings", json=body, headers=headers or _admin(client))


def test_kiosk_set_on_the_admin_screen_works_immediately(client, admin_employee):
    # Niets in config.yaml (test_settings): eerst geweigerd, na opslaan meteen aanvaard.
    kiosk = TestClient(client.app, client=(KIOSK_IP, 50000))
    assert kiosk.post("/api/lemon/session", json=_session()).status_code == 403

    assert _save_kiosk(client).status_code == 200
    assert kiosk.post("/api/lemon/session", json=_session()).status_code == 200
    status = client.get("/api/admin/lemon", headers=_admin(client)).json()
    assert (status["kiosk_host"], status["kiosk_port"], status["poll_enabled"]) == (KIOSK_IP, 4100, False)
    assert client.get("/api/host/lemon/session", headers=paired(client, "host-1")).json()["enabled"] is True


def test_saved_kiosk_settings_survive_a_restart_and_beat_config_yaml(test_settings, client, admin_employee):
    _save_kiosk(client, kiosk_host="10.12.0.170", kiosk_port=4200, poll_enabled=True)

    # config.yaml zegt iets anders: wat op het beheerscherm bewaard werd, gaat voor.
    other = dataclasses.replace(test_settings, lemon_kiosk_host="10.0.0.9")
    with TestClient(create_app(other), client=("192.168.1.20", 50000)) as restarted:
        settings = restarted.app.state.settings
        assert (settings.lemon_kiosk_host, settings.lemon_kiosk_port, settings.lemon_poll_enabled) == (
            "10.12.0.170", 4200, True,
        )


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"kiosk_host": "kiosk.lokaal"}, "IP-adres"),
        ({"kiosk_host": "8.8.8.8"}, "internetadres"),
        ({"kiosk_port": 0}, "poort"),
        ({"kiosk_port": 70000}, "poort"),
        ({"kiosk_host": "", "poll_enabled": True}, "IP-adres van de kiosk"),
    ],
)
def test_invalid_kiosk_settings_are_refused(client, admin_employee, fields, message):
    response = _save_kiosk(client, **fields)
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_kiosk_can_be_switched_off(client, admin_employee):
    _save_kiosk(client)
    assert _save_kiosk(client, kiosk_host="").status_code == 200
    assert client.get("/api/admin/lemon", headers=_admin(client)).json()["kiosk_host"] is None
    events = client.get("/api/admin/logs?event_type=KIOSK_INGESTELD", headers=_admin(client)).json()
    assert [e["detail"]["kiosk"] for e in events] == ["uit", f"{KIOSK_IP}:4100"]


def test_only_the_admin_sets_the_kiosk(client, supervisor_employee):
    token = client.post("/api/auth/login", json={"pincode": "5678"}).json()["token"]
    assert _save_kiosk(client, headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_switching_get_fallback_on_needs_no_restart(test_settings, monkeypatch):
    import time

    import app.main as main

    calls = []
    monkeypatch.setattr(main, "fetch_players", lambda client, *, host, port: calls.append((host, port)) or _session())
    with TestClient(create_app(test_settings), client=("192.168.1.20", 50000)) as client:
        db = client.app.state.session_factory()
        from app.models import EmployeeModel
        from app.security import hash_pincode
        from app.services.common import now_utc

        db.add(EmployeeModel(name="Beheerder", pincode_hash=hash_pincode("123456"), role="admin",
                             active=True, created_at=now_utc()))
        db.commit()
        db.close()
        time.sleep(0.2)
        assert calls == []  # ophalen staat uit

        token = client.post("/api/auth/login", json={"pincode": "123456"}).json()["token"]
        _save_kiosk(client, headers={"Authorization": f"Bearer {token}"}, poll_enabled=True)
        deadline = time.monotonic() + 3
        while not calls and time.monotonic() < deadline:
            time.sleep(0.05)
    assert calls and calls[0] == (KIOSK_IP, 4100)


# --- Enkel via de kiosk: bandjes scannen (NFC of een lezer) kan niet meer ---

def test_a_scanned_wristband_is_refused(lemon_client):
    host = paired(lemon_client, "host-1")
    for wristband_id in ("04A2B3C4D5E680", PLAYER_ID):  # NFC-UID, of een UUID die niet van de kiosk kwam
        response = lemon_client.post("/api/host/scan", json={"wristband_id": wristband_id}, headers=host)
        assert response.status_code == 403
        assert response.json()["detail"] == "Spelers komen enkel binnen via de kiosk."


def test_a_kiosk_player_opens_until_judged_and_again_after_a_new_kiosk_scan(lemon_client):
    host = paired(lemon_client, "host-1")
    _kiosk(lemon_client).post("/api/lemon/session", json=_session("sessie-1"))
    assert lemon_client.post("/api/host/scan", json={"wristband_id": PLAYER_ID}, headers=host).status_code == 200
    assert lemon_client.post("/api/host/verdict", json={"verdict": "ROOD"}, headers=host).status_code == 200

    # Na het oordeel: pas opnieuw na een nieuwe scan aan de kiosk.
    assert lemon_client.post("/api/host/scan", json={"wristband_id": PLAYER_ID}, headers=host).status_code == 403
    _kiosk(lemon_client).post("/api/lemon/session", json=_session("sessie-2"))
    response = lemon_client.post("/api/host/scan", json={"wristband_id": PLAYER_ID}, headers=host)
    assert response.status_code == 200
    assert response.json()["status"] == "HERKANSING"


def test_the_test_player_can_be_opened(lemon_admin):
    client = lemon_admin
    host = paired(client, "host-1")
    client.post("/api/admin/lemon/test-session", headers=_admin(client))
    test_id = client.get("/api/host/lemon/session", headers=host).json()["session"]["players"][0]["id"]
    assert client.post("/api/host/scan", json={"wristband_id": test_id}, headers=host).status_code == 200


def test_host_and_admin_pages_no_longer_read_wristbands():
    frontend = Path(__file__).resolve().parents[2] / "frontend"
    assert not (frontend / "shared" / "reader.js").exists()
    for page in ("host/app.js", "admin/app.js", "host/index.html", "admin/index.html"):
        text = (frontend / page).read_text(encoding="utf-8")
        assert "reader.js" not in text and "sim=1" not in text and "NativeBridge" not in text
