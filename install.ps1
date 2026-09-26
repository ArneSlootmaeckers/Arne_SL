# Windows-installatiescript: zet een Python virtualenv op in backend\.venv
# en installeert de dependencies -- geen bash/WSL nodig. Het bash-
# equivalent (Linux/macOS) is install.sh. Zie README.md voor het volledige
# overzicht.
#
# Uitvoeren: rechtsklik dit bestand -> "Uitvoeren met PowerShell", of vanaf
# een PowerShell-venster: .\install.ps1

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $scriptDir "backend"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Geen 'python' gevonden op het PATH." -ForegroundColor Red
    Write-Host "Installeer Python 3.12 of hoger van https://python.org -- vink tijdens" -ForegroundColor Red
    Write-Host "de installatie zeker 'Add python.exe to PATH' aan." -ForegroundColor Red
    Read-Host "Druk op Enter om te sluiten"
    exit 1
}

Push-Location $backendDir

$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Virtualenv aanmaken in backend\.venv..."
    python -m venv .venv
}

& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r requirements.txt

Pop-Location

New-Item -ItemType Directory -Force -Path (Join-Path $scriptDir "data") | Out-Null

Write-Host ""
Write-Host "Installatie klaar." -ForegroundColor Green
Write-Host "  Server starten:          dubbelklik je bureaubladsnelkoppeling (zie"
Write-Host "                           maak-bureaubladsnelkoppeling.ps1), of start-app.bat"
Write-Host "  Eerste admin aanmaken:   cd backend; .venv\Scripts\python.exe create_admin.py"
Write-Host "  Demo-gegevens seeden:    cd backend; .venv\Scripts\python.exe seed.py"
Read-Host "Druk op Enter om te sluiten"
