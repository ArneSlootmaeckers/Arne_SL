"""Start het Toelatingssysteem op de Windows-pc als één venster.

De bureaubladsnelkoppeling start dit met pythonw.exe, Python zonder
consolevenster: de server draait onzichtbaar op de achtergrond, en enkel het
app-venster (Chrome of Edge zonder adresbalk) staat in de taakbalk.

- Het venster sluiten stopt de server niet: de telefoons blijven werken.
  Opnieuw op de snelkoppeling dubbelklikken opent het venster weer.
- "Applicatie afsluiten" (Beheer -> Systeem) stopt de server; dit script
  sluit dan ook het venster.
- Zonder console schrijft de server zijn meldingen naar data/logs/server.log:
  enkel meldingen en fouten, geen lijst van alle verzoeken.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
LOG_DIR = BACKEND_DIR.parent / "data" / "logs"
# Een eigen, apart browserprofiel: zo is het app-venster altijd een eigen
# browserproces, dat bij het afsluiten gericht gesloten kan worden.
PROFILE_DIR = Path(tempfile.gettempdir()) / "ToelatingssysteemKiosk"
APP_PATH = "/admin/"


def redirect_output_if_windowless(log_dir: Path) -> bool:
    """pythonw.exe heeft geen console (sys.stdout is None): schrijf dan naar
    een logbestand. Het vorige logbestand blijft bewaard als server.vorige.log."""
    if sys.stdout is not None and sys.stderr is not None:
        return False
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "server.log"
    mode = "w"
    try:
        if log_file.exists():
            log_file.replace(log_dir / "server.vorige.log")
    except OSError:
        # Nog in gebruik (Windows laat dan geen hernoemen toe): gewoon aanvullen.
        mode = "a"
    stream = open(log_file, mode, encoding="utf-8", buffering=1)  # noqa: SIM115 (open tot het einde)
    sys.stdout = sys.stderr = stream
    return True


def browser_candidates() -> list[Path]:
    env = os.environ
    return [
        Path(env.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(env.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(env.get("LocalAppData", "")) / "Google/Chrome/Application/chrome.exe",
        Path(env.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(env.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
    ]


def find_browser(candidates: list[Path]) -> Path | None:
    return next((path for path in candidates if path.is_file()), None)


def server_running(port: int) -> bool:
    """Draait het systeem al (bv. het venster werd gesloten, de server niet)?"""
    from app.api.routes_health import SERVER_APP_ID

    # Rechtstreeks, nooit via een proxyserver die op de pc ingesteld staat.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
            return json.load(response).get("app") == SERVER_APP_ID
    except (OSError, ValueError):
        return False


def open_window(url: str) -> None:
    browser = find_browser(browser_candidates())
    if browser is None:
        # Geen Chrome of Edge: dan gewoon een tabblad in de standaardbrowser.
        webbrowser.open(url)
        return
    subprocess.Popen([str(browser), f"--app={url}", "--no-first-run", f"--user-data-dir={PROFILE_DIR}"])


def close_window() -> None:
    """Sluit elk browserproces met ons eigen profiel, onzichtbaar (geen
    consolevenster dat even opflitst)."""
    if os.name != "nt":
        return
    profile = str(PROFILE_DIR).replace("'", "''")
    command = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'chrome.exe' OR Name = 'msedge.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{profile}*' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        creationflags=subprocess.CREATE_NO_WINDOW, check=False, timeout=60,
    )


def show_error(message: str) -> None:
    if os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "Toelatingssysteem", 0x10)  # MB_ICONERROR
    else:
        print(message, file=sys.stderr)


def main() -> None:
    # De instellingen (config.yaml, ../data/...) gaan uit van backend/.
    os.chdir(BACKEND_DIR)

    from app.config import load_settings

    port = load_settings().local_port
    url = f"http://127.0.0.1:{port}{APP_PATH}"
    if server_running(port):
        # Draait al: enkel het venster terug openen, en het logbestand van
        # de draaiende server niet aanraken.
        open_window(url)
        return

    redirect_output_if_windowless(LOG_DIR)

    try:
        import run  # maakt de app al aan: ook een fout hierin hoort een melding te geven

        run.serve(access_log=False, on_started=lambda: open_window(url))
    except SystemExit as exc:
        if exc.code not in (0, None):
            show_error(
                "Het Toelatingssysteem kon niet starten (draait het misschien al, of is poort "
                f"8000 of 8001 bezet?).\n\nMeer info in {LOG_DIR / 'server.log'}"
            )
        raise
    except Exception:
        # De volledige foutmelding komt via raise in het logbestand.
        show_error(f"Het Toelatingssysteem is gestopt door een fout.\n\nMeer info in {LOG_DIR / 'server.log'}")
        raise
    finally:
        close_window()


if __name__ == "__main__":
    main()
