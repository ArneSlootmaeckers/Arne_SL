# Toelatingssysteem veiligheidssprong

Softwaresysteem voor de veiligheidssprong-attractie: bezoekers scannen hun
bandje bij elke test- of oefensprong, de host bij de testsprong beoordeelt
de sprong met groen/rood, en de Ski Jump controleert de status van het
bandje bij de ingang. Zie de statuslogica in hoofdstuk 2 van de opdracht (of
`backend/app/domain/status.py`) voor de volledige regels.

## Overzicht

- **Backend**: Python (FastAPI) + SQLite, met de volledige statuslogica in
  één pure module (`backend/app/domain/status.py`, zonder I/O — dus
  volledig unit-testbaar).
- **Frontend**: drie eenvoudige HTML/CSS/JS-schermen, meegeserveerd door
  dezelfde backend:
  - `/host/` — hostscherm bij de testsprong
  - `/gate/` — toegangscontrole bij de Ski Jump
  - `/admin/` — beheerscherm voor bevoegd personeel
- **Geen internetverbinding nodig**: alles draait lokaal op één server
  (mini-pc of Raspberry Pi) binnen het park-netwerk.

## Vereisten

- Python 3.12 of hoger (bij installatie zonder Docker)
- **Of** Docker + Docker Compose

## Installatie

### Optie A — Docker Compose (aanbevolen voor de serverinstallatie)

```bash
docker compose up -d --build
```

De server luistert daarna op poort 8000 van de host-machine. Het
SQLite-bestand staat in `./data/toelating.db` (gekoppeld als volume, blijft
dus bewaard bij een herbouw van de container). Pas `backend/config.yaml` aan
en herstart de container (`docker compose restart`) om configuratie te
wijzigen — dat bestand wordt read-only in de container gemount.

### Optie B — installatiescript zonder Docker

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

**Eén commando** (na installatie via optie A of B):

```bash
./start.sh
```

Of via Docker: `docker compose up -d`.

De schermen zijn dan bereikbaar op `http://<server-ip>:8000/host/`,
`.../gate/` en `.../admin/`. `http://<server-ip>:8000/` toont een
startpagina met het Sparkx-logo en een kaart per scherm.

### Bureaubladsnelkoppeling (Windows)

Voor gebruik op de tablet/pc zelf (niet als aparte server): dubbelklikken
en meteen in de app zitten, zonder terminal.

1. Eenmalig: rechtsklik `maak-bureaubladsnelkoppeling.ps1` → **"Uitvoeren
   met PowerShell"**. Dit zet een snelkoppeling "Toelatingssysteem" op het
   bureaublad, met het Sparkx-logo als icoon.
2. Vanaf dan: dubbelklik die snelkoppeling om de server te starten (in een
   apart, geminimaliseerd venster) en meteen de startpagina te openen in de
   browser.

Dit vereist dat `install.sh` al uitgevoerd is (stap "Optie B" hierboven) —
de snelkoppeling gebruikt dezelfde virtualenv.

## Eerste admin aanmaken

Medewerkers (met hun pincode) worden normaal aangemaakt via het
beheerscherm — maar dat vereist al een ingelogde admin. Maak daarom de
allereerste admin aan met een apart script:

```bash
cd backend
source .venv/bin/activate   # niet nodig bij Docker: gebruik dan `docker compose exec toelatingssysteem python3 create_admin.py`
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

De database is één SQLite-bestand (`data/toelating.db`), maar draait in
WAL-modus — een gewone `cp` terwijl de server draait kan een inconsistente
kopie geven. Gebruik daarom het ingebouwde back-upcommando van SQLite, dat
wél veilig is terwijl de server actief blijft draaien:

```bash
sqlite3 data/toelating.db ".backup data/backup-$(date +%Y%m%d-%H%M%S).db"
```

Zet dit desgewenst in een cronjob voor dagelijkse back-ups.

## Mappenstructuur

```
backend/
  app/
    domain/       # pure statuslogica (status.py, calendar.py) — geen I/O
    services/      # scan-/oordeelflow, toegang, auth, medewerkers, logs, rapport
    hardware/       # hekje- en kussen-sensor-abstracties (dummy-implementaties)
    api/             # FastAPI-routes
  tests/             # unit- en integratietests
  seed.py            # demo-seed (testbandjes + demo-admin/-supervisor)
  create_admin.py    # eerste admin aanmaken
  config.yaml
frontend/
  home/    # startpagina met kaarten naar de drie schermen (/)
  host/    # hostscherm (/host/)
  gate/    # toegangscontrole Ski Jump (/gate/)
  admin/   # beheerscherm (/admin/)
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
- **"Kussen vrij"-sensor** (buiten scope, sectie 10 van de opdracht): de
  interface staat klaar in `backend/app/hardware/cushion_sensor.py`
  (`DummyCushionSensor` geeft nu altijd "vrij" terug), met een
  `cushion_sensor_enabled`-vlag in `config.yaml` — nog nergens aan gekoppeld.
