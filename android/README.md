# Toelatingssysteem — native Android-app (in ontwikkeling)

Dit is een volledige herbouw van het toelatingssysteem als standalone
Android-app: geen aparte pc/server nodig, en scannen via de NFC-chip van
de telefoon zelf in plaats van een los NFC-leesapparaat. Reden hiervoor:
de bestaande Python/FastAPI-backend (`backend/`) kan niet in een
Android-app draaien — Pydantic v2 (dat FastAPI vereist) steunt op een
Rust-kern (`pydantic-core`) die geen Android-builds publiceert. Vandaar
een echte herschrijving in Kotlin, in plaats van een truc om Python mee
te smokkelen.

## Status: fase 1 van 5, enkel de statuslogica

Er is nog geen bruikbare app. Wat er nu is:

- **`domain/`** — een zuivere Kotlin-module zonder Android-afhankelijkheden,
  met de kernregels van het systeem: de status-overgangstabel
  (NOG_NIET_GESPRONGEN → HERKANSING/GESLAAGD → NIET_GESLAAGD) en de
  dagwisseling rond middernacht in de Brusselse tijdzone (incl. de
  overgang naar/van zomertijd). Dit is een regel-voor-regel vertaling van
  `backend/app/domain/status.py` en `backend/app/domain/calendar.py`.
- Volledige testsuite (19 tests, gebaseerd op `backend/tests/test_status_domain.py`
  en `backend/tests/test_day_rollover.py`), **echt uitgevoerd en groen** in
  deze omgeving met Gradle/JUnit — zie "Wat hier wel/niet getest is" hieronder.

Nog te bouwen (geen van deze bestaat nog):

1. Room-database (het equivalent van `backend/app/models.py` +
   `backend/app/db.py`): polsbandjes, medewerkers, logs, lokaal op het
   toestel opgeslagen.
2. Hostscherm-UI in Jetpack Compose (het equivalent van `frontend/host/`).
3. Echte NFC-integratie via Android's `NfcAdapter`/`Ndef`-API's.
4. Beheerscherm-UI (het equivalent van `frontend/admin/`): pincodes,
   medewerkersbeheer, dagoverzicht, CSV-export.
5. Verpakking als installeerbare APK en documentatie.

## Waarom een aparte Gradle-module (`domain/`)

`domain/` is een eigen, op zichzelf staand Gradle-project (eigen
`settings.gradle.kts`), los van een toekomstige Android `app`-module.
Reden: zodra een module de `com.android.application`-plugin gebruikt,
heeft Gradle het Android SDK nodig om zelfs maar de build te
*configureren* — lukt dat niet, dan faalt in veel gevallen de hele build,
inclusief losstaande modules die er niets mee te maken hebben. Door de
statuslogica in een eigen project te zetten, blijft die altijd bouwbaar en
testbaar, ook zonder Android SDK. De toekomstige `app`-module koppelt hier
later aan via Gradle's `includeBuild` (composite builds).

## Wat hier wel/niet getest is

Deze sandbox-omgeving heeft Java 21, Gradle 8.14.3 en Kotlin 2.0.21
voorgeïnstalleerd, en kan Maven Central bereiken — genoeg om `domain/` op
zichzelf te compileren en de tests uit te voeren:

```bash
cd android/domain
gradle test    # of ./gradlew test zodra er een wrapper is toegevoegd
```

Waar deze omgeving **niet** bij kan: Google's Android SDK-downloadservers
(`dl.google.com`) zijn geblokkeerd voor deze sandbox. Zonder SDK is er geen
`android.jar` (het Android-platform), en dus geen manier om hier een
Android `app`-module, Compose-UI, Room-database of NFC-code te compileren
of te testen — dat werk kan alleen via **Android Studio op een gewone pc**,
met een normale internetverbinding. Concreet betekent dit dat fase 2 t/m 5
hierboven door Claude geschreven kunnen worden, maar niet hier
gecompileerd/getest — dat gebeurt in Android Studio, met jouw hulp om de
resultaten te controleren (bv. de app op een telefoon of emulator
uitproberen).

## `jvmToolchain`

`domain/build.gradle.kts` zet `jvmToolchain(21)`, omdat dat de enige JDK is
die in deze sandbox beschikbaar is. Als Android Studio of je gekozen
Android Gradle Plugin-versie liever een oudere bytecode-target heeft
(17 is een veelgebruikte, veilige keuze), is dat een eenregelige wijziging.
