; Windows-installer voor het Toelatingssysteem: één dubbelklik-programma
; i.p.v. een los .ps1-script -- vermijdt zo PowerShell's execution policy
; (die blokkeerde eerder setup.ps1 stilzwijgend, zonder duidelijke fout,
; wanneer bestanden na een download als "afkomstig van het internet"
; gemarkeerd stonden). Een gecompileerde installer is geen "script" in die
; zin en heeft daar geen last van.
;
; Bouwen: ./build.sh (zie build.sh) vanuit deze map. Dat zet een schone
; checkout van het project in build/payload/ en de meegeleverde Python in
; build/python/, en roept daarna makensis aan.
;
; Python zit in de installer zelf (naar $INSTDIR\python): op de doel-pc
; hoeft vooraf niets geïnstalleerd te zijn, en een andere Python op die pc
; (of het ontbreken van "Add python.exe to PATH") speelt geen rol.

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"

Name "Toelatingssysteem veiligheidssprong"
OutFile "Toelatingssysteem-Setup.exe"
InstallDir "$LOCALAPPDATA\Toelatingssysteem"
RequestExecutionLevel user
ShowInstDetails show
ShowUninstDetails show

Var AdminPage
Var AdminPincodeField
Var AdminPincodeConfirmField
Var AdminPincode
Var AdminPincodeConfirm

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
Page custom AdminPageCreate AdminPageLeave
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\start-app.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Toelatingssysteem nu starten"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Dutch"

Function AdminPageCreate
  !insertmacro MUI_HEADER_TEXT "Pincode van de beheerder" "Hiermee log je meteen in op het beheerscherm. Laat leeg om dit later zelf te doen."
  nsDialogs::Create 1018
  Pop $AdminPage
  ${If} $AdminPage == error
    Abort
  ${EndIf}

  ; Geen naam: het systeem bewaart geen personeelsgegevens, enkel een
  ; pincode per groep (beheerder, vaste medewerkers, studenten).
  ${NSD_CreateLabel} 0 0 100% 12u "Pincode van de beheerder (min. 6 tekens):"
  Pop $0
  ${NSD_CreatePassword} 0 13u 100% 13u ""
  Pop $AdminPincodeField

  ${NSD_CreateLabel} 0 32u 100% 12u "Herhaal pincode:"
  Pop $0
  ${NSD_CreatePassword} 0 45u 100% 13u ""
  Pop $AdminPincodeConfirmField

  ${NSD_CreateLabel} 0 68u 100% 36u "De pincodes voor vaste medewerkers en studenten stel je daarna in op het beheerscherm, tabblad Pincodes. Laat beide velden leeg om dit later handmatig te doen (zie README.md, 'Pincode van de beheerder instellen')."
  Pop $0

  nsDialogs::Show
FunctionEnd

Function AdminPageLeave
  ${NSD_GetText} $AdminPincodeField $AdminPincode
  ${NSD_GetText} $AdminPincodeConfirmField $AdminPincodeConfirm

  ${If} $AdminPincode == ""
  ${AndIf} $AdminPincodeConfirm == ""
    Return
  ${EndIf}

  ${If} $AdminPincode != $AdminPincodeConfirm
    MessageBox MB_OK|MB_ICONEXCLAMATION "De pincodes komen niet overeen."
    Abort
  ${EndIf}

  StrLen $1 $AdminPincode
  ${If} $1 < 6
    MessageBox MB_OK|MB_ICONEXCLAMATION "De pincode moet minstens 6 tekens lang zijn."
    Abort
  ${EndIf}
FunctionEnd

Section "Installeren"
  DetailPrint "Bestanden uitpakken..."
  SetOutPath "$INSTDIR"
  File /r "build\payload\*.*"

  DetailPrint "Python uitpakken..."
  SetOutPath "$INSTDIR\python"
  File /r "build\python\*.*"

  ; --clear: een bestaande .venv (bv. van een vroegere installatie met een
  ; andere Python) volledig opnieuw opbouwen op de meegeleverde Python.
  DetailPrint "Virtuele omgeving aanmaken (kan even duren)..."
  SetOutPath "$INSTDIR\backend"
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" -m venv --clear .venv'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_OK|MB_ICONSTOP "Aanmaken van de virtuele omgeving is mislukt.$\r$\n$\r$\nStaat het Toelatingssysteem nog open? Sluit het af (Beheer -> Systeem -> Applicatie afsluiten) en voer deze installer opnieuw uit."
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

  ; Poort 8000 enkel open voor het eigen netwerk en dicht voor internet (zie
  ; firewall.ps1). Het script vraagt zelf de beheerdersrechten die daarvoor
  ; nodig zijn; de rest van deze installer heeft die niet nodig.
  DetailPrint "Windows-firewall instellen (Windows vraagt om bevestiging)..."
  nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$INSTDIR\firewall.ps1"'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_OK|MB_ICONEXCLAMATION "De Windows-firewall kon niet ingesteld worden (geen beheerdersrechten gekregen?).$\r$\n$\r$\nDe server weigert internetadressen ook zelf, maar laat voor de zekerheid IT het bestand firewall.ps1 in $INSTDIR uitvoeren (rechtsklik -> Uitvoeren met PowerShell)."
  ${EndIf}

  ${If} $AdminPincode != ""
    DetailPrint "Pincode van de beheerder instellen..."
    nsExec::ExecToLog '"$INSTDIR\backend\.venv\Scripts\python.exe" create_admin.py --pincode "$AdminPincode"'
    Pop $0
    ${If} $0 != "0"
      MessageBox MB_OK|MB_ICONEXCLAMATION "Instellen van de pincode van de beheerder is mislukt (bv. een pincode die al door een andere groep gebruikt wordt). Je kan dit achteraf handmatig doen -- zie README.md, 'Pincode van de beheerder instellen'."
    ${EndIf}
  ${EndIf}

  DetailPrint "Bureaubladsnelkoppeling aanmaken..."
  CreateShortcut "$DESKTOP\Toelatingssysteem.lnk" "$INSTDIR\start-app.bat" "" "$INSTDIR\frontend\shared\icons\favicon.ico"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  DetailPrint "Installatie voltooid."
SectionEnd

Section "Uninstall"
  nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$INSTDIR\firewall.ps1" -Remove'
  Delete "$DESKTOP\Toelatingssysteem.lnk"
  RMDir /r "$INSTDIR"
SectionEnd
