# Handleiding — hostscherm (testsprong & Ski Jump)

Het hostscherm draait op de **telefoon**, in de app "Toelatingssysteem".
Dit ene scherm doet twee dingen: de testsprong beoordelen, én meteen ook
tonen of de bezoeker naar de Ski Jump mag.

Bezoekers scannen hun bandje **enkel aan de kiosk** van de experience. Met
de telefoon zelf wordt niets gescand: een bandje tegen de telefoon houden
doet niets.

De pc waar het systeem op draait, toont het beheerscherm (zie
`handleiding-beheer.md`). De pc moet aan staan en het systeem moet draaien,
anders werkt de telefoon niet.

## Opstarten

Open de app op de telefoon. De telefoon moet op **hetzelfde wifinetwerk**
zitten als de pc.

- **De eerste keer** zoekt de app de pc zelf op het netwerk ("Server
  zoeken…", enkele seconden) en opent daarna het hostscherm. Je hoeft
  niets in te typen.
- Vindt de app de pc niet, dan opent het venster **Instellingen**.
  Tik op **Automatisch zoeken**, of vul het adres in dat op de pc staat
  (beheerscherm → tabblad **Systeem** → "Verbinden met de telefoon-app",
  bv. `10.18.0.155:8000`) en tik op **Opslaan**.
- De app onthoudt dit. De volgende keren opent ze meteen het hostscherm.

## Toestel koppelen (eenmalig)

Een nieuwe telefoon mag nog niet scannen: het hostscherm toont dan
**"Toestel koppelen"**. Zo kan geen enkel ander toestel op het netwerk
bandjes goedkeuren.

1. Vraag een beheerder om een **koppelcode**. Die maakt ze aan op de pc:
   beheerscherm → tabblad **Systeem** → **Nieuwe koppelcode** (6 cijfers,
   10 minuten geldig, voor één telefoon).
2. Typ de code in bij **Koppelcode**.
3. Controleer de **naam** van de telefoon (bv. "Host 1") en tik op
   **Koppelen**.

Dit hoeft maar één keer. Verschijnt "Toestel koppelen" later opnieuw, dan
werd de telefoon ontkoppeld op het beheerscherm (bv. omdat hij verloren
was): vraag dan een nieuwe code.

Vijf keer een foute code na elkaar? Dan blokkeert het systeem de telefoon
5 minuten. Wacht en probeer daarna opnieuw met een juiste code.

## Spelers van de kiosk

Het scherm toont **"Wacht op de volgende speler"**. Zodra een speler aan
de kiosk start, verschijnt hij vanzelf: voornaam, de eerste letter van de
achternaam en de foto. Geef dan het oordeel zoals hieronder bij "Werking".

Staat er **"Geen kiosk ingesteld"**, dan komen er geen spelers binnen:
vraag een beheerder om de kiosk in te stellen (beheerscherm, tabblad
**Systeem**).

- **Meerdere spelers tegelijk?** Dan verschijnt **"Wie springt er?"** met
  een knop per speler. Tik op wie nu springt. Na het oordeel kies je de
  volgende.
- **Meerdere telefoons?** Een speler verschijnt op elke telefoon. Zodra
  hij op één telefoon een oordeel kreeg, kan dat op de andere niet meer.
- Namen worden nergens bewaard; ze staan enkel op het scherm zolang de
  speler aan de beurt is.

## Werking

1. Het scherm toont **"Wacht op de volgende speler"**.
2. De bezoeker scant zijn bandje aan de kiosk. Je ziet meteen de speler en
   zijn status van vandaag, met een duidelijke kleur:

   | Kleur | Betekenis |
   |---|---|
   | 🟢 Groen — "1e poging" | Bezoeker mag de testsprong doen, eerste kans vandaag |
   | 🟠 Oranje — "2e poging – laatste kans" | Herkansing na een afgekeurde 1e sprong |
   | 🟢 Groen — "Geslaagd – oefensprong" | Al geslaagd vandaag, dit is een oefensprong |
   | 🔴 Rood — "Vandaag niet meer toegestaan" | Twee keer afgekeurd, mag niet meer springen |

3. **Bij oranje of het eerste groen** (1e/2e poging): beoordeel de sprong en
   druk op de grote knop **GESLAAGD** (goed) of **GEFAALD** (fout). Hier
   is **geen tijdslimiet**: het scherm blijft staan tot je een oordeel
   geeft, hoe lang de sprong ook duurt.
   - Wordt de sprong goedgekeurd? Dan toont het scherm meteen "Geslaagd —
     oefensprong" met een leeglopende balk, en sluit zichzelf na
     5 seconden automatisch af.
   - Bij "2e poging – laatste kans" die ook wordt afgekeurd, toont het
     scherm "Vandaag niet meer toegestaan" met dezelfde balk, en sluit
     zichzelf na 5 seconden automatisch af.
4. **Bij "Geslaagd – oefensprong"**: er is geen oordeel nodig — de bezoeker
   mag door naar de Ski Jump. Je hoeft niets in te drukken: het scherm
   toont een leeglopende balk en sluit zichzelf na 5 seconden automatisch
   af en is dan klaar voor de volgende speler. Ging de oefensprong toch niet
   door? Druk dan op **"Geen sprong / annuleer"**.
5. **Bij "Vandaag niet meer toegestaan"**: laat deze bezoeker niet meer
   springen. Het scherm sluit zichzelf na 5 seconden automatisch af, of
   druk op **"Geen sprong / annuleer"** om meteen terug te gaan.

**Sprong toch niet doorgegaan?** (bezoeker bedenkt zich, wordt weggeroepen, …)
Druk dan, tijdens het beoordelen, op de kleine link **"Geen sprong /
annuleer"** onder de knoppen. Dit wist de openstaande sprong meteen,
zonder dat de status verandert. De speler kan later opnieuw starten aan de
kiosk.

**2e poging?** Na een afgekeurde 1e sprong scant de speler opnieuw aan de
kiosk; hij verschijnt dan opnieuw, in het oranje.

## Belangrijk

- **Een nieuwe speler van de kiosk verschijnt altijd**, ook als de vorige
  nog op een oordeel wacht. Het scherm toont dan meteen de nieuwe speler.
  De vorige kreeg dan geen oordeel en behoudt gewoon zijn status (net
  alsof je "Geen sprong / annuleer" had gedrukt) — hij mag dus later
  opnieuw. Geef het oordeel dus vóór de volgende speler aan de kiosk start.
- Komt tijdens een oefensprong (de balk van 5 seconden) al de volgende
  speler binnen, dan telt die oefensprong gewoon mee.
- **Je kan hier niets terugdraaien.** Als je per ongeluk de verkeerde knop
  indrukt, kan dat enkel gecorrigeerd worden door een vaste medewerker via
  de knop **"Profiel"** rechtsboven — die opent het beheerscherm, waar je
  met de pincode van je groep inlogt. Studenten kunnen daar een bandje
  enkel opzoeken, niet aanpassen.

## Geen verbinding

Verliest de telefoon de verbinding met de pc (wifi weg, pc uit, …), dan
verschijnt meteen het venster **"Geen verbinding"**. **Laat dan niemand
springen of naar de Ski Jump gaan** — de status kan niet opgeslagen worden.

Je hoeft meestal niets te doen:
- Komt de verbinding terug, dan verdwijnt het venster vanzelf ("Verbinding
  hersteld").
- Kreeg de pc intussen een ander adres, dan zoekt de app hem zelf opnieuw
  op het netwerk (onderaan in het geel: "Server wordt automatisch
  gezocht…") en laadt alles vanzelf ("Server gevonden op …").

Blijft het venster staan: controleer of de pc aan staat en het systeem
draait, en of de telefoon op het juiste wifi zit. Met **Opnieuw proberen**
probeer je meteen opnieuw; met **Instellingen** kan je het adres zelf
aanpassen (zie "Opstarten" hierboven).

## Server niet vertrouwd

Toont de app **"Server niet vertrouwd"**, dan antwoordt er wel iets op het
adres van de pc, maar niet met de vaste herkenningscode van het systeem.
**Laat dan niemand springen** en verwittig een beheerder. Dit gebeurt
normaal enkel nadat het systeem op de pc volledig opnieuw geïnstalleerd
werd; de beheerder kan het dan oplossen (zie "Instellingen openen").

## Instellingen openen

Er is bewust geen instellingenknop op het scherm. Houd je vinger **10
seconden ononderbroken** ergens op het scherm, tot het venster
**Instellingen** opent. Het heeft twee delen:
- **Server:** het adres van de pc wijzigen, of **Automatisch zoeken**.
  Hier staat ook de **certificaatcode** (bv. `A6A9 E891 DBC2 04C5`): die
  moet gelijk zijn aan de code op de pc (beheerscherm → **Systeem**). Na
  "Server niet vertrouwd" staat hier de nieuwe code met de knop **Nieuw
  certificaat vertrouwen**: enkel gebruiken als de code gelijk is aan die
  op de pc.
- **Dit toestel:**
  - de **naam** van deze telefoon (bv. "Host 1") — die zie je later in de
    logs op het beheerscherm, zodat je weet welke telefoon wat gedaan heeft;
  - of de app het **Hostscherm** of het **Beheerscherm** toont;
  - **App vastzetten** aan of uit (zie hieronder).

Wijzigingen gelden pas na **Opslaan**.

## App vastzetten (enkel voor de beheerder)

Zodat niemand de app per ongeluk verlaat: instellingen (10 seconden
drukken) → zet **App vastzetten** aan → **Opslaan** → in het venster van
Android **Ik snap het**. De thuisknop en de knop voor recente apps werken
dan niet meer, en de app zet zichzelf ook na een herstart opnieuw vast.
Losmaken: instellingen → zet **App vastzetten** uit → **Opslaan**.

Zet op de telefoon ook **"Pincode vragen voor losmaken"** aan
(Instellingen → Beveiliging → App vastzetten; de naam verschilt per merk).
Probeert iemand dan de app los te maken met het gebaar dat Android toont,
dan gaat de telefoon op slot en is de pincode van de telefoon nodig.

## Testen zonder kiosk (demo)

Op het beheerscherm, tabblad **Systeem**, stuurt **Testspeler sturen** een
verzonnen speler naar elk gekoppeld hostscherm — handig om het scherm uit
te proberen zonder de kiosk.
