"""Updates van deze pc-installatie, via GitHub Releases.

- Een gewone release (bv. tag v1.3.0) is een stabiele versie. Staat
  "Automatisch bijwerken" aan op het beheerscherm, dan wordt die bij het
  opstarten van de app vanzelf geïnstalleerd.
- Een pre-release op GitHub (bv. v1.4.0-beta.1) is een beta: die wordt
  nooit automatisch geïnstalleerd, enkel met de knop op het beheerscherm.
- Drafts worden genegeerd.

Hoe een update verloopt: de server downloadt de broncode van de release
(zip van GitHub), pakt die uit in data/updates/ en controleert dat
backend/app/version.py dezelfde versie draagt als de tag. Daarna stopt de
server. Bij elke start voeren run.py en desktop.py eerst `update.py
--startup` uit (in een apart proces, vóór de app-code geladen wordt): dat
installeert de klaargezette update, of zoekt zelf een nieuwe stabiele versie
als automatisch bijwerken aanstaat. Mislukt het installeren (pip of de opstartcontrole), dan worden
de vorige bestanden teruggezet.

Nooit overschreven: de database en back-ups (data/), de virtuele omgeving
(backend/.venv), de meegeleverde Python (python/) en de eigen instellingen
(backend/config.yaml). Een ontwikkelkopie (met .git) wordt nooit bijgewerkt:
daar hoort git pull.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

INSTALL_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPO = "ArneSlootmaeckers/Arne_SL"
# run.py stopt met deze code als de server stopt om een update te
# installeren (systemd start hem dan opnieuw); desktop.py start zichzelf
# dan opnieuw. Gelijk houden met run.EXIT_CODE_RESTART.
EXIT_CODE_RESTART = 3
# `update.py --startup` stopt met deze code als er iets geïnstalleerd werd.
# Gelijk houden met update.EXIT_CODE_INSTALLED.
EXIT_CODE_INSTALLED = 10
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024

# Relatief t.o.v. de installatiemap; nooit overschreven of verwijderd.
PRESERVED = (".git", "backend/.venv", "data", "python", "backend/config.yaml", "installer/cache", "installer/build")

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")
_VERSION_IN_FILE = re.compile(r'^APP_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)


class UpdateError(Exception):
    """Algemene, korte melding: wordt zo op het beheerscherm getoond."""


# --- Versies ---------------------------------------------------------------

def version_key(text: str) -> tuple | None:
    """Sorteersleutel voor "1.2.3" of "v1.3.0-beta.2"; None als het geen
    versie is. Een beta komt vóór de gewone versie met hetzelfde nummer."""
    match = _VERSION.match(text.strip())
    if match is None:
        return None
    major, minor, patch, pre = match.groups()
    if pre is None:
        return (int(major), int(minor), int(patch), 1, ())
    parts = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split("."))
    return (int(major), int(minor), int(patch), 0, parts)


def is_newer(candidate: str, current: str) -> bool:
    new, old = version_key(candidate), version_key(current)
    return new is not None and (old is None or new > old)


# --- Releases op GitHub ----------------------------------------------------

@dataclass(frozen=True)
class Release:
    version: str  # zonder "v"
    tag: str
    name: str
    prerelease: bool
    published_at: str | None
    zipball_url: str
    html_url: str

    def as_dict(self) -> dict:
        return asdict(self)


def fetch_releases(client: httpx.Client, repo: str) -> list[Release]:
    try:
        response = client.get(
            f"https://api.github.com/repos/{repo}/releases",
            params={"per_page": 30},
            headers={"Accept": "application/vnd.github+json", "User-Agent": "toelatingssysteem-updater"},
        )
        response.raise_for_status()
        items = response.json()
    except httpx.HTTPError:
        raise UpdateError("GitHub niet bereikbaar.") from None
    except ValueError:
        raise UpdateError("Onverwacht antwoord van GitHub.") from None
    if not isinstance(items, list):
        raise UpdateError("Onverwacht antwoord van GitHub.")

    releases = []
    for item in items:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        tag = str(item.get("tag_name") or "")
        if version_key(tag) is None or not item.get("zipball_url"):
            continue
        releases.append(Release(
            version=tag.lstrip("v"),
            tag=tag,
            name=str(item.get("name") or tag),
            prerelease=bool(item.get("prerelease")),
            published_at=item.get("published_at"),
            zipball_url=str(item["zipball_url"]),
            html_url=str(item.get("html_url") or ""),
        ))
    return releases


def latest_releases(releases: list[Release]) -> tuple[Release | None, Release | None]:
    """(nieuwste stabiele, nieuwste beta). Een beta telt enkel als ze nieuwer
    is dan de nieuwste stabiele versie."""
    stable = max((r for r in releases if not r.prerelease), key=lambda r: version_key(r.version), default=None)
    beta = max((r for r in releases if r.prerelease), key=lambda r: version_key(r.version), default=None)
    if beta is not None and stable is not None and not is_newer(beta.version, stable.version):
        beta = None
    return stable, beta


# --- Downloaden en klaarzetten ---------------------------------------------

def _staged_version(root: Path) -> str | None:
    version_file = root / "backend" / "app" / "version.py"
    if not version_file.is_file():
        return None
    match = _VERSION_IN_FILE.search(version_file.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def _safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    target = target.resolve()
    for member in archive.infolist():
        destination = (target / member.filename).resolve()
        if destination != target and target not in destination.parents:
            raise UpdateError("Ongeldig updatebestand.")
    archive.extractall(target)


def download_and_stage(client: httpx.Client, release: Release, updates_dir: Path) -> Path:
    """Downloadt de release, pakt ze uit en controleert de versie. Geeft de
    map met de nieuwe bestanden terug (nog niet geïnstalleerd)."""
    updates_dir.mkdir(parents=True, exist_ok=True)
    for old in updates_dir.glob("staged-*"):
        shutil.rmtree(old, ignore_errors=True)
    zip_path = updates_dir / "download.zip"
    try:
        with client.stream(
            "GET", release.zipball_url, headers={"User-Agent": "toelatingssysteem-updater"}, follow_redirects=True
        ) as response:
            response.raise_for_status()
            size = 0
            with open(zip_path, "wb") as out:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES:
                        raise UpdateError("Updatebestand is te groot.")
                    out.write(chunk)
    except httpx.HTTPError:
        raise UpdateError("Downloaden van de update mislukt.") from None

    staged = updates_dir / f"staged-{release.version}"
    try:
        with zipfile.ZipFile(zip_path) as archive:
            _safe_extract(archive, staged)
    except zipfile.BadZipFile:
        raise UpdateError("Ongeldig updatebestand.") from None
    finally:
        zip_path.unlink(missing_ok=True)

    # GitHub zet alles in één map (eigenaar-repo-commit/).
    entries = [p for p in staged.iterdir()]
    root = entries[0] if len(entries) == 1 and entries[0].is_dir() else staged
    if not (root / "backend" / "run.py").is_file() or _staged_version(root) != release.version:
        shutil.rmtree(staged, ignore_errors=True)
        raise UpdateError(f"Release {release.tag} klopt niet (versie in backend/app/version.py verschilt).")
    return root


# --- Instellingen en status (data/updates/) --------------------------------

class UpdateStore:
    def __init__(self, updates_dir: Path) -> None:
        self.dir = updates_dir

    def _read(self, name: str) -> dict | None:
        try:
            data = json.loads((self.dir / name).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, ValueError):
            return None

    def _write(self, name: str, data: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / f"{name}.tmp"
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.dir / name)

    def auto_install(self) -> bool:
        return bool((self._read("settings.json") or {}).get("auto_install", False))

    def set_auto_install(self, enabled: bool) -> None:
        self._write("settings.json", {"auto_install": enabled})

    def pending(self) -> dict | None:
        return self._read("pending.json")

    def set_pending(self, version: str, staged_root: Path, channel: str) -> None:
        self._write("pending.json", {"version": version, "staged_root": str(staged_root), "channel": channel})

    def clear_pending(self) -> None:
        (self.dir / "pending.json").unlink(missing_ok=True)
        for staged in self.dir.glob("staged-*"):
            shutil.rmtree(staged, ignore_errors=True)

    def last_result(self) -> dict | None:
        return self._read("last-result.json")

    def set_last_result(self, *, ok: bool, message: str, version: str | None) -> None:
        self._write("last-result.json", {
            "ok": ok, "message": message, "version": version,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })


def updates_dir_for(database_path: str) -> Path:
    return Path(database_path).resolve().parent / "updates"


# --- Installeren -----------------------------------------------------------

def is_dev_checkout(install_root: Path) -> bool:
    return (install_root / ".git").exists()


def _is_preserved(relative: Path) -> bool:
    text = relative.as_posix()
    return any(text == p or text.startswith(p + "/") for p in PRESERVED)


def default_post_install(install_root: Path) -> None:
    """Dependencies bijwerken en nagaan dat de nieuwe code opstart."""
    backend = install_root / "backend"
    for args in (
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "requirements.txt"],
        [sys.executable, "-c", "import app.main"],
    ):
        result = subprocess.run(args, cwd=backend, capture_output=True, timeout=600)
        if result.returncode != 0:
            step = "dependencies installeren" if "pip" in args else "opstartcontrole"
            raise UpdateError(f"Update mislukt bij {step}; vorige versie teruggezet.")


def apply_update(
    install_root: Path, staged_root: Path, updates_dir: Path,
    *, post_install: Callable[[Path], None] = default_post_install,
) -> None:
    """Kopieert de klaargezette bestanden over de installatie. Lukt de
    nazorg (pip, opstartcontrole) niet, dan wordt alles teruggezet."""
    if is_dev_checkout(install_root):
        raise UpdateError("Dit is een ontwikkelkopie (git): werk die bij met git pull.")
    if not staged_root.is_dir():
        raise UpdateError("Klaargezette update niet gevonden.")

    backup = updates_dir / "backup"
    shutil.rmtree(backup, ignore_errors=True)
    replaced: list[Path] = []
    added: list[Path] = []

    def rollback() -> None:
        for relative in added:
            (install_root / relative).unlink(missing_ok=True)
        for relative in replaced:
            shutil.copy2(backup / relative, install_root / relative)

    try:
        for source in sorted(p for p in staged_root.rglob("*") if p.is_file()):
            relative = source.relative_to(staged_root)
            if _is_preserved(relative):
                continue
            destination = install_root / relative
            if destination.exists():
                (backup / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup / relative)
                replaced.append(relative)
            else:
                added.append(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        post_install(install_root)
    except UpdateError:
        rollback()
        raise
    except Exception:
        rollback()
        raise UpdateError("Update mislukt; vorige versie teruggezet.") from None


def run_startup(
    *, install_root: Path, updates_dir: Path, repo: str, current_version: str,
    client_factory: Callable[[], httpx.Client],
    post_install: Callable[[Path], None] = default_post_install,
) -> tuple[bool, str]:
    """Bij het opstarten: een klaargezette update installeren, of (als
    automatisch bijwerken aanstaat) de nieuwste stabiele versie. Gooit
    nooit: geeft terug of er iets geïnstalleerd werd, met een korte melding;
    de server start hoe dan ook."""
    store = UpdateStore(updates_dir)
    pending = store.pending()
    if pending is not None:
        version = pending.get("version")
        try:
            apply_update(install_root, Path(str(pending.get("staged_root"))), updates_dir, post_install=post_install)
        except UpdateError as exc:
            store.set_last_result(ok=False, message=str(exc), version=version)
            return False, str(exc)
        finally:
            store.clear_pending()
        store.set_last_result(ok=True, message=f"Versie {version} geïnstalleerd.", version=version)
        return True, f"Versie {version} geïnstalleerd."

    if not store.auto_install() or is_dev_checkout(install_root):
        return False, "Geen update."
    try:
        with client_factory() as client:
            stable, _ = latest_releases(fetch_releases(client, repo))
            if stable is None or not is_newer(stable.version, current_version):
                return False, "Geen update."
            staged = download_and_stage(client, stable, updates_dir)
        apply_update(install_root, staged, updates_dir, post_install=post_install)
    except UpdateError as exc:
        store.set_last_result(ok=False, message=f"Automatisch bijwerken: {exc}", version=None)
        return False, str(exc)
    finally:
        store.clear_pending()
    store.set_last_result(ok=True, message=f"Versie {stable.version} automatisch geïnstalleerd.", version=stable.version)
    return True, f"Versie {stable.version} geïnstalleerd."


def http_client() -> httpx.Client:
    return httpx.Client(timeout=30.0)


def main(argv: list[str]) -> int:
    """`python update.py --startup` vanuit backend/ (zie run.py)."""
    if argv != ["--startup"]:
        print("Gebruik: python update.py --startup")
        return 2
    from app.config import load_settings
    from app.version import APP_VERSION

    settings = load_settings()
    installed, message = run_startup(
        install_root=INSTALL_ROOT,
        updates_dir=updates_dir_for(settings.database_path),
        repo=settings.update_repo,
        current_version=APP_VERSION,
        client_factory=http_client,
    )
    print(f"Updatecontrole: {message}")
    return EXIT_CODE_INSTALLED if installed else 0
