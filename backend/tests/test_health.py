"""/api/health: zonder login bereikbaar, en draagt het herkenningsteken
waarmee de Android-app de server automatisch op het netwerk terugvindt."""
from __future__ import annotations


def test_health_is_public_and_identifies_the_server(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "toelatingssysteem"


def test_health_reports_a_stable_frontend_version(client):
    first = client.get("/api/health").json()["frontend_version"]
    assert len(first) == 12
    assert client.get("/api/health").json()["frontend_version"] == first


def test_frontend_version_changes_when_a_screen_file_changes(tmp_path, monkeypatch):
    from app import main

    (tmp_path / "host").mkdir()
    page = tmp_path / "host" / "app.js"
    page.write_text("oud")
    monkeypatch.setattr(main, "_FRONTEND_DIR", tmp_path)
    before = main._frontend_version()
    page.write_text("nieuw")
    assert main._frontend_version() != before


def test_frontend_files_are_never_served_from_a_stale_cache(client):
    # Een oude, opgeslagen app.js met een nieuwe server liet scans meteen
    # verdwijnen: telefoons moeten na een update altijd de nieuwe versie laden.
    for path in ("/host/", "/host/app.js", "/shared/api.js", "/admin/"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
