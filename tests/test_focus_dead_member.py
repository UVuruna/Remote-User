"""The dead-member fence gate (owner report 2026-08-13, game-breaking: "our
application blocked me and my agents").

He had two solo layouts of the same project. Layout 2's only member was a VS
Code tab TORN OFF layout 1's window (our own extraction flow). He then, BY
HAND on the PC, dragged that tab back into its origin window — Windows
DESTROYS the torn-off window on such a merge, through no removal path of
ours (`drop_member`/`eject_member`/`merge`/`remove` never ran). Layout 2's
member list still named the now-dead hwnd, and nothing prunes it until the
PHONE next acts (`focus`/`layout_state`/… — see `LayoutRegistry.prune`'s
callers). Every focus_guard call in between — the per-message fence AND the
0.25s poll of `watch()` — kept targeting that dead hwnd: `_layout_target`
picked it via `lay.members[0]`/`last_member`, `_refocus`/`raise_window` were
called on it every cycle, and the fence never gave the keyboard back to
whatever was really in front. Confirmed by planting the ORIGINAL code back
(see PLANT below) and driving it through this exact scenario with the same
fakes `test_focus_guard.py` uses — nothing here touches the owner's desktop.

THE RULE (non-negotiable, owner decree): a fence whose target no longer
exists must fail OPEN — give the keyboard back — never closed. A layout
whose members are all gone must not survive as a fence.

Run:  .venv\\Scripts\\python tests/test_focus_dead_member.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import (  # noqa: E402
    MEMBER_A, MEMBER_B, Raises, focus_guard, fresh_conn, layout_with,
    run_checks, with_win32, window_manager,
)

LIVE_OTHER = 0x77


# ═══════════════ 1. a single-member layout's dead member fails open ═══════════════
def check_dead_only_member_fails_open() -> bool:
    """The owner's exact scenario: a solo layout's only member is destroyed
    outside every removal path. The keyboard must go to whatever is really in
    front — never be fought over a hwnd that no longer exists."""
    reg = layout_with([MEMBER_A])
    conn = fresh_conn(active=0)
    with_win32(fg=LIVE_OTHER, alive=(LIVE_OTHER,))   # MEMBER_A is DEAD
    raises = Raises().install()
    target = focus_guard.guard(reg, conn)
    return target == LIVE_OTHER and raises == [] and conn["pin"] == LIVE_OTHER


# ═══════════════ 2. the continuous poll never fights a real window for a dead one ═══════════════
def check_the_poll_never_refocuses_a_dead_window() -> bool:
    """`watch()`'s 0.25s defence pass (`guard(..., typing=False)`) is what ran
    every cycle while the phone showed the dead layout — this is the part
    that could steal focus from the owner's REAL desk work, repeatedly,
    forever, which is what "blocked me and my agents" names."""
    reg = layout_with([MEMBER_A])
    conn = fresh_conn(active=0)
    with_win32(fg=LIVE_OTHER, alive=(LIVE_OTHER,))
    raises = Raises().install()
    for _ in range(5):   # simulate several poll cycles
        target = focus_guard.guard(reg, conn, typing=False)
    return target == LIVE_OTHER and raises == []


# ═══════════════ 3. one live member among several still fences correctly ═══════════════
def check_one_live_member_still_fences() -> bool:
    """A layout with SOME members dead and at least one alive must keep
    defending the live one — only an ALL-dead layout releases the fence."""
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    conn = fresh_conn(active=0)
    # MEMBER_A destroyed, MEMBER_B alive, foreground is a thief.
    with_win32(fg=LIVE_OTHER, alive=(MEMBER_B, LIVE_OTHER))
    raises = Raises().install()
    target = focus_guard.guard(reg, conn)
    return target == MEMBER_B and raises == [(MEMBER_B, True)]


# ═══════════════ 4. a dead pin/last_member is never re-offered as the target ═══════════════
def check_a_dead_pin_is_never_retargeted() -> bool:
    """`conn["pin"]` can independently name the exact member that just died
    (it was the one being typed into). `_layout_target` must skip it, not
    hand it straight back as "the" target."""
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_A)
    conn = fresh_conn(active=0)
    conn["pin"], conn["pin_stale"] = MEMBER_A, False   # pinned to the one that dies
    with_win32(fg=LIVE_OTHER, alive=(MEMBER_B, LIVE_OTHER))   # MEMBER_A is dead
    raises = Raises().install()
    target = focus_guard.guard(reg, conn)
    return target == MEMBER_B and raises == [(MEMBER_B, True)]


# ═══════════════ 5. current_target (read-only) agrees, and stays read-only ═══════════════
def check_current_target_also_fails_open() -> bool:
    """`current_target` answers the same question for the caret (Caret reads
    it several times a second) — it must never claim a dead hwnd is where
    typing would land, and it must still take no action (no raise)."""
    reg = layout_with([MEMBER_A])
    conn = fresh_conn(active=0)
    with_win32(fg=LIVE_OTHER, alive=(LIVE_OTHER,))
    raises = Raises().install()
    target = focus_guard.current_target(reg, conn)
    return target == LIVE_OTHER and raises == []


CHECKS = [
    ("a solo layout's only member dying fails the fence open",
     check_dead_only_member_fails_open),
    ("the continuous poll never fights a real window for a dead one",
     check_the_poll_never_refocuses_a_dead_window),
    ("one live member among several still fences correctly",
     check_one_live_member_still_fences),
    ("a dead pin/last_member is never re-offered as the target",
     check_a_dead_pin_is_never_retargeted),
    ("current_target (read-only) also fails open",
     check_current_target_also_fails_open),
]


def test_gate():
    assert run_checks(
        "DEAD MEMBER FENCE GATE", CHECKS,
        "a member destroyed outside every removal path never leaves the "
        "keyboard fenced to a window that no longer exists") == 0


if __name__ == "__main__":
    sys.exit(run_checks(
        "DEAD MEMBER FENCE GATE", CHECKS,
        "a member destroyed outside every removal path never leaves the "
        "keyboard fenced to a window that no longer exists"))
