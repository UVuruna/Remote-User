"""Windows says the instant the foreground moves — instead of us asking.

WHY THIS MODULE EXISTS: [Focus Guard](focus_guard.py) defends the layout the
phone is showing by POLLING the foreground four times a second. That poll is
honest but late — up to 250 ms in which a program that grabbed the keyboard
keeps it, and dictation is exactly the case where late is the same as never
(Android's recognizer delivers a whole utterance at the END of a round, so a
window that holds focus for a quarter of a second while the owner speaks can
still end up with the entire sentence).

Windows already knows. `SetWinEventHook(EVENT_SYSTEM_FOREGROUND)` calls us
2-5 ms after the change, and this module is the thread that receives it: an
out-of-context hook is delivered to the thread that INSTALLED it, through its
own message queue, so it needs a real thread with a real `GetMessage` loop —
which is the whole reason this is a module and not four lines inside the
guard. The guard keeps the policy (what may hold the keyboard); this keeps the
plumbing (how we hear about it).

A LISTENER MAY ONLY SIGNAL (verified 2026-08-07, and it cost a measured 2.99 s
stall to learn). A callback runs INSIDE Windows' own event dispatch, inside
`GetMessage`, on this one thread: everything the desktop does with the
foreground queues behind it. The first version called the guard straight from
here — and the guard can wait on a lock held across a window raise that waits
for a frame to settle. So a callback must hand the work to somebody else and
return, and this module MEASURES that it did: an overrun is an ERROR in the
log, because a hook that is slow to return is one Windows silently detaches,
after which we would believe we have millisecond reaction while running on the
poll alone.

THE POLL STAYS. A hook can be dropped, and `SetWinEventHook` can be refused
outright. Belt and braces — `listen()` reports whether Windows really took the
hook, `event_count()` lets the guard notice a hook that went quiet, and the
0.25 s poll runs either way.

NOTHING OF OURS OUTLIVES US (owner decree 2026-08-05, the same discipline as
the topmost ledger in [Window Manager](window_manager.py)): `stop()` is THE
exit call — idempotent, wired into `ServerController.release_windows()`, which
every exit path already funnels through (server stop, Apply & restart, tray
Quit, Ctrl+C, a console close, `atexit`). A stop whose join times out does NOT
forget the thread: it keeps its identity so the next stop can try again and so
no second hook is ever installed over a live one.
"""

import atexit
import ctypes
import ctypes.wintypes as wintypes
import logging
import threading
import time

# ═══════════════════════════ WIN32 HANDLES ═══════════════════════════
# Our OWN handles on user32/kernel32: the argtypes below are pinned on them (a
# hook handle is a POINTER and the default int return truncates it on 64-bit,
# which would make UnhookWinEvent fail on the way out), and
# `ctypes.windll.user32` is one cached object shared by every module in this
# process — pinning signatures on that would reach into window_manager's calls.
logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


# ═══════════════════════════ WINDOWS FACTS ═══════════════════════════
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
OBJID_WINDOW = 0        # the event is about the window itself, not a child part
WM_QUIT = 0x0012

# void CALLBACK WinEventProc(HWINEVENTHOOK, DWORD event, HWND, LONG idObject,
#                            LONG idChild, DWORD idEventThread, DWORD dwmsTime)
_WINEVENTPROC = ctypes.WINFUNCTYPE(
    None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
    wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)

user32.SetWinEventHook.restype = wintypes.HANDLE
user32.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
                                   _WINEVENTPROC, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD]
user32.UnhookWinEvent.restype = wintypes.BOOL
user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
# GetMessageW returns -1 on error, so it must be read SIGNED — the loop below
# tests "> 0" and an unsigned read would spin forever on a broken queue.
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                               ctypes.c_uint, ctypes.c_uint]


# ═══════════════════════════ TIMINGS ═══════════════════════════
# A listener may only SIGNAL, so this is what "short" means in milliseconds.
# Anything past it runs inside Windows' event dispatch for that long and is
# logged as the defect it is.
CALLBACK_BUDGET_S = 0.010
# The thread only has to report in / return from GetMessage and unhook —
# microseconds of real work. These are deliberately SMALL because they are
# paid on the owner's Quit: `stop()` is called from the Qt UI thread (tray
# Quit) and from the console CTRL handler, whose budget Windows measures in
# seconds. A join that misses is not a hang, it is an orphan we log and retry.
START_TIMEOUT_S = 1.0
STOP_TIMEOUT_S = 0.25


# ═══════════════════════════ THE LISTENER ═══════════════════════════
# One thread per PROCESS, not per connection: a Win32 hook is a process-wide
# resource, and there is only ever one phone (protocol: one device at a time).
# Callers register a callback and drop it again; the thread lives exactly as
# long as somebody is listening.
_lock = threading.RLock()
_callbacks: list = []
_thread: threading.Thread | None = None
_tid: int = 0
_installed = False
_orphaned = False
_events = 0
_ready = threading.Event()


def _dispatch(_hook, event, _hwnd, id_object, _id_child, _event_tid, _time_ms) -> None:
    """The WinEventProc itself — runs ON THE HOOK THREAD, inside GetMessage.

    It is an ANNOUNCEMENT, not data: the hwnd Windows names here may already
    be stale by the time a listener acts, so listeners re-read the foreground
    for themselves. And it is SHORT — a listener that works here holds up
    Windows' own dispatch and risks the hook being detached, so the time spent
    is measured and an overrun is an ERROR."""
    if event != EVENT_SYSTEM_FOREGROUND or id_object != OBJID_WINDOW:
        return
    global _events
    _events += 1
    started = time.perf_counter()
    for callback in tuple(_callbacks):
        try:
            callback()
        except Exception:
            # A listener that throws must not take the hook down with it: the
            # next foreground change still has to be defended.
            logger.exception("A foreground listener raised — the hook stays installed")
    spent = time.perf_counter() - started
    if spent > CALLBACK_BUDGET_S:
        logger.error(
            "A foreground listener took %.0f ms — this runs INSIDE Windows' "
            "own event dispatch, and a hook slow to return is one Windows "
            "detaches without telling us. A listener may only signal.",
            spent * 1000)


def _run() -> None:
    global _tid, _installed
    proc = _WINEVENTPROC(_dispatch)   # a local: it must outlive the hook, and does
    _tid = kernel32.GetCurrentThreadId()
    hook = user32.SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
                                  None, proc, 0, 0, WINEVENT_OUTOFCONTEXT)
    _installed = bool(hook)
    _ready.set()
    if not hook:
        logger.warning("Windows refused the foreground hook (error %s) — the "
                       "layout is defended by the guard's poll alone",
                       ctypes.get_last_error())
        _tid = 0
        return
    msg = wintypes.MSG()
    try:
        # Out-of-context WinEvents are delivered to THIS thread while it pumps;
        # WM_QUIT from stop() is what ends the loop.
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnhookWinEvent(hook)
        _installed = False


def listen(callback) -> bool:
    """Call `callback()` (no arguments) whenever the foreground window changes.

    **The callback may only signal** — see this module's docstring; it runs
    inside Windows' dispatch and is timed.

    Starts the listener thread on the first caller. Returns True when Windows
    really took the hook and False when it refused — the caller then knows it
    is running on its backstop alone, and says so in the log. Blocking (thread
    start + a bounded wait): call it through `asyncio.to_thread`."""
    with _lock:
        if callback not in _callbacks:
            _callbacks.append(callback)
        _start()
        return _installed


def release(callback) -> None:
    """Drop one listener; the thread ends with the last of them. Blocking —
    call it through `asyncio.to_thread`."""
    with _lock:
        if callback in _callbacks:
            _callbacks.remove(callback)
        if _callbacks:
            return
        stop()


def stop() -> None:
    """THE exit call — no hook, no thread, nothing left behind.

    Idempotent by design: it is reached from `ServerController.release_windows`
    (server stop, Apply & restart, tray Quit, Ctrl+C, a console close, Qt's
    aboutToQuit), from `atexit`, and from `release()` when the last listener
    goes — being called three times on the way out is the point.

    A join that TIMES OUT does not forget the thread. Clearing the identity
    there was a real leak (found by an independent probe 2026-08-07): the hook
    stayed installed, its thread stayed alive with an unreachable tid, and the
    next `listen()` cheerfully started a SECOND one over it. The thread keeps
    its place in the book instead, is named in the log, and the next stop
    tries again."""
    global _thread, _tid, _orphaned
    with _lock:
        _callbacks.clear()
        thread = _thread
        if thread is None:
            return
        if not thread.is_alive():
            _thread, _tid, _orphaned = None, 0, False
            return
        if _tid and not user32.PostThreadMessageW(_tid, WM_QUIT, 0, 0):
            logger.warning("WM_QUIT to the foreground-hook thread was refused "
                           "(error %s)", ctypes.get_last_error())
        thread.join(STOP_TIMEOUT_S)
        if thread.is_alive():
            _orphaned = True
            logger.error(
                "The foreground-hook thread (tid %s) did not stop within "
                "%.2fs — its hook is STILL INSTALLED. It is kept in the book "
                "so the next stop can try again and so no second hook is ever "
                "installed over it.", _tid, STOP_TIMEOUT_S)
            return                        # identity KEPT, deliberately
        _thread, _tid, _orphaned = None, 0, False


def installed() -> bool:
    """Does Windows currently hold a hook of ours? (The guard uses this to
    tell "no hook" apart from "a hook that has gone quiet".)"""
    return _installed


def event_count() -> int:
    """How many foreground changes the hook has announced. A number that does
    not move while the foreground demonstrably did is how a DETACHED hook
    becomes visible — Windows never says it dropped one."""
    return _events


def _start() -> None:
    """Caller holds `_lock`."""
    global _thread, _orphaned
    if _thread is not None and _thread.is_alive():
        if _orphaned:
            logger.warning("Riding the foreground-hook thread a previous stop "
                           "could not join (tid %s) — its hook is still live, "
                           "so no second one is installed", _tid)
        return
    _orphaned = False
    _ready.clear()
    # daemon: a stop() we somehow never reached may cost us the hook handle at
    # process death, but it may NEVER hold the process open — the owner's Quit
    # has to end the app.
    _thread = threading.Thread(target=_run, name="foreground-hook", daemon=True)
    _thread.start()
    if not _ready.wait(START_TIMEOUT_S):
        logger.error("The foreground-hook thread did not report in within %.0fs",
                     START_TIMEOUT_S)


atexit.register(stop)
