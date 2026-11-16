"""Updatecontrole bij het opstarten (zie app/services/update_service.py).

run.py en desktop.py roepen run_before_start() op vóór ze de app-code laden:
die start `update.py --startup` in een apart proces, dat een klaargezette
update installeert of (als automatisch bijwerken aanstaat) de nieuwste
stabiele versie. Dit bestand importeert zelf geen app-code, zodat het
opstarten daarna de nieuwe bestanden laadt.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Moet gelijk zijn aan update_service.EXIT_CODE_INSTALLED.
EXIT_CODE_INSTALLED = 10


def run_before_start() -> bool:
    """True als er net een update geïnstalleerd werd. Een fout houdt het
    opstarten nooit tegen."""
    backend = Path(__file__).resolve().parent
    extra = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    try:
        result = subprocess.run(
            [sys.executable, str(backend / "update.py"), "--startup"], cwd=backend, timeout=900, **extra
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Updatecontrole overgeslagen ({type(exc).__name__})")
        return False
    return result.returncode == EXIT_CODE_INSTALLED


if __name__ == "__main__":
    from app.services.update_service import main

    sys.exit(main(sys.argv[1:]))
