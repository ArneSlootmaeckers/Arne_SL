# Toelatingssysteem Kiosk — Android-app

Een dunne Android-app rond het bestaande, al volledig geteste hostscherm/
beheerscherm (`backend/` + `frontend/`): eigen icoon op het startscherm,
geen adresbalk, volledig scherm, en scant bandjes met de NFC-chip van de
telefoon zelf. De server blijft draaien op een pc op het lokale netwerk,
precies zoals nu — deze app toont dezelfde pagina als een browser zou doen
en geeft er enkel een NFC-scan aan door, verder verandert er niets.

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

Bij de eerste opstart vraagt de app om:
1. **Serveradres**: het IP-adres + poort van de pc die de server draait,
   bv. `192.168.1.50:8000` (te vinden via `ipconfig` op die pc, zie de
   hoofd-`README.md`).
2. **Hostscherm of Beheerscherm**: welke van de twee pagina's deze app
   toont.

Dit onthoudt de app nadien. Om het later te wijzigen: tik op het kleine
tandwiel-icoontje rechtsonder in beeld.

De WebView laadt elke pagina altijd vers op (geen cache) — een aanpassing
aan `frontend/` op de server verschijnt dus meteen bij de volgende keer
openen, zonder dat je de app zelf opnieuw moet installeren of de cache
handmatig moet wissen.

## NFC scannen met de telefoon

Bandje tegen de achterkant van de telefoon houden is genoeg: de app leest
de hardware-UID van het tagje (via Android's `NfcAdapter`, zie
`MainActivity.kt`) en geeft die door aan de pagina, op dezelfde manier als
een USB-lezer dat vandaag doet. Bandjes registreren zichzelf automatisch
bij de eerste scan (zie `backend/app/services/common.py`), dus er is geen
vooraf ingestelde lijst van geldige bandjes nodig — eender welk NFC-tagje
werkt.

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
