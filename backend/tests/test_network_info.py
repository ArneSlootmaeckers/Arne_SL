"""Systeem-tabblad: toont het IP-adres + poort dat in de telefoon-app ingevuld
moet worden (enkel voor admins). En: de server weigert elk verzoek vanaf
een internetadres."""
from __future__ import annotations

import dataclasses

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import network_service


def _login(client, pincode: str) -> dict:
    token = client.post("/api/auth/login", json={"pincode": pincode}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_network_info_requires_authentication(client):
    assert client.get("/api/admin/network").status_code == 401


def test_network_info_requires_admin_role(client, supervisor_employee):
    response = client.get("/api/admin/network", headers=_login(client, "5678"))
    assert response.status_code == 403


def test_network_info_returns_port_and_addresses(client, admin_employee, monkeypatch):
    monkeypatch.setattr(network_service, "local_ipv4_addresses", lambda: ["10.18.0.155"])

    response = client.get("/api/admin/network", headers=_login(client, "1234"))

    assert response.status_code == 200
    assert response.json() == {"port": 8000, "addresses": ["10.18.0.155"], "certificate_fingerprint": None}


def test_addresses_skip_loopback_and_link_local_and_keep_primary_first(monkeypatch):
    monkeypatch.setattr(network_service, "_primary_ipv4", lambda: "192.168.1.20")
    monkeypatch.setattr(
        network_service, "_all_ipv4",
        lambda: ["127.0.0.1", "169.254.3.4", "10.0.0.5", "192.168.1.20"],
    )

    assert network_service.local_ipv4_addresses() == ["192.168.1.20", "10.0.0.5"]


def test_addresses_without_any_network_is_empty(monkeypatch):
    monkeypatch.setattr(network_service, "_primary_ipv4", lambda: None)
    monkeypatch.setattr(network_service, "_all_ipv4", lambda: ["127.0.0.1"])

    assert network_service.local_ipv4_addresses() == []


@pytest.mark.parametrize(
    "host",
    ["10.18.0.155", "192.168.1.20", "172.16.0.1", "127.0.0.1", "169.254.3.4", "100.64.1.1", "::1", "fe80::1"],
)
def test_local_network_addresses_are_allowed(host):
    assert network_service.is_local_client(host) is True


@pytest.mark.parametrize("host", ["8.8.8.8", "81.82.83.84", "::ffff:8.8.8.8", "2a02:1810::1", None, "testclient"])
def test_internet_and_unknown_addresses_are_refused(host):
    assert network_service.is_local_client(host) is False


def test_extra_allowed_network():
    assert network_service.is_local_client("203.0.113.7", ["203.0.113.0/24"]) is True
    assert network_service.is_local_client("203.0.114.7", ["203.0.113.0/24"]) is False


def test_server_refuses_requests_from_the_internet(test_settings):
    app = create_app(test_settings)
    with TestClient(app, client=("81.82.83.84", 50000)) as outsider:
        for path in ("/api/health", "/host/", "/admin/"):
            response = outsider.get(path)
            assert response.status_code == 403
            assert "eigen netwerk" in response.json()["detail"]
        assert outsider.post("/api/auth/login", json={"pincode": "1234"}).status_code == 403

    with TestClient(app, client=("10.18.0.42", 50000)) as insider:
        assert insider.get("/api/health").status_code == 200


def test_extra_allowed_networks_from_config(test_settings):
    settings = dataclasses.replace(test_settings, extra_allowed_networks=["81.82.83.0/24"])
    with TestClient(create_app(settings), client=("81.82.83.84", 50000)) as client:
        assert client.get("/api/health").status_code == 200
