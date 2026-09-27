# Toelatingssysteem op Android — twee sporen

Er zijn hier twee verschillende Android-projecten, met een heel ander doel
en een heel andere status. Ze delen enkel de map `android/` — het zijn
losse Gradle-projecten die je apart opent.

## `webview-app/` — de app om nu te bouwen en te tonen

Een dunne, snel te bouwen Android-app die het bestaande, volledig geteste
hostscherm/beheerscherm toont als "echte" app (eigen icoon, geen adresbalk,
volledig scherm) en bandjes scant met de NFC-chip van de telefoon zelf. De
server blijft draaien op een pc op het netwerk, net als nu — dit verandert
niets aan hoe het systeem werkt, enkel hoe het eruitziet en hoe een scan
binnenkomt. Zie **[`webview-app/README.md`](webview-app/README.md)** voor
hoe je dit opent en bouwt in Android Studio.

Dit is de praktische keuze om **vandaag** een Android-versie naast de
Windows-versie te kunnen tonen.

## `domain/` — eerste stap van een volledige native herbouw (gepauzeerd)

Een zuivere Kotlin-poort van de kernlogica (`backend/app/domain/status.py`
en `calendar.py`), bedoeld als eerste fase van een veel groter project: een
volledig standalone Android-app, zonder pc, die de NFC-chip van de telefoon
zelf gebruikt om bandjes te scannen. Reden waarom dit een volledige
herschrijving in Kotlin vergt in plaats van de bestaande Python-backend
hergebruiken: Pydantic v2 (dat FastAPI vereist) steunt op een Rust-kern
(`pydantic-core`) die geen Android-builds publiceert.

**Status: fase 1 van 5, gepauzeerd.** Enkel de statuslogica is er, met een
volledige testsuite (19 tests, gebaseerd op `backend/tests/test_status_domain.py`
en `backend/tests/test_day_rollover.py`), **echt uitgevoerd en groen** in
deze omgeving. Nog te bouwen (geen van deze bestaat nog): een Room-database,
het hostscherm in Jetpack Compose, echte NFC-integratie, het beheerscherm,
en verpakking als APK — samen weken werk, en zonder Android SDK in deze
omgeving kan ik dat werk hier schrijven maar niet compileren of testen (zie
hieronder). `webview-app/` hierboven levert op korte termijn een bruikbare
Android-versie op; dit spoor ligt klaar om verder te zetten als dat ooit
alsnog gewenst is.

### Waarom een aparte Gradle-module

`domain/` is een eigen, op zichzelf staand Gradle-project (eigen
`settings.gradle.kts`), los van `webview-app/` en van een eventuele
toekomstige native `app`-module. Reden: zodra een module de
`com.android.application`-plugin gebruikt, heeft Gradle het Android SDK
nodig om zelfs maar de build te *configureren* — lukt dat niet, dan faalt
in veel gevallen de hele build, inclusief losstaande modules die er niets
mee te maken hebben. Door de statuslogica in een eigen project te zetten,
blijft die altijd bouwbaar en testbaar, ook zonder Android SDK.

### Wat hier wel/niet getest is

Deze sandbox-omgeving heeft Java 21, Gradle 8.14.3 en Kotlin 2.0.21
voorgeïnstalleerd, en kan Maven Central bereiken — genoeg om `domain/` op
zichzelf te compileren en de tests uit te voeren:

```bash
cd android/domain
gradle test
```

Waar deze omgeving **niet** bij kan: Google's Android SDK-downloadservers
zijn geblokkeerd voor deze sandbox (bevestigd door zowel `dl.google.com`
als de `google()` Gradle-repository te testen — beide onbereikbaar). Zonder
SDK is er geen `android.jar` (het Android-platform), en dus geen manier om
hier Android-specifieke code (UI, database, NFC) te compileren of te
testen, en zelfs geen manier om hier een Gradle-wrapper te genereren voor
een project dat de Android-plugin gebruikt (`webview-app/`'s wrapper is
daarom apart, vanuit een leeg project, gegenereerd). Dat werk kan alleen
via **Android Studio op een gewone pc**, met een normale internetverbinding.

### `jvmToolchain`

`domain/build.gradle.kts` zet `jvmToolchain(21)`, omdat dat de enige JDK is
die in deze sandbox beschikbaar is. Als Android Studio of je gekozen
Android Gradle Plugin-versie liever een oudere bytecode-target heeft
(17 is een veelgebruikte, veilige keuze), is dat een eenregelige wijziging.
