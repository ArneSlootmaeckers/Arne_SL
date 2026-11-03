# Handleiding — beheerscherm (bevoegd personeel)

Het beheerscherm draait op de **pc**. Dubbelklik op de snelkoppeling
"Toelatingssysteem" op het bureaublad: het systeem start en het
beheerscherm opent meteen. De telefoons van de hosts tonen het hostscherm
(zie `handleiding-host.md`).

Je kan het beheerscherm ook op een telefoon openen, via de knop
**"Profiel"** rechtsboven op het hostscherm.

Log in met de pincode van je groep. Er zijn drie groepen, elk met één
pincode, en het systeem bewaart geen namen:

| Groep | Ziet en mag |
|---|---|
| **Beheerder** | Alle tabbladen: ook Pincodes en Systeem |
| **Vaste medewerkers** | Bandje (opzoeken én corrigeren), Logs, Dagoverzicht |
| **Studenten** | Enkel Bandje: opzoeken, niet aanpassen |

Na **5 foute pincodes** na elkaar is dat toestel **5 minuten geblokkeerd**
(zo valt een pincode niet te raden); wacht dan en probeer opnieuw. Na
**2 minuten inactiviteit** log je automatisch uit. Rechtsboven zie je je
groep; met het **uitlog-icoontje** ernaast log je af, en **← Host** opent
het hostscherm.

## Tabblad "Bandje"

Scan een bandje of typ het nummer in en klik op **Bekijk**. Op een
telefoon kan je het bandje ook tegen de achterkant van de telefoon houden:
het nummer wordt dan vanzelf ingevuld.

- Je ziet de huidige status en de **geschiedenis van vandaag** (alle scans,
  oordelen en wijzigingen voor dit bandje).
- Onder **"Status handmatig zetten"** kies je een van de vier statussen:
  **Nog niet gesprongen**, **Herkansing**, **Geslaagd** of **Niet
  geslaagd**, en klik je op **Toepassen**. Vul altijd een **reden** in —
  dit wordt gelogd samen met je groep en de oude/nieuwe status. Studenten
  zien dit deel niet: zij kunnen een bandje enkel opzoeken. Gebruik dit
  enkel om een fout van de host te corrigeren, niet als vervanging voor een
  echte beoordeling bij de testsprong.

## Tabblad "Logs"

Filter op datum, bandje-ID, groep en/of type gebeurtenis, en klik
**Zoek**. De kolom **Groep** toont welke groep iets deed. De kolom **Bron** toont welke telefoon iets deed: de naam die op
die telefoon ingesteld is (bv. "Host 1"), of anders een code zoals
"toestel-a8f3k2". Met **Exporteer CSV** download je precies de gefilterde lijst als
CSV-bestand, bijvoorbeeld voor een incidentonderzoek of rapportage.

## Tabblad "Dagoverzicht"

Kies een datum en klik **Toon** voor het aantal testsprongen, hoeveel
daarvan geslaagd/herkansing/niet geslaagd waren, het aantal oefensprongen,
en de gemiddelde tijd tussen twee sprongen bij de testsprong die dag.

## Tabblad "Pincodes" (enkel voor de beheerder)

Bovenaan zie je de drie groepen, wat ze mogen en of hun pincode ingesteld
is.
- **Pincode instellen of wijzigen**: kies de groep, typ de nieuwe pincode
  twee keer en klik **Opslaan**. Minstens 6 tekens, en elke groep een
  andere. De vorige pincode van die groep werkt meteen niet meer: geef de
  nieuwe door aan iedereen van die groep. **Wijzig de pincode van een groep
  als er iemand van die groep vertrekt.**
- **Uitzetten**: niemand van die groep kan nog inloggen (bv. buiten het
  seizoen voor studenten), tot je een nieuwe pincode instelt. De beheerder
  zelf kan niet uitgezet worden.
- Een oudere pincode van minder dan 6 tekens blijft werken, maar wie
  daarmee inlogt, ziet een oranje balk: stel dan een nieuwe in.

## Tabblad "Systeem" (enkel voor de beheerder)

**Verbinden met de telefoon-app** toont het adres van de pc (bv.
`10.18.0.155:8000`). Normaal vindt de telefoon-app de pc vanzelf; lukt dat
niet, vul dan dit adres in bij de instellingen van de app (op de telefoon
10 seconden ergens op het scherm drukken). Wissel je van netwerk, klik dan
op **Vernieuwen**. Daaronder staat de **certificaatcode** (bv. `A6A9 E891
DBC2 04C5`): de app toont dezelfde code bij haar instellingen. Zo kan je
nakijken dat een telefoon echt met deze pc praat.

**Gekoppelde toestellen**: enkel telefoons die je hier gekoppeld hebt,
mogen bandjes scannen en een oordeel geven.
- **Nieuwe koppelcode** toont een code van 6 cijfers, 10 minuten geldig,
  voor één telefoon. Typ die in op de telefoon, in het scherm "Toestel
  koppelen". Klik daarna op **Vernieuwen** om de telefoon in de lijst te
  zien.
- De lijst toont elke gekoppelde telefoon, wanneer hij gekoppeld werd en
  wanneer hij laatst iets deed.
- **Ontkoppelen**: de telefoon kan meteen niets meer (bv. bij verlies of
  diefstal). Opnieuw gebruiken kan pas met een nieuwe koppelcode.

**Simulatiemodus** opent het hostscherm met een paneel van testbandjes,
om te oefenen of te demonstreren zonder een echt bandje. Ook dat scherm
moet de eerste keer gekoppeld worden met een koppelcode.

**Applicatie afsluiten** sluit het systeem netjes af: het host- en
beheerscherm werken vanaf dan niet meer, ook niet op de telefoons. Vraagt
eerst een bevestiging. Opnieuw opstarten kan **enkel via de pc zelf**
(snelkoppeling op het bureaublad) — niet vanaf een telefoon. Gebruik dit
dus bij het einde van de dag of voor onderhoud, niet zomaar tussendoor.

Vaste medewerkers en studenten zien de tabbladen Pincodes en Systeem niet,
en kunnen de applicatie dus ook niet afsluiten.

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
2. **Koppel de telefoon**: maak hier op het tabblad **Systeem** een
   **Nieuwe koppelcode** aan en typ die in op de telefoon (scherm
   "Toestel koppelen").
3. Geef de telefoon een naam: 10 seconden drukken → onder **Dit toestel**
   de naam invullen (bv. "Host 1") → **Opslaan**. Zo zie je in de logs
   welke telefoon wat gedaan heeft. Geef elke telefoon een andere naam.
4. Zet in de Android-instellingen een **pincode** op de telefoon, en zet
   **"Pincode vragen voor losmaken"** aan (Instellingen → Beveiliging →
   App vastzetten; de naam verschilt per merk).
5. In de app: 10 seconden drukken → zet **App vastzetten** aan →
   **Opslaan** → **Ik snap het**.
   De hosts kunnen de app nu niet meer verlaten.

## Telefoon toont "Server niet vertrouwd"

De app vertrouwt enkel het vaste certificaat van deze pc. Toont een
telefoon "Server niet vertrouwd", dan is dat veranderd — normaal enkel
nadat het systeem op de pc volledig opnieuw geïnstalleerd werd zonder de
map `data` te bewaren. Oplossen, per telefoon:
1. Open de instellingen van de app (10 seconden drukken, of de knop
   **Instellingen** in het venster).
2. Vergelijk de **nieuwe code** daar met de certificaatcode op het tabblad
   **Systeem** hier.
3. **Enkel als ze gelijk zijn**: tik op **Nieuw certificaat vertrouwen** en
   daarna **Opslaan**. Zijn ze verschillend, doe dan niets en verwittig
   IT: dan doet mogelijk een ander toestel zich voor als de pc.

## Technisch onderhoud

Voor installatie, opstarten, de pincode van de beheerder en back-ups: zie
`README.md` in de hoofdmap van het project. Voor de telefoon-app: zie
`android/webview-app/README.md`.
