"""HTTP-level tests for the Ski Jump gate (section 3.2)."""
from __future__ import annotations


def test_gate_denies_before_test_jump(client):
    response = client.post("/api/gate/scan", json={"wristband_id": "G001", "device_id": "gate-1"})
    body = response.json()
    assert body["allowed"] is False
    assert body["status"] == "NOG_NIET_GESPRONGEN"
    assert "testsprong" in body["reason"].lower()


def test_gate_denies_during_herkansing(client):
    client.post("/api/host/scan", json={"wristband_id": "G004", "device_id": "host-1"})
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "ROOD"})

    response = client.post("/api/gate/scan", json={"wristband_id": "G004", "device_id": "gate-1"})
    body = response.json()
    assert body["allowed"] is False
    assert body["status"] == "HERKANSING"


def test_gate_allows_after_geslaagd(client):
    client.post("/api/host/scan", json={"wristband_id": "G002", "device_id": "host-1"})
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "GROEN"})

    response = client.post("/api/gate/scan", json={"wristband_id": "G002", "device_id": "gate-1"})
    body = response.json()
    assert body["allowed"] is True
    assert body["status"] == "GESLAAGD"
    assert body["reason"] is None


def test_gate_denies_niet_geslaagd(client):
    wristband_id = "G003"
    client.post("/api/host/scan", json={"wristband_id": wristband_id, "device_id": "host-1"})
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "ROOD"})
    client.post("/api/host/scan", json={"wristband_id": wristband_id, "device_id": "host-1"})
    client.post("/api/host/verdict", json={"device_id": "host-1", "verdict": "ROOD"})

    response = client.post("/api/gate/scan", json={"wristband_id": wristband_id, "device_id": "gate-1"})
    body = response.json()
    assert body["allowed"] is False
    assert body["status"] == "NIET_GESLAAGD"
