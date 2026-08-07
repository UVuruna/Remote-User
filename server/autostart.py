"""«Start with Windows» — the REAL Task Scheduler task, read and written.

The installer already creates one (`setup/installer.nsi` -> SecAutostart), and
it is a Task Scheduler logon task rather than an HKCU Run value for a reason
that cost this project a release: the app runs ELEVATED (Windows' UIPI eats
injected input from a non-elevated process whenever an elevated window has
focus — the 2026-07-29 dead-mouse failure), and HKCU Run silently REFUSES to
start elevated apps. So the task carries `/RL HIGHEST`, and there is no
second, easier place to keep this state.

Which is exactly why this module exists at all. The Settings window's switch
(round R2, owner 2026-08-07) had to be a switch over WINDOWS, not a
preference of our own: a tick that merely remembered an intention would show
"on" over a machine with no task, or "off" over one the installer created —
and a setting that only pretends is the failure mode this project keeps
paying for. `installed()` asks schtasks; `set_autostart()` creates or deletes
the same task the installer does, character for character.

Not in `config.py` (nothing here is a tunable) and not in the GUI (the window
owns a checkbox, not a Windows API): its own responsibility, its own module.
"""

import logging
import subprocess
import sys
from pathlib import Path

from config import FROZEN, PROJECT_ROOT, SETTINGS

logger = logging.getLogger(__name__)

# A windowed PyInstaller app has no console, and every schtasks call would
# otherwise flash a black window across the owner's screen.
CREATE_NO_WINDOW = 0x08000000
SCHTASKS_TIMEOUT_S = 15


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          timeout=SCHTASKS_TIMEOUT_S,
                          creationflags=CREATE_NO_WINDOW)


def _target() -> str:
    """What the task runs. Installed: the exe itself, started in the tray.
    A dev checkout has no exe, so the interpreter plus the GUI entry point
    stands in — the switch is then still HONEST about what it created."""
    if FROZEN:
        return f'"{sys.executable}" --minimized'
    return (f'"{sys.executable}" '
            f'"{Path(PROJECT_ROOT) / "server" / "gui_main.py"}" --minimized')


def installed() -> bool:
    """Does the logon task exist RIGHT NOW? Asked of Windows every time the
    Settings window opens — never cached, never inferred from a setting."""
    try:
        return _run(["schtasks", "/Query", "/TN", SETTINGS.autostart_task]).returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning("Could not query the autostart task: %s", e)
        return False


def set_autostart(on: bool) -> tuple[bool, str]:
    """Create or delete the logon task. Returns (ok, what to tell the user) —
    the empty string when there is nothing to say.

    `/RL HIGHEST` needs an elevated caller. The packaged app always is
    (`--uac-admin`); a dev run from a plain shell is not, and Windows refuses
    with a message the window then shows instead of leaving a switch that
    lies.
    """
    args = (["schtasks", "/Create", "/F",
             "/TN", SETTINGS.autostart_task, "/SC", "ONLOGON",
             "/RL", "HIGHEST", "/TR", _target()]
            if on else
            ["schtasks", "/Delete", "/F", "/TN", SETTINGS.autostart_task])
    try:
        result = _run(args)
    except (OSError, subprocess.SubprocessError) as e:
        # The raw exception is for the log, never the caption (round R2
        # grade, 2026-08-07 — a Python exception repr is not a sentence the
        # owner can act on).
        logger.error("Autostart task change failed: %s", e)
        return False, ("Windows would not change the startup task — the log "
                       "has the exact reason.")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        message = detail[-1] if detail else f"schtasks exited {result.returncode}"
        logger.error("schtasks %s failed: %s", "create" if on else "delete", message)
        return False, ("Windows refused to change the startup task. "
                       "Running Remote User as administrator lets it. "
                       f"({message})")
    logger.info("Autostart task %s", "created" if on else "removed")
    return True, ""
