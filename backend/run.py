"""Serverlauncher: bewaart een verwijzing naar de lopende `uvicorn.Server`
op `app.state`, zodat het beheerscherm de server netjes kan laten stoppen
(zelfde effect als Ctrl+C in het serverscherm) via `server.should_exit`.

Dat is nodig omdat een OS-signaal (SIGTERM) naar het eigen proces sturen op
Windows geen nette shutdown geeft — daar killt dat het proces meteen, zonder
de FastAPI-lifespan (achtergrondtaken, databaseverbinding) netjes af te
sluiten. `should_exit` is een gewone Python-vlag die uvicorn zelf ook zet
bij Ctrl+C, en werkt daarom identiek op Linux en Windows.
"""
from __future__ import annotations

import os

import uvicorn

from app.config import load_settings
from asgi import app

if __name__ == "__main__":
    settings = load_settings()
    host = os.environ.get("TOELATING_HOST", "0.0.0.0")
    config = uvicorn.Config(app, host=host, port=settings.port)
    server = uvicorn.Server(config)
    app.state.uvicorn_server = server
    server.run()
