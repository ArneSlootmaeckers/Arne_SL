from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.version import APP_VERSION, MIN_ANDROID_VERSION_CODE

router = APIRouter(prefix="/api", tags=["health"])

# De Android-app zoekt het lokale netwerk af naar deze waarde, om de server
# te onderscheiden van eender welk ander toestel dat toevallig op poort 8000
# antwoordt -- niet wijzigen zonder ook ServerDiscovery.kt aan te passen.
SERVER_APP_ID = "toelatingssysteem"


@router.get("/health")
def health(request: Request) -> dict:
    return {
        "status": "ok",
        "app": SERVER_APP_ID,
        "frontend_version": request.app.state.frontend_version,
        "app_version": APP_VERSION,
        # Een oudere Android-app toont dan een updatevenster (zie MainActivity.kt).
        "min_android_version_code": MIN_ANDROID_VERSION_CODE,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
