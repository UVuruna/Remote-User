"""Windows' own "no program may steal the foreground" switch, borrowed safely.

The desktop half of the focus work (Settings window, round R2, owner
2026-08-07). The phone's half — WHERE a dictated sentence lands — lives in
`focus_guard.py` and fences one window at a time. This module fences the whole
PC: Windows already has a rule that says a process may not push itself in
front of the user for N milliseconds after the user's last input
(`SPI_SETFOREGROUNDLOCKTIMEOUT`), and the default N is small enough to be no
rule at all. Raising it is the closest thing Windows offers to the owner's
sentence: *"ne daj aplikacijama da otimaju fokus"*.

WHY THIS IS DANGEROUS, AND WHAT MAKES IT SAFE

It is a MACHINE-WIDE setting. Change it carelessly and the owner's PC keeps
our value long after this app is gone — the same class of failure as the
always-on-top band that twice left his Chrome and VSCode nailed above
everything (`window_manager.py`'s topmost ledger, owner decree 2026-08-05).
So this module is built on exactly that module's shape, with one extra piece
of luck: the flag word is deliberately EMPTY.

  * **No `SPIF_UPDATEINIFILE`.** The new value is never written to the
    registry. It lives in this Windows session's memory only — so a reboot,
    a logoff, even a crash of the whole desktop already restores it. That is
    a net `window_manager` does not have.
  * **We get to run code** (tray Quit, Ctrl+C, a console close, Qt's
    aboutToQuit, `atexit`, an unhandled crash): `release()` writes the value
    we found back. Idempotent — being called three times on the way out is
    the design.
  * **We do NOT** (Task Manager, the installer's `taskkill`, a power cut):
    the ledger is mirrored to `SETTINGS.foreground_lock_ledger_path` on every
    change and `repair_stranded()` reads it at the next start. It only writes
    back when the timeout is STILL the value we left behind — if anything
    else has moved it since, that someone outranks our note, exactly as a
    recycled window handle outranks a stale topmost entry.

Nothing here ever raises: a machine that refuses the call gets a logged
warning and a `False`, and the switch in the Settings window says so.
"""

import ctypes
import json
import logging
import os
from ctypes import wintypes

from config import SETTINGS

logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)

SPI_GETFOREGROUNDLOCKTIMEOUT = 0x2000
SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001
# THE FLAG WORD IS ZERO AND MUST STAY ZERO. SPIF_UPDATEINIFILE (0x01) is what
# would persist this to the registry; SPIF_SENDCHANGE (0x02) would broadcast
# it. We want neither — a setting that cannot outlive the process is a setting
# that cannot be left behind.
SPIF_NOTHING = 0

# The value this run found before it raised anything. None = we have not
# raised (or have already put it back), which is also what makes release()
# safe to call from every exit path.
_previous: int | None = None


def _read() -> int | None:
    """The current foreground lock timeout in ms, or None when Windows
    refuses to answer (documented fallback — the caller reports it)."""
    value = wintypes.DWORD()
    if not user32.SystemParametersInfoW(SPI_GETFOREGROUNDLOCKTIMEOUT, 0,
                                        ctypes.byref(value), SPIF_NOTHING):
        logger.warning("Could not read the foreground lock timeout (error %d)",
                       ctypes.get_last_error())
        return None
    return int(value.value)


def _write(ms: int) -> bool:
    """Set the timeout for THIS Windows session only (see SPIF_NOTHING).

    The value travels in pvParam cast to a pointer — that is the documented
    calling convention for this particular SPI, not a trick.
    """
    if not user32.SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT, 0,
                                        ctypes.c_void_p(int(ms)), SPIF_NOTHING):
        logger.error("Could not set the foreground lock timeout to %d ms "
                     "(error %d)", ms, ctypes.get_last_error())
        return False
    return True


def _ledger_save(previous: int, raised: int) -> None:
    """Mirror what we changed, for a run that never gets to change it back.
    Best effort by design: a repair note we cannot write must never stop the
    switch the owner just flipped."""
    try:
        SETTINGS.foreground_lock_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.foreground_lock_ledger_path.write_text(
            json.dumps({"pid": os.getpid(), "previous": previous, "raised": raised}),
            encoding="utf-8")
    except OSError as e:
        logger.warning("Foreground lock ledger not written: %s", e)


def _ledger_clear() -> None:
    try:
        SETTINGS.foreground_lock_ledger_path.unlink()
    except OSError:
        pass  # never existed, or already gone — both mean "nothing owed"


def is_raised() -> bool:
    """Whether THIS process currently holds the lock raised."""
    return _previous is not None


def apply(on: bool) -> bool:
    """Raise the foreground lock, or put it back. Returns whether Windows
    accepted; idempotent in both directions."""
    global _previous
    if not on:
        return release()
    if _previous is not None:
        return True
    current = _read()
    if current is None:
        return False
    raised = int(SETTINGS.foreground_lock_timeout_ms)
    if not _write(raised):
        return False
    _previous = current
    _ledger_save(current, raised)
    logger.info("Foreground lock raised: %d ms (was %d ms) — this Windows "
                "session only, never the registry", raised, current)
    return True


def release() -> bool:
    """Hand the machine its own setting back — THE exit call, wired into every
    way this process can end. A no-op when we never raised anything, so a
    stranded ledger from a KILLED run is left for `repair_stranded()` to read
    rather than being deleted by an exit that owes nothing."""
    global _previous
    if _previous is None:
        return True
    ok = _write(_previous)
    if ok:
        logger.info("Foreground lock restored to %d ms", _previous)
    _previous = None
    _ledger_clear()
    return ok


def repair_stranded() -> None:
    """Put right what a killed previous run left raised. Runs once at start,
    before this process can raise anything of its own.

    The identity check is the timeout itself: the value is only written back
    while it is STILL the one that run left behind. Anything else — the owner,
    another tool, a Windows restart that already reset it — means someone has
    moved it since, and their value outranks our note (the same rule that
    keeps a recycled window handle out of the topmost repair).
    """
    path = SETTINGS.foreground_lock_ledger_path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if data.get("pid") == os.getpid():
        return  # our own file, this very run
    previous, raised = data.get("previous"), data.get("raised")
    if isinstance(previous, int) and _read() == raised:
        if _write(previous):
            logger.warning("Restored the foreground lock timeout (%d ms) that a "
                           "previous run was killed holding at %d ms",
                           previous, raised)
    _ledger_clear()
