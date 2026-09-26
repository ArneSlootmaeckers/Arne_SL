@echo off
REM Start de server en opent meteen de app in de browser.
REM Bedoeld om te koppelen aan een bureaubladsnelkoppeling — zie
REM maak-bureaubladsnelkoppeling.ps1 om die snelkoppeling met het
REM Sparkx-icoon aan te maken.

setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\activate.bat" (
    echo Geen virtuele omgeving gevonden in backend\.venv.
    echo Voer eerst install.sh uit ^(of volg de installatiestappen in README.md^).
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

set TOELATING_HOST=127.0.0.1
start "Toelatingssysteem - server (dit venster niet sluiten)" /min cmd /c "python run.py"

REM Even wachten tot de server opgestart is voor de browser opent.
timeout /t 2 /nobreak >nul

start "" "http://127.0.0.1:8000/"
