"""DIALOG CENTER GATE — a dialog opens in the middle of its parent, whichever
layout the parent is in, and even when it is in none.

Owner report 2026-08-19, a REPEAT of constraint 19 one layout over: his UVuruna
VS Code raised its "open this link in Chrome?" box while the phone was showing
ANOTHER layout, the box was offered to him as a new window, he said yes, and the
app built a layout around a 625x189 dialog that cannot take a rect. His
sentences, each a check below:

  * not a new window — the middle of ITS PARENT, not of whichever layout is up;
  * if UVuruna's window raised it, the next time he comes to UVuruna it is in
    the middle of that window — and a notice says so, whose tap takes him there;
  * no layout at all — still the middle of its parent.

NOTHING HERE TOUCHES THE OWNER'S DESKTOP: the desk is the fake from
tests/test_layout_popup.py (the same members, the same ledger dict), extended
by one more layout and one more application.

Run:  .venv\\Scripts\\python tests/test_dialog_center.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import run_checks, window_manager  # noqa: E402

import test_layout_popup as popup_gate  # noqa: E402
from test_layout_popup import (  # noqa: E402
    DIALOG, LEDGER, MEMBER_A, MEMBER_B, OLD_TWIN, PIDS, PROCESS_NAMES,
    PROCESS_OF_MEMBER, RECTS, STRANGER, centered,
)

import dialog_center  # noqa: E402
import layout_popup  # noqa: E402
import notice_channel  # noqa: E402

# ONE MORE LAYOUT on the bar — UVuruna — and its own VS Code window. The
# focused layout (index 0) is popup_gate's [MEMBER_A, MEMBER_B]; this one is
# index 1 and the phone is NOT looking at it.
UVURUNA = 0x70
UVURUNA_RECT = (1400, 100, 900, 800)
# A DIALOG the UVuruna window raised, standing where Windows put it: off its
# parent, in the corner of the screen.
UV_DIALOG = 0x71
UV_DIALOG_HOME = (2000, 1100, 500, 200)
# An application in NO layout, and ITS dialog off to the side.
LONE = 0x72
LONE_RECT = (300, 900, 700, 400)
LONE_DIALOG = 0x73
LONE_DIALOG_HOME = (1500, 1250, 400, 120)

PIDS.update({UVURUNA: 1000, UV_DIALOG: 1000, LONE: 5000, LONE_DIALOG: 5000})
PROCESS_NAMES.update({UVURUNA: PROCESS_OF_MEMBER, UV_DIALOG: PROCESS_OF_MEMBER,
                      LONE: "lone.exe", LONE_DIALOG: "lone.exe"})

# Every placement this module asks for, WITH the z-band it asked for —
# `(hwnd, rect, topmost)` — because "never the topmost band" is half of what
# this gate proves, and popup_gate's own `_place` fake takes no such argument.
PLACED: list = []
# What `notice_channel.deliver` was handed.
DELIVERED: list = []
REFUSES: set = set()


def _place(hwnd, rect, topmost=True):
    PLACED.append((hwnd, tuple(rect), topmost))
    if hwnd in REFUSES:
        return False
    if topmost:
        LEDGER[hwnd] = "exe"
    RECTS[hwnd] = tuple(rect)
    return True


async def _deliver(notice):
    DELIVERED.append(notice)
    return "page"


# The real carrier, put back after this gate runs: `notice_channel.deliver` is
# a module attribute other gates (test_notice_channel, test_log_wiring) drive
# for real in the same pytest process, and a fake left behind here fails them
# — found exactly that way on the first full run.
_REAL_DELIVER = notice_channel.deliver


def desk(owner=None, active=0):
    """popup_gate's desk plus the second layout, the lone application and
    their dialogs. Returns (registry, connection)."""
    owner = owner if owner is not None else {DIALOG: MEMBER_A,
                                             UV_DIALOG: UVURUNA,
                                             LONE_DIALOG: LONE}
    alive = (MEMBER_A, MEMBER_B, OLD_TWIN, UVURUNA, UV_DIALOG, LONE, LONE_DIALOG,
             DIALOG, STRANGER)
    reg, conn = popup_gate.desk(fg=MEMBER_A, alive=alive, owner=owner)
    fake = window_manager.user32
    fake.IsWindowVisible = lambda hwnd: 1 if hwnd in fake.alive else 0
    RECTS.update({UVURUNA: UVURUNA_RECT, UV_DIALOG: UV_DIALOG_HOME,
                  LONE: LONE_RECT, LONE_DIALOG: LONE_DIALOG_HOME})
    window_manager.place_window = _place
    PLACED.clear()
    DELIVERED.clear()
    REFUSES.clear()
    notice_channel.deliver = _deliver
    reg.layouts.append(window_manager.Layout(
        "UVuruna", PROCESS_OF_MEMBER, [UVURUNA], None, "portrait", 0.5))
    conn["active"] = active
    # The desk as the phone last left it — the dialogs were NOT there.
    conn["dialog_seen"] = {MEMBER_A, MEMBER_B, OLD_TWIN, UVURUNA, LONE, STRANGER}
    conn["popup_known"] = set(conn["dialog_seen"])
    conn["birth_seen"] = set(conn["dialog_seen"])
    popup_gate.DESK_WINDOWS.clear()
    popup_gate.DESK_WINDOWS.update(alive)
    return reg, conn


def sweep(reg, conn, times=1):
    for _ in range(times):
        conn["dialog_swept"] = 0.0          # past the 1 s cadence
        dialog_center.sweep(reg, conn)


# ═══════════════ 1. his first two sentences: the parent's middle, THAT layout ═══
def check_another_layouts_dialog_is_centred_on_its_parent_and_adopted_there() -> bool:
    """The UVuruna dialog, while the phone shows layout 0: it lands in the
    middle of the UVURUNA window (not of the focused layout's region), it is
    ADOPTED by layout 1 with its home remembered, and it is nowhere near the
    topmost band — that band is the shown layout's alone.

    Defect planted: with `dialog_center.sweep` out of the watcher's loop the
    dialog stays in its corner and no layout knows it."""
    reg, conn = desk()
    sweep(reg, conn)
    uv = reg.layouts[1]
    if RECTS[UV_DIALOG] != centered(UV_DIALOG_HOME, UVURUNA_RECT):
        print(f"  DETAIL dialog stands at {RECTS[UV_DIALOG]}, parent {UVURUNA_RECT}")
        return False
    if UV_DIALOG not in uv.adopted or uv.adopted_home.get(UV_DIALOG) != UV_DIALOG_HOME:
        print(f"  DETAIL adopted={uv.adopted} home={uv.adopted_home}")
        return False
    if UV_DIALOG in reg.layouts[0].adopted:
        print("  DETAIL the FOCUSED layout adopted another layout's dialog")
        return False
    if any(top for h, _, top in PLACED if h == UV_DIALOG) or UV_DIALOG in LEDGER:
        print(f"  DETAIL the dialog entered the topmost band: {PLACED} {dict(LEDGER)}")
        return False
    return True


def check_it_is_never_offered_as_a_new_window() -> bool:
    """HIS REPORT EXACTLY: the popup sweep used to run its process rule
    against the FOCUSED layout, whose VS Code shares the exe, and offered the
    dialog with "Make a layout" on the chip. A window any layout holds is
    nobody's question — and a dialog is not a window a layout could hold.

    Defect planted: deleting the `held` test in `layout_popup.sweep` puts
    the chip back (the fake `is_listable` here is deliberately permissive, so
    it is the held rule and not the listable one that this check reads)."""
    reg, conn = desk()
    sweep(reg, conn)
    conn["popup_swept"] = 0.0
    layout_popup.sweep(reg, conn)
    chips = [m for m in popup_gate.offers(conn) if m.get("type") == "window_offer"
             and m.get("hwnd") == UV_DIALOG]
    if chips:
        print(f"  DETAIL the dialog was offered: {chips}")
        return False
    return True


def check_he_is_told_once_and_the_notice_jumps_to_that_layout() -> bool:
    """ONE notice — the same frame an agent's "needs you" rides on — naming
    the layout, with the jump the phone's tap follows (client/notify.js ->
    `layout`). Sweeping again tells him nothing twice.

    Defect planted: dropping `where=` from `_tell` leaves a notice that cannot
    be tapped anywhere; dropping `dialog_told` sends one per second."""
    reg, conn = desk()
    sweep(reg, conn, times=3)
    asyncio.run(dialog_center.flush_notices(conn))
    if len(DELIVERED) != 1:
        print(f"  DETAIL {len(DELIVERED)} notices delivered: {DELIVERED}")
        return False
    notice = DELIVERED[0]
    jump = notice.get("layout") or {}
    if notice.get("type") != "notify" or jump.get("index") != 1 \
            or jump.get("name") != "UVuruna":
        print(f"  DETAIL notice does not jump to layout 1: {notice}")
        return False
    if "UVuruna" not in notice.get("title", "") or not notice.get("speak_text"):
        print(f"  DETAIL notice does not name the layout: {notice}")
        return False
    # …and a second flush has nothing left to send.
    if asyncio.run(dialog_center.flush_notices(conn)) != 0:
        return False
    # A dialog that REFUSES its rect is looked at again every second — and is
    # still one notice, not one per look.
    reg, conn = desk()
    REFUSES.add(UV_DIALOG)
    sweep(reg, conn, times=3)
    asyncio.run(dialog_center.flush_notices(conn))
    if len(DELIVERED) != 1:
        print(f"  DETAIL a refusing dialog was told {len(DELIVERED)} times")
        return False
    return True


def check_a_second_sweep_moves_nothing_again() -> bool:
    """Centred is centred. A dialog standing in its parent's middle is not
    re-placed on the next pass — that would be a fight with any app that lays
    its own dialog out."""
    reg, conn = desk()
    sweep(reg, conn)
    moves = len([p for p in PLACED if p[0] == UV_DIALOG])
    sweep(reg, conn, times=3)
    again = len([p for p in PLACED if p[0] == UV_DIALOG])
    if moves != 1 or again != 1:
        print(f"  DETAIL placed {moves} then {again} times")
        return False
    return True


# ═══════════════ 2. his third sentence: no layout, still the parent's middle ═══
def check_a_dialog_of_a_window_in_no_layout_is_centred_silently() -> bool:
    """LONE is in no layout. Its dialog still goes to its middle — and nothing
    else happens: no adoption anywhere, no notice, no topmost."""
    reg, conn = desk()
    sweep(reg, conn)
    asyncio.run(dialog_center.flush_notices(conn))
    if RECTS[LONE_DIALOG] != centered(LONE_DIALOG_HOME, LONE_RECT):
        print(f"  DETAIL lone dialog stands at {RECTS[LONE_DIALOG]}")
        return False
    if any(LONE_DIALOG in lay.adopted for lay in reg.layouts):
        print("  DETAIL a layout adopted a stranger's dialog")
        return False
    if any("lone" in str(n).lower() for n in DELIVERED) or LONE_DIALOG in LEDGER:
        print(f"  DETAIL told or raised about the lone dialog: {DELIVERED} {dict(LEDGER)}")
        return False
    return True


# ═══════════════ 3. what it leaves alone ═══════════════
def check_the_focused_layouts_own_dialog_is_constraint_19s_and_not_this() -> bool:
    """DIALOG is owned by MEMBER_A, a member of the SHOWN layout: `layout_popup`
    has placed that case since 2026-08-13 and this module must not compete
    with it — two placers on one window is a fight."""
    reg, conn = desk()
    sweep(reg, conn)
    if any(h == DIALOG for h, _, _ in PLACED):
        print(f"  DETAIL this module moved the focused layout's own dialog: {PLACED}")
        return False
    return True


def check_a_window_that_is_not_a_dialog_is_never_moved() -> bool:
    """STRANGER has no owner. Whatever else it is, it is not this module's."""
    reg, conn = desk()
    sweep(reg, conn)
    return not any(h == STRANGER for h, _, _ in PLACED)


def check_a_dialog_that_refuses_its_rect_is_not_fought_forever() -> bool:
    """A fixed window that will not take the rect is tried MAX_CONTAIN_TRIES
    times and then left where it is — never four times a second for the rest
    of the session."""
    reg, conn = desk()
    REFUSES.add(UV_DIALOG)
    sweep(reg, conn, times=10)
    tries = len([p for p in PLACED if p[0] == UV_DIALOG])
    import popup_contain
    if tries != popup_contain.MAX_CONTAIN_TRIES:
        print(f"  DETAIL tried {tries} times, expected {popup_contain.MAX_CONTAIN_TRIES}")
        return False
    return UV_DIALOG in conn["dialog_seen"]


def check_nothing_moves_while_he_is_away_or_before_a_baseline() -> bool:
    """Away is away; and with no baseline nothing is new, so nothing moves."""
    reg, conn = desk()
    conn["away"] = 1.0
    sweep(reg, conn)
    if PLACED:
        print(f"  DETAIL moved while away: {PLACED}")
        return False
    reg, conn = desk()
    conn["dialog_seen"] = None
    sweep(reg, conn)
    return not PLACED


def check_the_watcher_runs_it_beside_the_birth_scan() -> bool:
    """The call must sit in the watcher loop OUTSIDE the `_defending` gate —
    the parent may be in any layout or none, and the phone may be at the
    desktop — and the notices must be flushed from the same loop. Read off
    the source: the loop is the only async context the guard has."""
    src = (Path(__file__).resolve().parent.parent / "server" / "focus_guard.py"
           ).read_text(encoding="utf-8")
    loop = src[src.index("while True:"):src.index("if not _defending(conn):")]
    return ("dialog_center.sweep" in loop and "dialog_center.flush_notices" in loop
            and "layout_birth.scan" in loop)


CHECKS = [
    ("another layout's dialog is centred on ITS parent and adopted THERE",
     check_another_layouts_dialog_is_centred_on_its_parent_and_adopted_there),
    ("it is never offered as a new window",
     check_it_is_never_offered_as_a_new_window),
    ("he is told once, and the notice jumps to that layout",
     check_he_is_told_once_and_the_notice_jumps_to_that_layout),
    ("a second sweep moves nothing again",
     check_a_second_sweep_moves_nothing_again),
    ("a dialog of a window in no layout is centred, silently",
     check_a_dialog_of_a_window_in_no_layout_is_centred_silently),
    ("the focused layout's own dialog is constraint 19's, not this module's",
     check_the_focused_layouts_own_dialog_is_constraint_19s_and_not_this),
    ("a window that is not a dialog is never moved",
     check_a_window_that_is_not_a_dialog_is_never_moved),
    ("a dialog that refuses its rect is not fought forever",
     check_a_dialog_that_refuses_its_rect_is_not_fought_forever),
    ("nothing moves while he is away or before a baseline",
     check_nothing_moves_while_he_is_away_or_before_a_baseline),
    ("the watcher runs it beside the birth scan, outside the defending gate",
     check_the_watcher_runs_it_beside_the_birth_scan),
]


def main() -> int:
    try:
        return run_checks("DIALOG CENTER GATE", CHECKS,
                          "a dialog opens in the middle of its parent, wherever the parent is.")
    finally:
        notice_channel.deliver = _REAL_DELIVER


def test_dialog_center():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
