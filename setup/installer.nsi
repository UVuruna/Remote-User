Unicode true

; =================================================================
; Remote User Installer -- NSIS Script
;
; A standard Windows installer that also drives the dependencies
; (hard owner requirement -- the user NEVER side-installs anything):
;   - ffmpeg ships INSIDE the app payload (copied by build.py)
;   - Tailscale is CHAIN-INSTALLED here when not already present
;   - a firewall allow-rule is added for the server (no first-run
;     "blocked by firewall" mystery)
;   - Start Menu + optional Desktop shortcut + optional autostart
; =================================================================

!include "MUI2.nsh"
!include "FileFunc.nsh"

; -- App Info -----------------------------------------------------
!define APP_NAME "RemoteUser"
!define APP_DISPLAY "Remote User"
!define APP_EXE "RemoteUser.exe"
!define APP_DESCRIPTION "Control this PC from your phone — screen, mouse, keyboard"

!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
!define TAILSCALE_EXE "$PROGRAMFILES64\Tailscale\tailscale-ipn.exe"

; -- Paths and company info (passed from build.py via /D flags) ---
; DIST_DIR / SETUP_DIR / VENDOR_DIR / APP_VERSION / APP_PUBLISHER / APP_URL

; -- General Settings ---------------------------------------------
Name "${APP_DISPLAY}"
OutFile "${DIST_DIR}\${APP_NAME}_Setup.exe"
InstallDir "$PROGRAMFILES64\${APP_DISPLAY}"
InstallDirRegKey HKLM "${UNINST_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

; -- Version Info -------------------------------------------------
VIProductVersion "${APP_VERSION}.0"
VIFileVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "${APP_DISPLAY}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey "FileDescription" "${APP_DISPLAY} Installer"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "LegalCopyright" "Copyright (C) ${APP_PUBLISHER}"

; -- Icons --------------------------------------------------------
!define MUI_ICON "${SETUP_DIR}\icon-setup.ico"
!define MUI_UNICON "${SETUP_DIR}\icon-setup.ico"

; -- Interface ----------------------------------------------------
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Welcome to ${APP_DISPLAY} Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard installs ${APP_DISPLAY} on this PC.$\r$\n$\r$\n${APP_DESCRIPTION}.$\r$\n$\r$\nIt also sets up everything the app needs — including Tailscale for access from anywhere. You never install anything by hand.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${APP_DISPLAY} (shows the pairing QR)"

; -- Pages --------------------------------------------------------
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; =================================================================
; INITIALIZATION -- force the 64-bit registry view (64-bit-only app;
; without this a 32-bit NSIS stub writes under WOW6432Node and
; Add/Remove Programs never sees the uninstall entry)
; =================================================================

Function .onInit
    SetRegView 64
FunctionEnd

Function un.onInit
    SetRegView 64
FunctionEnd

; =================================================================
; INSTALLER SECTIONS
; =================================================================

Section "!${APP_DISPLAY} (required)" SecMain
    SectionIn RO

    ; Close a running instance so locked files can be replaced on upgrade
    nsExec::ExecToLog 'taskkill /im "${APP_EXE}" /f'
    Sleep 500

    ; Remove any previous autostart unconditionally -- SecAutostart recreates
    ; it only when selected, so unchecking it on upgrade actually disables it
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APP_NAME}"

    SetOutPath "$INSTDIR"
    File /r "${DIST_DIR}\${APP_NAME}\*.*"

    ; Firewall allow-rule for the server (LAN + Tailscale WebSocket traffic).
    ; Without it Windows silently blocks the phone's connection until the
    ; user notices the firewall prompt -- the classic support case.
    nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="${APP_DISPLAY}"'
    nsExec::ExecToLog 'netsh advfirewall firewall add rule name="${APP_DISPLAY}" dir=in action=allow program="$INSTDIR\${APP_EXE}" enable=yes'

    ; Start Menu shortcuts
    CreateDirectory "$SMPROGRAMS\${APP_DISPLAY}"
    CreateShortcut "$SMPROGRAMS\${APP_DISPLAY}\${APP_DISPLAY}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\icon.ico"
    CreateShortcut "$SMPROGRAMS\${APP_DISPLAY}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Add/Remove Programs
    WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${APP_DISPLAY} - ${APP_DESCRIPTION}"
    WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\icon.ico"
    WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
    WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKLM "${UNINST_KEY}" "URLInfoAbout" "${APP_URL}"
    WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"
    WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1

    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "${UNINST_KEY}" "EstimatedSize" $0
SectionEnd

Section "Tailscale — access from anywhere" SecTailscale
    ; Chain-install (hard owner requirement: the app drives ALL dependencies).
    ; Skipped when Tailscale is already on the machine. The Tailscale setup
    ; runs its own visible wizard; the one-time login is guided afterwards by
    ; the ${APP_DISPLAY} window (Set up Tailscale button).
    IfFileExists "${TAILSCALE_EXE}" TailscaleDone
    DetailPrint "Installing Tailscale (one-time)…"
    File "/oname=$TEMP\tailscale-setup.exe" "${VENDOR_DIR}\tailscale-setup.exe"
    ExecWait '"$TEMP\tailscale-setup.exe"'
    Delete "$TEMP\tailscale-setup.exe"
TailscaleDone:
SectionEnd

Section "Desktop Shortcut" SecDesktop
    CreateShortcut "$DESKTOP\${APP_DISPLAY}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\icon.ico"
SectionEnd

Section "Start with Windows" SecAutostart
    ; Standard-user app -> HKCU Run (root build spec); starts hidden in tray
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APP_NAME}" '"$INSTDIR\${APP_EXE}" --minimized'
SectionEnd

; -- Section Descriptions -----------------------------------------
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "Install ${APP_DISPLAY} core files, bundled ffmpeg, and the firewall rule (required)."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecTailscale} "Install Tailscale so your phone reaches this PC from anywhere (skipped if already installed). Free for personal use."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Create a shortcut on your Desktop."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecAutostart} "Start ${APP_DISPLAY} in the tray when Windows starts."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; =================================================================
; UNINSTALLER
; =================================================================

Section "Uninstall"
    nsExec::ExecToLog 'taskkill /im "${APP_EXE}" /f'
    Sleep 500

    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APP_NAME}"
    nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="${APP_DISPLAY}"'

    Delete "$DESKTOP\${APP_DISPLAY}.lnk"
    RMDir /r "$SMPROGRAMS\${APP_DISPLAY}"
    RMDir /r "$INSTDIR"

    ; User data (settings, token, logs) -- ${APP_DISPLAY} keeps it under
    ; LOCALAPPDATA\RemoteUser (see server/config.py)
    RMDir /r "$LOCALAPPDATA\${APP_NAME}"

    DeleteRegKey HKLM "${UNINST_KEY}"

    ; Tailscale is intentionally NOT uninstalled -- it may serve other apps
    ; and removing a VPN behind the user's back is hostile.
SectionEnd
