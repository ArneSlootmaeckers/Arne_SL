# Windows-installer bouwen

`Toelatingssysteem-Setup.exe` is een echte, dubbelklikbare Windows-installer
(gemaakt met [NSIS](https://nsis.sourceforge.io/)) die:

1. de projectbestanden uitpakt naar `%LOCALAPPDATA%\Toelatingssysteem`
   (geen adminrechten nodig),
2. controleert of Python 3.12+ aanwezig is,
3. een virtuele omgeving aanmaakt en de dependencies installeert,
4. en een bureaubladsnelkoppeling plaatst.

Omdat het een gecompileerd programma is — geen `.ps1`-script — heeft hij
geen last van PowerShell's execution policy. Dat blokkeerde eerder wel
eens stilzwijgend het losse `setup.ps1`-script, omdat Windows bestanden na
een download (zip uitgepakt, browser-download, ...) als "afkomstig van het
internet" markeert.

De `.exe` zelf staat niet in git (het is een bouwresultaat, net als
`backend/.venv`) — enkel het NSIS-script (`Toelatingssysteem-Setup.nsi`)
en dit bouwscript.

## Bouwen

Vereist `makensis` (het NSIS-compilatieprogramma):

```bash
sudo apt install nsis   # Debian/Ubuntu/Raspberry Pi OS
# of: brew install nsis  (macOS)
# of: installeer NSIS zelf van nsis.sourceforge.io (Windows)
```

Dan, vanuit deze map:

```bash
./build.sh
```

Dit zet een schone kopie van het project (via `git archive`, dus zonder
`.venv`, `data/*.db` of andere niet-ingecheckte bestanden) in `build/` en
compileert `Toelatingssysteem-Setup.exe` ernaast. `build.sh` werkt op
Linux, macOS én Windows (met `makensis` op het PATH) — de uitkomst is
altijd een Windows-`.exe`, ongeacht op welk platform je bouwt.

Herbouw de installer na elke wijziging aan het project die je wil
meenemen — hij bevat een momentopname, geen live-koppeling naar de
broncode.

## Getest

Het volledige installatie- en verwijderproces is end-to-end getest onder
Wine (een Windows-compatibiliteitslaag op Linux) met een echte Windows-
Python-runtime: bestanden uitpakken, virtuele omgeving aanmaken, alle
dependencies installeren, bureaubladsnelkoppeling aanmaken, en de
uninstaller die alles weer opruimt — allemaal bevestigd werkend. Niet
getest op een fysieke Windows-machine.
