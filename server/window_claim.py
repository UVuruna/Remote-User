"""WHOSE WINDOW IS THIS — the MAKER's own statement, made before the fact.

Split out of [Layout Popup](layout_popup.py) on 2026-08-17 at THE STRUCTURE
LAW's wall, and BY RESPONSIBILITY: every other rule in that module is a GUESS
about a window nobody told us anything about — a process match, an owner chain,
a click that happened to be recent — and each of those guesses is why the phone
ASKS instead of acting. This is the opposite kind of statement. It is not
evidence weighed against other evidence; it is the code that made the window
saying so, and the only correct answer to it is silence.

Its one question is `is_ours(hwnd)`, asked by every pass that could raise a
chip: [Layout Popup](layout_popup.py)'s `handle`, `sweep` and `sweep_lost`, and
[Layout Birth](layout_birth.py)'s `scan`.

## Two statements, and the second exists because the first arrives late

`mine(hwnd)` names the exact window, once it is known. `expect(process)` arms a
claim BEFORE the act, for the seconds in which the window already exists and
its handle does not. See `expect` for the measurements that forced it.
"""

import time

import window_manager as wm


# ═══════════════════ WINDOWS WE MADE OURSELVES ═══════════════════
# OWNER REPORT 2026-08-13, his point 4A: inside a layout he taps "create a
# layout from a tap", picks a TAB of that layout, and the moment the layout is
# built the phone asks him whether to show the brand-new window in the layout.
#
# It is new, it does belong to a member's process, and every rule above is
# therefore RIGHT about it — which is the point: no attribution rule can save
# us here, because the window genuinely is the layout's work. What none of them
# can know is that the layout's work in this case was OURS. We tore that tab
# off ourselves, seconds ago, on his instruction.
#
# And he named the general case before we hit it: "it will probably happen
# every time a tab is separated from its original window". So this is not a
# patch on the creation path — it is a fact every pass in this module has to be
# told, once, by whoever makes a window: `mine(hwnd)`.
#
# MODULE-LEVEL and not per-connection, because the maker does not have a `conn`
# — `uia.extract_tab` is called from the layout API on a worker thread — and
# because a window we made is ours on every connection, not just the one that
# happened to be open. Bounded in time: a handle is a number Windows re-uses,
# and a permanent set would one day silence a chip about a stranger's window
# that inherited the number.
OURS_TTL_S = 60.0
_OURS: dict[int, float] = {}


def mine(hwnd: int) -> None:
    """Record that WE created this window. Called by every path that makes one
    (today: tab extraction). Cheap and safe to call with a 0/None hwnd."""
    if not hwnd:
        return
    now = time.monotonic()
    for dead in [h for h, t in _OURS.items() if now - t > OURS_TTL_S]:
        del _OURS[dead]
    _OURS[int(hwnd)] = now


# ═══════════ THE CLAIM MADE BEFORE THE WINDOW EXISTS ═══════════
# OWNER REPORT 2026-08-17: the phone asked him about a window he had JUST
# created himself with a tap. `mine()` is exactly the mechanism that should
# have stopped it, it was called, and it was still too late — which is a
# STRUCTURAL race and not a missing line, so it is closed structurally.
#
# Every maker in this codebase makes its window the same way: do the thing,
# THEN watch for a window to appear, THEN call `mine()`. Two agents measured
# what that costs. `uia.extract_tab` leaves the window standing for up to 6-8
# seconds before the claim (it waits for rect stability, for the address band,
# for the foreground) and `layout_acts`' VS Code act only begins watching after
# the Command Palette sequence has RETURNED — while VS Code can raise the
# window the instant Enter is pressed. Meanwhile `sweep()` runs every second on
# an independent thread, and its attribution has NO grace at all for a window
# it can tie to a member. Whoever looks first wins, and nothing arbitrates.
#
# So a maker ARMS the claim BEFORE it acts: "a window of this process is about
# to appear because he asked for it". A claim is bounded in time (it is a
# promise about the next few seconds, not a licence) and it deliberately does
# NOT name a handle — the whole difficulty is that the handle does not exist
# yet, which is what made every after-the-fact claim a race.
#
# It does not replace `mine()`. `mine()` still marks the exact window once it
# is known, which is what survives past the claim's short life; the claim only
# covers the gap in between. Both are asked by `_is_ours`.
EXPECT_TTL_S = 30.0
_EXPECT: list[tuple[str, float]] = []


def expect(process: str) -> None:
    """Arm the claim: a window of `process` appearing in the next
    `EXPECT_TTL_S` is OURS, because he just asked for it. Called BEFORE the
    act — that is the entire point (see above). Safe to call with nothing."""
    name = (process or "").strip().lower()
    if not name:
        return
    now = time.monotonic()
    _EXPECT[:] = [(p, t) for p, t in _EXPECT if now - t <= EXPECT_TTL_S]
    _EXPECT.append((name, now))


def _expected(hwnd: int) -> bool:
    now = time.monotonic()
    _EXPECT[:] = [(p, t) for p, t in _EXPECT if now - t <= EXPECT_TTL_S]
    if not _EXPECT:
        return False
    name = (wm._process_name(hwnd) or "").strip().lower()
    return bool(name) and any(p == name for p, _ in _EXPECT)


def is_ours(hwnd: int) -> bool:
    made = _OURS.get(int(hwnd))
    if made is not None and time.monotonic() - made <= OURS_TTL_S:
        return True
    return _expected(hwnd)
