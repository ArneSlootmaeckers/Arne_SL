"""/api/health: zonder login bereikbaar, en draagt het herkenningsteken
waarmee de Android-app de server automatisch op het netwerk terugvindt."""
from __future__ import annotations


def test_health_is_public_and_identifies_the_server(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "toelatingssysteem"
