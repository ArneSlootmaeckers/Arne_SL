"""Systeem-tabblad: toont het IP-adres + poort dat in de telefoon-app ingevuld
moet worden. Enkel voor admins."""
from __future__ import annotations

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
    assert response.json() == {"port": 8000, "addresses": ["10.18.0.155"]}


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
