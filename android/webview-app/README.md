# Toelatingssysteem Kiosk — Android-app

Een dunne Android-app rond het bestaande, al volledig geteste hostscherm/
beheerscherm (`backend/` + `frontend/`): eigen icoon op het startscherm,
geen adresbalk, en scant bandjes met de NFC-chip van de telefoon zelf. De
server blijft draaien op een pc op het lokale netwerk, precies zoals nu —
deze app toont dezelfde pagina als een browser zou doen en geeft er enkel
een NFC-scan aan door, verder verandert er niets.

Wat dit dus **niet** is: geen standalone app die zelf de server draait
(dat zou de volledige native herbouw uit `android/domain/` zijn — zie
`../README.md`, gepauzeerd op fase 1/5). Deze app is de snellere, kleinere
stap: dezelfde functionaliteit en dezelfde server, gewoon met een beter
uiterlijk en een ingebouwde scanner op een telefoon/tablet.

## Status: gebouwd en werkend bevestigd

Deze omgeving heeft geen toegang tot het Android SDK (Google's
downloadservers zijn geblokkeerd — zie `../README.md`), dus de code kon hier
enkel met de hand nagekeken worden, niet gecompileerd. Ze is intussen wel
echt gebouwd in Android Studio en op een fysiek toestel uitgeprobeerd:
verbinding met de server, hostscherm en de NFC-scan met een echt bandje
werken. Bij een nieuwe checkout/wijziging kan een eerste Gradle-sync nog
steeds een versie-update voorstellen (AGP/Kotlin) — gewoon accepteren, dat
is normaal.

De verbindingscontrole hierboven (elke 5s /api/health checken) is nieuw en
nog niet apart op een fysiek toestel uitgeprobeerd — test dit door de
server even te stoppen terwijl de app openstaat, voor je hierop vertrouwt.

## Bouwen en installeren

Nodig: [Android Studio](https://developer.android.com/studio) (gratis), op
eender welke pc (Windows/Mac/Linux) — niet dezelfde pc als die de
toelatingssysteem-server draait.

1. Open Android Studio → **"Open"** → kies de map `android/webview-app`.
2. Laat Android Studio de eerste keer zijn ding doen (Gradle-sync,
   eventueel een melding om de Android Gradle Plugin/Gradle-versie te
   updaten — accepteer dat gerust, dat is normaal).
3. Sluit je Android-toestel aan via USB met **USB-debugging** aan (Instellingen
   → Over telefoon → 7x op buildnummer tikken → Ontwikkelaarsopties →
   USB-debugging), of gebruik een emulator.
4. Klik op de groene **Run ▶**-knop.

Voor een installeerbaar bestand om door te sturen (zonder Android Studio
erbij): **Build → Build App Bundle(s) / APK(s) → Build APK(s)**, dan vind
je de `.apk` in `app/build/outputs/apk/debug/`. Die kan je gewoon naar een
telefoon sturen en daar openen om te installeren (Android vraagt dan om
"installatie uit onbekende bron" toe te staan — normaal voor een
niet-Play-Store-app).

## Eerste gebruik

Bij de eerste opstart **zoekt de app de server zelf** op het wifinetwerk
("Server zoeken…", enkele seconden) en opent daarna het hostscherm. Vindt
ze niets, dan vraagt ze om:
1. **Serveradres**: het IP-adres + poort van de pc die de server draait,
   bv. `192.168.1.50:8000` — staat op de pc in het beheerscherm, tabblad
   **Systeem**, onder "Verbinden met de telefoon-app".
2. **Hostscherm of Beheerscherm**: welke van de twee pagina's deze app
   toont.

Het instellingenvenster heeft ook een knop **Automatisch zoeken**.

### Hoe het automatisch zoeken werkt

De app kent haar eigen adres op het wifi (bv. `192.168.8.23`) en vraagt elk
ander adres in dat netwerk op poort 8000 naar `/api/health`. Enkel een
antwoord met `"app": "toelatingssysteem"` telt (zie
`backend/app/api/routes_health.py`), zodat een ander toestel dat toevallig
op poort 8000 draait nooit per ongeluk gekozen wordt. Er is dus **geen extra
poort of firewallregel** op de pc nodig. Zie `ServerDiscovery.kt`.

Beperkingen:
- Werkt enkel waar toestellen elkaar op het netwerk kunnen bereiken — op
  een gastennetwerk met client-isolatie (zoals "SPARKX Guest") lukt dit
  niet, maar daar werkt de app sowieso niet.
- Op een heel groot netwerk (groter dan ~1000 adressen, bv. een
  bedrijfsnetwerk) zoekt de app enkel de ~250 adressen rond haar eigen
  adres af: een volledige scan zou te lang duren en kan door IT als
  verdacht gezien worden. Op een reisroutertje of thuisnetwerk speelt dit
  niet.
- Vereist een server met de herkenningswaarde in `/api/health`: installeer
  dus ook de nieuwste versie van de pc-installer.

Dit onthoudt de app nadien. Om het later te wijzigen: **houd je vinger 10
seconden ononderbroken ergens op het scherm** (bewust lang, zodat dit niet
per ongeluk gebeurt tijdens normaal gebruik — geen apart knopje meer, dat nam
ruimte in
beeld in). De app opent zonder gedwongen volledig scherm; de status-/
navigatiebalk van het toestel blijft gewoon zichtbaar.

De WebView laadt elke pagina altijd vers op (geen cache) — een aanpassing
aan `frontend/` op de server verschijnt dus meteen bij de volgende keer
openen, zonder dat je de app zelf opnieuw moet installeren of de cache
handmatig moet wissen.

## Bij verbindingsverlies

De pagina zelf toont al een rode balk als de server onbereikbaar is (zelfde
gedrag als in een browser), maar dat is enkel een bannertje op een verder
onveranderd scherm — op een telefoon valt dat makkelijk niet op, en het
scherm kan zo "bevroren" aanvoelen. Deze app controleert daarom zelf, apart
van de pagina, **elke 2 seconden** of de server bereikbaar is, en toont al
bij de **eerste mislukking** een duidelijk "Geen verbinding"-venster met
**Instellingen** (serveradres wijzigen) en **Opnieuw proberen** — bewust
zonder wachttijd of aantal pogingen, want een onbereikbare server mag bij
dit systeem nooit onopgemerkt blijven.

Dat venster (en het serverinstellingen-venster erachter) is in de eigen
Sparkx-huisstijl opgebouwd (donker petrolblauw paneel, geel-oranje
verloopknop — dezelfde kleuren als de webpagina zelf), niet het standaard
grijze Android-dialoogvenster. De achterliggende WebView zelf toont bij een
mislukte paginalading ook geen Android/Chromium-standaardfoutpagina (wit,
met groen robotje) meer, maar een lege pagina in dezelfde donkere kleur —
die was anders rond de randen van het venster zichtbaar gebleven.

Die controle blijft ook doorlopen terwijl dat venster open staat. Komt de
server terug (bv. na een korte wifi-onderbreking die zichzelf herstelt, of
gewoon een vals alarm van een heel kort haperingetje), dan sluit het venster
**automatisch** zodra de eerstvolgende controle weer slaagt — personeel
hoeft dus niet zelf te tikken, en de lopende pagina (met alles wat erop
stond) blijft gewoon intact. Enkel als de allereerste paginalading zelf
nooit gelukt is (bv. de app werd net gestart tijdens een storing) laadt dit
herstel de pagina alsnog opnieuw, want dan stond er nog niets bruikbaars op
het scherm.

Terwijl het venster open staat, **zoekt de app de server ook opnieuw op het
netwerk** (meteen, en daarna om de 15 seconden; onderaan in het venster in
het geel te zien). Kreeg de pc intussen een ander IP-adres (bv. na een
herstart van de pc of de router), dan wordt het nieuwe adres vanzelf
gevonden, opgeslagen en geladen — niemand hoeft iets over te typen.

## NFC scannen met de telefoon

Bandje tegen de achterkant van de telefoon houden is genoeg: de app leest
de hardware-UID van het tagje (via Android's `NfcAdapter`, zie
`MainActivity.kt`) en geeft die door aan de pagina, op dezelfde manier als
een USB-lezer dat vandaag doet. Werkt op **beide** schermen: op het
hostscherm start het een scan (zelfde flow als vandaag); op het
beheerscherm (tab "Bandje") vult het automatisch het bandje-ID-veld in en
toont meteen de status. Bandjes registreren zichzelf automatisch bij de
eerste scan (zie `backend/app/services/common.py`), dus er is geen vooraf
ingestelde lijst van geldige bandjes nodig — eender welk NFC-tagje werkt.

Aandachtspunten:
- **NFC moet aanstaan** in de Android-instellingen van het toestel. Staat
  het uit, dan toont de app een korte melding. Heeft het toestel helemaal
  geen NFC-chip, dan werkt deze functie niet, maar blijft de rest van de
  app (en het beheerscherm) gewoon bruikbaar.
- Zolang het bandje tegen het toestel blijft liggen, negeert de app
  herhaalde detecties van hetzelfde tagje twee seconden lang, om geen
  dubbele scans te sturen.
- **Bevestigd werkend met een echt toestel en een echt NFC-bandje**
  tijdens de eerste installatie.

## Nog steeds ondersteund: externe NFC-lezer

Een los USB/Bluetooth NFC-lezer die als toetsenbord werkt (typt het
bandje-ID + Enter — zie `frontend/shared/reader.js`: `KeyboardWedgeReader`)
blijft ook werken, aangesloten op de telefoon via USB-OTG of
Bluetooth-koppeling: een WebView geeft toetsaanslagen van fysieke
toetsenborden gewoon door aan de pagina, net als een browser op een pc.
Ook dit pad is niet met echte hardware getest.
