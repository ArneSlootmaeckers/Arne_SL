@echo off
REM Start het Toelatingssysteem, net als de bureaubladsnelkoppeling: de
REM server zonder consolevenster, en enkel het app-venster in de taakbalk.
REM Zie backend\desktop.py.

setlocal
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\pythonw.exe" (
    echo Geen virtuele omgeving gevonden in backend\.venv.
    echo Voer eerst de installer of setup.ps1 uit.
    pause
    exit /b 1
)

start "" "%~dp0backend\.venv\Scripts\pythonw.exe" "%~dp0backend\desktop.py"
