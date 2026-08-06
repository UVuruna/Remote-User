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

import logging

import window_manager

logger = logging.getLogger(__name__)


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


def guard(layouts, conn: dict) -> int:
    """Make sure the next keystroke lands on the owner's target, and return
    that target's hwnd. Blocking (Win32 + a possible raise) — call it through
    `asyncio.to_thread`, before the injection, on every message that TYPES."""
    fg = _foreground()
    root = _owner_root(fg)
    lay = _active_layout(layouts, conn)

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
        logger.error("Focus left the layout while the phone was typing — %s took "
                     "it; handing it back to %s", describe(fg), describe(target))
        window_manager.raise_window(target)   # a member: topmost + ledger, as always
        return _accept(conn, lay, target)

    pin = conn.get("pin")
    if conn.get("pin_stale", True) or not pin or not window_manager.user32.IsWindow(pin):
        return _accept(conn, None, fg)        # first key of this burst — arm here
    if fg == pin:
        return _accept(conn, None, pin)
    if root == pin:
        return fg          # a dialog of the target — the owner opened it himself
    logger.error("Focus left the typing target — %s took it from %s; handing it back",
                 describe(fg), describe(pin))
    # NOT topmost: this window is nobody's layout member, and a topmost raise
    # here would strand it above the desk for the rest of the Windows session
    # (window_manager.raise_window, owner decree 2026-08-05).
    window_manager.raise_window(pin, topmost=False)
    return _accept(conn, None, pin)
