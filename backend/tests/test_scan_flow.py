"""HTTP-level tests for the host screen: scans, verdicts, practice jumps,
"one scan = one verdict", and time-outs (see section 3.1 and 8 of the assignment).
"""
from __future__ import annotations

import time


def _scan(client, wristband_id="B001", device_id="host-1"):
    return client.post("/api/host/scan", json={"wristband_id": wristband_id, "device_id": device_id})


def test_first_scan_is_not_yet_jumped(client):
    response = _scan(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NOG_NIET_GESPRONGEN"
    assert body["requires_verdict"] is True
    assert body["requires_practice_ack"] is False


def test_green_verdict_sets_geslaagd(client):
    _scan(client)
    response = client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})
    assert response.status_code == 200
    assert response.json()["status"] == "GESLAAGD"


def test_red_then_green_sets_geslaagd_via_herkansing(client):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "ROOD"})

    second_scan = _scan(client)
    assert second_scan.json()["status"] == "HERKANSING"

    response = client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})
    assert response.json()["status"] == "GESLAAGD"


def test_red_twice_sets_niet_geslaagd_and_blocks_test_jump(client):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "ROOD"})
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "ROOD"})

    third_attempt = _scan(client)
    body = third_attempt.json()
    assert body["status"] == "NIET_GESLAAGD"
    assert body["requires_verdict"] is False
    assert body["requires_practice_ack"] is False


def test_geslaagd_scan_requires_practice_ack_not_verdict(client):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})

    practice_scan = _scan(client)
    body = practice_scan.json()
    assert body["status"] == "GESLAAGD"
    assert body["requires_verdict"] is False
    assert body["requires_practice_ack"] is True

    ack = client.post("/api/host/practice-ack", json={"device_id": "host-1"})
    assert ack.status_code == 200


def test_new_scan_replaces_a_scan_still_waiting_for_a_verdict(client, db_session):
    _scan(client, wristband_id="B001")
    response = _scan(client, wristband_id="B002")
    assert response.status_code == 200
    assert response.json()["wristband_id"] == "B002"

    # Het oordeel gaat nu naar het nieuwe bandje...
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})
    assert _scan(client, wristband_id="B002").json()["status"] == "GESLAAGD"
    # ...en het vervangen bandje kreeg geen oordeel: status ongewijzigd.
    assert _scan(client, wristband_id="B001").json()["status"] == "NOG_NIET_GESPRONGEN"

    from app.models import EventModel

    replaced = db_session.query(EventModel).filter_by(event_type="GEANNULEERD").all()
    assert [e.wristband_id for e in replaced] == ["B001"]
    assert "nieuwe scan zonder oordeel" in replaced[0].detail


def test_new_scan_during_practice_jump_counts_as_practice_jump(client, db_session):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})
    assert _scan(client).json()["requires_practice_ack"] is True

    assert _scan(client, wristband_id="B002").status_code == 200

    from app.models import EventModel

    practice = db_session.query(EventModel).filter_by(event_type="OEFENSPRONG").all()
    assert [e.wristband_id for e in practice] == ["B001"]


def test_verdict_has_no_time_limit(client, db_session):
    scan = _scan(client)
    assert scan.json()["expires_at"] is None
    time.sleep(1.2)  # langer dan test_settings.scan_timeout_seconds == 1

    from app.main import reap_expired_pending_scans

    assert reap_expired_pending_scans(client.app.state.session_factory()) == 0
    response = client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})
    assert response.status_code == 200
    assert response.json()["status"] == "GESLAAGD"

    from app.models import EventModel

    assert db_session.query(EventModel).filter_by(event_type="TIME_OUT").count() == 0


def test_practice_jump_still_times_out(client, db_session):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})
    assert _scan(client).json()["expires_at"] is not None
    time.sleep(1.2)

    response = client.post("/api/host/practice-ack", json={"device_id": "host-1"})
    assert response.status_code == 409

    from app.models import EventModel

    assert db_session.query(EventModel).filter_by(event_type="TIME_OUT").count() == 1


def test_verdict_without_pending_scan_is_rejected(client):
    response = client.post("/api/host/verdict", json={"device_id": "no-such-device", "verdict": "GROEN"})
    assert response.status_code == 409


def test_practice_ack_via_verdict_endpoint_is_rejected(client):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})
    _scan(client)  # now GESLAAGD, requires practice-ack

    response = client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})
    assert response.status_code == 400


def test_cancel_scan_discards_pending_scan_without_status_change(client):
    """The visitor scanned but didn't actually jump (changed their mind, ...):
    cancelling must leave the status untouched, exactly like a time-out."""
    scan = _scan(client)
    assert scan.json()["status"] == "NOG_NIET_GESPRONGEN"

    cancel = client.post("/api/host/cancel", json={"device_id": "host-1"})
    assert cancel.status_code == 200

    # Status unchanged, and the device is immediately free for the next scan
    # (no need to wait out the timeout).
    again = _scan(client)
    assert again.json()["status"] == "NOG_NIET_GESPRONGEN"


def test_cancel_scan_works_while_a_verdict_is_pending_on_herkansing(client):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "ROOD"})
    scan = _scan(client)
    assert scan.json()["status"] == "HERKANSING"

    cancel = client.post("/api/host/cancel", json={"device_id": "host-1"})
    assert cancel.status_code == 200

    again = _scan(client)
    assert again.json()["status"] == "HERKANSING"  # niet gedegradeerd, niet gepromoveerd


def test_cancel_scan_also_works_for_a_pending_practice_jump(client):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})
    scan = _scan(client)
    assert scan.json()["requires_practice_ack"] is True

    cancel = client.post("/api/host/cancel", json={"device_id": "host-1"})
    assert cancel.status_code == 200

    again = _scan(client)
    assert again.json()["status"] == "GESLAAGD"


def test_cancel_scan_without_pending_scan_is_rejected(client):
    response = client.post("/api/host/cancel", json={"device_id": "no-such-device"})
    assert response.status_code == 409


def test_cancel_scan_is_logged_as_geannuleerd(client, db_session):
    _scan(client)
    client.post("/api/host/cancel", json={"device_id": "host-1"})

    from app.models import EventModel

    events = db_session.query(EventModel).filter_by(event_type="GEANNULEERD").all()
    assert len(events) == 1
    assert events[0].wristband_id == "B001"


# --- Ski Jump-toegang meteen mee op het hostscherm (geen apart toegangsscherm) ---


def test_scan_of_a_pending_wristband_has_no_ski_jump_info_yet(client):
    body = _scan(client).json()
    assert body["status"] == "NOG_NIET_GESPRONGEN"
    assert body["ski_jump_toegestaan"] is None
    assert body["ski_jump_reden"] is None


def test_green_verdict_response_grants_ski_jump_access(client):
    _scan(client)
    response = client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})
    body = response.json()
    assert body["status"] == "GESLAAGD"
    assert body["ski_jump_toegestaan"] is True
    assert body["ski_jump_reden"] is None


def test_red_verdict_on_first_attempt_has_no_ski_jump_info_yet(client):
    _scan(client)
    response = client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "ROOD"})
    body = response.json()
    assert body["status"] == "HERKANSING"
    assert body["ski_jump_toegestaan"] is None


def test_red_verdict_on_herkansing_denies_ski_jump_access(client):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "ROOD"})
    _scan(client)
    response = client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "ROOD"})
    body = response.json()
    assert body["status"] == "NIET_GESLAAGD"
    assert body["ski_jump_toegestaan"] is False
    assert body["ski_jump_reden"] == "Vandaag niet meer toegestaan"


def test_rescanning_a_geslaagd_wristband_also_shows_ski_jump_access(client):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})

    body = _scan(client).json()
    assert body["status"] == "GESLAAGD"
    assert body["ski_jump_toegestaan"] is True


def test_ski_jump_access_check_is_logged(client, db_session):
    _scan(client)
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})

    from app.models import EventModel

    events = db_session.query(EventModel).filter_by(event_type="TOEGANG_SKI_JUMP").all()
    assert len(events) == 1
    assert events[0].wristband_id == "B001"
