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

**Windows**: dubbelklik **`Toelatingssysteem-Setup.exe`** (zie
[installer/](installer/)) en doorloop de wizard — Volgende, Volgende,
Installeren. Dit is een echte Windows-installer, geen script: hij
controleert Python, zet de virtuele omgeving en dependencies op, en
plaatst de bureaubladsnelkoppeling, allemaal automatisch. Omdat het een
gecompileerd programma is (geen `.ps1`-bestand), heeft hij geen last van
PowerShell's execution policy — een script kan Windows na een download
soms stilzwijgend blokkeren, een installer niet.

Deze `.exe` wordt niet in git bijgehouden (het is een bouwresultaat); zie
[installer/README.md](installer/README.md) om hem zelf te (her)bouwen, of
vraag de laatst gebouwde versie op.

Geen zin in de installer, of liever een script dat je zelf kan aanpassen?
Rechtsklik `setup.ps1` → **"Uitvoeren met PowerShell"** doet exact
hetzelfde (maar loopt, als losstaand script, wél het hierboven genoemde
execution-policy-risico).

**Linux/macOS/Raspberry Pi**:

```bash
./install.sh
```

Dit maakt een virtualenv aan in `backend/.venv` en installeert de
dependencies.

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
en meteen in de app zitten, zonder terminal. `setup.ps1` (zie
"Installatie" hierboven) zet deze automatisch klaar — er is dus niets
apart voor nodig.

Dubbelklik de snelkoppeling "Toelatingssysteem" op het bureaublad om de
server te starten (in een apart, geminimaliseerd venster) en meteen het
hostscherm te openen — in een kiosk-achtig, volledig schermvullend
browservenster zonder adresbalk/tabbladen (via Chrome of Edge's `--app`-
en `--start-fullscreen`-modus, als een van beide geïnstalleerd is; anders
in een gewone browsertab).

### Stoppen

`Ctrl+C` in het terminalvenster van de server (op Linux), of de knop
**"Applicatie afsluiten"** op het tabblad **"Systeem"** van het
beheerscherm (enkel voor rol admin). Dat sluit de server netjes af —
geen `kill -9` of een venster gewoon wegklikken nodig.

Via de bureaubladsnelkoppeling (`start-app.bat`/`start-app.ps1`) sluit het
browservenster daarbij ook automatisch mee: het script onthoudt welk
browserproces het gestart is (in een eigen, geïsoleerd profiel) en sluit
dat proces actief af zodra de server stopt — dit hangt niet af van of de
pagina zelf haar venster mag sluiten (browsers staan dat normaal niet toe
voor een venster dat niet via een script geopend is). Werkt enkel als
Chrome of Edge geïnstalleerd is; is geen van beide gevonden, dan opent de
snelkoppeling een gewone browsertab die na het afsluiten handmatig
gesloten moet worden.

### Startscherm-icoon op Android/tablet

Het hostscherm heeft een `manifest.json` met naam, logo en kleuren. Om er
een icoon van te maken op een Android-toestel:

1. Open `http://<server-ip>:8000/` in Chrome.
2. Tik op het menu (⋮, rechtsboven) → **"Toevoegen aan startscherm"**.

Dit geeft een icoon met het Sparkx-logo op het startscherm. Let op: omdat
dit systeem bewust zonder internetverbinding/HTTPS werkt (gewoon HTTP op
het lokale netwerk), blijft de adresbalk van Chrome zichtbaar bovenaan —
een browservenster zonder adresbalk (zoals de Windows-snelkoppeling) is op
Android enkel mogelijk via HTTPS of een aparte app.

Voor een volwaardige, standalone Android-app (eigen NFC-scanner, geen
aparte pc nodig) is een native herbouw in Kotlin gestart — zie
[`android/README.md`](android/README.md) voor de status daarvan.

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
geopend worden (bv. `http://localhost:8000/host/?sim=1`) — of, sneller,
via de knop **"Open hostscherm in simulatiemodus"** op het tabblad
**"Systeem"** van het beheerscherm. Dat toont een paneel onderaan met een
paar testbandjes om op te klikken, en een veld om een willekeurig
bandje-ID in te typen. Een lezer die zich als toetsenbord gedraagt
(bandje-ID + Enter) werkt op elk scherm sowieso al, ook zonder `?sim=1` —
er hoeft geen tekstveld actief te zijn.

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

## Migreren naar een andere pc

**Windows, met de installer (eenvoudigst):**

1. **Sluit de server af** op de oude pc (knop **"Applicatie afsluiten"**
   op tabblad "Systeem" van het beheerscherm, of Ctrl+C).
2. Zet **`Toelatingssysteem-Setup.exe`** op de nieuwe pc (USB-stick,
   netwerkschijf, OneDrive — wat je toepasselijk vindt) en voer hem uit.
   Dit zet een volledig nieuwe, werkende installatie op (Python-check,
   virtuele omgeving, dependencies, bureaubladsnelkoppeling) in
   `%LOCALAPPDATA%\Toelatingssysteem`.
3. **Bestaande gegevens (bandjes, logs, medewerkers) meenemen?** Kopieer
   de map `data\` van de oude installatie over die van de nieuwe
   (dezelfde locatie, `%LOCALAPPDATA%\Toelatingssysteem\data`) en herstart
   de server. Geen eigen `data\` meegenomen? Maak dan een eerste admin aan
   (zie hierboven) voor je kan inloggen op het beheerscherm.

**Handmatig (Linux/macOS, of Windows zonder de installer):**

1. Sluit de server af op de oude pc (zie hierboven).
2. Kopieer de volledige projectmap naar de nieuwe pc, maar **sla
   `backend/.venv` over**: die virtualenv bevat absolute paden naar de
   Python-installatie van de oude pc en werkt niet op een andere machine
   (staat sowieso niet in git, dus ook niet in een zip via
   `git archive`). Bestaande gegevens behouden? Neem `data/` mee; anders
   sla je die ook over.
3. Op de nieuwe pc: zorg dat Python 3.12+ geïnstalleerd is, en voer de
   installatie opnieuw uit (`./install.sh`, of op Windows `setup.ps1`).
4. Geen eigen `data/` meegenomen? Maak een eerste admin aan.

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
installer/
  Toelatingssysteem-Setup.nsi         # NSIS-bronbestand voor de Windows-installer
  build.sh                            # bouwt Toelatingssysteem-Setup.exe (niet in git)
  README.md                           # hoe (her)bouwen
data/      # SQLite-bestand + back-ups (niet in git)
install.sh                          # installatie (Linux/macOS/WSL)
setup.ps1                           # installatie + bureaubladsnelkoppeling (Windows, alternatief script)
start.sh                            # server starten (Linux/macOS/WSL)
start-app.bat                       # startpunt van de snelkoppeling, roept start-app.ps1 aan
start-app.ps1                       # server + browser starten, browser mee afsluiten (Windows)
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
