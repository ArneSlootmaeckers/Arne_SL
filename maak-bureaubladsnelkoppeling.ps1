# Maakt een snelkoppeling "Toelatingssysteem" op het bureaublad die
# start-app.bat opstart, met het Sparkx-logo als icoon.
#
# Eenmalig uitvoeren: rechtsklik dit bestand -> "Uitvoeren met PowerShell".

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $scriptDir "start-app.bat"
$icon = Join-Path $scriptDir "frontend\shared\icons\favicon.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Toelatingssysteem.lnk"

if (-not (Test-Path $target)) {
    Write-Host "Kan start-app.bat niet vinden op: $target" -ForegroundColor Red
    Write-Host "Voer dit script uit vanuit de hoofdmap van het project." -ForegroundColor Red
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $scriptDir
$shortcut.IconLocation = $icon
$shortcut.Description = "Toelatingssysteem veiligheidssprong (Sparkx)"
$shortcut.Save()

Write-Host "Snelkoppeling aangemaakt op het bureaublad: $shortcutPath" -ForegroundColor Green
Write-Host "Dubbelklik erop om de server te starten en de app te openen."
