# Handleiding — beheerscherm (bevoegd personeel)

Bereikbaar op `/admin/`. Log in met je persoonlijke pincode. Na **2 minuten
inactiviteit** log je automatisch uit — sla je werk dus niet te lang op.

## Tabblad "Bandje"

Scan een bandje of typ het nummer in en klik op **Bekijk**:

- Je ziet de huidige status en de **geschiedenis van vandaag** (alle scans,
  oordelen en wijzigingen voor dit bandje).
- Onder **"Status handmatig zetten"** kan je de status van het bandje op elk
  van de vier waarden zetten (`NOG_NIET_GESPRONGEN`, `HERKANSING`,
  `GESLAAGD`, `NIET_GESLAAGD`). Vul altijd een **reden** in — dit wordt
  gelogd samen met je naam en de oude/nieuwe status. Gebruik dit enkel om
  een fout van de host te corrigeren, niet als vervanging voor een echte
  beoordeling bij de testsprong.

## Tabblad "Logs"

Filter op datum, bandje-ID, medewerker en/of type gebeurtenis, en klik
**Zoek**. Met **Exporteer CSV** download je precies de gefilterde lijst als
CSV-bestand, bijvoorbeeld voor een incidentonderzoek of rapportage.

## Tabblad "Dagoverzicht"

Kies een datum en klik **Toon** voor het aantal testsprongen, hoeveel
daarvan geslaagd/herkansing/niet geslaagd waren, het aantal oefensprongen,
en de gemiddelde tijd tussen twee sprongen bij de testsprong die dag.

## Tabblad "Medewerkers" (enkel zichtbaar voor rol admin)

- **Nieuwe medewerker**: naam, pincode en rol (`admin` of `supervisor`).
  Een pincode moet uniek zijn onder de actieve medewerkers.
- **Intrekken / Heractiveren**: een ingetrokken medewerker kan niet meer
  inloggen, maar blijft zichtbaar in de logs (voor de geschiedenis).
- **Nieuwe pincode**: vervangt de pincode van een medewerker (bv. na een
  vermoeden van misbruik).

Rol **supervisor** kan bandjes opzoeken en status wijzigen (tabblad
"Bandje"), logs bekijken en het dagoverzicht raadplegen, maar geen
medewerkers beheren.

## Verbindingsproblemen

Een rode balk bovenaan ("Geen verbinding met de server") betekent dat
wijzigingen niet betrouwbaar opgeslagen worden — wacht tot de balk
verdwijnt voor je verdergaat.

## Technisch onderhoud

Voor installatie, opstarten, de eerste admin aanmaken en back-ups: zie
`README.md` in de hoofdmap van het project.
