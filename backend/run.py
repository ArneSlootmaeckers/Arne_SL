"""Serverlauncher. Start twee servers op dezelfde app:

- https op `port` (standaard 8000) voor de telefoons en de rest van het
  netwerk, met het eigen certificaat uit app/tls.py: zo kan niemand op het
  netwerk meelezen of berichten aanpassen;
- gewone http op 127.0.0.1:`local_port` (standaard 8001), enkel bereikbaar
  vanop deze pc zelf, voor het beheerscherm op de server-pc (zonder
  certificaatwaarschuwing in de browser).

Op de Windows-pc start de bureaubladsnelkoppeling dit niet rechtstreeks,
maar via desktop.py (zonder consolevenster, met het app-venster erbij).

Bewaart ook een verwijzing naar de hoofdserver op `app.state`, zodat het
beheerscherm de server netjes kan laten stoppen (zelfde effect als Ctrl+C in
het serverscherm) via `server.should_exit`. Dat is nodig omdat een OS-signaal
(SIGTERM) naar het eigen proces sturen op Windows geen nette shutdown geeft —
daar killt dat het proces meteen, zonder de FastAPI-lifespan
(achtergrondtaken, databaseverbinding) netjes af te sluiten. `should_exit` is
een gewone Python-vlag die uvicorn zelf ook zet bij Ctrl+C, en werkt daarom
identiek op Linux en Windows.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from collections.abc import Callable
from pathlib import Path

import uvicorn

if __name__ == "__main__":
    # Eerst een update installeren, vóór de app-code hieronder geladen wordt
    # (desktop.py doet hetzelfde vóór `import run`).
    import update

    update.run_before_start()

from app.config import load_settings  # noqa: E402
from app.tls import ensure_certificate
from asgi import app


class _LocalServer(uvicorn.Server):
    """De tweede server laat Ctrl+C over aan de hoofdserver: die stopt deze mee."""

    @contextlib.contextmanager
    def capture_signals(self):
        yield


async def _serve(main: uvicorn.Server, local: uvicorn.Server, on_started: Callable[[], object] | None) -> None:
    main_task = asyncio.create_task(main.serve())
    # Pas starten als de hoofdserver klaar is: die zet bij het opstarten
    # (lifespan) de database en instellingen klaar die beide nodig hebben.
    while not main.started and not main_task.done():
        await asyncio.sleep(0.05)
    local_task = asyncio.create_task(local.serve()) if main.started else None
    try:
        if local_task is not None and on_started is not None:
            while not local.started and not local_task.done():
                await asyncio.sleep(0.05)
            if local.started:
                on_started()
        await main_task
    finally:
        if local_task is not None:
            local.should_exit = True
            await local_task


def serve(*, access_log: bool = True, on_started: Callable[[], object] | None = None) -> None:
    """Start beide servers en draait tot ze stoppen (Ctrl+C of "Applicatie
    afsluiten"). `on_started` wordt opgeroepen zodra ze klaar zijn."""
    settings = load_settings()
    cert_path, key_path = ensure_certificate(Path(settings.tls_dir))
    host = os.environ.get("TOELATING_HOST", "0.0.0.0")

    # proxy_headers uit: er staat geen proxy voor, en anders zou een proces op
    # deze pc via X-Forwarded-For een ander adres kunnen opgeven (en zo de
    # blokkering na foute pincodes omzeilen).
    main_server = uvicorn.Server(
        uvicorn.Config(
            app, host=host, port=settings.port, ssl_certfile=cert_path, ssl_keyfile=key_path,
            proxy_headers=False, access_log=access_log,
        )
    )
    local_server = _LocalServer(
        uvicorn.Config(
            app, host="127.0.0.1", port=settings.local_port, lifespan="off", proxy_headers=False,
            access_log=access_log,
        )
    )
    app.state.uvicorn_server = main_server
    # Ctrl+C: beide servers zijn dan al netjes gestopt; geen foutmelding tonen.
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_serve(main_server, local_server, on_started))


# Moet gelijk zijn aan update_service.EXIT_CODE_RESTART.
EXIT_CODE_RESTART = 3


def restart_requested() -> bool:
    """Gestopt om een update te installeren (Beheer -> Systeem -> Updates)?"""
    return bool(getattr(app.state, "restart_for_update", False))


if __name__ == "__main__":
    serve()
    if restart_requested():
        # systemd (Restart=on-failure) start de server opnieuw; dan
        # installeert run_before_start de klaargezette update.
        print("Update klaargezet; de server start opnieuw op om ze te installeren.")
        sys.exit(EXIT_CODE_RESTART)
