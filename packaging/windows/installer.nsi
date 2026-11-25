; Installer NSIS di adbx-legacy.
;
; Compilato da tools/package.py con le define:
;   APP_VERSION, APP_EXE, SOURCE, OUTFILE, ICON, LICENSE
; Richiede NSIS 3.x (Unicode).

Unicode true
SetCompressor /SOLID lzma

!ifndef APP_VERSION
  !error "APP_VERSION non definita"
!endif
!ifndef SOURCE
  !error "SOURCE non definita"
!endif
!ifndef OUTFILE
  !error "OUTFILE non definita"
!endif
!ifndef ICON
  !error "ICON non definita"
!endif
!ifndef LICENSE
  !error "LICENSE non definita"
!endif

!define APP_NAME "adbx-legacy"
!define APP_PUBLISHER "vigliafg"
!define APP_URL "https://github.com/vigliafg/adbx-legacy"
!define APP_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\adbx-legacy"
!ifndef APP_EXE
  !define APP_EXE "adbx-legacy.exe"
!endif

Name "${APP_NAME} ${APP_VERSION}"
OutFile "${OUTFILE}"
InstallDir "$PROGRAMFILES64\adbx-legacy"
InstallDirRegKey HKLM "Software\adbx-legacy" "InstallDir"
RequestExecutionLevel admin
BrandingText "adbx-legacy ${APP_VERSION} — clone di Alpha Four v3"

!include "MUI2.nsh"
!define MUI_ICON "${ICON}"
!define MUI_UNICON "${ICON}"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Avvia adbx legacy"
!define MUI_WELCOMEPAGE_TITLE "adbx legacy ${APP_VERSION}"
!define MUI_WELCOMEPAGE_TEXT "Clone funzionale di Alpha Four v3 su griglia 80x25.$\r$\n$\r$\nL'installer copia l'applicazione, crea i collegamenti e registra il disinstallatore."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${LICENSE}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Italian"
!insertmacro MUI_LANGUAGE "English"

Section "adbx-legacy" SecMain
  SetOutPath "$INSTDIR"
  File /r "${SOURCE}\*.*"
  WriteUninstaller "$INSTDIR\uninstall.exe"

  CreateDirectory "$SMPROGRAMS\adbx-legacy"
  CreateShortcut "$SMPROGRAMS\adbx-legacy\adbx legacy.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\adbx-legacy\Disinstalla adbx legacy.lnk" "$INSTDIR\uninstall.exe"
  CreateShortcut "$DESKTOP\adbx legacy.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0

  WriteRegStr HKLM "Software\adbx-legacy" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "${APP_KEY}" "DisplayName" "adbx legacy ${APP_VERSION}"
  WriteRegStr HKLM "${APP_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${APP_KEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "${APP_KEY}" "URLInfoAbout" "${APP_URL}"
  WriteRegStr HKLM "${APP_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKLM "${APP_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${APP_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "${APP_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${APP_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\adbx legacy.lnk"
  Delete "$SMPROGRAMS\adbx-legacy\adbx legacy.lnk"
  Delete "$SMPROGRAMS\adbx-legacy\Disinstalla adbx legacy.lnk"
  RMDir "$SMPROGRAMS\adbx-legacy"

  DeleteRegKey HKLM "${APP_KEY}"
  DeleteRegKey HKLM "Software\adbx-legacy"

  RMDir /r "$INSTDIR"
SectionEnd
