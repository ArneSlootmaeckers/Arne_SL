"""Updates via GitHub Releases: een gewone release mag automatisch bij het
opstarten, een beta (pre-release) nooit automatisch maar wel met één klik."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.services import update_service
from app.services.update_service import UpdateError, UpdateStore
from app.version import APP_VERSION, MIN_ANDROID_VERSION_CODE

REPO = "ArneSlootmaeckers/Arne_SL"


def _zip(version: str, *, extra: dict[str, str] | None = None, top: str = "ArneSlootmaeckers-Arne_SL-abc123/") -> bytes:
    files = {
        "backend/run.py": "# run\n",
        "backend/app/version.py": f'APP_VERSION = "{version}"\nMIN_ANDROID_VERSION_CODE = 2\n',
        "backend/config.yaml": "nieuw: true\n",
        "frontend/admin/app.js": f"// {version}\n",
        **(extra or {}),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(top + name, content)
    return buffer.getvalue()


def _release(tag: str, *, prerelease: bool = False, draft: bool = False) -> dict:
    return {
        "tag_name": tag, "name": tag, "prerelease": prerelease, "draft": draft,
        "published_at": "2026-11-10T10:00:00Z",
        "zipball_url": f"https://api.github.com/repos/{REPO}/zipball/{tag}",
        "html_url": f"https://github.com/{REPO}/releases/tag/{tag}",
    }


class FakeGitHub:
    def __init__(self, releases: list[dict], zips: dict[str, bytes] | None = None) -> None:
        self.releases = releases
        self.zips = zips or {}
        self.requests: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        if request.url.path == f"/repos/{REPO}/releases":
            return httpx.Response(200, json=self.releases)
        tag = request.url.path.rsplit("/", 1)[-1]
        if tag in self.zips:
            return httpx.Response(200, content=self.zips[tag])
        return httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


def _install(root: Path, version: str = "1.0.0") -> Path:
    files = {
        "backend/run.py": "# oud\n",
        "backend/app/version.py": f'APP_VERSION = "{version}"\n',
        "backend/config.yaml": "eigen: instelling\n",
        "backend/.venv/marker": "venv\n",
        "data/toelating.db": "database\n",
        "frontend/admin/app.js": "// oud\n",
    }
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(content, encoding="utf-8")
    return root


# --- Versies en releases ---------------------------------------------------

def test_versions_sort_with_beta_before_final():
    ordered = ["1.0.0", "1.0.1", "v1.1.0-beta.1", "1.1.0-beta.2", "1.1.0-beta.10", "1.1.0", "2.0.0"]
    keys = [update_service.version_key(v) for v in ordered]
    assert keys == sorted(keys)
    assert update_service.version_key("niet-een-versie") is None
    assert update_service.is_newer("1.1.0", "1.0.0") and not update_service.is_newer("1.0.0", "1.0.0")


def test_latest_releases_skips_drafts_and_old_betas():
    github = FakeGitHub([
        _release("v1.1.0"), _release("v1.0.0"), _release("v1.3.0", draft=True),
        _release("v1.0.5-beta.1", prerelease=True), _release("rommel"),
    ])
    with github.client() as client:
        stable, beta = update_service.latest_releases(update_service.fetch_releases(client, REPO))
    assert stable.version == "1.1.0"
    assert beta is None  # ouder dan de nieuwste stabiele versie

    github.releases.append(_release("v1.2.0-beta.1", prerelease=True))
    with github.client() as client:
        _, beta = update_service.latest_releases(update_service.fetch_releases(client, REPO))
    assert beta.version == "1.2.0-beta.1" and beta.prerelease


def test_github_errors_are_short():
    def down(request):
        raise httpx.ConnectError("weg")

    with httpx.Client(transport=httpx.MockTransport(down)) as client:
        with pytest.raises(UpdateError, match="GitHub niet bereikbaar"):
            update_service.fetch_releases(client, REPO)


# --- Downloaden en klaarzetten ---------------------------------------------

def test_download_and_stage_checks_the_version(tmp_path):
    release = update_service.Release("1.1.0", "v1.1.0", "v1.1.0", False, None,
                                     f"https://api.github.com/repos/{REPO}/zipball/v1.1.0", "")
    github = FakeGitHub([], {"v1.1.0": _zip("1.1.0")})
    with github.client() as client:
        staged = update_service.download_and_stage(client, release, tmp_path / "updates")
    assert (staged / "backend" / "run.py").is_file()
    assert not (tmp_path / "updates" / "download.zip").exists()

    github.zips["v1.1.0"] = _zip("1.0.9")  # tag en version.py verschillen
    with github.client() as client:
        with pytest.raises(UpdateError, match="klopt niet"):
            update_service.download_and_stage(client, release, tmp_path / "updates")


def test_zip_with_paths_outside_the_folder_is_refused(tmp_path):
    release = update_service.Release("1.1.0", "v1.1.0", "", False, None,
                                     f"https://api.github.com/repos/{REPO}/zipball/v1.1.0", "")
    github = FakeGitHub([], {"v1.1.0": _zip("1.1.0", extra={"../../buiten.txt": "x"})})
    with github.client() as client:
        with pytest.raises(UpdateError, match="Ongeldig"):
            update_service.download_and_stage(client, release, tmp_path / "updates")
    assert not (tmp_path / "buiten.txt").exists()


# --- Installeren -----------------------------------------------------------

def _staged(tmp_path: Path, version: str, extra: dict[str, str] | None = None) -> Path:
    root = tmp_path / "staged"
    with zipfile.ZipFile(io.BytesIO(_zip(version, extra=extra, top=""))) as archive:
        archive.extractall(root)
    return root


def test_apply_keeps_data_venv_and_config(tmp_path):
    root = _install(tmp_path / "install")
    staged = _staged(tmp_path, "1.1.0", {"backend/app/nieuw.py": "x = 1\n", "data/toelating.db": "LEEG"})
    update_service.apply_update(root, staged, tmp_path / "updates", post_install=lambda r: None)

    assert (root / "frontend/admin/app.js").read_text() == "// 1.1.0\n"
    assert (root / "backend/app/nieuw.py").is_file()
    assert (root / "backend/config.yaml").read_text() == "eigen: instelling\n"
    assert (root / "data/toelating.db").read_text() == "database\n"
    assert (root / "backend/.venv/marker").is_file()


def test_failed_post_install_rolls_back(tmp_path):
    root = _install(tmp_path / "install")
    staged = _staged(tmp_path, "1.1.0", {"backend/app/nieuw.py": "x = 1\n"})

    def broken(install_root):
        raise UpdateError("Update mislukt bij dependencies installeren; vorige versie teruggezet.")

    with pytest.raises(UpdateError, match="teruggezet"):
        update_service.apply_update(root, staged, tmp_path / "updates", post_install=broken)
    assert (root / "frontend/admin/app.js").read_text() == "// oud\n"
    assert (root / "backend/app/version.py").read_text() == 'APP_VERSION = "1.0.0"\n'
    assert not (root / "backend/app/nieuw.py").exists()


def test_a_git_checkout_is_never_overwritten(tmp_path):
    root = _install(tmp_path / "install")
    (root / ".git").mkdir()
    with pytest.raises(UpdateError, match="git pull"):
        update_service.apply_update(root, _staged(tmp_path, "1.1.0"), tmp_path / "updates", post_install=lambda r: None)
    assert (root / "frontend/admin/app.js").read_text() == "// oud\n"


# --- Bij het opstarten -----------------------------------------------------

def _startup(root: Path, updates: Path, github: FakeGitHub | None, current: str = "1.0.0") -> tuple[bool, str]:
    def no_network():
        pytest.fail("Mag GitHub niet contacteren")

    return update_service.run_startup(
        install_root=root, updates_dir=updates, repo=REPO, current_version=current,
        client_factory=github.client if github else no_network, post_install=lambda r: None,
    )


def test_startup_installs_a_pending_update(tmp_path):
    root, updates = _install(tmp_path / "install"), tmp_path / "updates"
    store = UpdateStore(updates)
    store.set_pending("1.2.0-beta.1", _staged(tmp_path, "1.2.0-beta.1"), "beta")

    assert _startup(root, updates, None) == (True, "Versie 1.2.0-beta.1 geïnstalleerd.")
    assert (root / "frontend/admin/app.js").read_text() == "// 1.2.0-beta.1\n"
    assert store.pending() is None
    assert store.last_result()["ok"] is True


def test_startup_without_auto_install_stays_offline(tmp_path):
    root, updates = _install(tmp_path / "install"), tmp_path / "updates"
    assert _startup(root, updates, None) == (False, "Geen update.")


def test_auto_install_takes_stable_never_beta(tmp_path):
    root, updates = _install(tmp_path / "install"), tmp_path / "updates"
    UpdateStore(updates).set_auto_install(True)
    github = FakeGitHub(
        [_release("v1.1.0"), _release("v1.2.0-beta.1", prerelease=True)],
        {"v1.1.0": _zip("1.1.0"), "v1.2.0-beta.1": _zip("1.2.0-beta.1")},
    )
    _startup(root, updates, github)
    assert (root / "frontend/admin/app.js").read_text() == "// 1.1.0\n"
    assert not any("beta" in url for url in github.requests if "zipball" in url)

    # Enkel een nieuwere beta: niets automatisch.
    github.releases = [_release("v1.1.0"), _release("v1.3.0-beta.1", prerelease=True)]
    assert _startup(root, updates, github, current="1.1.0") == (False, "Geen update.")


def test_failed_auto_install_is_reported(tmp_path):
    root, updates = _install(tmp_path / "install"), tmp_path / "updates"
    store = UpdateStore(updates)
    store.set_auto_install(True)
    github = FakeGitHub([_release("v1.1.0")], {"v1.1.0": _zip("9.9.9")})
    assert _startup(root, updates, github)[0] is False
    assert store.last_result()["ok"] is False
    assert (root / "frontend/admin/app.js").read_text() == "// oud\n"


# --- Beheerscherm en /api/health -------------------------------------------

def test_health_tells_the_app_its_minimum_version(client):
    body = client.get("/api/health").json()
    assert body["app_version"] == APP_VERSION
    assert body["min_android_version_code"] == MIN_ANDROID_VERSION_CODE


@pytest.fixture
def github():
    newer = update_service.version_key(APP_VERSION)[:3]
    stable = f"{newer[0]}.{newer[1] + 1}.0"
    beta = f"{newer[0]}.{newer[1] + 2}.0-beta.1"
    return SimpleNamespace(
        fake=FakeGitHub(
            [_release(f"v{stable}"), _release(f"v{beta}", prerelease=True)],
            {f"v{stable}": _zip(stable), f"v{beta}": _zip(beta)},
        ),
        stable=stable, beta=beta,
    )


@pytest.fixture
def admin(client, admin_employee, github, tmp_path):
    client.app.state.update_http_client = github.fake.client
    client.app.state.install_root = _install(tmp_path / "install")
    token = client.post("/api/auth/login", json={"pincode": "1234"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_updates_are_for_the_admin_only(client, supervisor_employee):
    token = client.post("/api/auth/login", json={"pincode": "5678"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/admin/updates", headers=headers).status_code == 403
    assert client.post("/api/admin/updates/install", json={"channel": "stable"}, headers=headers).status_code == 403


def test_check_shows_stable_and_beta(client, admin, github):
    body = client.post("/api/admin/updates/check", headers=admin).json()
    assert body["current_version"] == APP_VERSION and body["auto_install"] is False
    assert body["check"]["stable"]["version"] == github.stable and body["check"]["stable"]["newer"]
    assert body["check"]["beta"]["version"] == github.beta and body["check"]["beta"]["prerelease"]


def test_auto_install_setting_is_saved_and_logged(client, admin, test_settings):
    assert client.put("/api/admin/updates/settings", json={"auto_install": True}, headers=admin).json()["auto_install"]
    assert UpdateStore(update_service.updates_dir_for(test_settings.database_path)).auto_install()
    events = client.get("/api/admin/logs?event_type=UPDATE_INSTELLING", headers=admin).json()
    assert events[0]["detail"] == {"automatisch": True}


def test_install_needs_run_py(client, admin):
    response = client.post("/api/admin/updates/install", json={"channel": "stable"}, headers=admin)
    assert response.status_code == 503


@pytest.mark.parametrize("channel", ["stable", "beta"])
def test_one_click_install_stages_and_restarts(client, admin, github, test_settings, channel):
    client.app.state.uvicorn_server = SimpleNamespace(should_exit=False)
    response = client.post("/api/admin/updates/install", json={"channel": channel}, headers=admin)
    assert response.status_code == 200
    expected = github.stable if channel == "stable" else github.beta
    assert response.json()["version"] == expected

    pending = UpdateStore(update_service.updates_dir_for(test_settings.database_path)).pending()
    assert pending["version"] == expected and pending["channel"] == channel
    assert Path(pending["staged_root"], "backend", "run.py").is_file()
    assert client.app.state.uvicorn_server.should_exit and client.app.state.restart_for_update
    event = client.get("/api/admin/logs?event_type=UPDATE_GESTART", headers=admin).json()[0]
    assert event["detail"] == {"van": APP_VERSION, "naar": expected, "kanaal": channel}


def test_install_refuses_a_git_checkout_and_nothing_newer(client, admin, github):
    client.app.state.uvicorn_server = SimpleNamespace(should_exit=False)
    (client.app.state.install_root / ".git").mkdir()
    assert client.post("/api/admin/updates/install", json={"channel": "stable"}, headers=admin).status_code == 409
    (client.app.state.install_root / ".git").rmdir()

    github.fake.releases = [_release(f"v{APP_VERSION}")]
    response = client.post("/api/admin/updates/install", json={"channel": "stable"}, headers=admin)
    assert response.status_code == 409 and not client.app.state.uvicorn_server.should_exit


def test_install_reports_github_errors(client, admin):
    def down():
        return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))

    client.app.state.uvicorn_server = SimpleNamespace(should_exit=False)
    client.app.state.update_http_client = down
    response = client.post("/api/admin/updates/install", json={"channel": "stable"}, headers=admin)
    assert response.status_code == 502 and "GitHub" in response.json()["detail"]
    assert json.loads(client.get("/api/admin/updates", headers=admin).text)["check"]["error"]
