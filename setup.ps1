# Eén script voor de volledige installatie op Windows: controleert Python,
# maakt de virtuele omgeving aan, installeert de dependencies, en zet een
# bureaubladsnelkoppeling klaar. Dit vervangt de vroegere install.ps1 +
# maak-bureaubladsnelkoppeling.ps1 -- nu is er nog maar één bestand nodig.
#
# Uitvoeren: rechtsklik dit bestand -> "Uitvoeren met PowerShell".
# Op een nieuwe pc: kopieer eerst de hele projectmap (zonder backend\.venv),
# voer dan dit script uit.

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $scriptDir "backend"

function Stop-WithError($message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Red
    Read-Host "Druk op Enter om te sluiten"
    exit 1
}

Write-Host "=== Toelatingssysteem installeren ===" -ForegroundColor Cyan
Write-Host ""

# 1. Python controleren
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Stop-WithError "Geen 'python' gevonden op het PATH.`nInstalleer Python 3.12 of hoger van https://python.org -- vink tijdens de installatie `"Add python.exe to PATH`" aan, en start dit script daarna opnieuw."
}

$versionOutput = (& python --version 2>&1) -join " "
Write-Host "Gevonden: $versionOutput"
if ($versionOutput -match "Python (\d+)\.(\d+)") {
    $major = [int]$matches[1]
    $minor = [int]$matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 12)) {
        Stop-WithError "$versionOutput is te oud -- er is minstens Python 3.12 nodig.`nInstalleer een nieuwere versie van https://python.org en start dit script opnieuw."
    }
} else {
    Write-Host "Kon de Python-versie niet herkennen uit '$versionOutput' -- ga toch verder." -ForegroundColor Yellow
}

# 2. Virtuele omgeving + dependencies
Write-Host ""
Write-Host "Virtuele omgeving en dependencies installeren (kan even duren)..."
Push-Location $backendDir
try {
    $venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { Stop-WithError "Aanmaken van de virtuele omgeving (backend\.venv) is mislukt." }
    }

    & $venvPython -m pip install --upgrade pip --quiet
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Bijwerken van pip is mislukt. Controleer je internetverbinding." }

    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Installeren van de dependencies is mislukt. Controleer je internetverbinding en voer dit script opnieuw uit." }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path (Join-Path $scriptDir "data") | Out-Null
Write-Host "Installatie geslaagd." -ForegroundColor Green

# 3. Bureaubladsnelkoppeling
Write-Host ""
Write-Host "Bureaubladsnelkoppeling aanmaken..."
$target = Join-Path $scriptDir "start-app.bat"
$icon = Join-Path $scriptDir "frontend\shared\icons\favicon.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Toelatingssysteem.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $scriptDir
$shortcut.IconLocation = $icon
$shortcut.Description = "Toelatingssysteem veiligheidssprong (Sparkx)"
$shortcut.Save()

Write-Host "Snelkoppeling aangemaakt op het bureaublad: Toelatingssysteem" -ForegroundColor Green

Write-Host ""
Write-Host "=== Klaar! ===" -ForegroundColor Cyan
Write-Host "Dubbelklik de snelkoppeling 'Toelatingssysteem' op je bureaublad om te starten."
Write-Host ""
Write-Host "Nog geen medewerkers/admin op deze pc? Maak een eerste admin aan met:"
Write-Host "  cd backend; .venv\Scripts\python.exe create_admin.py"
Write-Host ""
Read-Host "Druk op Enter om te sluiten"
