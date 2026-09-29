# Handleiding — beheerscherm (bevoegd personeel)

Het beheerscherm draait op de **pc**. Dubbelklik op de snelkoppeling
"Toelatingssysteem" op het bureaublad: het systeem start en het
beheerscherm opent meteen. De telefoons van de hosts tonen het hostscherm
(zie `handleiding-host.md`).

Je kan het beheerscherm ook op een telefoon openen, via de knop
**"Profiel"** rechtsboven op het hostscherm.

Log in met je persoonlijke pincode. Na **2 minuten inactiviteit** log je
automatisch uit. Rechtsboven zie je je naam; met het **uitlog-icoontje**
ernaast log je af, en **← Host** opent het hostscherm.

## Tabblad "Bandje"

Scan een bandje of typ het nummer in en klik op **Bekijk**. Op een
telefoon kan je het bandje ook tegen de achterkant van de telefoon houden:
het nummer wordt dan vanzelf ingevuld.

- Je ziet de huidige status en de **geschiedenis van vandaag** (alle scans,
  oordelen en wijzigingen voor dit bandje).
- Onder **"Status handmatig zetten"** kies je een van de vier statussen:
  **Nog niet gesprongen**, **Herkansing**, **Geslaagd** of **Niet
  geslaagd**, en klik je op **Toepassen**. Vul altijd een **reden** in —
  dit wordt gelogd samen met je naam en de oude/nieuwe status. Gebruik dit
  enkel om een fout van de host te corrigeren, niet als vervanging voor een
  echte beoordeling bij de testsprong.

## Tabblad "Logs"

Filter op datum, bandje-ID, medewerker en/of type gebeurtenis, en klik
**Zoek**. De kolom **Bron** toont welke telefoon iets deed: de naam die op
die telefoon ingesteld is (bv. "Host 1"), of anders een code zoals
"toestel-a8f3k2". Met **Exporteer CSV** download je precies de gefilterde lijst als
CSV-bestand, bijvoorbeeld voor een incidentonderzoek of rapportage.

## Tabblad "Dagoverzicht"

Kies een datum en klik **Toon** voor het aantal testsprongen, hoeveel
daarvan geslaagd/herkansing/niet geslaagd waren, het aantal oefensprongen,
en de gemiddelde tijd tussen twee sprongen bij de testsprong die dag.

## Tabblad "Medewerkers" (enkel zichtbaar voor rol admin)

- **Nieuwe medewerker**: naam, pincode en rol
  (**Admin** of **Supervisor**). Een pincode moet uniek zijn onder de
  actieve medewerkers.
- **Intrekken / Heractiveren**: een ingetrokken medewerker kan niet meer
  inloggen, maar blijft zichtbaar in de logs (voor de geschiedenis).
- **Nieuwe pincode**: vervangt de pincode van een medewerker (bv. na een
  vermoeden van misbruik).

## Tabblad "Systeem" (enkel zichtbaar voor rol admin)

**Verbinden met de telefoon-app** toont het adres van de pc (bv.
`10.18.0.155:8000`). Normaal vindt de telefoon-app de pc vanzelf; lukt dat
niet, vul dan dit adres in bij de instellingen van de app (op de telefoon
10 seconden ergens op het scherm drukken). Wissel je van netwerk, klik dan
op **Vernieuwen**.

**Simulatiemodus** opent het hostscherm met een paneel van testbandjes,
om te oefenen of te demonstreren zonder een echt bandje.

**Applicatie afsluiten** sluit het systeem netjes af: het host- en
beheerscherm werken vanaf dan niet meer, ook niet op de telefoons. Vraagt
eerst een bevestiging. Opnieuw opstarten kan **enkel via de pc zelf**
(snelkoppeling op het bureaublad) — niet vanaf een telefoon. Gebruik dit
dus bij het einde van de dag of voor onderhoud, niet zomaar tussendoor.

Rol **supervisor** kan bandjes opzoeken en status wijzigen (tabblad
"Bandje"), logs bekijken en het dagoverzicht raadplegen, maar geen
medewerkers beheren, het systeem-tabblad gebruiken of de applicatie
afsluiten.

## Verbindingsproblemen

- Een **rode balk bovenaan** ("Geen verbinding met de server") betekent
  dat wijzigingen niet opgeslagen worden — wacht tot de balk verdwijnt
  voor je verdergaat.
- Krijgen de **telefoons** geen verbinding: controleer of de pc aan staat
  en het systeem draait, en of de telefoons op **hetzelfde netwerk** zitten
  als de pc. Een gastennetwerk (bv. "SPARKX Guest") werkt niet: daar
  kunnen toestellen elkaar niet bereiken. Gebruik dan een eigen
  routertje, waar de pc met een netwerkkabel op aangesloten is en de
  telefoons op het wifi.

## Telefoons klaarzetten

Per telefoon, één keer:
1. Installeer de app en open ze. Ze zoekt de pc zelf en opent het
   hostscherm.
2. Geef de telefoon een naam: 10 seconden drukken → vul **"Naam van dit
   toestel"** in (bv. "Host 1") → **Opslaan**. Zo zie je in de logs welke
   telefoon wat gedaan heeft. Geef elke telefoon een andere naam.
3. Zet in de Android-instellingen een **pincode** op de telefoon, en zet
   **"Pincode vragen voor losmaken"** aan (Instellingen → Beveiliging →
   App vastzetten; de naam verschilt per merk).
4. In de app: 10 seconden drukken → **App vastzetten** → **Ik snap het**.
   De hosts kunnen de app nu niet meer verlaten.

## Technisch onderhoud

Voor installatie, opstarten, de eerste admin aanmaken en back-ups: zie
`README.md` in de hoofdmap van het project. Voor de telefoon-app: zie
`android/webview-app/README.md`.
