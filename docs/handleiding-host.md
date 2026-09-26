# Handleiding — hostscherm (testsprong & Ski Jump)

Dit ene scherm doet twee dingen: de testsprong beoordelen, én meteen ook
tonen of de bezoeker naar de Ski Jump mag. Je hoeft dus nergens anders
opnieuw te scannen. Dit is meteen ook de pagina die opent zodra het
systeem opstart (`http://<server>:8000/`).

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
   druk op de grote knop **GROEN** (goed) of **ROOD** (fout).
   - Wordt de sprong goedgekeurd? Dan verschijnt meteen een extra balk
     **"Ski Jump — Doorgaan"** (groen): de bezoeker mag door naar de Ski
     Jump zelf.
   - Bij "2e poging – laatste kans" die ook wordt afgekeurd, verschijnt
     **"Ski Jump — Vandaag niet meer toegestaan"** (rood): deze bezoeker
     mag vandaag niet meer naar de Ski Jump.
4. **Bij "Geslaagd – oefensprong"**: er is geen oordeel nodig — je ziet
   meteen **"Ski Jump — Doorgaan"**. Druk op **"Oefensprong klaar"** zodra
   de bezoeker de oefensprong gedaan heeft, of laat het scherm vanzelf
   terug naar wachten gaan.
5. **Bij "Vandaag niet meer toegestaan"**: je ziet meteen
   **"Ski Jump — Vandaag niet meer toegestaan"**. Laat deze bezoeker niet
   springen en niet door naar de Ski Jump. Er is niets te doen op dit
   scherm — het keert vanzelf terug naar wachten.

**Sprong toch niet doorgegaan?** (bezoeker bedenkt zich, wordt weggeroepen, …)
Druk dan op de kleine link **"Geen sprong / annuleer"** onder de knoppen. Dit
wist de openstaande scan meteen, zonder dat de status verandert — je hoeft
niet de volle time-out af te wachten en het bandje kan meteen opnieuw
gescand worden.

## Belangrijk

- **Eén scan = één oordeel.** Zolang je nog geen groen/rood hebt gegeven
  (of de oefensprong nog niet bevestigd/geannuleerd is), weigert het scherm
  een nieuwe scan — je ziet dan kort een melding bovenaan. Rond eerst de
  vorige scan af (oordeel geven, of "Geen sprong / annuleer").
- Als je te lang wacht, vervalt de scan vanzelf (voortgangsbalk onder de
  status) zonder dat de status verandert. Scan dan gewoon opnieuw.
- **Je kan hier niets terugdraaien.** Als je per ongeluk de verkeerde knop
  indrukt, kan dat enkel gecorrigeerd worden door bevoegd personeel via de
  knop **"Profiel"** rechtsboven — die opent het beheerscherm, waar je met
  een pincode inlogt om de status van een bandje aan te passen.
- Verschijnt er een **rode balk bovenaan** ("Geen verbinding met de
  server")? Laat dan niemand springen of naar de Ski Jump gaan tot de balk
  verdwijnt — de status kan dan niet betrouwbaar opgeslagen worden.

## Testen zonder bandje (demo)

Voeg `?sim=1` toe aan de link in de adresbalk om een paneel met testbandjes
te krijgen, handig om het scherm uit te proberen zonder een echte lezer.
