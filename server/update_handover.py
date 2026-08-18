"""Installing a new version WITHOUT losing the session you are installing from.

The owner's report, 2026-08-07, and it is the most expensive shape of bug this
project can have:

    *"da li možeš da implementiraš da se aplikacija ugasi tek u onoj zadnjoj
    fazi kada krene da se instalira i da se ponovo upali to jest pokrene
    server — dešava se da ja ne mogu da instaliram novu verziju ako nisam
    kući, zato što čim uđem u instalaciju on će meni ugasiti Vibe Coder i
    više neću moći da komandujem odavde."*

Every fix this project ships reaches him ONLY through an install, and starting
the install killed the remote session he was installing FROM. The trap ate
itself: away from home, running an old build, unable to take the new one.

What he asked for is "quit later". What this module builds is stronger,
because "later" still leaves him holding a phone in front of an installer's
Next button he cannot press: **after he taps Update, nothing else is needed
from him and control comes back by itself.**

WHO IS ALIVE, STEP BY STEP
--------------------------
    the app          the .cmd          the installer       the new app
    ---------------------------------------------------------------------
 1  downloads          -                    -                  -
 2  VERIFIES the file  -                    -                  -          <- nothing is handed over unverified
 3  TELLS the phone    -                    -                  -          <- the last message he gets for a minute
 4  spawns  ─────────▶ waiting              -                  -
 5  exits              waiting              -                  -          <- the LAST possible moment
 6    -                runs ───────────▶ replacing files       -
 7    -                waiting           exits                 -
 8    -                starts ──────────────────────────────▶ binding
 9    -                proves it is up      -                 serving
10    -                exits                -                 serving     <- the phone's own 2 s retry reconnects

The script is the only thing alive at step 6, which is exactly why it does not
live in the install folder: the installer is overwriting that folder. It sits
in USER_DIR with the log it writes, and it is written fresh on every handover.

WHY A .cmd AND NOT PYTHON
-------------------------
There is no interpreter in the packaged app (PyInstaller freezes the code, not
a python.exe the way a script could be re-run), and the one process that could
run our code is the process that has to die. `cmd.exe` is the only executor on
a Windows PC that is guaranteed present, needs nothing installed, and outlives
its parent. Every value it needs arrives in its ENVIRONMENT rather than baked
into the file — so the script text is constant, pure ASCII, and cannot be
corrupted by a code page when a path carries a non-ASCII character.

THE ROLLBACK IS ONE LINE, AND IT IS THE SAME LINE AS THE SUCCESS PATH
---------------------------------------------------------------------
`start "%RU_EXE%"` runs whatever the install left at that path — and a silent
NSIS run that fails replaces nothing, so that path still holds the OLD app.
There is no branch to get wrong, no backup to restore, no state to reconcile:
whatever happened to the installer, the owner gets an app back on the same
port with the same persisted token, and his phone reconnects into it. The only
case that cannot be rescued from here is "there is no exe at all", and that one
is SAID — in the log, and by the next start's `announce()`.
"""

import asyncio
import ctypes
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import notice_channel
import updates
from config import SETTINGS, app_version

logger = logging.getLogger(__name__)

# What a real Vibe Coder installer weighs, floored hard. The whole point of
# this number is that a captive-portal login page, an HTML error body or a
# zero-length file saved over a dropped connection can never be mistaken for
# an installer — they are all orders of magnitude below it.
MIN_INSTALLER_BYTES = 5_000_000

# Windows process-creation flags. CREATE_NO_WINDOW gives the script a real
# console that is never drawn — invisible, but a console, which is not a
# cosmetic distinction: DETACHED_PROCESS (no console at all) was the first
# attempt and `tasklist` silently returns NOTHING there, so both of the
# script's questions — "is the old app gone?" and "did the new one come up?" —
# answered "yes" instantly and wrongly. Measured, not guessed: the gate's wait
# check went red on it. CREATE_NEW_PROCESS_GROUP keeps a Ctrl+C aimed at this
# app from reaching the handover. A Windows child outlives its parent by
# default, which is what lets the script keep running after we exit.
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200

# How long the app waits for the phone to be told before it goes. Short on
# purpose: the notice is worth having, but a phone that has just gone quiet
# must never be able to hold a whole update hostage.
TELL_TIMEOUT_S = 3.0

RECORD_STATE = "handover"

# Every sentence this module can put on the owner's button. None of them is an
# exception's own text — the log gets that (rules/CODE.md: no error masking,
# and no raw repr in front of a human either).
DAMAGED_TEXT = "The downloaded update was incomplete — retry"
NOT_ELEVATED_TEXT = "Update needs a click on the PC — retry there"
HANDOVER_FAILED_TEXT = "Could not prepare the update — retry"
ALREADY_ARMED_TEXT = "An update is already installing — hold on"

# ═══════════════════════════ THE HANDOVER SCRIPT ═══════════════════════════
# Constant text, ASCII only, every value from the environment (see the module
# docstring). Read it as the six steps of the table above: wait for us to go,
# install, start whatever is at the path, prove it, say so.
#
# The trailing space before every `>>` is not a typo. `echo %~1>>"%LOG%"` with
# a message ending in a digit — "the installer exited with code 0" — parses as
# a STREAM redirect (`0>>`), and the line vanishes from the log. The space is
# what keeps the one record of a failed update readable.
SCRIPT = r"""@echo off
setlocal EnableExtensions
rem ------------------------------------------------------------------
rem  Vibe Coder - unattended update handover.
rem  Written by server/update_handover.py; every value arrives in the
rem  environment. While this runs, it is the ONLY thing standing between
rem  the owner and a PC he cannot reach. Do not make it clever.
rem ------------------------------------------------------------------
rem  Every value, checked. Not defensiveness for its own sake: an undefined
rem  tick count turns `if %n% GEQ %RU_EXIT_TICKS%` into a batch syntax error
rem  printed to a console nobody is watching, which is the silent failure this
rem  whole module exists to abolish. Missing anything = refuse, and SAY so.
if not defined RU_EXE goto badenv
if not defined RU_NAME goto badenv
if not defined RU_INSTALLER goto badenv
if not defined RU_LOG goto badenv
if not defined RU_PID goto badenv
if not defined RU_EXIT_TICKS goto badenv
if not defined RU_UP_TICKS goto badenv

rem  Windows' OWN tools, by full path. Never by name: PATH is the user's, and
rem  a PC with Git for Windows on it answers "find" with GNU find, which reads
rem  its argument as a FILE, fails, and turns every "is that process alive?"
rem  question below into a confident, instant NO. Measured, not imagined - it
rem  is what the gate's wait check caught on the dev machine, and it would
rem  have meant the installer starting while the app was still writing.
set "TASKLIST=%SystemRoot%\System32\tasklist.exe"
set "FIND=%SystemRoot%\System32\find.exe"
set "SLEEP=%SystemRoot%\System32\ping.exe -n 2 127.0.0.1"

call :say "--- handover to v%RU_VERSION% begins (old pid %RU_PID%) ---"

rem  1. The old app leaves on its own. We WAIT for it: an installer that has
rem     to kill a process is an installer racing a process still writing its
rem     own settings file.
set /a n=0
:waitexit
"%TASKLIST%" /FI "PID eq %RU_PID%" /NH 2>nul | "%FIND%" "%RU_PID%" >nul
if errorlevel 1 goto gone
set /a n+=1
if %n% GEQ %RU_EXIT_TICKS% goto tooslow
%SLEEP% >nul
goto waitexit
:tooslow
call :say "the old app is STILL running after %RU_EXIT_TICKS%s - going ahead anyway "
:gone
call :say "the old app is gone "

rem  2. The installer, silent. /S is NSIS's own switch and installer.nsi is
rem     built to honour it end to end (no pages, no Tailscale wizard, and it
rem     keeps the shortcut/autostart choices already on this PC).
rem     `call`, not a bare invocation: it waits for the installer and brings
rem     its exit code back for BOTH kinds of target, which is what lets the
rem     gate stand a script in for the real setup and still prove this path.
call :say "installing: %RU_INSTALLER% /S "
call "%RU_INSTALLER%" /S
set "RC=%ERRORLEVEL%"
call :say "the installer exited with code %RC% "

rem  3. THE ROLLBACK AND THE SUCCESS PATH ARE THIS ONE LINE. A silent NSIS run
rem     that failed replaced nothing, so the old app is still sitting at this
rem     path - starting it is both "the update worked" and "the update did
rem     not, give him his PC back".
if not exist "%RU_EXE%" goto noexe
start "" /B "%RU_EXE%"
call :say "started %RU_EXE% "

rem  4. Prove it. A start that did not take is a PC the phone cannot reach, so
rem     it is worth one more try before we give up and write it down.
set /a n=0
:waitup
%SLEEP% >nul
"%TASKLIST%" /FI "IMAGENAME eq %RU_NAME%" /NH 2>nul | "%FIND%" /I "%RU_NAME%" >nul
if not errorlevel 1 goto isup
set /a n+=1
if %n% LSS %RU_UP_TICKS% goto waitup
call :say "it did not come up within %RU_UP_TICKS%s - starting it once more "
start "" /B "%RU_EXE%"
goto done
:isup
call :say "the new app is running - the phone can reach this PC again "
goto done

:noexe
call :say "FATAL: nothing to run at %RU_EXE% - Vibe Coder must be launched on this PC by hand "
goto done

:badenv
if defined RU_LOG call :say "REFUSED: the handover environment was incomplete "
goto :eof

:done
call :say "--- handover finished --- "
endlocal
exit /b 0

:say
echo [%DATE% %TIME%] %~1 >>"%RU_LOG%"
exit /b 0
"""


# ═══════════════════════════ THE FILE WE STAKE THE PC ON ═══════════════════
def verify(path: Path, expected_size: int | None) -> str:
    """Is this really a complete Vibe Coder installer? Returns "" when it is,
    and a sentence for the LOG when it is not.

    This is the one check that cannot be skipped. Everything after it is
    irreversible from the owner's side: the app exits, the files are replaced,
    and if what ran was a half-downloaded file he is left with a PC he cannot
    reach until he is physically in front of it. A dropped Wi-Fi mid-download
    is an ordinary Tuesday.
    """
    if not path.exists():
        return f"the downloaded installer is not on disk ({path})"
    size = path.stat().st_size
    if expected_size and size != expected_size:
        return (f"the download is incomplete — {size} bytes of the "
                f"{expected_size} GitHub says the installer weighs")
    if size < MIN_INSTALLER_BYTES:
        return (f"the download is far too small to be an installer "
                f"({size} bytes)")
    with open(path, "rb") as f:
        if f.read(2) != b"MZ":
            return "the download is not a Windows program (no MZ header)"
    return ""


def elevated() -> bool:
    """Whether this process can start an admin-manifested installer WITHOUT a
    UAC prompt appearing on a PC nobody is standing at.

    The packaged app is always elevated (`--uac-admin`, because UIPI eats
    non-elevated SendInput — project CLAUDE.md constraint 8), so this is True
    in every shipped copy. A dev checkout run from a normal shell is the case
    it exists for, and it is answered honestly instead of being handed a
    handover that would stall on a prompt.
    """
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError) as e:      # non-Windows / no shell32
        logger.warning("Could not read this process's elevation: %s", e)
        return False


# ═══════════════════════════ THE RECORD THAT SURVIVES US ═══════════════════
# The one piece of state that has to outlive the process, because the process
# is the thing being replaced. Deliberately tiny and deliberately NOT a queue:
# it answers exactly one question at the next start — "did the version we
# installed actually become the version now running?"
def _write_record(target: str, installer: Path, exe: Path) -> None:
    SETTINGS.update_record_path.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.update_record_path.write_text(json.dumps({
        "state": RECORD_STATE,
        "from": app_version(),
        "to": target,
        "at": time.time(),
        "installer": str(installer),
        "exe": str(exe),
    }), encoding="utf-8")


def _read_record() -> dict | None:
    path = SETTINGS.update_record_path
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Update record unreadable (%s) — ignoring it", e)
        return None


def announce() -> str:
    """Called once per process start: if the last run handed this PC over to
    an installer, tell the phone how that ended. Returns the title it queued
    ("" when there was no handover to report).

    It is queued, not sent: there is no phone attached yet at this point in a
    start-up, and `notice_channel`'s queue is exactly the carrier for "something the
    owner should know, held until he is reachable" — it even stamps the time,
    so the phone says "2 min ago" instead of pretending it just happened.

    A FAILED update is announced just as loudly as a successful one. He is the
    only one who can act on it, and an update that silently did not happen is
    how a man ends up testing a build he never installed.
    """
    record = _read_record()
    if not record or record.get("state") != RECORD_STATE:
        return ""
    # Consumed whatever we decide below — a record read twice would announce
    # the same update again on the next "Apply & restart".
    SETTINGS.update_record_path.unlink(missing_ok=True)
    target, running = record.get("to", "?"), app_version()
    if updates.numbers(running) == updates.numbers(target):
        title = f"Vibe Coder updated to v{target}"
        text = "The PC is back — nothing else to do."
        event = "finished"
        logger.info("Update handover succeeded: now running v%s", running)
    else:
        title = f"Vibe Coder is still on v{running}"
        text = (f"The update to v{target} did not install. "
                f"Everything works as before; the update log on the PC says why.")
        event = "failed"
        logger.error("Update handover FAILED: wanted v%s, running v%s — see %s",
                     target, running, SETTINGS.update_log_path)
    notice_channel.queue({
        "type": "notify", "agent": "Vibe Coder", "event": event,
        "title": title, "text": text,
        "speak": SETTINGS.notify_speak, "voice": SETTINGS.notify_voice,
        "rate": SETTINGS.notify_rate, "at": time.time(),
    })
    return title


# ═══════════════════════════ TELLING THE PHONE ═══════════════════════════
def tell_phone(controller, version: str) -> bool:
    """The last thing he hears before the screen goes dark for a minute.

    Sent through `notice_channel.deliver`, so it takes whichever carrier is alive —
    the open page (banner + spoken + toast on the status pill) or, if he has
    already put the phone down, the waiting channel his foreground service
    holds. Both outlive the moment; neither needs him to be looking.

    Returns whether it went. False is not a reason to abort the update — the
    update is what he asked for, and a phone that has gone quiet must not be
    able to veto it — but it IS written down.
    """
    loop = getattr(controller, "loop", None)
    if loop is None or not loop.is_running():
        logger.info("No running server loop — the phone gets no update notice")
        return False
    notice = {
        "type": "notify", "agent": "Vibe Coder", "event": "updating",
        "title": f"Installing v{version}",
        "text": "The picture goes for about a minute and comes back by itself.",
        "speak": SETTINGS.notify_speak, "voice": SETTINGS.notify_voice,
        "rate": SETTINGS.notify_rate, "at": time.time(),
    }
    try:
        carrier = asyncio.run_coroutine_threadsafe(
            notice_channel.deliver(notice), loop).result(timeout=TELL_TIMEOUT_S)
    except Exception as e:  # noqa: BLE001 — a dying socket must not stop an update
        logger.warning("Could not tell the phone about the update: %s", e)
        return False
    logger.info("Told the phone the update is starting (carrier: %s)", carrier)
    return carrier != "held"


# ═══════════════════════════ THE ARMING LOCK ═══════════════════════════
# Exactly ONE handover may be live at a time (owner 2026-08-09, the night the
# updater installed his app more than twenty times over — "instalirao mi je
# preko 20 aplikacija").  lang-ok: owner quote
#
# Nothing used to stop a SECOND script being armed while the first still ran:
# every armed script survives this process ON PURPOSE, each one runs the
# installer and starts an app, every started app asks GitHub within seconds —
# and with six releases published in four hours, each fresh app found a newer
# version to arm again. One script became two became four; his update.log
# printed "--- handover finished ---" dozens of times in one second, because
# every waiting script's "did it come up?" probe is satisfied by ANY instance
# of the image name. The fork is cut here, at the one choke point every arm
# must pass, with a fact on DISK — the fork's whole nature is that the
# processes involved know nothing about each other.
#
# The lock lives beside the script it guards (USER_DIR — a place the installer
# never overwrites) and holds {pid, at}: the armer's pid first, then — the
# moment the spawn returns — the script's own cmd.exe pid, so the lock stays
# honest exactly as long as a handover is genuinely alive. Two ways it can
# never brick the next update (a lock that outlives a crash and refuses
# forever would be a worse bug than the fork it prevents):
#   - a lock whose pid is DEAD is reclaimed on the next arm;
#   - a lock older than LOCK_STALE_S is reclaimed even when its pid looks
#     alive, because Windows recycles pids and a stranger's process must not
#     hold this door shut.

# Far past everything a handover can honestly spend: update_wait_exit_s (30)
# + the silent install + update_wait_up_s (40) + slack for an antivirus
# first-touch scan. A handover still "live" after this long is a lie.
LOCK_STALE_S = 15 * 60

# Win32 process-probe constants (ctypes; no psutil in the packaged app).
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
ERROR_ACCESS_DENIED = 5


def _lock_path() -> Path:
    """Derived, not a config field of its own: the lock guards the SCRIPT, so
    wherever the script is told to live (USER_DIR in production, a temp folder
    in the gate), the lock is already beside it."""
    return SETTINGS.update_script_path.parent / "handover.lock"


def _pid_alive(pid: int) -> bool:
    """Windows-honest liveness. A pid that exists but refuses to open counts
    as ALIVE (refusing an arm is recoverable; forking again is the bug we had),
    and an open handle is asked for its exit code — OpenProcess also succeeds
    on a process that has exited while somebody still holds a handle to it."""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return ctypes.get_last_error() == ERROR_ACCESS_DENIED
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(ctypes.c_void_p(handle),
                                               ctypes.byref(code)):
                return True  # unreadable — the recoverable answer is "alive"
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
    except (AttributeError, OSError) as e:  # non-Windows dev machine
        logger.warning("Could not probe pid %s: %s", pid, e)
        return False


def live_handover() -> int | None:
    """The pid of a handover that is genuinely running right now, else None.
    Garbage, a dead pid and old age all read as None — every one of those is
    a lock to reclaim, never a reason to refuse an update forever."""
    path = _lock_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pid, at = int(data["pid"]), float(data["at"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        logger.warning("Handover lock unreadable (%s) — treating it as stale", e)
        return None
    if time.time() - at > LOCK_STALE_S:
        return None
    return pid if _pid_alive(pid) else None


def _acquire_lock() -> bool:
    """Take the arming lock atomically. False = a handover is already live,
    or a sibling arm won the race in this very instant (O_EXCL is the judge —
    two `begin`s that both saw a free lock cannot both create the file)."""
    path = _lock_path()
    if live_handover() is not None:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # A dead or stale lock is RECLAIMED here — the line that keeps one
        # crash from bricking every future update.
        if path.exists():
            logger.info("Reclaiming a stale handover lock (%s)", path)
            path.unlink(missing_ok=True)
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False  # a sibling arm slipped in between the check and here
    except OSError as e:
        # USER_DIR unwritable: the script write below would fail the same
        # way, so refusing is honest, and it is logged with the real reason.
        logger.error("Could not take the arming lock: %s", e)
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"pid": os.getpid(), "at": time.time()}))
    return True


def _stamp_lock(pid: int | None) -> None:
    """Re-write the lock with the SCRIPT's own pid. The armer is about to
    exit — its pid going dead is the design — and the script is the thing
    whose lifetime the lock must follow: cmd.exe dies, the lock goes stale,
    the next arm reclaims it. No release step exists on the success path."""
    if not pid:
        return
    try:
        _lock_path().write_text(
            json.dumps({"pid": int(pid), "at": time.time()}), encoding="utf-8")
    except OSError as e:
        logger.warning("Could not stamp the arming lock with the script pid: %s", e)


def _release_lock() -> None:
    """Only for an arm that FAILED after taking the lock — a lock with no
    script behind it must not cost him the next try."""
    _lock_path().unlink(missing_ok=True)


# ═══════════════════════════ THE HANDOVER ITSELF ═══════════════════════════
def _spawn(env: dict) -> subprocess.Popen:
    """Start the handover script so that it survives our own exit."""
    return subprocess.Popen(
        ["cmd", "/c", str(SETTINGS.update_script_path)],
        env=env, cwd=str(SETTINGS.update_script_path.parent),
        creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def hand_over(installer: Path, version: str, exe: Path | None = None) -> Path:
    """Write the script, arm the record, and start the script. Raises OSError
    if any of that fails — the caller must NOT exit when it does.

    `exe` defaults to this process's own executable, which under PyInstaller is
    exactly the path the installer is about to replace and exactly the path the
    script has to start again. Nothing here guesses an install directory.
    """
    exe = Path(exe or sys.executable)
    # THE FORK GUARD (owner 2026-08-09): the lock is taken BEFORE anything is
    # written or spawned, at the one point every arm must pass — a second
    # handover armed beside a live one is how one tap became 20+ installs.
    if not _acquire_lock():
        raise OSError("a handover is already live — refusing to arm a second")
    try:
        SETTINGS.update_script_path.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.update_script_path.write_text(SCRIPT, encoding="ascii")
        _write_record(version, installer, exe)
        env = {**os.environ,
               "RU_PID": str(os.getpid()),
               "RU_EXE": str(exe),
               "RU_NAME": exe.name,
               "RU_INSTALLER": str(installer),
               "RU_LOG": str(SETTINGS.update_log_path),
               "RU_VERSION": version,
               "RU_EXIT_TICKS": str(SETTINGS.update_wait_exit_s),
               "RU_UP_TICKS": str(SETTINGS.update_wait_up_s)}
        proc = _spawn(env)
    except OSError:
        _release_lock()  # an arm that failed must never hold the door shut
        raise
    _stamp_lock(getattr(proc, "pid", None))
    logger.info("Handover armed: %s will install %s and restart %s",
                SETTINGS.update_script_path, installer, exe)
    return SETTINGS.update_script_path


def begin(controller, installer: Path, version: str,
          expected_size: int | None) -> tuple[str, str]:
    """The whole sequence, in the order that makes it survivable. Returns
    `(action, button_text)` where action is one of:

      "quit"   — the handover is armed; exit NOW, at the last possible moment.
      "manual" — this process cannot install unattended (not elevated, a dev
                 checkout). Fall back to launching the installer visibly.
      "stop"   — nothing was started and nothing was touched; show the text.

    The ORDER is the design, not an implementation detail. Verify before we
    tell him anything, tell him before anything can take his screen away, and
    arm the restart before we give up the ability to do anything at all.
    """
    problem = verify(installer, expected_size)
    if problem:
        logger.error("Refusing the update handover: %s", problem)
        return "stop", DAMAGED_TEXT
    # THE FORK GUARD, consulted before the phone hears anything (owner
    # 2026-08-09, the 20-install fork): a refused arm must not announce
    # "Installing vX" for an install that will not run. The atomic take is
    # inside hand_over(); this early look exists only to keep the refusal
    # ahead of tell_phone, and the thief is NAMED — a silent refusal is how
    # the same week gets spent twice.
    holder = live_handover()
    if holder is not None:
        logger.warning("Refusing to arm a second handover — one is already "
                       "live (script pid %s)", holder)
        return "stop", ALREADY_ARMED_TEXT
    tell_phone(controller, version)
    if not elevated():
        logger.warning("Not elevated — the installer needs a UAC prompt "
                       "somebody has to click on this PC")
        return "manual", NOT_ELEVATED_TEXT
    try:
        hand_over(installer, version)
    except OSError as e:
        logger.error("Could not arm the update handover: %s", e)
        return "stop", HANDOVER_FAILED_TEXT
    return "quit", ""
