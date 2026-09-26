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

set "APP_URL=http://127.0.0.1:8000/"
set "BROWSER_PATH="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BROWSER_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER_PATH if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "BROWSER_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER_PATH if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "BROWSER_PATH=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER_PATH if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "BROWSER_PATH=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not defined BROWSER_PATH if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "BROWSER_PATH=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"

if defined BROWSER_PATH (
    REM "--app" opent een kiosk-achtig venster zonder adresbalk/tabbladen —
    REM verbetert de kans dat de "Applicatie afsluiten"-knop het venster ook
    REM zelf kan sluiten (browsers laten dat normaal enkel toe voor vensters
    REM die via een script geopend zijn). Niet 100% gegarandeerd in elke
    REM Chrome/Edge-versie; werkt dat niet, dan blijft het venster gewoon
    REM open met de boodschap dat het handmatig gesloten mag worden.
    start "" "%BROWSER_PATH%" --app=%APP_URL% --no-first-run
) else (
    start "" "%APP_URL%"
)
