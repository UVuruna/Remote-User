"""Where the TYPING CARET is on the PC screen — and an honest "I cannot see it".

WHY THIS MODULE EXISTS (owner report 2026-08-07, screenshots again 2026-08-08,
so this is a REPEAT and the process half is written down beside it): the
phone's soft keyboard covers the bottom of its own screen, and the row he is
typing into is somewhere on the PC's. Two guesses were shipped before this
module and both were wrong in the same way — they moved the picture by a
CONSTANT and never asked where the text actually was:

* squeeze/lift the canvas by the keyboard's height — fine for a box at the
  BOTTOM of the PC screen, and for a box at the TOP it carried the very row he
  was watching off the screen (`kbShift`, withdrawn by the owner 2026-08-07);
* leave it alone — and the keyboard covers exactly the row he types into.

His own instruction is this module's specification, in his words:
*"Najoptimalnije rešenje bilo bi da naš program prepozna gde se nalazi, koja
je pozicija na ekranu, kursora koji kuca."* The PC is the only side that can
know it, so the PC says it and the phone decides what to do with it.

THE HONEST HALF IS THE POINT. Some apps expose no caret at all, and a feature
that pretends otherwise is worse than one that says nothing: the picture would
jump to a rect that means nothing. So the answer is either a MEASURED rect or
`known: false` — never a default, never (0, 0). The phone's rule then follows
from the truth it is given: no caret ⇒ do not move the picture.

WHAT IT ACTUALLY READS (measured on the owner's machine, 2026-08-08, three
read-only sampling runs over his real desktop while he worked):

| source | verdict on HIS apps |
|---|---|
| `GetGUIThreadInfo().rcCaret` (classic Win32 caret) | NOT ONE hit in ~3 minutes across VSCode, Chrome, Explorer, Paint, Spotify, Snipping Tool. Kept — it is the cheap, exact answer for classic Win32 edit controls (Notepad, dialogs) and it costs microseconds — but on this desktop it fires for nothing. |
| UIA `TextPattern.GetSelection()` | VSCode's editor answers with the CARET'S LINE — e.g. `(300, 1248, 995, 25)`, and the `top` follows the row he types on (1130 → 1248 → 1272 → 1296). Chrome's page document answers with a 1×1 caret box. |
| the same, range `ExpandToEnclosingUnit(Character)` | the LOAD-BEARING fallback: the Claude Code chat box inside VSCode returns an EMPTY rect list for its collapsed caret and only the expanded range gives `(1203, 936, 21, 21)`. |

So the answer to "do Electron apps expose anything" is: **VSCode does, and it
is the row, which is exactly what the keyboard has to clear.** What VSCode
does NOT give is a 1-px caret — its accessibility surface is a proxy element
literally named "The editor is not accessible…" — and the row is better for
this purpose than the caret pixel would be.

WHAT THE MEASUREMENT ALSO FOUND, and why `HOLD_S` exists: while he types in
VSCode the suggestion list takes UIA focus on nearly every keystroke
(`ListItemControl 'prave, Text'`, no text pattern at all), and a rect that was
there 200 ms ago is still where the picture should sit. Reporting unknown the
instant a popup takes focus would make the phone's picture drop and lift again
mid-word. The last MEASURED rect is therefore held; it is never invented, only
kept.

AND IT FOUND A BUG BEFORE THE OWNER COULD (2026-08-08). Running this module
read-only against his real desktop answered `no-caret` for 150 seconds while
he typed in VSCode. The cause was a rule that looked obviously right on
paper — "use the caret only if the focused element belongs to the window we
are watching" — and that in fact discards every caret in his main app: the
whole element chain under those suggestion items carries NO window handle at
all, so "cannot tell" was being read as "someone else's". A window that cannot
be NAMED is now accepted; only a window that names a DIFFERENT one is refused.
After the fix the same run reported 11 caret positions in 45 seconds, from the
editor and from the Claude Code chat box. A gate that only ever ran against
fakes would have stayed green through all of it.

Split out of [Focus Guard](focus_guard.py) rather than added to it (THE
STRUCTURE LAW): that module decides WHERE typed input goes and defends it —
this one only ever LOOKS, four times a second, and must never raise a window
or take a lock while doing it.
"""

import asyncio
import ctypes
import ctypes.wintypes as wintypes
import json
import logging
import time

import focus_guard
import uia

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32


# ═══════════════════════════ TIMINGS ═══════════════════════════
# The cheap Win32 read runs at this rate; it is microseconds of ctypes.
POLL_S = 0.15
# The UI Automation read is the expensive one — MEASURED on the owner's PC
# 2026-08-08 against his own VSCode: GetFocusedControl plus the walk up to the
# owning window, median 5.3 ms (39.7 ms on the very first, COM-warming call);
# the text read itself 0.6 ms. This rides the same socket as the stream, so it
# may never become a per-frame cost. A caret that answers a third of a second
# late is invisible to a person; a stream that stutters is not.
UIA_MIN_INTERVAL_S = 0.3
# …and the FLOOR is not enough by itself, because that 4 ms is not what every
# window costs. MEASURED the same day on his PC: reading the caret of the
# Claude Code chat box (a VSCode webview) took 516 ms, 532 ms, 516 ms — while
# the editor beside it answered in 6 ms. A fixed interval would have put a
# half-second COM call on a worker thread three times a second for as long as
# he dictated into that box. So every read PAYS FOR ITSELF: the next one waits
# at least this many times what the last one cost, which holds this feature to
# ~10% of one background thread whatever window he is typing into.
UIA_DUTY_FACTOR = 10
# How long the last MEASURED rect survives after the caret stops being
# readable. Not a comfort setting — MEASURED cause, on his PC while he typed
# Serbian prose into VSCode on 2026-08-08: the editor's own element holds UIA
# focus only in bursts, because the word-suggestion list takes it on nearly
# every keystroke (`ListItemControl 'prave, Text'`, no text pattern at all)
# and gives it back a moment later. Reporting unknown in each of those gaps
# would drop and re-lift the phone's picture several times a sentence. What
# is held is the row he is typing IN, and that row does not move while a
# suggestion popup is open — it moves when he presses Enter, and the popup
# closes with it.
HOLD_S = 4.0


# ═══════════════════════════ WINDOWS FACTS ═══════════════════════════
class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", wintypes.RECT)]


def _win32_caret(hwnd: int) -> tuple[int, int, int, int] | None:
    """The classic Win32 caret of `hwnd`'s GUI thread, in SCREEN pixels — or
    None, which on the owner's desktop is the answer for every app he uses.

    `rcCaret` is relative to the client area of `hwndCaret` (which is the
    focused CHILD control, not the window we asked about), so the conversion
    to screen coordinates must use that handle and no other."""
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    if not tid:
        return None
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
        return None
    caret = int(info.hwndCaret or 0)
    if not caret:
        return None
    r = info.rcCaret
    width, height = r.right - r.left, r.bottom - r.top
    if height <= 0:
        # A thread can own a caret handle whose rect is empty (observed on the
        # owner's PC). An empty rect is not a position — it is a "no".
        return None
    point = wintypes.POINT(r.left, r.top)
    if not user32.ClientToScreen(caret, ctypes.byref(point)):
        return None
    return (point.x, point.y, max(width, 1), height)


# ═══════════════════════════ THE MESSAGE ═══════════════════════════
# The phone is told one of exactly two things, and the unknown carries NO
# coordinates at all — deliberately. A client that forgets to test `known`
# then reads `undefined` and breaks visibly, instead of quietly lifting its
# picture to the top-left corner of the screen, which is what a (0, 0)
# "unknown" would mean to it. Reasons are named so his log can say WHY the
# feature did nothing for a given app.
def unknown(why: str) -> dict:
    """The honest answer: we could not see the caret, and this is why."""
    return {"type": "caret", "known": False, "why": why}


def _normalized(rect: tuple[int, int, int, int],
                mon_rect: tuple[int, int, int, int]) -> dict:
    """A screen-pixel caret rect as the phone reads coordinates: 0-1 inside
    the monitor it is being shown. A caret on ANOTHER monitor is not on the
    picture the phone is looking at, so it is unknown there — not a number
    outside 0-1 that the page would have to guess about."""
    left, top, width, height = mon_rect
    if width <= 0 or height <= 0:
        return unknown("no-monitor")
    x, y, w, h = rect
    cx, cy = x + w / 2, y + h / 2
    if not (left <= cx < left + width and top <= cy < top + height):
        return unknown("off-monitor")
    return {"type": "caret", "known": True,
            "x": round((x - left) / width, 4),
            "y": round((y - top) / height, 4),
            "w": round(w / width, 4),
            "h": round(h / height, 4)}


# ═══════════════════════════ THE WATCH ═══════════════════════════
class CaretTracker:
    """One per connection: reads the caret and answers with a message ONLY
    when the answer changed.

    Change detection is the whole reason this is an object. The caret is read
    three times a second for the life of a connection, and it rides the same
    socket as the video — a message per read would be a per-frame cost for a
    thing that moves when a person types a line, i.e. rarely.

    `now` is passed in rather than read here so the gate can drive the hold
    without sleeping through it."""

    def __init__(self) -> None:
        self._last: dict | None = None      # what the phone was last told
        self._rect: tuple | None = None     # last MEASURED rect (screen px)
        self._rect_at = 0.0                 # when it was measured
        self._uia_next = -1e9               # earliest next UIA read (throttle)
        self._uia_rect: tuple | None = None
        self._uia_hwnd = 0

    def poll(self, layouts, conn: dict, mon_rect: tuple[int, int, int, int],
             now: float) -> dict | None:
        """The message to send, or None when nothing changed. Blocking (Win32
        and possibly COM) — call it through `asyncio.to_thread`."""
        message = self._read(layouts, conn, mon_rect, now)
        if message == self._last:
            return None
        self._last = message
        return message

    def _read(self, layouts, conn: dict, mon_rect, now: float) -> dict:
        # WHICH window is being typed into is not this module's question —
        # the focus guard already answers it, and re-deriving it here is how
        # two answers to one question start to disagree.
        hwnd = focus_guard.current_target(layouts, conn)
        if not hwnd:
            return unknown("no-window")
        rect = self._caret_rect(hwnd, now)
        if rect is not None:
            self._rect, self._rect_at = rect, now
            return _normalized(rect, mon_rect)
        if self._rect is not None and now - self._rect_at < HOLD_S:
            # Held, not invented: this rect WAS measured, moments ago. See
            # HOLD_S — the suggestion popup is the reason.
            return _normalized(self._rect, mon_rect)
        self._rect = None
        return unknown("no-caret")

    def _caret_rect(self, hwnd: int, now: float) -> tuple | None:
        """The caret of `hwnd` in screen pixels: the classic Win32 caret when
        the app keeps one, else UI Automation's text selection — throttled,
        because that one costs milliseconds and this loop is continuous."""
        rect = _win32_caret(hwnd)
        if rect is not None:
            return rect
        if hwnd == self._uia_hwnd and now < self._uia_next:
            return self._uia_rect
        self._uia_hwnd = hwnd
        started = time.monotonic()
        self._uia_rect = uia.caret_rect(hwnd)
        cost = time.monotonic() - started
        # Every read buys the silence that follows it (see UIA_DUTY_FACTOR):
        # a 6 ms window is re-read three times a second, a 516 ms one every
        # five seconds. The expensive window is the one the phone can least
        # afford to make expensive — it shares this machine with the encoder.
        self._uia_next = now + max(UIA_MIN_INTERVAL_S, cost * UIA_DUTY_FACTOR)
        return self._uia_rect


async def watch(ws, layouts, conn: dict, injector) -> None:
    """One task per connection: tell the phone where the caret is whenever
    that answer CHANGES, and nothing at all in between.

    It lives here rather than in the web layer for the same reason
    `presence.watchdog` and `focus_guard.watch` do — the loop is this
    module's subject, and the web layer's job is only to start and cancel it.

    The read is done on a worker thread: Win32 and COM both block, and this
    task shares an event loop with the video.

    It goes quiet while the phone is away (an excursion or a leave). Nobody is
    looking at the picture then, so nothing has to be measured about where the
    keyboard would sit on it — and the UIA read is the most expensive thing in
    this file."""
    tracker = CaretTracker()
    while True:
        if conn.get("away") or conn.get("left"):
            await asyncio.sleep(POLL_S)
            continue
        try:
            message = await asyncio.to_thread(
                tracker.poll, layouts, conn, injector.monitor_rect, time.monotonic())
            if message is not None:
                await ws.send_text(json.dumps(message))
        except RuntimeError:
            return   # socket closed under us — the receive loop logs the disconnect
        await asyncio.sleep(POLL_S)
