"""WHO WE ARE, AND WHO HAS THE FOREGROUND — measured, never asserted.

WHY THIS MODULE EXISTS AT ALL (owner ruling 2026-08-17): the injector's UIPI
alarm printed "…(UIPI: an elevated window or the lock screen has focus, and
this process is not elevated)" as FIXED TEXT, every time a commanded cursor
jump failed to land. Nothing under `server/` measured any part of that
sentence. It was the alarm author's hypothesis about a likely cause, printed
in the voice of a finding — and it did exactly what a printed hypothesis
does: it was read out of a log as evidence and reported to the owner as the
cause of a failure it had nothing to do with (2026-08-16 19:19, where the
real defect was a dead capture, `capture_recovery.py`).

His ruling was the right one and it is general: a thing that does not do
what it says either starts doing it or goes away. So the alarm now calls in
here and prints what was FOUND.

WHAT IS MEASURED, and every one of them is a real question with a real answer:

  * `IsUserAnAdmin()` — are WE elevated. The packaged app is manifested to
    require it (`build.py --uac-admin`, `VibeCoder.spec uac_admin=True`), so
    the honest expectation is True and a False here is genuinely worth the
    word "not elevated" — which, until now, was printed either way.
  * The foreground window: its handle, its process name and its title. UIPI
    is decided by the window that HAS the input focus, so naming it is the
    difference between "something stole your input" and "Task Manager did".
  * That window's integrity level, read from its process token
    (`TokenIntegrityLevel`). This is the one that actually settles UIPI: a
    HIGH or SYSTEM window above a MEDIUM us is the documented case where
    Windows silently discards `SendInput` and still returns success.

WHAT IS NOT GUESSED. Every field is independently nullable and rendered as
"unknown" rather than filled in with a plausible value — a process we cannot
open (a SYSTEM process usually refuses) yields `None`, not "probably high".
`describe()` therefore builds its sentence out of what it HAS, and when it
has nothing it says so; there is no branch anywhere that produces a cause.

WHY THIS IS ITS OWN MODULE rather than four functions inside
`input_injector.py`: the injector's responsibility is putting input into
Windows on a hot path, and this is diagnosis of the environment — read once
when something has already gone wrong, never per event. It is also needed by
the use log (`session_log`'s `state.app` record) and would otherwise have to
be imported FROM the injector by a module with no business there.

NOTHING HERE MAY RAISE. It runs inside an error path: a diagnosis that
throws replaces a wrong explanation with no explanation at all.
"""

import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

# Integrity level RIDs, from the Windows SDK. Named rather than compared as
# bare numbers because the whole point of this module is that a reader can
# check the claim.
_INTEGRITY = [
    (0x4000, "system"),
    (0x3000, "high"),
    (0x2000, "medium"),
    (0x1000, "low"),
    (0x0000, "untrusted"),
]

TOKEN_QUERY = 0x0008
TOKEN_INTEGRITY_LEVEL = 25
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def is_elevated() -> bool | None:
    """Are WE running elevated? `None` when the question cannot be asked
    (non-Windows, no shell32) — never a guess, and never False-by-default,
    which would be the same lie the alarm used to tell."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError) as e:
        logger.debug("Elevation: IsUserAnAdmin unavailable (%s)", e)
        return None


def _process_of(hwnd: int) -> int | None:
    try:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) or None
    except OSError:
        return None


def integrity_of(pid: int) -> str | None:
    """The integrity level of `pid`'s token, as one of the names above.

    `None` whenever it cannot be read — most often because the process is
    more privileged than we are and refuses to open, which is itself
    consistent with the UIPI case but is NOT proof of it, so it is reported
    as unknown rather than as "high".
    """
    k32, a32 = ctypes.windll.kernel32, ctypes.windll.advapi32
    # SIGNATURES DECLARED, not left to ctypes' int default. A PSID is a
    # POINTER and on 64-bit Windows it does not fit an int — the first
    # version of this module raised
    # `ArgumentError: int too long to convert` on the very first real call,
    # found by RUNNING it against this desk rather than by reading it.
    a32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
    a32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    a32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    a32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
    k32.OpenProcess.restype = wintypes.HANDLE
    handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    token = wintypes.HANDLE()
    try:
        if not a32.OpenProcessToken(handle, TOKEN_QUERY, ctypes.byref(token)):
            return None
        size = wintypes.DWORD()
        a32.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, None, 0,
                                ctypes.byref(size))
        buf = ctypes.create_string_buffer(size.value or 64)
        if not a32.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, buf,
                                       size.value, ctypes.byref(size)):
            return None
        # TOKEN_MANDATORY_LABEL { SID_AND_ATTRIBUTES Label { PSID Sid; ... } }
        sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
        if not sid:
            return None
        last = a32.GetSidSubAuthorityCount(sid)[0] - 1
        rid = a32.GetSidSubAuthority(sid, last)[0]
        for floor, name in _INTEGRITY:
            if rid >= floor:
                return name
        return None
    except OSError:
        return None
    finally:
        if token:
            k32.CloseHandle(token)
        k32.CloseHandle(handle)


def foreground() -> dict:
    """The window that currently HAS the input focus — handle, process name,
    title and integrity level. Every field independently nullable."""
    out = {"hwnd": None, "process": None, "title": None, "integrity": None}
    try:
        u32 = ctypes.windll.user32
        hwnd = int(u32.GetForegroundWindow() or 0)
    except OSError:
        return out
    if not hwnd:
        # A real state, not a failure: the secure desktop (UAC prompt, lock
        # screen) leaves no foreground window readable from our session, and
        # that is itself the most informative thing we could say.
        return out
    out["hwnd"] = hwnd
    try:
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        out["title"] = buf.value or None
    except OSError:
        pass
    pid = _process_of(hwnd)
    if pid is None:
        return out
    out["integrity"] = integrity_of(pid)
    try:
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            try:
                name = ctypes.create_unicode_buffer(260)
                size = wintypes.DWORD(260)
                if k32.QueryFullProcessImageNameW(handle, 0, name,
                                                  ctypes.byref(size)):
                    out["process"] = name.value.rsplit("\\", 1)[-1] or None
            finally:
                k32.CloseHandle(handle)
    except OSError:
        pass
    return out


def snapshot() -> dict:
    """One reading of both halves, for the use log's `state.app` record."""
    return {"elevated": is_elevated(), "foreground": foreground()}


def describe() -> str:
    """The sentence the UIPI alarm prints — built ONLY out of what was
    measured. No branch here produces a cause; the reader is handed the
    facts and the one comparison that is genuinely decidable.

    The comparison that IS decidable: a foreground window at HIGH or SYSTEM
    integrity while we are not elevated is the documented UIPI case, and
    saying so is a measurement, not a hypothesis. Everything else is
    reported as what it is, including "unknown".
    """
    try:
        us = is_elevated()
        fg = foreground()
    except Exception as e:                     # never raise from an error path
        return f"could not measure the environment ({type(e).__name__})"

    ours = ("this process IS elevated" if us
            else "this process is NOT elevated" if us is False
            else "our own elevation could not be read")

    if fg["hwnd"] is None:
        # No readable foreground = the secure desktop, and that IS the answer.
        return (f"{ours}; no foreground window is readable from this session "
                f"— the secure desktop (a UAC prompt or the lock screen) is up, "
                f"which discards injected input by design")

    who = fg["process"] or "an unnamed process"
    title = f' "{fg["title"]}"' if fg["title"] else ""
    level = fg["integrity"] or "an integrity level we could not read"
    line = f"{ours}; the foreground window is {who}{title} (0x{fg['hwnd']:x}) at {level}"

    if us is False and fg["integrity"] in ("high", "system"):
        line += " — that combination IS the UIPI case: Windows discards our input"
    elif fg["integrity"] is None:
        line += (" — the level could not be read, which is what a more "
                 "privileged process looks like from here, but is not proof of one")
    return line
