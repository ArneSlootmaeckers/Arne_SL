"""Opstarten op de Windows-pc als één venster (desktop.py): de server zonder
consolevenster, met enkel het app-venster in de taakbalk."""
from __future__ import annotations

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import desktop
import run


@pytest.fixture
def restore_output():
    stdout, stderr = sys.stdout, sys.stderr
    yield
    if sys.stdout is not stdout:
        sys.stdout.close()
    sys.stdout, sys.stderr = stdout, stderr


def test_with_a_console_nothing_is_redirected(tmp_path, restore_output):
    assert desktop.redirect_output_if_windowless(tmp_path / "logs") is False
    assert not (tmp_path / "logs").exists()


def test_without_console_output_goes_to_a_log_file(tmp_path, monkeypatch, restore_output):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "server.log").write_text("vorige keer\n")
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    assert desktop.redirect_output_if_windowless(logs) is True
    print("hallo")
    assert (logs / "server.log").read_text() == "hallo\n"
    assert (logs / "server.vorige.log").read_text() == "vorige keer\n"


def test_log_still_in_use_is_appended_to(tmp_path, monkeypatch, restore_output):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "server.log").write_text("al open\n")
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    def in_use(self, target):
        raise PermissionError("in gebruik")

    monkeypatch.setattr(Path, "replace", in_use)
    desktop.redirect_output_if_windowless(logs)
    print("erbij")
    assert (logs / "server.log").read_text() == "al open\nerbij\n"


def test_first_installed_browser_is_used(tmp_path):
    edge = tmp_path / "msedge.exe"
    edge.write_text("")
    assert desktop.find_browser([tmp_path / "chrome.exe", edge]) == edge
    assert desktop.find_browser([tmp_path / "chrome.exe"]) is None


def _health_server(app_id: str) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"app": app_id}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_detects_an_already_running_system():
    ours, other = _health_server("toelatingssysteem"), _health_server("iets-anders")
    try:
        assert desktop.server_running(ours.server_port) is True
        assert desktop.server_running(other.server_port) is False
    finally:
        ours.shutdown()
        other.shutdown()
    assert desktop.server_running(ours.server_port) is False  # niets luistert meer


class _FakeServer:
    def __init__(self) -> None:
        self.started = False
        self.should_exit = False

    async def serve(self) -> None:
        await asyncio.sleep(0.01)
        self.started = True
        while not self.should_exit:
            await asyncio.sleep(0.01)


def test_window_opens_only_when_both_servers_are_ready():
    main, local = _FakeServer(), _FakeServer()
    seen = []

    def on_started():
        seen.append((main.started, local.started))
        main.should_exit = True  # zoals "Applicatie afsluiten"

    asyncio.run(asyncio.wait_for(run._serve(main, local, on_started), timeout=5))
    assert seen == [(True, True)]
    assert local.should_exit is True  # de lokale server stopt mee
