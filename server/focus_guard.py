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

And two rounds later (owner-approved build round R1, 2026-08-07) the last two
gaps in that fence were closed:

5. **The guard runs INSIDE a typed message, not only before it.** Typing is
   MEASURED at ~1.84 ms per character on the owner's PC, so a 600-character
   dictated sentence is over a SECOND of `SendInput` — a thief striking
   inside it used to take the whole remainder with no check of any kind, and
   nothing replays injected characters. `typist()` hands the injector a
   check it runs before every character; the happy path is one bare
   `GetForegroundWindow` (194 ns, 0.01% of a character), and only a
   foreground that is not the target pays for the full `checkpoint()`. The
   callable is passed DOWN, so the injector never imports back up.
6. **Windows TELLS us the foreground moved** ([Focus Hook](focus_hook.py)):
   2-5 ms instead of the poll's up to 250 ms. The poll stays as the backstop,
   because a hook can be refused or dropped — and the hook's callback may
   only SIGNAL this module's loop, never run the guard on Windows' own
   dispatch thread (measured: it stalled a second caller for 2.99 s, which
   the owner felt as a juddering mouse).
7. **What could not be typed reaches the PHONE**, not just the log. He is
   looking at his device while he speaks; a sentence destroyed in silence is
   the original failure wearing a different coat.

Split out of [Web Layer] on 2026-08-06 (THE STRUCTURE LAW): "where does typed
input land" is one responsibility with its own rules and its own gate
(`tests/test_focus_guard.py`, plus `tests/test_focus_hook.py` for the
machinery), not an `if` in the message dispatcher.
"""

import asyncio
import logging
import threading
import time

import focus_hook
import layout_birth
import layout_popup
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
# How long a mid-sentence checkpoint waits for the foreground to actually come
# back AFTER the guard has asked for it. `SetForegroundWindow` returning
# success is not the same as Windows having moved the foreground — it is a
# request the window manager completes a moment later — so the target is
# VERIFIED, not assumed.
#
# Honest about what this number is NOT: it is not the cost of a stolen
# character. The `guard()` call one line above it can itself take SECONDS when
# it has to raise a window — `window_manager.raise_window` waits for the frame
# to settle (`SETTLE_TIMEOUT_S`, 1.5 s, and twice on the fallback path). This
# is only the tail: the extra time spent confirming that the raise landed.
REFOCUS_SETTLE_S = 0.05
REFOCUS_POLL_S = 0.005


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
# Three threads can ask "where may the keyboard be" at the same time now — the
# message that types, the poll, and the hook — so the decision is taken one at
# a time (see guard()).
_GUARD_LOCK = threading.Lock()


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


def _layout_target(lay, conn: dict) -> int:
    """Which member of `lay` the phone's keyboard belongs to when the
    foreground is NOT one of them. One implementation, two callers: the guard
    below (which then puts focus there) and `current_target` (which only
    looks) — two copies of this rule would be two answers to one question."""
    pin = conn.get("pin")
    if pin in lay.members:
        return pin
    return lay.last_member if lay.last_member in lay.members else lay.members[0]


def _armed_pin(conn: dict) -> int:
    """The desktop pin when it is actually armed and its window still exists —
    0 otherwise, meaning "the next key re-reads the foreground"."""
    pin = conn.get("pin")
    if conn.get("pin_stale", True) or not pin or not window_manager.user32.IsWindow(pin):
        return 0
    return pin


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

    `typing=True` — before injecting, on every message that TYPES, and again
    between the chunks of one long one (`checkpoint`).
    `typing=False` — the defence below: the poll four times a second AND the
    foreground hook. A layout is defended continuously; the DESKTOP pin is
    not, because outside a layout there is no fence to defend, only a memory
    of where typing began, and fighting the whole desktop for it would be us
    stealing focus.

    SERIALIZED (2026-08-07): the poll is no longer the only voice — the hook
    fires on its own thread the instant Windows moves the foreground, and two
    threads deciding the target at once would race over `conn`'s pin and
    could raise two different windows."""
    with _GUARD_LOCK:
        return _decide(layouts, conn, typing)


def _decide(layouts, conn: dict, typing: bool) -> int:
    fg = _foreground()
    root = _owner_root(fg)
    lay = _active_layout(layouts, conn)
    if lay is None and not typing:
        return fg

    if lay is not None:
        members = lay.members
        if fg in members:
            return _accept(conn, lay, fg)
        # IS THIS THE LAYOUT'S OWN WORK? (owner eruption 2026-08-11, task 202.)
        # A dialog of a member, a second window the member opened, the viewer
        # it started — those are not thieves, and refusing them was only half
        # the failure: they open OUTSIDE the layout's region, where the phone
        # can see them and not touch them. [Layout Popup](layout_popup.py)
        # attributes such a window and ASKS HIM on the phone (his amendment
        # the same day: never auto-grab); it answers truthy only once he has
        # said "show it in the layout", and "" for a stranger, for a window he
        # left on the desktop and for one he has not answered yet — all three
        # of which are the refusal below, exactly as before.
        adopted = layout_popup.handle(lay, fg, root, conn)
        if adopted or root in members:
            if root in members:
                # A dialog of a member window — the owner is typing into it on
                # purpose. Accepted, and the MEMBER stays the remembered target.
                _accept(conn, lay, root)
            else:
                # A window of the layout's work that is nobody's member: the
                # keyboard may sit on it, but `last_member` must keep naming a
                # real member — `focus()` raises it last and `_layout_target`
                # falls back to it.
                conn["pin"], conn["pin_stale"] = fg, False
            return fg
        target = _layout_target(lay, conn)
        _log_steal(conn, fg, target, "the layout the phone is showing")
        _refocus(target)
        return _accept(conn, lay, target)

    pin = _armed_pin(conn)
    if not pin:
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


def current_target(layouts, conn: dict) -> int:
    """WHERE the phone's keys would land right now — READ ONLY.

    Same rules as `guard`, none of its actions: it raises nothing, arms
    nothing, takes no lock and writes nothing into `conn`. That separation is
    the point. [Caret](caret.py) has to ask this question several times a
    second so the phone knows which row on the PC it must not cover, and a
    passive watcher that could raise a window would be a second, uninvited
    focus policy running beside the real one.

    It answers from this module because the answer belongs to this module: a
    caret read that decided for itself which window is being typed into would
    be a second opinion, and two opinions about one window are exactly what
    the layout fence exists to prevent."""
    fg = _foreground()
    lay = _active_layout(layouts, conn)
    if lay is not None:
        if (fg in lay.members or _owner_root(fg) in lay.members
                or fg in lay.adopted):
            return fg
        return _layout_target(lay, conn)
    pin = _armed_pin(conn)
    if not pin:
        return fg                         # nothing armed — typing would land here
    if fg == pin or _owner_root(fg) == pin:
        return fg                         # the target, or a dialog it owns
    return pin                            # a thief holds it; `guard` hands it back


# ═══════════════════════════ INSIDE ONE SENTENCE ═══════════════════════════
def _holds(target: int) -> bool:
    """Is `target` (or a dialog it owns) really the foreground RIGHT NOW?"""
    if not target:
        return False
    fg = _foreground()
    return fg == target or _owner_root(fg) == target


def checkpoint(layouts, conn: dict) -> int:
    """Between two chunks of ONE typed message: may the injector keep typing,
    and into what? Returns the target's hwnd, or **0** when focus could not be
    brought back — the caller must then stop, because every further character
    would be typed into the thief.

    Why this exists at all (the hole build round R1 was called to close): the
    guard used to run once per MESSAGE. A 600-character dictated sentence is
    20-60 ms of `SendInput`, and a window that takes focus inside those
    milliseconds gets the rest of the sentence — silently, since nothing
    replays injected characters and Windows reports no error.

    The restore is VERIFIED, never assumed: `SetForegroundWindow` succeeding
    is a request, not a fact, so the foreground is re-read until it really is
    the target or `REFOCUS_SETTLE_S` runs out."""
    target = guard(layouts, conn)
    if _holds(target):
        return target
    deadline = time.monotonic() + REFOCUS_SETTLE_S
    while time.monotonic() < deadline:
        time.sleep(REFOCUS_POLL_S)
        if _holds(target):
            return target
    logger.error("Focus could NOT be returned to %s — %s still holds it; the "
                 "rest of what the phone is typing will NOT be sent",
                 describe(target), describe(_foreground()))
    return 0


def loss_notice(lost: str) -> str:
    """What the PHONE is told when typing was cut off — the size of the loss
    and the start of what is missing, so he knows what to say again.

    It lives here, not in the dispatcher, because it is this module's subject:
    the whole point of the guard is that the owner is looking at his device,
    not at a server log, and a sentence destroyed in silence is the original
    failure wearing a different coat."""
    return (f"{len(lost)} characters did NOT reach the PC — another window "
            f"took the keyboard: “{lost[:40]}”")


def typist(layouts, conn: dict):
    """The checkpoint as the injector wants it: a zero-argument callable that
    answers "may I keep typing, and where".

    Handed IN to `InputInjector.type_text` on purpose — the injector is the
    layer below and must know nothing about layouts, connections or fences;
    inverting that import to give it a guard would be the layering defect this
    project splits modules to avoid.

    The happy path is BARE (measured on the owner's PC, 2026-08-07): one
    `GetForegroundWindow` at 194 ns against the armed target — no lock, no
    owner walk, nothing that can block. A foreground that is NOT the target is
    the only case that pays for the full `checkpoint`. That measurement is
    what made a check before EVERY CHARACTER affordable (a typed character
    costs ~1.84 ms of `SendInput` on this machine, so the check is 0.01% of
    it) — and a check per character is what takes the characters a thief can
    still catch from "up to 39" down to zero."""
    def check() -> int:
        target = conn.get("pin")
        if target and _foreground() == target:
            return target
        return checkpoint(layouts, conn)
    return check


# ═══════════════════════════ THE DEFENCE ═══════════════════════════
def _log_silent_hook(conn: dict) -> None:
    """Windows never says it detached a hook. The evidence is exactly this:
    the POLL found focus outside the layout and had to put it back, while the
    hook — which Windows still claims to hold — announced nothing at all.

    Once per connection, because if it is true it stays true, and because the
    point is to be TOLD we are down to the 250 ms backstop rather than to
    believe we still have milliseconds."""
    if conn.get("hook_silent"):
        return
    conn["hook_silent"] = True
    logger.warning(
        "The foreground hook is installed but announced nothing about a change "
        "the poll then had to undo — Windows has most likely DETACHED it "
        "(which is what it does to a hook that is slow to return). Reaction is "
        "the %.2fs poll now, not milliseconds.", WATCH_POLL_S)


def _defend(layouts, conn: dict, announced: bool) -> None:
    """One defence pass, on a worker thread — never on the hook thread."""
    before = _foreground()
    events = focus_hook.event_count()
    target = guard(layouts, conn, False)
    if (target != before and not announced
            and events == conn.get("hook_events") and focus_hook.installed()):
        _log_silent_hook(conn)
    conn["hook_events"] = events


async def _wait_for_change(woken: asyncio.Event) -> bool:
    """True when the hook announced a foreground change, False when the poll
    interval simply elapsed. Both lead to the same decision — the hook only
    makes it sooner."""
    try:
        await asyncio.wait_for(woken.wait(), WATCH_POLL_S)
    except TimeoutError:
        return False
    woken.clear()
    return True


def _defending(conn: dict) -> bool:
    """A layout is on screen and the phone is actually watching it. The
    desktop pin is deliberately NOT defended (see `guard`), and windows the
    phone has walked away from belong to the desk again."""
    return (conn.get("active") is not None
            and not conn.get("away") and not conn.get("left"))


async def watch(layouts, conn: dict, injector=None) -> None:
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
    exactly the sin this project spent two rounds fixing.

    TWO SOURCES, ONE DECISION (build round R1, 2026-08-07). Windows announces
    every foreground change through [Focus Hook](focus_hook.py), which puts
    the reaction at 2-5 ms instead of up to 250 ms — and the poll below STAYS,
    because a hook can be refused at install time or dropped later. Both wake
    this ONE loop, so the decision is taken in exactly one place, on a worker
    thread, whichever source spoke."""
    loop = asyncio.get_running_loop()
    woken = asyncio.Event()

    def _foreground_changed() -> None:
        """Runs INSIDE Windows' own event dispatch, on the hook thread — so it
        may only SIGNAL, never work.

        The first version of this called `guard` straight from here and was
        measured stalling Windows' dispatch for 2.99 s: `guard` waits on a
        lock held across a window raise that waits for a frame to settle. A
        WinEventProc that is slow to return is one Windows silently detaches,
        which would have left us believing we had millisecond reaction while
        running on the poll alone."""
        loop.call_soon_threadsafe(woken.set)

    # WHICH WINDOWS ALREADY EXISTED, taken once, here (task 202). A window
    # that appears LATER is the only kind [Layout Popup](layout_popup.py) may
    # attribute to a layout by process, because every VS Code window shares
    # one process and the owner's other one is exactly the thief this module
    # was written about. Before this line has run nothing is new and nothing
    # is adopted — the fence behaves exactly as it did.
    await asyncio.to_thread(layout_popup.baseline, conn)
    # WHICH MONITOR THE PHONE IS WATCHING, as a CALLABLE and never a value:
    # a note of it is stale the instant he switches monitors, and rescuing an
    # off-screen window onto a screen he stopped watching would be the same
    # bug wearing a different hat (constraint 13; server/lost_windows.py).
    if injector is not None:
        conn["mon_rect"] = lambda: injector.monitor_rect
    hooked = await asyncio.to_thread(focus_hook.listen, _foreground_changed)
    if not hooked:
        logger.warning("No foreground hook — the layout is defended by the "
                       "%.2fs poll alone", WATCH_POLL_S)
    conn["hook_events"] = focus_hook.event_count()
    try:
        while True:
            announced = await _wait_for_change(woken)
            # DID SOMETHING HE JUST OPENED APPEAR? (task 185.) Outside the
            # `_defending` gate on purpose: the commonest shape of his request
            # is at the DESKTOP — he double-clicks an .xlsx through the stream
            # and wants to be asked whether to make a layout with it. It moves
            # nothing and takes no foreground; the scan's own rules decide
            # whether there is anything to ask (server/layout_popup.py).
            if not conn.get("away") and not conn.get("left"):
                await asyncio.to_thread(layout_birth.scan, layouts, conn)
                # IS THERE A WINDOW HE CANNOT REACH AT ALL? (owner report
                # 2026-08-12, his fifth on one bug.) Beside `scan` and not
                # inside the `_defending` gate below, for the same reason and
                # a stronger one: a window that is off every screen is lost
                # at the desktop exactly as it is inside a layout, and the
                # case he reported HAPPENED while nothing was connected —
                # which is why no rule built on the baseline could see it
                # (server/lost_windows.py).
                await asyncio.to_thread(layout_popup.sweep_lost, layouts, conn)
                await layout_popup.flush_offers(conn)
            if not _defending(conn):
                continue
            await asyncio.to_thread(_defend, layouts, conn, announced)
            # DID A WINDOW OF THIS LAYOUT'S WORK APPEAR? (task 239.) Asked by
            # ENUMERATION and not by the foreground, because the window this
            # answers cannot HAVE the foreground: it opens under the members'
            # always-on-top band, and `_defend` one line above hands focus
            # back inside the layout anyway. The foreground-only eye is why
            # his chip appeared only when he left the layout — the pass below
            # is the one that sees it while he stays (server/layout_popup.py).
            await asyncio.to_thread(layout_popup.sweep, layouts, conn)
            # …and whatever the pass wants to ASK him goes out on the page's
            # own socket (task 202): a new window of the layout's work is
            # offered — "Show in layout" / "Leave on desktop" — never taken.
            # Sent from here because this loop is the only async context the
            # guard has, and `_defend` runs on a worker thread.
            await layout_popup.flush_offers(conn)
    finally:
        # The connection is over: this listener goes, and with the last one the
        # thread and the hook handle go too (nothing of ours outlives us).
        #
        # SYNCHRONOUS on purpose, unlike the `listen` above. The web layer
        # cancels this task and never awaits it, so anything here that needed
        # another turn of the event loop would simply never run — the hook
        # would stay installed for the life of the process, which is the exact
        # leak this block exists to prevent (caught by the gate, 2026-08-07).
        # It is bounded by focus_hook.STOP_TIMEOUT_S (0.25 s) and in practice
        # costs microseconds: the listener thread only signals, so it is
        # always sitting in GetMessage ready to take WM_QUIT.
        focus_hook.release(_foreground_changed)
