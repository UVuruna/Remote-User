"""The clipboard lives on BOTH devices (owner order, task 182, ~2026-08-11
17:05): everything copied lands on both the PC's clipboard and the phone's.

Two paths reach the phone:

1. **Immediate, on an injected Copy/Cut.** `after_copy_chord()` is called
   right after `injector.press_chord("ctrl+c" | "ctrl+x")` returns — the app
   that received the chord has had a moment to fill the clipboard, so the
   text is read back and pushed straight to the phone.
2. **Live, for a copy made AT THE PC.** `watch()` is one task per connection
   (started exactly like `focus_guard.watch` / `presence.watchdog`) that
   listens for the PC's clipboard changing while a phone session is live —
   `AddClipboardFormatListener` on a message-only window, following the same
   listener-thread shape as [Focus Hook](focus_hook.py): the window's
   procedure runs on a dedicated thread inside `GetMessage`, and it may only
   SIGNAL — the read (`OpenClipboard`/`GetClipboardData`) and the push happen
   on a worker thread, never inside Windows' own message dispatch.

TEXT ONLY for now (owner scoping, task 182): `CF_UNICODETEXT` in, plain text
out. Non-text formats (images, files) are OUT of scope — a later round can
widen `read_text()`'s format list without touching the push/dedup machinery
below it.

HONEST LIMIT (Android): the shell can only write ITS OWN app's clipboard
while the app is the FOREGROUND app — true while the session streams, false
during an away. A push that arrives while the page is hidden therefore
CANNOT be handed to the shell — there is nothing to hand it to; the socket
itself is usually gone (constraint 8: the client closes the WebSocket on
hide, excursions being the one case that lingers). So a push that cannot
reach a visible page is held as `_pending` — module-level, not per-connection,
because a hidden page has typically already dropped its socket and a fresh
one starts the conn dict over — and is delivered as the very first thing the
next connection (or the next non-away message on a lingering excursion
socket) does. Only the LATEST pending text survives a hidden stretch: a
second copy while away must not queue behind the first, and neither may
ever be silently dropped.

LOOP GUARD: one shared `_last_text` remembers the last value already known
to both sides, however it got there — pushed to the phone, or written to the
PC clipboard on the phone's behalf (`note_written`, called by
`content.paste_text`). Anything read back that matches it is a value we
already accounted for, not a fresh copy, and is never re-sent. This also
absorbs the natural race between path 1 and path 2: an injected Ctrl+C fires
the SAME `WM_CLIPBOARDUPDATE` the live listener sees, and whichever of the
two reads it first sets `_last_text` for the other.
"""

import asyncio
import ctypes
import ctypes.wintypes as wintypes
import logging
import threading
import time

logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ═══════════════════════════ WINDOWS FACTS ═══════════════════════════
WM_CLIPBOARDUPDATE = 0x031D
WM_DESTROY = 0x0002
WM_QUIT = 0x0012
HWND_MESSAGE = -3           # message-only window — no UI, never visible
CF_UNICODETEXT = 13
GHND = 0x0042

WNDPROCTYPE = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROCTYPE),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                  wintypes.LPARAM]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
# 64-bit handles: the ctypes default (c_int) TRUNCATES them — GetClipboardData
# returning a clipped HANDLE and GlobalLock dereferencing it was a live access
# violation in the input-pipeline gate, not a theory.
user32.GetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.OpenClipboard.argtypes = [wintypes.HWND]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.AddClipboardFormatListener.argtypes = [wintypes.HWND]
user32.RemoveClipboardFormatListener.argtypes = [wintypes.HWND]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                               ctypes.c_uint, ctypes.c_uint]

CLASS_NAME = "RemoteUserClipboardListener"

# ═══════════════════════════ TIMINGS ═══════════════════════════
START_TIMEOUT_S = 1.0
STOP_TIMEOUT_S = 0.25
# The app that received our injected Ctrl+C/Ctrl+X needs a beat to actually
# fill the clipboard — SendInput returns as soon as the keys are queued, not
# once the target has processed them.
COPY_SETTLE_TRIES = 6
COPY_SETTLE_STEP_S = 0.03
OPEN_RETRIES = 5


# ═══════════════════════════ READING TEXT ═══════════════════════════
def read_text() -> str | None:
    """The PC clipboard's plain text, or None (empty / not text / locked
    after retries). Text-only, per the owner's scoping of task 182."""
    for attempt in range(OPEN_RETRIES):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.02 * (attempt + 1))
    else:
        return None
    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        locked = kernel32.GlobalLock(handle)
        if not locked:
            return None
        try:
            text = ctypes.wstring_at(locked)
        finally:
            kernel32.GlobalUnlock(handle)
        return text
    finally:
        user32.CloseClipboard()


# ═══════════════════════════ DEDUP / LOOP GUARD ═══════════════════════════
_lock = threading.RLock()
_last_text: str | None = None
_pending: str | None = None


def note_written(text: str) -> None:
    """Call right after writing `text` to the PC clipboard ON THE PHONE'S
    BEHALF (`content.paste_text`). Marks it known, so the live listener
    (path 2) does not read its own echo and push it straight back."""
    global _last_text
    if not text:
        return
    with _lock:
        _last_text = text


def _fresh(text: str | None) -> bool:
    with _lock:
        if not text or text == _last_text:
            return False
        return True


def _remember(text: str) -> None:
    global _last_text
    with _lock:
        _last_text = text


def _hidden(conn: dict | None) -> bool:
    """The page cannot receive a push right now: no connection at all, or one
    that has announced itself away (excursion) since the last real message."""
    return conn is None or bool(conn.get("away"))


async def _push(ws, conn: dict | None, text: str) -> None:
    """Send `text` now if the page can see it, else hold it as the one
    pending value (task 182 honest limit — Android can only write its own
    clipboard while it is the foreground app)."""
    global _pending
    if ws is None or _hidden(conn):
        with _lock:
            _pending = text   # latest wins — never queued, never dropped
        logger.info("Clipboard change held for the phone (page not visible)")
        return
    try:
        import json
        await ws.send_text(json.dumps({"type": "clipboard", "text": text}))
    except Exception:
        logger.exception("Could not push clipboard text to the phone")
        with _lock:
            _pending = text


async def flush_pending(ws) -> None:
    """Call as the FIRST thing a fresh connection does (or on the first real
    message of a lingering excursion socket that just came back): if a
    clipboard push was held while the phone could not see it, it goes out
    now — the LATEST one only."""
    global _pending
    with _lock:
        text, _pending = _pending, None
    if text is not None and ws is not None:
        await _push(ws, {"away": False}, text)


# ═══════════════════════════ PATH 1: AFTER AN INJECTED COPY/CUT ═══════════
_COPY_CHORDS = frozenset({"ctrl+c", "ctrl+x"})


async def after_copy_chord(ws, conn: dict | None, chord: str) -> None:
    """Called right after `injector.press_chord(chord)` for the Edit set's
    Copy/Cut. Reads the PC clipboard back and pushes it to the phone."""
    if chord.lower().strip() not in _COPY_CHORDS:
        return

    def _read_settled() -> str | None:
        for _ in range(COPY_SETTLE_TRIES):
            text = read_text()
            if _fresh(text):
                return text
            time.sleep(COPY_SETTLE_STEP_S)
        return None

    text = await asyncio.to_thread(_read_settled)
    if text is None:
        return
    _remember(text)
    await _push(ws, conn, text)


# ═══════════════════════════ PATH 2: THE LIVE PC-SIDE LISTENER ═══════════
# One thread for the whole process, like focus_hook — a Win32 clipboard
# listener is process-wide, and the protocol only ever has one phone.
_thread: threading.Thread | None = None
_tid: int = 0
_hwnd: int = 0
_ready = threading.Event()
_thread_lock = threading.RLock()
_watchers = 0


def _wndproc_factory(on_update):
    def proc(hwnd, msg, wparam, lparam):
        if msg == WM_CLIPBOARDUPDATE:
            try:
                on_update()
            except Exception:
                logger.exception("Clipboard listener callback raised")
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
    return WNDPROCTYPE(proc)


def _run(on_update) -> None:
    global _tid, _hwnd
    _tid = kernel32.GetCurrentThreadId()
    wndproc = _wndproc_factory(on_update)   # local: must outlive the window

    wc = WNDCLASSW()
    wc.lpfnWndProc = wndproc
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.lpszClassName = CLASS_NAME
    # A previous run's class can still be registered if the process never
    # unregistered it (an orphaned stop, mirroring focus_hook's own honesty
    # about a join that times out) — that failure is harmless here, so it is
    # not fatal, only logged once at debug volume via the return value.
    user32.RegisterClassW(ctypes.byref(wc))

    hwnd = user32.CreateWindowExW(0, CLASS_NAME, "RemoteUserClipboard", 0,
                                  0, 0, 0, 0, HWND_MESSAGE, None, wc.hInstance, None)
    if not hwnd:
        logger.warning("Could not create the clipboard listener window "
                       "(error %s) — live PC->phone clipboard sync is off "
                       "this run; the injected-Copy push still works",
                       ctypes.get_last_error())
        _tid = 0
        _ready.set()
        return
    _hwnd = hwnd
    if not user32.AddClipboardFormatListener(hwnd):
        logger.warning("Windows refused AddClipboardFormatListener (error %s)"
                       " — live PC->phone clipboard sync is off this run",
                       ctypes.get_last_error())
        user32.DestroyWindow(hwnd)
        _hwnd, _tid = 0, 0
        _ready.set()
        return
    _ready.set()
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.RemoveClipboardFormatListener(hwnd)
        user32.DestroyWindow(hwnd)
        _hwnd = 0


def _start(on_update) -> None:
    global _thread
    with _thread_lock:
        if _thread is not None and _thread.is_alive():
            return
        _ready.clear()
        _thread = threading.Thread(target=_run, args=(on_update,),
                                   name="clipboard-listener", daemon=True)
        _thread.start()
        if not _ready.wait(START_TIMEOUT_S):
            logger.error("Clipboard listener thread did not report in within %.0fs",
                         START_TIMEOUT_S)


def _stop() -> None:
    global _thread, _tid
    with _thread_lock:
        thread = _thread
        if thread is None:
            return
        if not thread.is_alive():
            _thread, _tid = None, 0
            return
        if _tid and not user32.PostThreadMessageW(_tid, WM_QUIT, 0, 0):
            logger.warning("WM_QUIT to the clipboard listener was refused (error %s)",
                           ctypes.get_last_error())
        thread.join(STOP_TIMEOUT_S)
        if thread.is_alive():
            logger.error("The clipboard listener thread did not stop within %.2fs",
                         STOP_TIMEOUT_S)
            return   # identity kept, deliberately — mirrors focus_hook
        _thread, _tid = None, 0


async def watch(ws, conn: dict) -> None:
    """One task per connection (started in web.py alongside focus_guard.watch
    and presence.watchdog): while THIS phone session is live, a copy made AT
    THE PC is read back and pushed to it. Never runs with no client connected
    — the task exists only for the lifetime of one connection — and stops
    cleanly with it (server stop cancels every per-connection task, same as
    every other `watch()` in this file's family)."""
    global _watchers
    loop = asyncio.get_running_loop()
    woken = asyncio.Event()

    def _on_update() -> None:
        # Runs ON THE LISTENER THREAD, inside GetMessage — signal only,
        # exactly like focus_hook's WinEventProc.
        loop.call_soon_threadsafe(woken.set)

    with _thread_lock:
        _watchers += 1
    _start(_on_update)
    try:
        while True:
            await woken.wait()
            woken.clear()
            text = await asyncio.to_thread(read_text)
            if not _fresh(text):
                continue
            _remember(text)
            await _push(ws, conn, text)
    finally:
        with _thread_lock:
            _watchers -= 1
            if _watchers <= 0:
                _watchers = 0
                _stop()
