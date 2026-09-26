@echo off
REM Start de server en opent meteen de app in de browser. Dit is het
REM doelwit van de bureaubladsnelkoppeling die setup.ps1 aanmaakt.
REM
REM De eigenlijke logica (server starten, browser starten, en die browser
REM weer mee afsluiten zodra de server stopt) staat in start-app.ps1 --
REM PowerShell is betrouwbaarder dan batch voor dat procesbeheer. Dit
REM bestand start dat script gewoon onzichtbaar op de achtergrond, zodat
REM er geen terminalvenster blijft openstaan.

setlocal
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
    echo Geen virtuele omgeving gevonden in backend\.venv.
    echo Voer eerst setup.ps1 uit ^(rechtsklik -^> Uitvoeren met PowerShell^).
    pause
    exit /b 1
)

start "" powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0start-app.ps1"
