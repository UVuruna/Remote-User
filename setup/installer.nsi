Unicode true

; =================================================================
; Vibe Coder Installer -- NSIS Script
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
!include "Sections.nsh"   ; SelectSection / UnselectSection -- the silent path

; -- App Info -----------------------------------------------------
!define APP_NAME "VibeCoder"
!define APP_DISPLAY "Vibe Coder"
!define APP_EXE "VibeCoder.exe"
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

Function un.onInit
    SetRegView 64
FunctionEnd

; =================================================================
; INSTALLER SECTIONS
; =================================================================

Section "!${APP_DISPLAY} (required)" SecMain
    SectionIn RO

    ; Close a running instance so locked files can be replaced on upgrade.
    ; THIS LINE USED TO BE THE THING THAT KILLED HIS SESSION -- and it is
    ; kept, deliberately, as a last resort for a hand-run install. In the
    ; unattended path it finds nothing: server/update_handover.py's script
    ; WAITS for the old app's own pid to disappear before starting us, so
    ; the app closes itself, in order, with its always-on-top windows
    ; released -- instead of being shot mid-write.
    nsExec::ExecToLog 'taskkill /im "${APP_EXE}" /f'
    Sleep 500

    ; Remove any previous autostart unconditionally -- SecAutostart recreates
    ; it only when selected, so unchecking it on upgrade actually disables it.
    ; HKCU Run is the LEGACY location: it silently refuses to start elevated
    ; apps, and the app now runs elevated (UIPI -- see SecAutostart).
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APP_NAME}"
    nsExec::ExecToLog 'schtasks /Delete /F /TN "${APP_NAME}"'

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
    ; Never in a silent (unattended update) run -- .onInit unselects this
    ; section there, and this line is the second lock on the same door: the
    ; Tailscale wizard is VISIBLE and ExecWait would hang the whole update
    ; on a Next button nobody is there to press.
    IfSilent TailscaleDone
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
    ; The app runs ELEVATED (input injection over admin windows -- Windows'
    ; UIPI silently eats non-elevated SendInput whenever an elevated window
    ; has focus; live failure 2026-07-29). HKCU Run silently skips elevated
    ; apps, so autostart is a Task Scheduler logon task with highest
    ; privileges (root build spec) -- starts in the tray, no UAC prompt at
    ; logon (unlike a manual Start-menu launch).
    ; schtasks parses /TR with CRT rules: a path with spaces needs ESCAPED
    ; inner quotes (\"...\"), not bare nested ones — the bare form silently
    ; failed and shipped an installer that created no task at all (caught by
    ; verifying the installed machine, 2026-07-29). $\\$\" emits \" in NSIS.
    ; NSIS has NO backslash escape (a backslash is literal, only quotes need
    ; $\") — the earlier "$\\$\"" form emitted garbage and schtasks failed
    ; silently, shipping an installer that created no task at all.
    nsExec::ExecToLog 'schtasks /Create /F /TN "${APP_NAME}" /SC ONLOGON /RL HIGHEST /TR "\$\"$INSTDIR\${APP_EXE}\$\" --minimized"'
SectionEnd

; =================================================================
; INITIALIZATION
;
; Two jobs. First, force the 64-bit registry view (64-bit-only app;
; without this a 32-bit NSIS stub writes under WOW6432Node and
; Add/Remove Programs never sees the uninstall entry).
;
; Second -- and this is the reason this function sits BELOW the
; sections, where ${SecTailscale} & co. are already defined -- the
; UNATTENDED path (owner report 2026-08-07). He installs updates from
; his phone, through the very session the install replaces:
;
;   "cim udjem u instalaciju on ce meni ugasiti Remote User i vise
;    necu moci da komandujem odavde"
;
; So the running app hands this installer over with NSIS's own /S and
; there is nobody at the PC to click anything. Three things have to be
; true for that to work, and all three are decided here:
;
;   1. The Tailscale chain-install must NOT run. Its setup opens a
;      VISIBLE wizard and our ExecWait would block forever with nobody
;      to press Next. A silent run is by definition an UPGRADE of an
;      app that is already reaching a phone -- over Tailscale -- so the
;      dependency is already on the machine.
;   2. A silent run must change NOTHING he did not ask to change. In
;      silent mode NSIS takes the DEFAULT section selection, which
;      would re-create a desktop shortcut he deleted and re-arm an
;      autostart he switched off. So both are read off the machine
;      first and the sections are set to match what is already there.
;   3. Nothing may prompt. Every remaining section is registry, files
;      and nsExec -- all silent.
; =================================================================

; ---- THE ONE-HANDOVER LOCK (owner 2026-08-09/2026-08-11, task 148/187) ----
; task 148 armed ONE handover script per running app, guarded from
; server/update_handover.py -- but that guard lives INSIDE the app being
; replaced, and the app that launches a real-world handover is, by
; definition, whatever OLD (possibly broken) build was still running on
; his machine. His 102->103 storm proved the app-side lock holds once it
; ships -- but the installer must survive an OLDER build that forked the
; handover BEFORE 148 ever existed, or a future bug in a 148-shipped
; build. The installer is the one piece of this hand-off that is ALWAYS
; the new, fixed code, so the lock belongs here too, independent of
; whatever state the app that spawned us is in.
;
; A named OS mutex is the simplest correct answer: the kernel itself
; refuses a second holder, a crashed or killed instance releases it for
; free (no stale-lock arithmetic to get wrong a second time -- see
; update_handover.py's own LOCK_STALE_S comment for why that arithmetic
; is worth avoiding when the OS will do it for us), and "Global\" makes
; it visible across the whole session so a handover running as
; SYSTEM/another session still collides with one running interactively.
Function .onInit
    SetRegView 64

    ; CreateMutexA + the inline "?e" flag, NOT CreateMutexW/"w" -- measured,
    ; not guessed: the wide-string form silently returned a bogus, always-
    ; "already exists" GetLastError on this NSIS build (ANSI installer, "t"
    ; is its native TCHAR width), which would have made every install refuse
    ; itself with the "already installing" message -- the opposite failure
    ; from the one this lock exists to prevent.
    System::Call 'kernel32::CreateMutexA(i 0, i 1, t "Global\VibeCoderInstallerRunning") i .r0 ?e'
    Pop $1  ; GetLastError() -- 183 = ERROR_ALREADY_EXISTS
    IntCmp $1 183 MutexHeld MutexFree MutexFree
MutexHeld:
    ; Somebody else already holds the install -- another forked handover
    ; racing this one, or a second manual run. Refuse instead of letting
    ; two installers race the same files on disk (the exact shape of his
    ; 20-install storm, one level down from where 148 stopped it).
    IfSilent SilentAbort
    MessageBox MB_OK|MB_ICONINFORMATION "${APP_DISPLAY} is already being installed by another process. This installer will now close."
SilentAbort:
    ; The mutex handle is intentionally never closed -- it lives exactly
    ; as long as this process does, which is precisely the lifetime the
    ; lock needs, and Windows reclaims it the instant we exit for any
    ; reason (clean or crashed). No cleanup code can get that wrong.
    Quit
MutexFree:

    ; ---- STRAY HANDOVER-LOCK CLEANUP (task 187b) ----
    ; server/update_handover.py's own arming lock (handover.lock, beside
    ; the .cmd script in %LOCALAPPDATA%\VibeCoder) is supposed to go
    ; stale and get reclaimed by the NEXT arm -- but "the next arm" is
    ; the very app this installer is about to replace and restart, and a
    ; storm like his leaves that lock pointing at a pid that is already
    ; gone. We are the one guaranteed-clean actor in this whole handover:
    ; wipe it here so the freshly installed app starts with no borrowed
    ; lock state to reason about, silent or not, whichever way we found
    ; our way onto the machine. The .cmd script itself is left alone: it
    ; may still be the very process running us (Windows does not lock a
    ; batch file while cmd.exe executes it), and it is Python's file to
    ; rewrite fresh on its next arm regardless.
    Delete "$LOCALAPPDATA\VibeCoder\handover.lock"

    IfSilent 0 InitDone

    !insertmacro UnselectSection ${SecTailscale}

    IfFileExists "$DESKTOP\${APP_DISPLAY}.lnk" KeepDesktop 0
    !insertmacro UnselectSection ${SecDesktop}
    Goto CheckAutostart
KeepDesktop:
    !insertmacro SelectSection ${SecDesktop}

CheckAutostart:
    ; SecMain deletes the logon task unconditionally and SecAutostart
    ; re-creates it only when selected -- so this query has to happen
    ; here, before any section runs, or the answer is always "no".
    nsExec::ExecToStack 'schtasks /Query /TN "${APP_NAME}"'
    Pop $0      ; exit code: 0 = the task exists
    Pop $1      ; output (discarded -- the stack must be left clean)
    StrCmp $0 "0" KeepAutostart 0
    !insertmacro UnselectSection ${SecAutostart}
    Goto InitDone
KeepAutostart:
    !insertmacro SelectSection ${SecAutostart}

InitDone:
FunctionEnd

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
    nsExec::ExecToLog 'schtasks /Delete /F /TN "${APP_NAME}"'
    nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="${APP_DISPLAY}"'

    Delete "$DESKTOP\${APP_DISPLAY}.lnk"
    RMDir /r "$SMPROGRAMS\${APP_DISPLAY}"
    RMDir /r "$INSTDIR"

    ; User data (settings, token, logs) -- ${APP_DISPLAY} keeps it under
    ; LOCALAPPDATA\VibeCoder (see server/config.py)
    RMDir /r "$LOCALAPPDATA\${APP_NAME}"

    DeleteRegKey HKLM "${UNINST_KEY}"

    ; Tailscale is intentionally NOT uninstalled -- it may serve other apps
    ; and removing a VPN behind the user's back is hostile.
SectionEnd
