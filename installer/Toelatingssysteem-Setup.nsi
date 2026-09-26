; Windows-installer voor het Toelatingssysteem: één dubbelklik-programma
; i.p.v. een los .ps1-script -- vermijdt zo PowerShell's execution policy
; (die blokkeerde eerder setup.ps1 stilzwijgend, zonder duidelijke fout,
; wanneer bestanden na een download als "afkomstig van het internet"
; gemarkeerd stonden). Een gecompileerde installer is geen "script" in die
; zin en heeft daar geen last van.
;
; Bouwen: ./build.sh (zie build.sh) vanuit deze map, of handmatig:
;   1. Kopieer een schone checkout van het project naar build/payload/
;      (zonder .git, backend/.venv, data/*).
;   2. makensis Toelatingssysteem-Setup.nsi
;
; Vereist Python 3.12+ op de doel-pc zelf (wordt gecontroleerd tijdens
; installatie) -- Python zelf wordt niet meegeleverd.

!include "MUI2.nsh"
!include "LogicLib.nsh"

Name "Toelatingssysteem veiligheidssprong"
OutFile "Toelatingssysteem-Setup.exe"
InstallDir "$LOCALAPPDATA\Toelatingssysteem"
RequestExecutionLevel user
ShowInstDetails show
ShowUninstDetails show

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\start-app.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Toelatingssysteem nu starten"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Dutch"

Section "Installeren"
  DetailPrint "Bestanden uitpakken..."
  SetOutPath "$INSTDIR"
  File /r "build\payload\*.*"

  DetailPrint "Python controleren..."
  nsExec::ExecToLog 'cmd /c python --version'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_OK|MB_ICONSTOP "Geen 'python' gevonden op het PATH.$\r$\n$\r$\nInstalleer Python 3.12 of hoger van python.org (vink 'Add python.exe to PATH' aan tijdens de installatie) en voer deze installer daarna opnieuw uit."
    Abort
  ${EndIf}

  nsExec::ExecToLog 'cmd /c python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_OK|MB_ICONSTOP "Je Python-versie is te oud -- er is minstens Python 3.12 nodig.$\r$\n$\r$\nInstalleer een nieuwere versie van python.org en voer deze installer daarna opnieuw uit."
    Abort
  ${EndIf}

  DetailPrint "Virtuele omgeving aanmaken (kan even duren)..."
  SetOutPath "$INSTDIR\backend"
  nsExec::ExecToLog 'cmd /c python -m venv .venv'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_OK|MB_ICONSTOP "Aanmaken van de virtuele omgeving is mislukt."
    Abort
  ${EndIf}

  DetailPrint "Dependencies installeren (kan even duren)..."
  nsExec::ExecToLog '"$INSTDIR\backend\.venv\Scripts\python.exe" -m pip install --upgrade pip'
  nsExec::ExecToLog '"$INSTDIR\backend\.venv\Scripts\python.exe" -m pip install -r requirements.txt'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_OK|MB_ICONSTOP "Installeren van de dependencies is mislukt. Controleer je internetverbinding en voer deze installer opnieuw uit."
    Abort
  ${EndIf}

  CreateDirectory "$INSTDIR\data"

  DetailPrint "Bureaubladsnelkoppeling aanmaken..."
  CreateShortcut "$DESKTOP\Toelatingssysteem.lnk" "$INSTDIR\start-app.bat" "" "$INSTDIR\frontend\shared\icons\favicon.ico"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  DetailPrint "Installatie voltooid."
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\Toelatingssysteem.lnk"
  RMDir /r "$INSTDIR"
SectionEnd
