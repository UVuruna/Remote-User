"""ADDING A MEMBER TO AN EXISTING LAYOUT — the `layout_member_add` gate.

Owner request (task 195), his words in translation: grow a layout by one
window — solo→2, 2→3, 3→4 — "if there is room ... unless it already has four".
Until this round a grid could only LOSE a window (`layout_member_remove`,
task 165) or be BUILT whole (`layout_create`/`layout_merge`); there was no way
to add one more window to a layout that already existed short of deleting it
and making it again with the extra window included.

It is `layout_member_remove` read forwards, and it shares that check's whole
premise: `LayoutRegistry._template_for` is the ONE function that decides what
shape a layout of N windows wears, used by `add_member` exactly as
`drop_member` and `merge` use it — growing and shrinking can never disagree
about what a three is.

The half that is genuinely new here is `resolve_slot` reuse: a member added by
TAB is torn into its own window through the identical path `layout_create`
uses, never a second implementation of that dance. And the DUPLICATE guard —
a window belongs to exactly one layout, the rule `member_hwnds` already
enforces on the creation list — has to hold here too, since `layout_api`'s
`_list_entries` is what feeds the "Add a window" panel and nothing stops a
stale reply naming a window another tap already claimed in the meantime.

WHY ITS OWN FILE (THE STRUCTURE LAW): tests/test_layout_member.py is already
sized for `layout_member_remove` alone; this is the same seam that separated
test_layout_drag.py from test_layout_protocol.py — a layout GROWING is its own
responsibility from a layout SHRINKING, even though both lean on the same
`_template_for`.

NOTHING is copied: the desk model, `drive`, `sent_of` and `build_layouts` are
imported from the sibling gates, one definition each.

Run:  .venv\\Scripts\\python tests/test_layout_grow.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import window_manager  # noqa: E402

from test_layout_drag import WIN_C, WIN_D, build_layouts, names_of  # noqa: E402
from test_layout_protocol import (  # noqa: E402
    MON, PLACED, WIN_A, WIN_B, drive, install_fakes, sent_of,
)


def grow_run(members, add_hwnd, grid=None, track=True):
    """One layout of `members`, then one `layout_member_add` for `add_hwnd`."""
    conn, layouts = build_layouts([("Work", list(members))], track=track)
    PLACED.clear()
    msg = {"type": "layout_member_add", "index": 0, "hwnd": add_hwnd, "tab": None}
    if grid:
        msg["grid"] = grid
    ws, conn, layouts = drive([msg], conn, layouts)
    return ws, conn, layouts


# ═══════════════════════ the sizes his sentence names ═══════════════════════
def check_a_layout_grows_one_window_at_a_time() -> bool:
    """His sentence, as sizes: a single becomes a two, a two a three, a three a
    four. The SHAPE must follow the size, and the phone must be told."""
    ok = True
    for members, add, want_grid in (
            ([WIN_A], WIN_B, "2"),
            ([WIN_A, WIN_B], WIN_C, "3-top"),
            ([WIN_A, WIN_B, WIN_C], WIN_D, "4")):
        label = f"{len(members)}->{len(members) + 1}"
        ws, conn, layouts = grow_run(members, add)
        if len(layouts.layouts) != 1:
            print(f"  DETAIL {label}: the layout count changed")
            ok = False
            continue
        lay = layouts.layouts[0]
        if lay.members != members + [add]:
            print(f"  DETAIL {label}: members are {lay.members}, expected "
                  f"{members + [add]}")
            ok = False
        if lay.template != want_grid:
            print(f"  DETAIL {label}: the shape became {lay.template!r}, "
                  f"expected {want_grid!r}")
            ok = False
        if not sent_of(ws, "layout_state"):
            print(f"  DETAIL {label}: the phone was never answered")
            ok = False
    return ok


def check_a_full_layout_refuses_a_fifth() -> bool:
    """A four is the catalogue's ceiling — his own words, "unless it already
    has four". Nothing may move, and the refusal must reach the phone in
    words, the same rule `layout_member_remove` follows for a bad ordinal."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C, WIN_D])])
    PLACED.clear()
    ws, conn, layouts = drive(
        [{"type": "layout_member_add", "index": 0, "hwnd": 0x99, "tab": None}],
        conn, layouts)
    lay = layouts.layouts[0]
    if len(lay.members) != 4 or 0x99 in lay.members:
        print(f"  DETAIL the layout changed: {lay.members}")
        return False
    if PLACED:
        print(f"  DETAIL windows moved on a refused add: {PLACED}")
        return False
    return bool(sent_of(ws, "toast"))


def check_a_window_already_in_a_layout_is_refused() -> bool:
    """One window belongs to exactly one layout — the rule `member_hwnds`
    already enforces on the creation list. A stale "Add a window" reply must
    not be able to put the SAME window in two layouts at once."""
    install_fakes(track_placement=True)
    window_manager.user32.alive.update({WIN_C, WIN_D})
    conn, layouts = window_manager.LayoutRegistry(), None
    conn, layouts = build_layouts([("A", [WIN_A]), ("B", [WIN_B])])
    PLACED.clear()
    ws, conn, layouts = drive(
        [{"type": "layout_member_add", "index": 0, "hwnd": WIN_B, "tab": None}],
        conn, layouts)
    a, b = layouts.layouts[0], layouts.layouts[1]
    if WIN_B in a.members or WIN_B not in b.members:
        print(f"  DETAIL WIN_B moved: A={a.members} B={b.members}")
        return False
    return bool(sent_of(ws, "toast"))


def check_the_new_member_is_placed_into_the_new_shape() -> bool:
    """Every member — old and new — must land on a cell of the NEW
    arrangement, read out of grids.py rather than restated here, so this
    check cannot agree with a wrong answer."""
    ok = True
    for members, add, want_grid in (
            ([WIN_A], WIN_B, "2"),
            ([WIN_A, WIN_B], WIN_C, "3-top")):
        label = f"{len(members)}->{len(members) + 1}"
        ws, conn, layouts = grow_run(members, add)
        placed = {hwnd: rect for hwnd, rect in PLACED}
        want_members = members + [add]
        if sorted(placed) != sorted(want_members):
            print(f"  DETAIL {label}: placed {sorted(placed)}, expected "
                  f"{sorted(want_members)}")
            ok = False
            continue
        region = window_manager.layout_region(
            window_manager._work_area(MON), 1.0 / conn["ratio"])
        cells = window_manager._cells(region, want_grid, "landscape")
        got = [placed[h] for h in want_members]
        if got != [tuple(c) for c in cells]:
            print(f"  DETAIL {label}: landed on {got}, expected {cells}")
            ok = False
    return ok


def check_growing_to_a_three_honours_the_phones_shape() -> bool:
    """1+1 -> 3 is the ONE size with a real choice (his sheet, 2026-08-07): the
    four arrangements a three may take. An unnamed or wrong-sized ask falls
    back to the default rather than an empty cell — `_template_for`'s own
    rule, asked here exactly as `layout_member_remove` asks it."""
    ok = True
    for grid, want in (("3-right", "3-right"), ("3-left", "3-left"),
                       (None, "3-top"), ("4", "3-top"), ("nonsense", "3-top")):
        _, _, layouts = grow_run([WIN_A, WIN_B], WIN_C, grid=grid)
        got = layouts.layouts[0].template
        if got != want:
            print(f"  DETAIL asked {grid!r}, got {got!r}, expected {want!r}")
            ok = False
    return ok


def check_a_layout_that_is_gone_is_refused_in_words() -> bool:
    conn, layouts = build_layouts([("Work", [WIN_A])])
    PLACED.clear()
    ws, conn, layouts = drive(
        [{"type": "layout_member_add", "index": 9, "hwnd": WIN_B, "tab": None}],
        conn, layouts)
    if len(layouts.layouts) != 1 or layouts.layouts[0].members != [WIN_A]:
        print("  DETAIL the real layout changed")
        return False
    return bool(sent_of(ws, "toast"))


def check_the_new_member_joins_the_topmost_ledger() -> bool:
    """CLAUDE.md constraint 10: a member joins through the ordinary raise
    order `focus()` walks — never a special case — so the new window is
    raised exactly like every other member of the layout it just joined."""
    conn, layouts = build_layouts([("Work", [WIN_A])])
    raised: list[int] = []
    window_manager.raise_window = lambda hwnd, topmost=True: raised.append(hwnd)
    drive([{"type": "layout_member_add", "index": 0, "hwnd": WIN_B, "tab": None}],
          conn, layouts)
    if WIN_B not in raised:
        print(f"  DETAIL the new member was never raised (raised: "
              f"{[hex(h) for h in raised]})")
        return False
    return True


CHECKS = [
    ("a layout grows one window at a time (1->2, 2->3, 3->4)",
     check_a_layout_grows_one_window_at_a_time),
    ("a full layout (four) refuses a fifth, in words",
     check_a_full_layout_refuses_a_fifth),
    ("a window already in a layout is refused, in words",
     check_a_window_already_in_a_layout_is_refused),
    ("the new member is placed into the new shape, with every survivor",
     check_the_new_member_is_placed_into_the_new_shape),
    ("growing to a three honours the phone's chosen arrangement",
     check_growing_to_a_three_honours_the_phones_shape),
    ("a layout that is gone is refused in words",
     check_a_layout_that_is_gone_is_refused_in_words),
    ("the new member joins the topmost ledger via the ordinary raise order",
     check_the_new_member_joins_the_topmost_ledger),
]


def main() -> int:
    print("=== LAYOUT GROW GATE (task 195) ===")
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as e:  # a crashing handler is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"LAYOUT GROW GATE FAILED — {failed} check(s).")
        return 1
    print("LAYOUT GROW GATE PASSED — a layout can gain one window, up to four.")
    return 0


def test_layout_grow():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
