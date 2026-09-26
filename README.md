# Toelatingssysteem veiligheidssprong

Softwaresysteem voor de veiligheidssprong-attractie: bezoekers scannen hun
bandje bij elke test- of oefensprong, de host beoordeelt de sprong met
groen/rood, en datzelfde hostscherm toont meteen ook of de bezoeker naar
de Ski Jump mag — geen apart scherm bij de Ski Jump zelf nodig. Zie de
statuslogica in hoofdstuk 2 van de opdracht (of
`backend/app/domain/status.py`) voor de volledige regels.

## Overzicht

- **Backend**: Python (FastAPI) + SQLite, met de volledige statuslogica in
  één pure module (`backend/app/domain/status.py`, zonder I/O — dus
  volledig unit-testbaar).
- **Frontend**: twee eenvoudige HTML/CSS/JS-schermen, meegeserveerd door
  dezelfde backend:
  - `/host/` — hostscherm: testsprong beoordelen én de Ski Jump-toegang
    (elke scan die meteen op GESLAAGD/NIET_GESLAAGD uitkomt, stuurt ook
    het hekje aan en logt de toegangscontrole). Dit is de standaard
    startpagina (`/` verwijst hiernaar door).
  - `/admin/` — beheerscherm voor bevoegd personeel, bereikbaar via de
    knop **"Profiel"** rechtsboven op het hostscherm (of rechtstreeks op
    `/admin/`)
- **Geen internetverbinding nodig**: alles draait lokaal op één server
  (mini-pc of Raspberry Pi) binnen het park-netwerk.

## Vereisten

- Python 3.12 of hoger

## Installatie

```bash
./install.sh
```

Dit maakt een virtualenv aan in `backend/.venv` en installeert de
dependencies. Werkt op elke machine met Python 3.12+, inclusief een
Raspberry Pi.

Voor een permanente installatie op een Linux-server kan
`deploy/toelatingssysteem.service` als systemd-service gebruikt worden:

```bash
sudo cp -r . /opt/toelatingssysteem
cd /opt/toelatingssysteem && ./install.sh
sudo useradd --system --home /opt/toelatingssysteem toelating
sudo chown -R toelating:toelating /opt/toelatingssysteem
sudo cp deploy/toelatingssysteem.service /etc/systemd/system/
sudo systemctl enable --now toelatingssysteem
```

## Opstarten

**Eén commando** (na installatie):

```bash
./start.sh
```

`http://<server-ip>:8000/` opent altijd rechtstreeks het hostscherm. Het
beheerscherm (`.../admin/`) is bereikbaar via de knop **"Profiel"**
rechtsboven op het hostscherm.

### Bureaubladsnelkoppeling (Windows)

Voor gebruik op de tablet/pc zelf (niet als aparte server): dubbelklikken
en meteen in de app zitten, zonder terminal.

1. Eenmalig: rechtsklik `maak-bureaubladsnelkoppeling.ps1` → **"Uitvoeren
   met PowerShell"**. Dit zet een snelkoppeling "Toelatingssysteem" op het
   bureaublad, met het Sparkx-logo als icoon.
2. Vanaf dan: dubbelklik die snelkoppeling om de server te starten (in een
   apart, geminimaliseerd venster) en meteen het hostscherm te openen in de
   browser.

Dit vereist dat `install.sh` al uitgevoerd is — de snelkoppeling gebruikt
dezelfde virtualenv.

### Stoppen

`Ctrl+C` in het terminalvenster van de server (op Linux), of, makkelijker
als dat venster geminimaliseerd is: de knop **"Applicatie afsluiten"** op
het tabblad **"Systeem"** van het beheerscherm (enkel voor rol admin). Dat
sluit de server netjes af — geen `kill -9` of het venster gewoon
wegklikken nodig.

## Eerste admin aanmaken

Medewerkers (met hun pincode) worden normaal aangemaakt via het
beheerscherm — maar dat vereist al een ingelogde admin. Maak daarom de
allereerste admin aan met een apart script:

```bash
cd backend
source .venv/bin/activate
python3 create_admin.py
```

Dit vraagt interactief om een naam en een pincode (die nooit in platte tekst
wordt opgeslagen, enkel gehasht). Log daarna in op `/admin/` met die pincode
om verdere medewerkers aan te maken.

## Simulatiemodus (ontwikkeling en demo)

Zonder een fysieke bandjeslezer kan elk scherm met `?sim=1` achter de URL
geopend worden (bv. `http://localhost:8000/host/?sim=1`). Dat toont een
paneel onderaan met een paar testbandjes om op te klikken, en een veld om
een willekeurig bandje-ID in te typen. Een lezer die zich als toetsenbord
gedraagt (bandje-ID + Enter) werkt op elk scherm sowieso al, ook zonder
`?sim=1` — er hoeft geen tekstveld actief te zijn.

Om meteen wat testbandjes en een demo-admin/-supervisor te hebben:

```bash
cd backend
source .venv/bin/activate
python3 seed.py
```

**Let op:** `seed.py` maakt een admin (pincode `1234`) en supervisor
(pincode `5678`) aan met vaste, publiek bekende pincodes. Enkel gebruiken
voor demo/ontwikkeling, nooit op de echte parkserver.

## Configuratie

Alle instelbare waarden staan in één bestand, `backend/config.yaml`:

| Sleutel | Betekenis | Standaard |
|---|---|---|
| `timezone` | Tijdzone voor de dagwissel | `Europe/Brussels` |
| `port` | Poort van de server | `8000` |
| `scan_timeout_seconds` | Hoelang een scan op een oordeel wacht | `60` |
| `session_inactivity_timeout_seconds` | Auto-uitloggen na inactiviteit (beheer) | `120` |
| `log_retention_days` | Bewaartermijn van logs | `365` |
| `polling_interval_seconds` | Hoe vaak schermen de server pollen | `3` |
| `cushion_sensor_enabled` | Uitbreidingspunt "kussen vrij"-sensor (buiten scope) | `false` |
| `gate_controller` | Implementatie voor het hekje (enkel `dummy` beschikbaar) | `dummy` |
| `database_path` | Locatie van het SQLite-bestand | `../data/toelating.db` |
| `maintenance_interval_hours` | Hoe vaak logs opgeruimd en een back-up gemaakt wordt | `24` |
| `backup_dir` | Map voor automatische back-ups | `../data/backups` |
| `backup_retention_days` | Bewaartermijn van automatische back-ups | `30` |

Herstart de server na een wijziging.

## Tests

```bash
cd backend
source .venv/bin/activate   # indien geïnstalleerd via install.sh
python3 -m pytest
```

Dit draait alle unit- en integratietests: de volledige statuslogica
(overgangen, dagwissel inclusief zomer-/wintertijd), de scan-/oordeelflow
("één scan = één oordeel", time-outs), pincodes en rollen, handmatige
wijzigingen met logging, en een integratietest die een volledige dag met
meerdere bezoekers simuleert.

## Back-up maken van de database

**Dit gebeurt automatisch.** De server maakt zelf een back-up in
`data/backups/` — meteen bij het opstarten, en daarna elke
`maintenance_interval_hours` (standaard elke 24 uur), via SQLite's eigen
back-up-API. Dat is veilig terwijl de server blijft draaien (de database
staat in WAL-modus; een gewone `cp` zou een inconsistente kopie kunnen
geven). Oudere back-ups worden na `backup_retention_days` automatisch
opgeruimd.

Wil je op elk moment ook zelf, meteen een back-up maken (bv. vlak voor een
update)? Gebruik hetzelfde ingebouwde commando van SQLite:

```bash
sqlite3 data/toelating.db ".backup data/backups/backup-$(date +%Y%m%d-%H%M%S).db"
```

## Mappenstructuur

```
backend/
  app/
    domain/       # pure statuslogica (status.py, calendar.py) — geen I/O
    services/      # scan-/oordeelflow, toegang, auth, medewerkers, logs, rapport
    hardware/       # hekje- en kussen-sensor-abstracties (dummy-implementaties)
    api/             # FastAPI-routes
  tests/             # unit- en integratietests
  run.py             # serverlauncher (start.sh/start-app.bat/systemd draaien dit)
  seed.py            # demo-seed (testbandjes + demo-admin/-supervisor)
  create_admin.py    # eerste admin aanmaken
  config.yaml
frontend/
  host/    # hostscherm: testsprong + Ski Jump-toegang in één, standaard startpagina (/, /host/)
  admin/   # beheerscherm, bereikbaar via de "Profiel"-knop op het hostscherm (/admin/)
  shared/  # gedeelde JS/CSS + logo/favicons: lezer-abstractie, API-client, basisstijl
docs/
  handleiding-host.md
  handleiding-beheer.md
data/      # SQLite-bestand + back-ups (niet in git)
start-app.bat                       # server starten + browser openen (Windows)
maak-bureaubladsnelkoppeling.ps1    # bureaubladicoon aanmaken (eenmalig, Windows)
```

## Uitbreidingspunten

- **Andere bandjeslezer** (serieel, netwerk, …): een nieuwe implementatie
  van de `ReaderSource`-interface in `frontend/shared/reader.js`, naast
  `KeyboardWedgeReader` en `SimulatedReader`.
- **Echt hekje**: een nieuwe implementatie van `GateController` in
  `backend/app/hardware/gate_controller.py`, geselecteerd via
  `gate_controller` in `config.yaml`.
- **Aparte toegangscontrole bij de Ski Jump**: momenteel doet het
  hostscherm de volledige toegangscontrole (er is geen fysiek aparte
  ingang). De backend-API `POST /api/gate/scan` bestaat wel nog los
  (getest in `backend/tests/test_gate_access.py`) voor het geval er later
  toch een apart scherm/lezer bij de Ski Jump zelf nodig is.
- **"Kussen vrij"-sensor** (buiten scope, sectie 10 van de opdracht): de
  interface staat klaar in `backend/app/hardware/cushion_sensor.py`
  (`DummyCushionSensor` geeft nu altijd "vrij" terug), met een
  `cushion_sensor_enabled`-vlag in `config.yaml` — nog nergens aan gekoppeld.
