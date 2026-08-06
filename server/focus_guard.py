"""The focus guard: what the phone types lands where the owner is looking.

WHY THIS MODULE EXISTS (owner report 2026-08-06, and the report itself is the
evidence): he dictates into a text box on the PC through the phone's Mic, and
mid-sentence the rest of his words appear in a DIFFERENT window — another
agent's session. He had to come back three times in one evening to say so, and
one of those stray sentences is still sitting in the wrong conversation.

The app never noticed, and could not have: `SendInput` has no target. Every
keystroke we inject goes to whatever window Windows currently calls the
FOREGROUND, so anything on this PC that takes focus while he speaks — an app
launching, a dialog appearing, a build finishing, another agent's editor
window — silently takes his sentence with it. Between two spoken utterances
there is no signal, no error and no way for the phone to know: the stream
keeps showing the PC, and the text simply grows somewhere else.

So the target stops being "whatever has focus" and becomes something the
server names before every keystroke:

1. **In a layout, the fence is the layout itself.** The phone is looking at
   that layout's member windows and at nothing else, so its keyboard may reach
   nothing else. Foreground outside the layout ⇒ the guard hands focus back to
   the member the phone was last typing into, and only then injects.
2. **At the full desktop there is no fence, so the guard builds one.** The
   window that had focus when the typing began IS the target, and it is
   re-armed by the things that legitimately choose a window: a click the phone
   injected, a layout switch, `next_input` (`retarget()`). A thief that grabs
   focus between two utterances arms nothing.
3. **A dialog of the target is the target.** A save/open dialog is a window of
   its own and would fail both tests above, so ownership is walked up
   (`GW_OWNER`): a modal the owner is typing into belongs to the window that
   raised it. Process identity deliberately is NOT used — every VSCode window
   shares one process, and one of those windows is exactly the thief.
4. **The thief is NAMED in the log** (exe + title), every single time. The app
   being the last to find out is what made this bug cost three trips back to
   the phone, and a restored keystroke that logs nothing would only hide the
   next cause.

Split out of [Web Layer] on 2026-08-06 (THE STRUCTURE LAW): "where does typed
input land" is one responsibility with its own rules and its own gate
(`tests/test_focus_guard.py`), not an `if` in the message dispatcher.
"""

import asyncio
import logging
import time

import window_manager

logger = logging.getLogger(__name__)


# ═══════════════════════════ TIMINGS ═══════════════════════════
# How often the layout's focus is DEFENDED, not merely checked when a key
# arrives (owner 2026-08-06, shouting, after the guard below was not enough:
# "kada uhvatimo fokus lejauta ne može nikakav program da izbaci fokus".
# Dictation is the case that proves it — Android's recognizer hands over a
# whole utterance at the END of a round, so a program that grabs focus while
# he speaks does not misplace one character, it silently discards half an
# hour of speech; by the time a key finally arrives there is nothing left to
# put anywhere. A defence that waits for a keystroke is therefore too late.)
WATCH_POLL_S = 0.25
# One thief, one log line per this many seconds. An app that fights for the
# foreground every 100 ms must not turn the server log into its own diary.
STEAL_LOG_QUIET_S = 5.0


# ═══════════════════════════ WINDOWS FACTS ═══════════════════════════
GW_OWNER = 4
_OWNER_HOPS = 8   # a dialog on a dialog on a dialog is still someone's; a loop is not


def _foreground() -> int:
    return int(window_manager.user32.GetForegroundWindow() or 0)


def _owner_root(hwnd: int) -> int:
    """The top window of `hwnd`'s owner chain — a modal dialog resolves to the
    window that raised it. This is what lets the owner type into VSCode's Save
    dialog without the guard yanking focus back out of it."""
    seen = hwnd
    for _ in range(_OWNER_HOPS):
        nxt = int(window_manager.user32.GetWindow(seen, GW_OWNER) or 0)
        if not nxt or nxt == seen:
            break
        seen = nxt
    return seen


def _refocus(hwnd: int) -> None:
    """Put the keyboard back on `hwnd` as cheaply as it can be done. A layout
    member is already placed and already topmost, so the full
    `raise_window` — restore, reposition, wait for the frame to settle — is
    both unnecessary and too slow to run four times a second. The full stack
    is still the fallback: it is what beats Windows' foreground lock when a
    plain call is refused."""
    u = window_manager.user32
    if u.IsIconic(hwnd):
        window_manager.raise_window(hwnd)   # minimized: it needs the full job
        return
    if u.SetForegroundWindow(hwnd):
        return
    fg = u.GetForegroundWindow()
    if fg:
        fg_tid = u.GetWindowThreadProcessId(fg, None)
        our_tid = window_manager.kernel32.GetCurrentThreadId()
        u.AttachThreadInput(our_tid, fg_tid, True)
        u.BringWindowToTop(hwnd)
        ok = u.SetForegroundWindow(hwnd)
        u.AttachThreadInput(our_tid, fg_tid, False)
        if ok:
            return
    window_manager.raise_window(hwnd)


def describe(hwnd: int) -> str:
    """`exe "title" (0x…)` — the log line that finally names a focus thief.
    Uses window_manager's own readers (same layer, one implementation)."""
    if not hwnd:
        return "no window"
    return (f'{window_manager._process_name(hwnd) or "?"} '
            f'"{window_manager._title(hwnd)[:60]}" ({hwnd:#x})')


# ═══════════════════════════ THE TARGET ═══════════════════════════
def retarget(conn: dict) -> None:
    """The owner just chose a window HIMSELF — a click the phone injected, a
    layout switch, `next_input`. The next keystroke re-reads the foreground
    instead of enforcing the previous target. Focus thieves arm nothing:
    they never come through a message."""
    conn["pin_stale"] = True


def _active_layout(layouts, conn: dict):
    index = conn.get("active")
    if layouts is None or index is None or not 0 <= index < len(layouts.layouts):
        return None
    lay = layouts.layouts[index]
    return lay if lay.members else None


def _accept(conn: dict, lay, hwnd: int) -> int:
    conn["pin"], conn["pin_stale"] = hwnd, False
    if lay is not None:
        lay.last_member = hwnd   # survives this connection — an excursion drops it
    return hwnd


def _log_steal(conn: dict, fg: int, target: int, where: str) -> None:
    """Name the thief — throttled per thief, because one that fights for the
    foreground in a loop would otherwise write the log by itself."""
    now = time.monotonic()
    last_hwnd, last_at = conn.get("steal_log", (0, 0.0))
    if fg == last_hwnd and now - last_at < STEAL_LOG_QUIET_S:
        return
    conn["steal_log"] = (fg, now)
    logger.error("Focus left %s — %s took it; handing it back to %s",
                 where, describe(fg), describe(target))


def guard(layouts, conn: dict, typing: bool = True) -> int:
    """Make sure the keyboard sits on the owner's target, and return that
    target's hwnd. Blocking (Win32 + a possible raise) — call it through
    `asyncio.to_thread`.

    `typing=True` — before injecting, on every message that TYPES.
    `typing=False` — the watcher below, four times a second. A layout is
    defended continuously; the DESKTOP pin is not, because outside a layout
    there is no fence to defend, only a memory of where typing began, and
    fighting the whole desktop for it would be us stealing focus."""
    fg = _foreground()
    root = _owner_root(fg)
    lay = _active_layout(layouts, conn)
    if lay is None and not typing:
        return fg

    if lay is not None:
        members = lay.members
        if fg in members:
            return _accept(conn, lay, fg)
        if root in members:
            # A dialog of a member window — the owner is typing into it on
            # purpose. Accepted, and the MEMBER stays the remembered target.
            _accept(conn, lay, root)
            return fg
        pin = conn.get("pin")
        target = pin if pin in members else (
            lay.last_member if lay.last_member in members else members[0])
        _log_steal(conn, fg, target, "the layout the phone is showing")
        _refocus(target)
        return _accept(conn, lay, target)

    pin = conn.get("pin")
    if conn.get("pin_stale", True) or not pin or not window_manager.user32.IsWindow(pin):
        return _accept(conn, None, fg)        # first key of this burst — arm here
    if fg == pin:
        return _accept(conn, None, pin)
    if root == pin:
        return fg          # a dialog of the target — the owner opened it himself
    _log_steal(conn, fg, pin, "the window the phone was typing in")
    # NOT topmost: this window is nobody's layout member, and a topmost raise
    # here would strand it above the desk for the rest of the Windows session
    # (window_manager.raise_window, owner decree 2026-08-05).
    window_manager.raise_window(pin, topmost=False)
    return _accept(conn, None, pin)


# ═══════════════════════════ THE DEFENCE ═══════════════════════════
async def watch(layouts, conn: dict) -> None:
    """While the phone is showing a layout, NOTHING may take the keyboard out
    of it (owner decree 2026-08-06). One task per connection, cancelled with
    it.

    Why this exists beside `guard`: dictation. Android's recognizer hands over
    a whole utterance at the END of a listening round, so a program that grabs
    focus while the owner is speaking does not misplace a character — it takes
    the window his half hour of speech was meant for, and by the time the text
    finally arrives there is nothing to give it back to. The defence has to
    stand while he speaks, not wake up when he stops.

    It sleeps while the phone is away (an excursion or a leave): those windows
    belong to the desk again, and pulling focus back to them there would be
    exactly the sin this project spent two rounds fixing."""
    while True:
        await asyncio.sleep(WATCH_POLL_S)
        if conn.get("active") is None or conn.get("away") or conn.get("left"):
            continue
        await asyncio.to_thread(guard, layouts, conn, False)
