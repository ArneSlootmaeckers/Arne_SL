# Windows-firewall voor het Toelatingssysteem. Vraagt zelf beheerdersrechten.
#
# Poort 8000 (https, voor de telefoons) wordt:
# - open gezet voor adressen van het eigen netwerk (10.x, 172.16-31.x,
#   192.168.x, ...), zodat de telefoons de server bereiken;
# - altijd dicht gezet voor internetadressen. Een blokkeerregel wint in
#   Windows van elke toelatingsregel -- ook van de regel die Windows zelf
#   aanmaakt als iemand bij de eerste start op "Toegang toestaan" klikt voor
#   Python. Zet iemand per ongeluk een poort op de router open, dan komt er
#   van buiten het park dus nog altijd niets binnen.
#
# De server weigert internetadressen ook zelf (zie
# backend/app/services/network_service.py: is_local_client); dit is het
# tweede slot, nog voor een verzoek het programma bereikt.
#
# De installer voert dit automatisch uit. Handmatig (bv. door IT):
# rechtsklik -> "Uitvoeren met PowerShell", of
#   powershell -ExecutionPolicy Bypass -File firewall.ps1 [-Port 8000] [-Remove]

param(
    [int]$Port = 8000,
    # Haalt de regels weer weg (bij het verwijderen van het programma).
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$allowName = "Toelatingssysteem - telefoons (eigen netwerk)"
$blockName = "Toelatingssysteem - geen toegang vanaf internet"

# Eigen netwerk: dezelfde adressen die de server zelf toelaat.
$localNetworks = @("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "169.254.0.0/16")
# Alle andere IPv4-adressen, dus het internet (127.x, de pc zelf, laat
# Windows altijd door).
$internetRanges = @(
    "1.0.0.0-9.255.255.255",
    "11.0.0.0-100.63.255.255",
    "100.128.0.0-126.255.255.255",
    "128.0.0.0-169.253.255.255",
    "169.255.0.0-172.15.255.255",
    "172.32.0.0-192.167.255.255",
    "192.169.0.0-255.255.255.255"
)

try {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        # Zichzelf opnieuw starten met beheerdersrechten (Windows vraagt dan
        # om bevestiging), en wachten tot dat klaar is.
        $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"", "-Port", $Port)
        if ($Remove) { $arguments += "-Remove" }
        $elevated = Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -Verb RunAs `
            -WindowStyle Hidden -Wait -PassThru
        exit $elevated.ExitCode
    }

    Get-NetFirewallRule -DisplayName $allowName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    Get-NetFirewallRule -DisplayName $blockName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    if ($Remove) {
        Write-Host "Firewallregels van het Toelatingssysteem verwijderd."
        exit 0
    }

    New-NetFirewallRule -DisplayName $allowName -Direction Inbound -Action Allow -Protocol TCP `
        -LocalPort $Port -RemoteAddress $localNetworks -Profile Any | Out-Null
    New-NetFirewallRule -DisplayName $blockName -Direction Inbound -Action Block -Protocol TCP `
        -LocalPort $Port -RemoteAddress $internetRanges -Profile Any | Out-Null
    Write-Host "Firewall ingesteld: poort $Port enkel open voor het eigen netwerk, dicht voor internet."
    exit 0
} catch {
    # Bv. "Nee" geklikt op de vraag om beheerdersrechten.
    Write-Host "Firewall instellen is mislukt: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
