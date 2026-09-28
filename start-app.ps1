# Start de server, opent de app in een kiosk-achtig browservenster, en
# sluit dat venster gegarandeerd mee af zodra de server zelf stopt (via de
# "Applicatie afsluiten"-knop op het beheerscherm, of Ctrl+C). Wordt
# onzichtbaar op de achtergrond gestart door start-app.bat -- PowerShell
# geeft betrouwbaar procesbeheer (starten, wachten, afsluiten), wat in
# batch onhandig is, en is robuuster dan browser-JavaScript (window.close()
# mag een browser om veiligheidsredenen negeren voor een venster dat niet
# via een script geopend is).

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $scriptDir "backend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    exit 1
}

# 0.0.0.0: luister op alle netwerkkaarten, niet enkel deze pc zelf -- nodig
# zodra iets anders dan deze pc (bv. de Android-app op een telefoon) de
# server over het lokale netwerk moet kunnen bereiken.
$env:TOELATING_HOST = "0.0.0.0"
$serverProcess = Start-Process -FilePath $venvPython -ArgumentList "run.py" `
    -WorkingDirectory $backendDir -WindowStyle Minimized -PassThru

Start-Sleep -Seconds 2

$appUrl = "http://127.0.0.1:8000/"
$browserPaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
$browserPath = $browserPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

# Een eigen, uniek profiel (i.p.v. het gewone Chrome/Edge-profiel van de
# gebruiker) zorgt ervoor dat dit altijd een volledig nieuw browserproces
# is -- anders herbruikt Chrome/Edge vaak een al lopende instantie, en zou
# er straks geen apart venster meer zijn om gericht af te sluiten.
$profileDir = Join-Path $env:TEMP "ToelatingssysteemKiosk"

if ($browserPath) {
    # De waarden in dubbele aanhalingstekens wikkelen is nodig zodra het
    # TEMP-pad een spatie bevat (bv. een gebruikersnaam met spatie) --
    # anders knipt Start-Process -ArgumentList het argument daar stuk.
    $arguments = @(
        "--app=`"$appUrl`"",
        "--no-first-run",
        "--user-data-dir=`"$profileDir`""
    )
    Start-Process -FilePath $browserPath -ArgumentList $arguments | Out-Null
} else {
    Start-Process -FilePath $appUrl | Out-Null
}

# Wacht tot de server stopt, en sluit dan het browservenster mee af.
$serverProcess.WaitForExit()

if ($browserPath) {
    Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe' OR Name = 'msedge.exe'" |
        Where-Object { $_.CommandLine -like "*$profileDir*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
