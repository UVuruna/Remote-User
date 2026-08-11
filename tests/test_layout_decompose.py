"""DECOMPOSING A GRID — the `layout_split` and `layout_member_eject` gates.

Owner request (task 197), two related acts from the ⚙ sheet:

  (a) SPLIT a grid into as many INDIVIDUAL layouts as it has members — every
      member becomes its own solo Layout. `Layout.sources` exists since task
      173 precisely so a member's ⭐/dependents record can travel WITH it when
      it stops sharing a grid with its siblings; this file proves that record
      really makes the trip.

  (b) EJECT one member into its OWN new layout — contrasted, explicitly, with
      the existing "Take one window out" / `layout_member_remove` (task 165),
      which leaves the window standing as plain DESKTOP material. Eject keeps
      it layout material; the difference is invisible on the desk and entirely
      in which list can still show the window to the phone.

Both share `LayoutRegistry._template_for` with `drop_member`/`merge`/
`add_member` for the survivors' shape — one definition, so a decompose can
never disagree with a grow or a shrink about what a three is.

Its own file (THE STRUCTURE LAW): tests/test_layout_member.py is
`layout_member_remove` alone, and this is a different act on a different
button in the same sheet — sized like the sibling gates.

Run:  .venv\\Scripts\\python tests/test_layout_decompose.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import window_manager  # noqa: E402

from test_layout_drag import (  # noqa: E402
    WIN_C, WIN_D, build_layouts, build_with_a_torn_off_tab, names_of,
)
from test_layout_protocol import (  # noqa: E402
    PLACED, WIN_A, WIN_B, drive, sent_of,
)


# ═════════════════════════ SPLIT (task 197a) ═════════════════════════
def check_split_makes_one_solo_layout_per_member() -> bool:
    ok = True
    for members in ([WIN_A, WIN_B], [WIN_A, WIN_B, WIN_C], [WIN_A, WIN_B, WIN_C, WIN_D]):
        conn, layouts = build_layouts([("Work", list(members))])
        ws, conn, layouts = drive(
            [{"type": "layout_split", "index": 0}], conn, layouts)
        label = f"{len(members)} members"
        if len(layouts.layouts) != len(members):
            print(f"  DETAIL {label}: got {len(layouts.layouts)} layouts, "
                  f"expected {len(members)}")
            ok = False
            continue
        for lay, want in zip(layouts.layouts, members):
            if lay.members != [want]:
                print(f"  DETAIL {label}: layout {lay.name!r} holds "
                      f"{lay.members}, expected [{want:#x}]")
                ok = False
            if lay.template is not None:
                print(f"  DETAIL {label}: {lay.name!r} is not solo "
                      f"({lay.template!r})")
                ok = False
        if not sent_of(ws, "layout_state"):
            print(f"  DETAIL {label}: the phone was never answered")
            ok = False
    return ok


def check_split_replaces_the_source_layout_in_place() -> bool:
    """The new layouts land where the grid stood in the list, in member
    order — not appended at the end, which would silently re-order every
    layout after it in the phone's list."""
    conn, layouts = build_layouts(
        [("Before", [WIN_A]), ("Work", [WIN_B, WIN_C]), ("After", [WIN_D])])
    drive([{"type": "layout_split", "index": 1}], conn, layouts)
    got = names_of(layouts)
    if len(got) != 4 or got[0] != "Before" or got[-1] != "After":
        print(f"  DETAIL order is {got}, expected Before, two split "
              f"pieces, After")
        return False
    return True


def check_a_solo_layout_has_nothing_to_split() -> bool:
    conn, layouts = build_layouts([("Solo", [WIN_A])])
    ws, conn, layouts = drive([{"type": "layout_split", "index": 0}], conn, layouts)
    if len(layouts.layouts) != 1:
        print(f"  DETAIL a solo layout changed: {names_of(layouts)}")
        return False
    return bool(sent_of(ws, "toast"))


def check_split_active_focus_moves_to_the_first_piece() -> bool:
    """The phone was looking at exactly the grid that split apart — it must
    land on the FIRST new piece, the same spot in the bar the grid stood in,
    never silently dropped to the desktop."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B])])
    drive([{"type": "layout_focus", "index": 0}], conn, layouts)
    if conn["active"] != 0:
        print("  DETAIL setup: the grid was never focused")
        return False
    ws, conn, layouts = drive([{"type": "layout_split", "index": 0}], conn, layouts)
    if conn["active"] != 0 or layouts.layouts[0].members != [WIN_A]:
        print(f"  DETAIL active={conn['active']}, layout 0 holds "
              f"{layouts.layouts[0].members if layouts.layouts else None}")
        return False
    return True


def check_split_preserves_each_members_own_source_record() -> bool:
    """TASK 173's whole reason for being: a source record is kept per MEMBER,
    not per layout, precisely so it can survive the member leaving its
    siblings. Built on the real torn-off-tab fixture — a hand-built dict would
    prove nothing about what `create` actually records."""
    ws, conn, layouts = build_with_a_torn_off_tab(1)  # tab lands in cell 1 of a 2-grid
    branch = next(l for l in layouts.layouts if l.name == "Branch")
    extracted = next(iter(branch.sources))
    src = branch.sources[extracted]
    index = names_of(layouts).index("Branch")
    ws, conn, layouts = drive([{"type": "layout_split", "index": index}], conn, layouts)
    piece = next((l for l in layouts.layouts if extracted in l.members), None)
    if piece is None:
        print("  DETAIL the extracted window is in no layout after the split")
        return False
    if piece.sources.get(extracted) != src:
        print(f"  DETAIL {piece.name!r}'s source record is "
              f"{piece.sources}, expected {{{extracted:#x}: {src:#x}}}")
        return False
    return True


# ═════════════════════════ EJECT (task 197b) ═════════════════════════
def check_eject_makes_a_new_layout_never_the_desktop() -> bool:
    """The contrast with `layout_member_remove` is the WHOLE point: the
    ejected window must appear as a NEW layout — something the phone can
    still show — not merely vanish from the grid onto the bare desk."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C])])
    ws, conn, layouts = drive(
        [{"type": "layout_member_eject", "index": 0, "member": 1}], conn, layouts)
    if len(layouts.layouts) != 2:
        print(f"  DETAIL {len(layouts.layouts)} layouts, expected 2 "
              f"(the shrunken grid + the ejected window's own new layout)")
        return False
    src = layouts.layouts[0]
    new = layouts.layouts[1]
    if WIN_B in src.members:
        print("  DETAIL the ejected window is still in the source grid")
        return False
    if new.members != [WIN_B]:
        print(f"  DETAIL the new layout holds {new.members}, expected [WIN_B]")
        return False
    return bool(sent_of(ws, "layout_state"))


def check_eject_reshapes_the_survivors() -> bool:
    ok = True
    for members, want_grid in (([WIN_A, WIN_B, WIN_C, WIN_D], "3-top"),
                               ([WIN_A, WIN_B, WIN_C], "2"),
                               ([WIN_A, WIN_B], None)):
        conn, layouts = build_layouts([("Work", list(members))])
        drive([{"type": "layout_member_eject", "index": 0, "member": 1}],
              conn, layouts)
        src = layouts.layouts[0]
        want_members = [h for h in members if h != members[1]]
        if src.members != want_members or src.template != want_grid:
            print(f"  DETAIL {len(members)} members: survivors "
                  f"{src.members}/{src.template}, expected "
                  f"{want_members}/{want_grid}")
            ok = False
    return ok


def check_the_ejected_window_drops_out_of_the_topmost_band() -> bool:
    """CLAUDE.md constraint 10: the ejected window belongs to a NEW layout
    that is not the one the phone is currently focused on, so it must not go
    on standing above everything the instant it changes hands."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C])])
    dropped: list[int] = []
    window_manager.drop_topmost = lambda hwnd: dropped.append(hwnd) or True
    drive([{"type": "layout_member_eject", "index": 0, "member": 1}],
          conn, layouts)
    if WIN_B not in dropped:
        print(f"  DETAIL the ejected window was never lowered (dropped: "
              f"{[hex(h) for h in dropped]})")
        return False
    return True


def check_eject_member_drops_topmost_at_its_own_boundary() -> bool:
    """THE METHOD'S OWN CONTRACT, asserted directly — because the end-to-end
    check above is MASKED: `layout_api.layout_member_eject` always follows
    `eject_member` with `layout_focus(index)`, whose own drop-pass lowers
    every OTHER layout's members (including the one the ejected window just
    joined) whether or not `eject_member` did its job. Calling the registry
    method directly, with no focus behind it, is the only way to see whether
    IT keeps its own promise — the same lesson `test_layout_member.py`'s
    `check_drop_member_leaves_the_orders_it_promises` was written for."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C])])
    dropped: list[int] = []
    window_manager.drop_topmost = lambda hwnd: dropped.append(hwnd) or True
    outcome = layouts.eject_member(0, 1)
    if outcome != "ejected":
        print(f"  DETAIL eject_member said {outcome!r}")
        return False
    if WIN_B not in dropped:
        print("  DETAIL eject_member itself never called drop_topmost — only "
              "the focus() that happens to follow it in the handler does")
        return False
    return True


def check_the_ejected_window_is_never_closed() -> bool:
    """Only the ✕ chooser closes windows, and only when he asked for that act
    (2026-08-08, task 116). Eject is not that act, and neither is split."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C])])
    drive([{"type": "layout_member_eject", "index": 0, "member": 1}],
          conn, layouts)
    if not window_manager.user32.IsWindow(WIN_B):
        print("  DETAIL the ejected window is no longer alive")
        return False
    return True


def check_eject_from_a_solo_is_refused_in_words() -> bool:
    """Nothing to eject FROM — the same guard `drop_member` uses for a
    single-member layout, just answered differently (there is no 'remove the
    whole layout' meaning for an eject)."""
    conn, layouts = build_layouts([("Solo", [WIN_A])])
    PLACED.clear()
    ws, conn, layouts = drive(
        [{"type": "layout_member_eject", "index": 0, "member": 0}], conn, layouts)
    if len(layouts.layouts) != 1 or layouts.layouts[0].members != [WIN_A]:
        print("  DETAIL the solo layout changed")
        return False
    return bool(sent_of(ws, "toast"))


def check_a_bad_member_ordinal_is_refused_in_words() -> bool:
    ok = True
    for member in (-1, 9):
        conn, layouts = build_layouts([("Work", [WIN_A, WIN_B])])
        ws, conn, layouts = drive(
            [{"type": "layout_member_eject", "index": 0, "member": member}],
            conn, layouts)
        if len(layouts.layouts) != 1 or layouts.layouts[0].members != [WIN_A, WIN_B]:
            print(f"  DETAIL member={member}: the layout changed")
            ok = False
        if not sent_of(ws, "toast"):
            print(f"  DETAIL member={member}: refused in silence")
            ok = False
    return ok


CHECKS = [
    ("split makes one solo layout per member",
     check_split_makes_one_solo_layout_per_member),
    ("split replaces the source layout IN PLACE, not at the list's end",
     check_split_replaces_the_source_layout_in_place),
    ("a solo layout has nothing to split",
     check_a_solo_layout_has_nothing_to_split),
    ("splitting the FOCUSED grid lands on its first piece",
     check_split_active_focus_moves_to_the_first_piece),
    ("split preserves EACH member's own source record (⭐/dependents)",
     check_split_preserves_each_members_own_source_record),
    ("eject makes a NEW layout, never the bare desktop",
     check_eject_makes_a_new_layout_never_the_desktop),
    ("eject reshapes the survivors (4->3, 3->2, 2->solo)",
     check_eject_reshapes_the_survivors),
    ("the ejected window drops out of the topmost band",
     check_the_ejected_window_drops_out_of_the_topmost_band),
    ("eject_member drops topmost at its OWN boundary (not masked by focus)",
     check_eject_member_drops_topmost_at_its_own_boundary),
    ("the ejected window is NEVER closed",
     check_the_ejected_window_is_never_closed),
    ("eject from a solo layout is refused in words",
     check_eject_from_a_solo_is_refused_in_words),
    ("a bad member ordinal is refused in words",
     check_a_bad_member_ordinal_is_refused_in_words),
]


def main() -> int:
    print("=== LAYOUT DECOMPOSE GATE (task 197) ===")
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
        print(f"LAYOUT DECOMPOSE GATE FAILED — {failed} check(s).")
        return 1
    print("LAYOUT DECOMPOSE GATE PASSED — a grid can come apart, whole or one "
          "window at a time.")
    return 0


def test_layout_decompose():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
