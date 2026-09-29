from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])

# De Android-app zoekt het lokale netwerk af naar deze waarde, om de server
# te onderscheiden van eender welk ander toestel dat toevallig op poort 8000
# antwoordt -- niet wijzigen zonder ook ServerDiscovery.kt aan te passen.
SERVER_APP_ID = "toelatingssysteem"


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": SERVER_APP_ID,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
