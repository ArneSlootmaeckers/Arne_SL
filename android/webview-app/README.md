# Toelatingssysteem Kiosk — Android-app

Een dunne Android-app rond het bestaande, al volledig geteste hostscherm/
beheerscherm (`backend/` + `frontend/`): eigen icoon op het startscherm,
geen adresbalk, volledig scherm. De server blijft draaien op een pc op het
lokale netwerk, precies zoals nu — deze app toont gewoon dezelfde pagina
als een browser zou doen, maar dan als "echte" app.

Wat dit dus **niet** is: geen standalone app die zelf de server draait of
de NFC-chip van de telefoon zelf gebruikt (dat zou de volledige native
herbouw uit `android/domain/` zijn — zie `../README.md`). Deze app is de
snellere, kleinere stap: dezelfde functionaliteit, gewoon met een beter
uiterlijk op een telefoon/tablet.

## Belangrijk: dit is geschreven maar niet gecompileerd

Deze omgeving heeft geen toegang tot het Android SDK (Google's
downloadservers zijn geblokkeerd — zie `../README.md`), dus de code hier is
zorgvuldig met de hand nagekeken tegen de Android-API's, maar **nooit
gebouwd of getest**. De eerste keer dat je dit opent in Android Studio is
dus ook de eerste echte compilatie. Kleine build-foutjes (een verkeerde
versiecombinatie, een ontbrekende dependency) zijn mogelijk — meld ze en ik
los ze op, maar reken er niet op dat het gegarandeerd in één keer lukt zoals
bij de Windows/backend-kant (die wel volledig getest is).

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

## Bekende beperking: NFC-lezer

Als er nu een USB/Bluetooth NFC-lezer aangesloten is die als toetsenbord
werkt (typt het bandje-ID + Enter — zie `frontend/shared/reader.js`), zou
die in theorie ook op een telefoon moeten werken via USB-OTG of
Bluetooth-koppeling, omdat een WebView toetsaanslagen van fysieke
toetsenborden gewoon doorgeeft aan de pagina, net als een browser op een pc.
**Dit is niet met echte hardware getest** — test dit met de effectieve
lezer voor je hierop vertrouwt voor een echte opendeurdag.
