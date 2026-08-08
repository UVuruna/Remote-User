"""Caret gate: the PC says WHERE the typing lands, or honestly says it cannot.

The owner's report, twice (2026-08-07, screenshots again 2026-08-08): the
phone's keyboard covers exactly the row he is typing into, and the fix that
lifted the whole picture by the keyboard's height carried that row off the top
instead. *"Najoptimalnije rešenje bilo bi da naš program prepozna gde se
nalazi, koja je pozicija na ekranu, kursora koji kuca."*

What this gate defends is not "a caret feature exists" — it is the three ways
this feature can be WORSE than not having it:

1. **A rect normalized against the wrong monitor.** The phone would move its
   picture by an amount computed from a monitor it is not showing. On a
   two-monitor desk that is not a small error, it is a random one.
2. **An unknown caret reported as a position.** Every app that exposes no
   caret would tell the phone "the caret is at the top-left corner", and the
   picture would lift for a row that does not exist. The unknown answer
   therefore carries NO coordinates at all — a client that forgets to test
   `known` must break visibly, not silently do the wrong thing.
3. **A message per read.** This rides the same socket as the video. A caret
   moves when a person types a line; sending one anyway three times a second
   for the life of a connection is the kind of cost the owner went looking
   for in his traffic window.

NOTHING HERE TOUCHES THE OWNER'S DESKTOP. `GetGUIThreadInfo`, `ClientToScreen`
and the whole UI Automation read are faked — he is working at this machine
while these run, and a gate that reads the real caret would also be a gate
whose result depends on which window he happened to click.

Run:  .venv\\Scripts\\python tests/test_caret.py
"""

import asyncio
import ctypes
import ctypes.wintypes as wintypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import (  # noqa: E402
    MEMBER_A, MEMBER_B, THIEF, FakeWs, Raises, focus_guard, fresh_conn,
    layout_with, run_checks, with_win32,
)

import caret  # noqa: E402
import uia  # noqa: E402

# Captured BEFORE any fake is installed. The checks below that exercise the
# real `uia.caret_rect` must put it back first — an earlier check replaces it
# with a spy, and a gate that ends up measuring its own fake proves nothing
# (this project has paid for that mistake once already, in the actions.json
# merge that every guard "verified" against a copy of the shipped file).
_REAL_CARET_RECT = uia.caret_rect
_REAL_UIA_CONTEXT = uia._uia
_REAL_UIA_USER32 = uia.user32

# The monitor the phone is being shown: the SECOND one, deliberately. A caret
# normalized against the virtual desktop, the primary monitor or a bare
# (0, 0, w, h) all pass on a single-monitor fake and are all wrong here.
MONITOR = (1920, 0, 3840, 2160)
OTHER_MONITOR_POINT = (400, 300)


# ═══════════════════════════ THE FAKE DESKTOP ═══════════════════════════
class FakeCaretWin32:
    """The three user32 calls `caret.py` makes, and nothing else.

    `client_caret` is what a real GUITHREADINFO carries: a rect in the CLIENT
    coordinates of the focused child control, which only becomes a screen
    position through that control's own origin. Faking it any other way would
    let a module that forgets the conversion pass."""

    def __init__(self, client_caret=None, origin=(0, 0), tid=77):
        self.client_caret = client_caret     # (hwndCaret, left, top, right, bottom)
        self.origin = origin
        self.tid = tid
        self.threads_asked: list[int] = []

    def GetWindowThreadProcessId(self, hwnd, _pid):      # noqa: N802 — Win32 name
        self.threads_asked.append(hwnd)
        return self.tid

    def GetGUIThreadInfo(self, _tid, ref):               # noqa: N802
        info = ctypes.cast(ref, ctypes.POINTER(caret.GUITHREADINFO)).contents
        if self.client_caret is None:
            info.hwndCaret = 0
            return 1
        handle, left, top, right, bottom = self.client_caret
        info.hwndCaret = handle
        info.rcCaret.left, info.rcCaret.top = left, top
        info.rcCaret.right, info.rcCaret.bottom = right, bottom
        return 1

    def ClientToScreen(self, _hwnd, ref):                # noqa: N802
        point = ctypes.cast(ref, ctypes.POINTER(wintypes.POINT)).contents
        point.x += self.origin[0]
        point.y += self.origin[1]
        return 1


class UiaSpy:
    """`uia.caret_rect` replaced: it answers from a script and COUNTS how
    often it was asked. The count is the whole point of one check — that read
    costs milliseconds of COM on the owner's PC (measured 4 ms), and this loop
    never stops."""

    def __init__(self, rect=None):
        self.rect = rect
        self.calls: list[int] = []

    def install(self):
        uia.caret_rect = self._read
        return self

    def _read(self, hwnd):
        self.calls.append(hwnd)
        return self.rect() if callable(self.rect) else self.rect


class FakeInjector:
    def __init__(self, monitor_rect=MONITOR):
        self.monitor_rect = monitor_rect


def desktop(client_caret=None, origin=(0, 0), uia_rect=None, fg=MEMBER_A):
    """One fake PC: a foreground window, a Win32 caret (or none) and a UIA
    answer (or none). Returns (win32, uia spy, conn)."""
    with_win32(fg=fg, alive=(MEMBER_A, MEMBER_B, THIEF))
    Raises().install()          # nothing on this machine is ever raised
    win32 = FakeCaretWin32(client_caret, origin)
    caret.user32 = win32
    spy = UiaSpy(uia_rect).install()
    conn = fresh_conn()
    return win32, spy, conn


# ═══════════════════ 1. the rect belongs to the shown monitor ═══════════════
def check_the_caret_is_normalized_to_the_shown_monitor() -> bool:
    """A caret at screen (2500, 1100) on a monitor that starts at x=1920 is
    15.1% across it — not 65% across the virtual desktop."""
    desktop(client_caret=(0x55, 80, 100, 82, 125), origin=(2420, 1000))
    message = caret.CaretTracker().poll(None, fresh_conn(), MONITOR, 1.0)
    return (message["known"] is True
            and message["x"] == round((2500 - 1920) / 3840, 4)
            and message["y"] == round(1100 / 2160, 4)
            and message["h"] == round(25 / 2160, 4))


def check_a_caret_on_another_monitor_is_unknown() -> bool:
    """The phone shows ONE monitor. A caret on the other one is not a small
    number outside 0-1 for the page to puzzle over — it is unknown."""
    desktop(client_caret=(0x55, 0, 0, 2, 25), origin=OTHER_MONITOR_POINT)
    message = caret.CaretTracker().poll(None, fresh_conn(), MONITOR, 1.0)
    return (message == {"type": "caret", "known": False, "why": "off-monitor"}
            and "x" not in message and "y" not in message)


# ═══════════════════ 2. unknown is unknown, never (0, 0) ═══════════════════
def check_an_unreadable_caret_is_unknown_and_carries_no_position() -> bool:
    """Neither source can see a caret — the measured answer for several of the
    owner's own apps. The phone must be told exactly that, with no numbers it
    could mistake for a position."""
    desktop(client_caret=None, uia_rect=None)
    message = caret.CaretTracker().poll(None, fresh_conn(), MONITOR, 1.0)
    return (message == {"type": "caret", "known": False, "why": "no-caret"}
            and not any(k in message for k in ("x", "y", "w", "h")))


def check_an_empty_win32_caret_rect_is_not_a_position() -> bool:
    """A GUI thread can own a caret HANDLE whose rect is empty (observed on
    the owner's PC). Zero height is not a place on the screen."""
    desktop(client_caret=(0x55, 0, 0, 0, 0), uia_rect=None)
    message = caret.CaretTracker().poll(None, fresh_conn(), MONITOR, 1.0)
    return message["known"] is False


# ═══════════════════ 3. the message is sent only on a CHANGE ═══════════════
def check_nothing_is_sent_while_nothing_changes() -> bool:
    """Same caret, three reads, one message."""
    desktop(client_caret=(0x55, 80, 100, 82, 125), origin=(2420, 1000))
    tracker = caret.CaretTracker()
    first = tracker.poll(None, fresh_conn(), MONITOR, 1.0)
    return (first is not None
            and tracker.poll(None, fresh_conn(), MONITOR, 1.1) is None
            and tracker.poll(None, fresh_conn(), MONITOR, 1.2) is None)


def check_a_moved_caret_is_sent() -> bool:
    """…and the moment it moves a row, it is."""
    win32, _spy, _conn = desktop(client_caret=(0x55, 80, 100, 82, 125),
                                 origin=(2420, 1000))
    tracker = caret.CaretTracker()
    tracker.poll(None, fresh_conn(), MONITOR, 1.0)
    win32.client_caret = (0x55, 80, 125, 82, 150)      # next row
    moved = tracker.poll(None, fresh_conn(), MONITOR, 1.1)
    return moved is not None and moved["y"] == round(1125 / 2160, 4)


def check_becoming_unknown_is_itself_a_change() -> bool:
    """A caret that goes away must be ANNOUNCED once — otherwise the phone
    holds a lifted picture forever."""
    win32, _spy, _conn = desktop(client_caret=(0x55, 80, 100, 82, 125),
                                 origin=(2420, 1000))
    tracker = caret.CaretTracker()
    tracker.poll(None, fresh_conn(), MONITOR, 1.0)
    win32.client_caret = None
    held = tracker.poll(None, fresh_conn(), MONITOR, 1.0 + caret.HOLD_S / 2)
    gone = tracker.poll(None, fresh_conn(), MONITOR, 1.0 + caret.HOLD_S + 0.1)
    return held is None and gone == {"type": "caret", "known": False,
                                     "why": "no-caret"}


# ═══════════════════ 4. the sources, and what they cost ═══════════════════
def check_uia_answers_when_the_window_has_no_win32_caret() -> bool:
    """The Electron case, and the one that matters most to him: VSCode keeps
    no classic Win32 caret at all — every rect comes from UI Automation."""
    desktop(client_caret=None, uia_rect=(2220, 1248, 995, 25))
    message = caret.CaretTracker().poll(None, fresh_conn(), MONITOR, 1.0)
    return (message["known"] is True
            and message["x"] == round((2220 - 1920) / 3840, 4)
            and message["y"] == round(1248 / 2160, 4))


def check_the_uia_read_is_throttled() -> bool:
    """~4 ms of COM per read, measured. Polling it as fast as the cheap Win32
    read would put a UIA walk on the same socket as the video."""
    _win32, spy, _conn = desktop(client_caret=None, uia_rect=(2000, 100, 2, 25))
    tracker = caret.CaretTracker()
    now = 1.0
    for _ in range(12):                    # 12 polls inside one throttle window
        tracker.poll(None, fresh_conn(), MONITOR, now)
        now += caret.UIA_MIN_INTERVAL_S / 12
    return len(spy.calls) == 1


def check_an_expensive_window_is_read_less_often() -> bool:
    """MEASURED on his PC 2026-08-08: the Claude Code chat box costs 516 ms
    per read where the editor beside it costs 6 ms. A fixed interval would put
    a half-second COM call on a worker thread three times a second for as long
    as he dictates into that box — so a read must buy the silence after it."""
    import time as _time

    def slow_read():
        _time.sleep(0.05)                  # a window that answers slowly
        return (2000, 100, 2, 25)

    _win32, spy, _conn = desktop(client_caret=None)
    spy.rect = slow_read
    tracker = caret.CaretTracker()
    tracker.poll(None, fresh_conn(), MONITOR, 1.0)          # 50 ms → wait 500 ms
    tracker.poll(None, fresh_conn(), MONITOR, 1.0 + caret.UIA_MIN_INTERVAL_S + 0.05)
    return len(spy.calls) == 1


def check_a_popup_stealing_focus_does_not_drop_the_row() -> bool:
    """Measured on his PC 2026-08-08: while he types in VSCode the suggestion
    list takes UIA focus for a sample or two and there is no caret to read.
    The last MEASURED rect stands for a moment — held, never invented."""
    _win32, spy, _conn = desktop(client_caret=None, uia_rect=(2220, 1248, 995, 25))
    tracker = caret.CaretTracker()
    first = tracker.poll(None, fresh_conn(), MONITOR, 1.0)
    spy.rect = None                                     # the popup has focus
    during = tracker.poll(None, fresh_conn(), MONITOR, 1.0 + caret.UIA_MIN_INTERVAL_S)
    return first["known"] is True and during is None


# ═══════════ 5. the UIA read itself: whose caret is it, and is there one ═════
class FakeRange:
    """A UIA text range. `rects` is what it answers plainly; `expanded` is
    what it answers after being expanded to one character — the two are
    separate because a collapsed caret really does answer differently."""

    def __init__(self, rects=(), expanded=()):
        self._rects, self._expanded = list(rects), list(expanded)
        self._is_clone = False

    def GetBoundingRectangles(self):              # noqa: N802 — UIA name
        return self._expanded if self._is_clone else self._rects

    def Clone(self):                              # noqa: N802
        clone = FakeRange(self._rects, self._expanded)
        clone._is_clone = True
        return clone

    def ExpandToEnclosingUnit(self, _unit):       # noqa: N802
        return None


class FakeRect:
    def __init__(self, left, top, width, height):
        self.left, self.top = left, top
        self._w, self._h = width, height

    def width(self):
        return self._w

    def height(self):
        return self._h


class FakeElement:
    """A focused UIA element. `window` is what the walk up to a real window
    handle finds — 0 means "cannot tell", which is what VSCode's suggestion
    chain really answers."""

    def __init__(self, window=0, text_range=None, parent=None):
        self.NativeWindowHandle = window
        self._range = text_range
        self._parent = parent
        if text_range is not None:
            # Only a TEXT control has the method at all. Real `uiautomation`
            # fails on the ATTRIBUTE, not on the call — measured on his PC:
            # "'PaneControl' object has no attribute 'GetTextPattern'" — and a
            # fake that raised on the call instead would push a perfectly
            # normal "this is not a text box" down the module's ERROR path.
            self.GetTextPattern = lambda: self

    def GetParentControl(self):                   # noqa: N802
        return self._parent

    def GetSelection(self):                       # noqa: N802
        return [self._range]


class FakeAuto:
    """The two members `uia.caret_rect` touches on the automation module."""

    class TextUnit:
        Character = 1

    def __init__(self, focused):
        self._focused = focused

    def GetFocusedControl(self):                  # noqa: N802
        return self._focused


def with_uia(focused):
    """Replace the per-thread COM context with a fake one. No COM is
    initialized and no real element is ever read."""
    from contextlib import contextmanager

    @contextmanager
    def fake_uia():
        yield FakeAuto(focused)

    uia.caret_rect = _REAL_CARET_RECT      # the function under test, not a spy
    uia._uia = fake_uia
    uia.user32 = _FakeAncestor()


class _FakeAncestor:
    def GetAncestor(self, hwnd, _flag):           # noqa: N802
        return hwnd


def check_a_caret_whose_window_cannot_be_named_is_still_his() -> bool:
    """MEASURED 2026-08-08: while he types in VSCode the focused element's
    whole chain carries no window handle at all. Treating "cannot tell" as
    "some other window" threw away every caret in the app that matters most
    to him."""
    element = FakeElement(window=0, text_range=FakeRange(
        rects=[FakeRect(300, 1930, 995, 24)]))
    with_uia(element)
    try:
        return uia.caret_rect(MEMBER_A) == (300, 1930, 995, 24)
    finally:
        uia._uia, uia.user32 = _REAL_UIA_CONTEXT, _REAL_UIA_USER32


def check_a_caret_in_another_window_is_refused() -> bool:
    """Keyboard focus is global. A caret that NAMES a different window is not
    the caret of the window the phone is typing into."""
    element = FakeElement(window=THIEF, text_range=FakeRange(
        rects=[FakeRect(300, 1930, 995, 24)]))
    with_uia(element)
    try:
        return uia.caret_rect(MEMBER_A) is None
    finally:
        uia._uia, uia.user32 = _REAL_UIA_CONTEXT, _REAL_UIA_USER32


def check_a_collapsed_caret_is_expanded_to_one_character() -> bool:
    """The Claude Code chat box inside VSCode: its selection answers with an
    EMPTY rect list, and only the range expanded to one character gives
    (1203, 936, 21, 21). Without the expansion that box has no caret at all."""
    element = FakeElement(window=0, text_range=FakeRange(
        rects=[], expanded=[FakeRect(1203, 936, 21, 21)]))
    with_uia(element)
    try:
        return uia.caret_rect(MEMBER_A) == (1203, 936, 21, 21)
    finally:
        uia._uia, uia.user32 = _REAL_UIA_CONTEXT, _REAL_UIA_USER32


def check_an_element_with_no_text_pattern_has_no_caret() -> bool:
    """The suggestion list item itself — focused, and not text."""
    with_uia(FakeElement(window=0, text_range=None))
    try:
        return uia.caret_rect(MEMBER_A) is None
    finally:
        uia._uia, uia.user32 = _REAL_UIA_CONTEXT, _REAL_UIA_USER32


# ═══════════════ 6. it reads the window the phone is typing into ═══════════
def check_the_caret_is_read_from_the_layout_member_not_the_thief() -> bool:
    """WHICH window is being typed into is the focus guard's answer, and the
    caret watch must use it: with a thief in the foreground the row that
    matters is still the layout member's."""
    win32, spy, _conn = desktop(client_caret=None, uia_rect=(2000, 100, 2, 25),
                                fg=THIEF)
    registry = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    conn = fresh_conn(active=0)
    caret.CaretTracker().poll(registry, conn, MONITOR, 1.0)
    return spy.calls == [MEMBER_B] and win32.threads_asked == [MEMBER_B]


def check_looking_at_the_caret_never_raises_a_window() -> bool:
    """The read must be passive. `guard()` can raise a window; a watcher that
    did the same three times a second would be a second focus policy running
    beside the real one — and the owner's desk has paid for that before."""
    with_win32(fg=THIEF, alive=(MEMBER_A, MEMBER_B, THIEF))
    raises = Raises().install()
    caret.user32 = FakeCaretWin32(None)
    UiaSpy(None).install()
    registry = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    target = focus_guard.current_target(registry, fresh_conn(active=0))
    return target == MEMBER_B and raises == []


# ═══════════════════════ 7. the task on a real loop ═══════════════════════
def check_the_watch_sends_one_message_per_change() -> bool:
    """The whole path the phone sees, driven on a real event loop: the task
    sends the caret once, stays silent while it stands still, sends it again
    when it moves — and says nothing at all while the phone is away."""
    async def drive() -> tuple:
        win32, _spy, conn = desktop(client_caret=(0x55, 80, 100, 82, 125),
                                    origin=(2420, 1000))
        caret.POLL_S = 0.005                       # the gate does not wait 150 ms
        ws = FakeWs([])
        task = asyncio.create_task(caret.watch(ws, None, conn, FakeInjector()))
        await asyncio.sleep(0.05)
        after_first = len(ws.sent)
        win32.client_caret = (0x55, 80, 125, 82, 150)
        await asyncio.sleep(0.05)
        after_move = len(ws.sent)
        conn["away"] = "lock"                      # the phone is gone
        win32.client_caret = (0x55, 80, 200, 82, 225)
        await asyncio.sleep(0.05)
        after_away = len(ws.sent)
        task.cancel()
        return after_first, after_move, after_away, ws.sent

    try:
        first, moved, away, sent = asyncio.run(drive())
    finally:
        caret.POLL_S = _REAL_POLL_S
    return (first == 1 and moved == 2 and away == 2
            and sent[0]["type"] == "caret" and sent[0]["known"] is True)


_REAL_POLL_S = caret.POLL_S


CHECKS = [
    ("the caret is normalized to the monitor the phone is shown",
     check_the_caret_is_normalized_to_the_shown_monitor),
    ("a caret on another monitor is unknown, not an out-of-range number",
     check_a_caret_on_another_monitor_is_unknown),
    ("an unreadable caret is unknown and carries NO position",
     check_an_unreadable_caret_is_unknown_and_carries_no_position),
    ("an empty Win32 caret rect is not a position",
     check_an_empty_win32_caret_rect_is_not_a_position),
    ("nothing is sent while nothing changes",
     check_nothing_is_sent_while_nothing_changes),
    ("a moved caret is sent", check_a_moved_caret_is_sent),
    ("becoming unknown is itself a change",
     check_becoming_unknown_is_itself_a_change),
    ("UIA answers for a window with no classic caret (VSCode)",
     check_uia_answers_when_the_window_has_no_win32_caret),
    ("the UIA read is throttled, never one per poll",
     check_the_uia_read_is_throttled),
    ("an expensive window is read less often, not on the same clock",
     check_an_expensive_window_is_read_less_often),
    ("a popup stealing focus does not drop the row",
     check_a_popup_stealing_focus_does_not_drop_the_row),
    ("a caret whose window cannot be named is still read (VSCode)",
     check_a_caret_whose_window_cannot_be_named_is_still_his),
    ("a caret that names ANOTHER window is refused",
     check_a_caret_in_another_window_is_refused),
    ("a collapsed caret is expanded to one character (Claude chat box)",
     check_a_collapsed_caret_is_expanded_to_one_character),
    ("an element with no text pattern has no caret",
     check_an_element_with_no_text_pattern_has_no_caret),
    ("the caret is read from the layout member, not the thief",
     check_the_caret_is_read_from_the_layout_member_not_the_thief),
    ("looking at the caret never raises a window",
     check_looking_at_the_caret_never_raises_a_window),
    ("the watch sends one message per change, and none while away",
     check_the_watch_sends_one_message_per_change),
]


def main() -> int:
    return run_checks("CARET GATE", CHECKS,
                      "the PC says where the typing lands, or says it cannot.")


def test_caret():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
