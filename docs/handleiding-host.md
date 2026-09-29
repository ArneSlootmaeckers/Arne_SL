# Handleiding — hostscherm (testsprong & Ski Jump)

Het hostscherm draait op de **telefoon**, in de app "Toelatingssysteem".
Dit ene scherm doet twee dingen: de testsprong beoordelen, én meteen ook
tonen of de bezoeker naar de Ski Jump mag. Je hoeft dus nergens anders
opnieuw te scannen.

De pc waar het systeem op draait, toont het beheerscherm (zie
`handleiding-beheer.md`). De pc moet aan staan en het systeem moet draaien,
anders werkt de telefoon niet.

## Opstarten

Open de app op de telefoon. De telefoon moet op **hetzelfde wifinetwerk**
zitten als de pc.

- **De eerste keer** zoekt de app de pc zelf op het netwerk ("Server
  zoeken…", enkele seconden) en opent daarna het hostscherm. Je hoeft
  niets in te typen.
- Vindt de app de pc niet, dan opent het venster **Serverinstellingen**.
  Tik op **Automatisch zoeken**, of vul het adres in dat op de pc staat
  (beheerscherm → tabblad **Systeem** → "Verbinden met de telefoon-app",
  bv. `10.18.0.155:8000`) en tik op **Opslaan**.
- De app onthoudt dit. De volgende keren opent ze meteen het hostscherm.

## Een bandje scannen

Houd het bandje tegen de **achterkant van de telefoon**, tot het scherm
reageert. De NFC-functie van de telefoon moet aan staan; staat ze uit, dan
toont de app een melding.

## Werking

1. Het scherm toont **"Scan het bandje"** en wacht.
2. De bezoeker scant het bandje. Je ziet meteen het bandjenummer en de
   status van vandaag, met een duidelijke kleur:

   | Kleur | Betekenis |
   |---|---|
   | 🟢 Groen — "1e poging" | Bezoeker mag de testsprong doen, eerste kans vandaag |
   | 🟠 Oranje — "2e poging – laatste kans" | Herkansing na een afgekeurde 1e sprong |
   | 🟢 Groen — "Geslaagd – oefensprong" | Al geslaagd vandaag, dit is een oefensprong |
   | 🔴 Rood — "Vandaag niet meer toegestaan" | Twee keer afgekeurd, mag niet meer springen |

3. **Bij oranje of het eerste groen** (1e/2e poging): beoordeel de sprong en
   druk op de grote knop **GESLAAGD** (goed) of **GEFAALD** (fout). Hier
   staat geen tijdslimiet op het scherm — de testsprong duurt vaak langer
   dan 30 seconden.
   - Wordt de sprong goedgekeurd? Dan toont het scherm meteen "Geslaagd —
     oefensprong" met een leeglopende balk, en sluit zichzelf na
     5 seconden automatisch af.
   - Bij "2e poging – laatste kans" die ook wordt afgekeurd, toont het
     scherm "Vandaag niet meer toegestaan" met dezelfde balk, en sluit
     zichzelf na 5 seconden automatisch af.
4. **Bij "Geslaagd – oefensprong"**: er is geen oordeel nodig — de bezoeker
   mag door naar de Ski Jump. Je hoeft niets in te drukken: het scherm
   toont een leeglopende balk en sluit zichzelf na 5 seconden automatisch
   af en is dan klaar voor de volgende scan. Ging de oefensprong toch niet
   door? Druk dan op **"Geen sprong / annuleer"**.
5. **Bij "Vandaag niet meer toegestaan"**: laat deze bezoeker niet meer
   springen. Het scherm sluit zichzelf na 5 seconden automatisch af, of
   druk op **"Geen sprong / annuleer"** om meteen terug te gaan.

**Sprong toch niet doorgegaan?** (bezoeker bedenkt zich, wordt weggeroepen, …)
Druk dan, tijdens het beoordelen, op de kleine link **"Geen sprong /
annuleer"** onder de knoppen. Dit wist de openstaande scan meteen, zonder
dat de status verandert — je hoeft niet te wachten en het bandje kan meteen
opnieuw gescand worden.

## Belangrijk

- **Eén scan = één oordeel.** Zolang je nog geen GESLAAGD/GEFAALD hebt
  gegeven, weigert het scherm een nieuwe scan — je ziet dan kort een
  melding bovenaan. Rond eerst de vorige scan af (oordeel geven, of "Geen
  sprong / annuleer").
- Geeft de host heel lang geen oordeel, dan vervalt de scan op de
  achtergrond vanzelf zonder dat de status verandert. Scan dan gewoon
  opnieuw.
- **Je kan hier niets terugdraaien.** Als je per ongeluk de verkeerde knop
  indrukt, kan dat enkel gecorrigeerd worden door bevoegd personeel via de
  knop **"Profiel"** rechtsboven — die opent het beheerscherm, waar je met
  een pincode inlogt om de status van een bandje aan te passen.

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

## Instellingen openen

Er is bewust geen instellingenknop op het scherm. Houd je vinger **10
seconden ononderbroken** ergens op het scherm, tot het venster
**Serverinstellingen** opent. Daar kan je:
- het adres van de pc wijzigen of automatisch laten zoeken;
- kiezen of de app het **Hostscherm** of het **Beheerscherm** toont;
- de app **vastzetten** of **losmaken** (zie hieronder).

## App vastzetten (enkel voor de beheerder)

Zodat niemand de app per ongeluk verlaat: instellingen (10 seconden
drukken) → **App vastzetten** → in het venster van Android **Ik snap het**.
De thuisknop en de knop voor recente apps werken dan niet meer, en de app
zet zichzelf ook na een herstart opnieuw vast. Losmaken: instellingen →
**App losmaken**.

Zet op de telefoon ook **"Pincode vragen voor losmaken"** aan
(Instellingen → Beveiliging → App vastzetten; de naam verschilt per merk).
Probeert iemand dan de app los te maken met het gebaar dat Android toont,
dan gaat de telefoon op slot en is de pincode van de telefoon nodig.

## Testen zonder bandje (demo)

Op het beheerscherm, tabblad **Systeem**, opent **Simulatiemodus** het
hostscherm met een paneel met testbandjes — handig om het scherm uit te
proberen zonder een echt bandje.
