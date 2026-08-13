"""ONE WINDOW OUT OF A GRID — the `layout_member_remove` gate.

Owner request 2026-08-09 (task 165), his words in translation: each row of the
layout list has a rename button and an aspect button, "but there must be a
button by which I can throw ONE member out of the grid — to enter the grid
state and remove any member, i.e. change it to a single or to a 2-grid."
Until this round a grid could only be BUILT (`layout_merge`) or removed WHOLE,
so losing one window of four meant deleting the layout and making it again.

It is the merge read backwards, and it inherits the merge's catalogue: the
shape a shrunken layout lands in comes from `LayoutRegistry._template_for`,
the one function both directions use, so growing and shrinking can never
disagree about what a three is (his sheet, UV/grid_variations.png,
2026-08-07 — a 2 and a 4 have one arrangement each, a 3 has four).

The check that matters most here is the SAFETY one, exactly as under the ✕
block of tests/test_layout_protocol.py: the window that leaves must NOT be
closed, and must NOT be left stranded in the always-on-top band. Of everything
in this file that is the only part he cannot undo from the phone.

WHY THIS IS ITS OWN FILE (THE STRUCTURE LAW): tests/test_layout_protocol.py
stands at the ceiling — these checks put it at 1,154 lines — and the boundary
is real anyway: what lives here is a layout SHRINKING, one window at a time.
It is the same seam tests/test_layout_drag.py was cut on the same day.

NOTHING is copied. The Windows model, the fake socket and the real-dispatcher
runner come from test_layout_protocol; the MULTI-WINDOW fixture
(`build_layouts`, `names_of`, WIN_C/WIN_D — a desk with more than two windows
on it) comes from test_layout_drag, which defines it. One copy, imported, in a
chain that only ever points one way: member -> drag -> protocol. Worth a
follow-up once both rounds are merged — `build_layouts` is harness, not a drag
gesture, and its home is really test_layout_protocol beside `install_fakes`.

Run:  .venv\\Scripts\\python tests/test_layout_member.py
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
    CLOSED, MON, PLACED, WIN_A, WIN_B, drive, install_close_model, sent_of,
)


def member_run(members, member, grid=None, track=True):
    """One layout of `members`, then one `layout_member_remove`. Built and
    driven through the REAL dispatcher, like every check in the sibling file —
    a hand-built registry would prove the handler nothing."""
    conn, layouts = build_layouts([("Work", list(members))], track=track)
    PLACED.clear()
    msg = {"type": "layout_member_remove", "index": 0, "member": member}
    if grid:
        msg["grid"] = grid
    ws, conn, layouts = drive([msg], conn, layouts)
    return ws, conn, layouts


# ═══════════════════════ the sizes his sentence names ═══════════════════════
def check_a_grid_shrinks_one_window_at_a_time() -> bool:
    """His sentence, as sizes: a four becomes a three, a three a two, a two a
    single. The SHAPE has to follow the size — three windows still standing in
    a 2x2 is not a three — and the phone has to be told."""
    ok = True
    for members, want_grid in (([WIN_A, WIN_B, WIN_C, WIN_D], "3-top"),
                               ([WIN_A, WIN_B, WIN_C], "2"),
                               ([WIN_A, WIN_B], None)):
        label = f"{len(members)}->{len(members) - 1}"
        ws, conn, layouts = member_run(members, member=1)
        if len(layouts.layouts) != 1:
            print(f"  DETAIL {label}: the layout itself disappeared")
            ok = False
            continue
        lay = layouts.layouts[0]
        want_members = [h for h in members if h != members[1]]
        if lay.members != want_members:
            print(f"  DETAIL {label}: members are {lay.members}, expected "
                  f"{want_members}")
            ok = False
        if lay.template != want_grid:
            print(f"  DETAIL {label}: the shape became {lay.template!r}, "
                  f"expected {want_grid!r}")
            ok = False
        if not sent_of(ws, "layout_state"):
            print(f"  DETAIL {label}: the phone was never answered")
            ok = False
    return ok


def check_the_leftovers_are_re_placed_into_the_new_shape() -> bool:
    """A shape change that moves no window is the Move handle's bug all over
    again (owner 2026-08-07, "uvek ostavi centrirano" — lang-ok: owner quote):
    the phone's panel changed and the PC did not. Every survivor must be
    commanded onto a cell of the NEW arrangement, and the rects must really be
    that arrangement's cells — read out of grids.py rather than restated here,
    so this check cannot agree with a wrong answer."""
    ok = True
    for members, want_grid in (([WIN_A, WIN_B, WIN_C, WIN_D], "3-top"),
                               ([WIN_A, WIN_B, WIN_C], "2"),
                               ([WIN_A, WIN_B], None)):
        label = f"{len(members)}->{len(members) - 1}"
        ws, conn, layouts = member_run(members, member=1)
        placed = {hwnd: rect for hwnd, rect in PLACED}
        survivors = [h for h in members if h != members[1]]
        if sorted(placed) != sorted(survivors):
            print(f"  DETAIL {label}: placed {sorted(placed)}, expected every "
                  f"survivor {sorted(survivors)}")
            ok = False
            continue
        # build_layouts creates landscape layouts, so the aspect is 1/ratio.
        region = window_manager.layout_region(
            window_manager._work_area(MON), 1.0 / conn["ratio"])
        cells = (window_manager._cells(region, want_grid, "landscape")
                 if want_grid else [region])
        got = [placed[h] for h in survivors]
        if got != [tuple(c) for c in cells]:
            print(f"  DETAIL {label}: landed on {got}, expected the "
                  f"{want_grid or 'solo'} cells {cells}")
            ok = False
    return ok


# ═════════════════ the half he cannot undo from the phone ═════════════════
def check_the_window_that_leaves_is_never_closed() -> bool:
    """THE SAFETY PROPERTY, the same one the ✕ block opens with. Throwing a
    window out of a grid takes it out of a LIST — it is not a close, and only
    the ✕ chooser closes windows, and only when he asked for that act
    (2026-08-08, task 116). Written against the real `close_windows` desk
    model, so a handler that reached for it is caught here and nowhere else."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C])])
    install_close_model()
    ws, conn, layouts = drive(
        [{"type": "layout_member_remove", "index": 0, "member": 1}],
        conn, layouts)
    if CLOSED:
        print(f"  DETAIL WM_CLOSE went to {[hex(h) for h in CLOSED]} — his windows")
        return False
    if not window_manager.user32.IsWindow(WIN_B):
        print("  DETAIL the window that left the grid is no longer alive")
        return False
    return True


def check_the_window_that_leaves_drops_out_of_the_topmost_band() -> bool:
    """CLAUDE.md constraint 10: nothing we raise may outlive us up there. The
    leaving window is exactly the one no member list can still name a moment
    later — the case the LEDGER was written for — so the drop has to happen ON
    THE WAY OUT, while we still know about it. Missing this strands one of his
    windows above everything for the rest of the Windows session, and nothing
    on the phone would ever say so."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C])])
    dropped: list[int] = []
    window_manager.drop_topmost = lambda hwnd: dropped.append(hwnd) or True
    drive([{"type": "layout_member_remove", "index": 0, "member": 1}],
          conn, layouts)
    if WIN_B not in dropped:
        print(f"  DETAIL the leaving window was never lowered (dropped: "
              f"{[hex(h) for h in dropped]})")
        return False
    return True


def check_the_last_member_removes_the_layout() -> bool:
    """A single window thrown out of a solo layout leaves nothing to BE a
    layout — and it goes through the same `remove()` path, not a second
    teardown of its own. The phone must be told, and the connection must stop
    claiming a focus that no longer exists."""
    ws, conn, layouts = member_run([WIN_A], member=0)
    if layouts.layouts:
        print(f"  DETAIL the empty layout survived: {names_of(layouts)}")
        return False
    if conn["active"] is not None or conn["region"] is not None:
        print(f"  DETAIL the connection still claims layout {conn['active']}")
        return False
    states = sent_of(ws, "layout_state")
    if not states or states[-1]["active"] is not None:
        print("  DETAIL the phone was not told the layout is gone")
        return False
    return bool(sent_of(ws, "toast"))


# ═══════════════════════ refusals, shapes and the keyboard ═══════════════════
def check_a_member_that_is_not_there_is_refused_in_words() -> bool:
    """The panel was open while the desk changed — a window closed, the layout
    pruned under it, and the ordinal he taps now names nothing. Nothing may
    move, and the refusal must reach the phone: a silent no-op reads as the
    button being broken, which is how a feature gets reported twice."""
    ok = True
    for index, member in ((0, 7), (0, -1), (5, 0)):
        conn, layouts = build_layouts([("Work", [WIN_A, WIN_B])], track=True)
        PLACED.clear()
        ws, conn, layouts = drive(
            [{"type": "layout_member_remove", "index": index, "member": member}],
            conn, layouts)
        if len(layouts.layouts) != 1 or layouts.layouts[0].members != [WIN_A, WIN_B]:
            print(f"  DETAIL index={index} member={member}: the layout changed")
            ok = False
        if PLACED:
            print(f"  DETAIL index={index} member={member}: windows moved: {PLACED}")
            ok = False
        if not sent_of(ws, "toast"):
            print(f"  DETAIL index={index} member={member}: refused in silence")
            ok = False
    return ok


def check_a_four_lands_on_the_three_the_phone_named() -> bool:
    """A four coming down to a three is the ONE place in the catalogue where a
    real choice exists (owner 2026-08-07 — his sheet holds four drawings in the
    3 row and one each in the 2 and 4 rows). So the message may carry it, an
    unnamed one takes the sheet's first drawing, and a name of the wrong SIZE
    is ignored rather than obeyed into a shape with an empty cell."""
    ok = True
    for grid, want in (("3-right", "3-right"), ("3-left", "3-left"),
                       ("3-bottom", "3-bottom"), (None, "3-top"),
                       ("4", "3-top"), ("nonsense", "3-top")):
        _, _, layouts = member_run([WIN_A, WIN_B, WIN_C, WIN_D], member=3,
                                   grid=grid)
        got = layouts.layouts[0].template if layouts.layouts else None
        if got != want:
            print(f"  DETAIL the phone asked for {grid!r} and got {got!r}, "
                  f"expected {want!r}")
            ok = False
    return ok


def check_the_keyboard_follows_when_its_window_leaves() -> bool:
    """`last_member` is WHICH window the phone types into, and `focus` raises
    it LAST so it keeps the keyboard (owner 2026-08-06 — a dictation
    interrupted by one excursion used to resume in the other agent's session).
    If the window he was typing into is the one thrown out, that pointer must
    move to a survivor: a handle no longer in the list leaves the raise order
    pointing at a stranger."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C])])
    layouts.layouts[0].last_member = WIN_B
    drive([{"type": "layout_member_remove", "index": 0, "member": 1}],
          conn, layouts)
    lay = layouts.layouts[0]
    if lay.last_member not in lay.members:
        print(f"  DETAIL the keyboard still points at {lay.last_member:#x}, "
              "which left the layout")
        return False
    return True


def check_drop_member_leaves_the_orders_it_promises() -> bool:
    """THE METHOD'S OWN CONTRACT, asserted at its own boundary — and this check
    exists because planting the defects proved the others could not see it.

    Two of `drop_member`'s promises are today MASKED by the focus that follows
    it: `focus` starts with `prune`, which re-homes a `last_member` that has
    left the list, and it re-places whenever `_standing` says the windows are
    not on their targets — which after a shape change they never are. So both
    lines could be deleted and every end-to-end check above would stay green,
    while the method quietly stopped keeping its word. They are not decoration:
    `place_pending` is the explicit order for the case where every member
    HAPPENS to stand on a cell of the new shape (the reason `focus` reads it at
    all), and the keyboard pointer must be right BEFORE anything else runs, not
    because something later tidies up after it.

    A check on a value the user cannot see proves nothing about a feature he
    judges by geometry (2026-08-07) — so this one is deliberately the SMALLEST
    such check, and it sits beside four that measure rects."""
    ok = True
    for members, want_grid in (([WIN_A, WIN_B, WIN_C, WIN_D], "3-top"),
                               ([WIN_A, WIN_B, WIN_C], "2"),
                               ([WIN_A, WIN_B], None)):
        _, layouts = build_layouts([("Work", list(members))])
        lay = layouts.layouts[0]
        lay.last_member = members[1]      # he is typing into the one that leaves
        lay.place_pending = False         # a settled layout, nothing outstanding
        outcome = layouts.drop_member(0, 1)
        if outcome != "dropped":
            print(f"  DETAIL {len(members)} members: drop_member said {outcome!r}")
            ok = False
            continue
        if members[1] in lay.members:
            print(f"  DETAIL {len(members)} members: {members[1]:#x} is still in "
                  "the layout")
            ok = False
        if lay.template != want_grid:
            print(f"  DETAIL {len(members)} members: shape is {lay.template!r}, "
                  f"expected {want_grid!r}")
            ok = False
        if not lay.place_pending:
            print(f"  DETAIL {len(members)} members: no re-place was ordered — a "
                  "shape change that every member happens to satisfy would "
                  "leave the windows in the old arrangement")
            ok = False
        if lay.last_member != lay.members[0]:
            print(f"  DETAIL {len(members)} members: the keyboard points at "
                  f"{lay.last_member:#x}, expected the first survivor "
                  f"{lay.members[0]:#x}")
            ok = False
    return ok


def check_layout_state_names_every_member() -> bool:
    """The phone cannot ask for a window it was never told about. `member_titles`
    rides every frame, in CELL ORDER — cell k of the drawing is member k
    (client/grid-icons.js) — which is what lets him pick by pointing at a
    square instead of reading a list."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C])])
    ws, conn, layouts = drive([{"type": "layout_focus", "index": 0}],
                              conn, layouts)
    states = sent_of(ws, "layout_state")
    if not states:
        print("  DETAIL no layout_state at all")
        return False
    entry = states[-1]["layouts"][0]
    titles = entry.get("member_titles")
    if not isinstance(titles, list) or len(titles) != entry["members"]:
        print(f"  DETAIL member_titles is {titles!r} for {entry['members']} "
              "members")
        return False
    if entry.get("title") != titles[0]:
        print("  DETAIL the first member's title disagrees with `title`")
        return False
    return True


def check_the_leaving_window_takes_its_source_record_with_it() -> bool:
    """TASK 173 + 171 (2026-08-09). A member that was EXTRACTED from another
    window carries a record of where it came from, and that record is what
    makes the other layout wear the ⭐ and what the ✕ chooser's warning is
    built out of ("Also destroys …"). When the extracted window LEAVES this
    layout, the record has to leave with it — otherwise the trunk goes on
    being marked as the parent of a branch that no longer holds its content,
    and the phone warns him about destroying something a close cannot touch.

    Driven through the REAL creation path, because the record is only ever
    written there: the pair is built by test_layout_drag's own fixture, so
    there is one definition of "a torn-off tab" in this chain."""
    ok = True
    ws, conn, layouts = build_with_a_torn_off_tab(1)
    branch = next((l for l in layouts.layouts if l.name == "Branch"), None)
    if branch is None or len(branch.sources) != 1:
        print(f"  DETAIL nothing was recorded to lose: "
              f"{getattr(branch, 'sources', None)}")
        return False
    extracted = next(iter(branch.sources))
    index = names_of(layouts).index("Branch")
    member = branch.members.index(extracted)
    ws, conn, layouts = drive(
        [{"type": "layout_member_remove", "index": index, "member": member}],
        conn, layouts)
    if branch.sources:
        print(f"  DETAIL the branch still remembers {branch.sources} after the "
              "window it was extracted into left the layout")
        ok = False
    # …AND AT THE METHOD'S OWN BOUNDARY, because planting the defect proved the
    # end-to-end case cannot see it: `focus` starts with `prune`, and `prune`
    # drops every source record whose member has left the list — so
    # `drop_member` could stop keeping its word and every frame above would
    # still be correct. The same masking the re-place order is checked around,
    # ten lines up, and the same answer.
    ws2, conn2, layouts2 = build_with_a_torn_off_tab(1)
    fresh = next(l for l in layouts2.layouts if l.name == "Branch")
    who = next(iter(fresh.sources))
    fresh.drop = layouts2.drop_member(
        names_of(layouts2).index("Branch"), fresh.members.index(who))
    if fresh.sources:
        print(f"  DETAIL drop_member left {fresh.sources} behind — only the "
              "prune that happens to follow it cleans up")
        ok = False
    # …and the phone is told: the trunk stops being a parent in the very frame
    # that answers the removal, not on some later refresh.
    states = sent_of(ws, "layout_state")
    trunk = next((e for e in (states[-1]["layouts"] if states else [])
                  if e["name"] == "Trunk"), None)
    if trunk is None or trunk.get("parent") or trunk.get("dependents"):
        print(f"  DETAIL the trunk is still marked: {trunk}")
        ok = False
    return ok


def check_an_organic_close_reshapes_the_grid() -> bool:
    """LIVE-TESTER DEFECT (2026-08-13): `layout_member_remove` is a deliberate
    act and it reshapes the grid through `_template_for`, exactly like
    `merge`/`eject_member`. A window closed at the DESK — never asked, never
    routed through that handler — is the one path that left `lay.template`
    naming a shape one window too big for what survived it: a four still
    called "4" with three members standing on three of its four quadrants,
    which is exactly what `_template_for`'s own catalogue warns a caller never
    to claim, and exactly what `layout_state` would then hand the phone.

    Driven at `LayoutRegistry.prune()` itself, not through a message: there is
    no protocol message for "a window closed on its own", so the method
    boundary IS the only boundary here."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C, WIN_D])])
    lay = layouts.layouts[0]
    if lay.template != "4" or len(lay.members) != 4:
        print(f"  DETAIL setup failed: template={lay.template!r} "
              f"members={lay.members}")
        return False
    window_manager.user32.alive.discard(WIN_C)   # closed organically, at the desk
    lay.place_pending = False                    # isolate THIS reshape's own trigger
    layouts.prune()
    if len(lay.members) != 3 or WIN_C in lay.members:
        print(f"  DETAIL the closed window is still counted: {lay.members}")
        return False
    if lay.template != "3-top":
        print(f"  DETAIL still claims {lay.template!r} over 3 survivors — "
              f"exactly the stale grid `layout_state` would repeat to the phone")
        return False
    if not lay.place_pending:
        print("  DETAIL the shape changed but no re-place was ordered — the "
              "survivors would stay sitting on the old template's quadrants")
        return False
    return True


CHECKS = [
    ("a grid shrinks one window at a time (4→3, 3→2, 2→single)",
     check_a_grid_shrinks_one_window_at_a_time),
    ("the leftovers are RE-PLACED into the new shape",
     check_the_leftovers_are_re_placed_into_the_new_shape),
    ("the window that leaves is NEVER closed",
     check_the_window_that_leaves_is_never_closed),
    ("the window that leaves drops out of the topmost band",
     check_the_window_that_leaves_drops_out_of_the_topmost_band),
    ("removing the LAST member removes the layout",
     check_the_last_member_removes_the_layout),
    ("a member that is not there is refused IN WORDS",
     check_a_member_that_is_not_there_is_refused_in_words),
    ("a four lands on the three the phone named",
     check_a_four_lands_on_the_three_the_phone_named),
    ("the keyboard follows when its own window leaves",
     check_the_keyboard_follows_when_its_window_leaves),
    ("drop_member leaves the orders it promises (re-place + keyboard)",
     check_drop_member_leaves_the_orders_it_promises),
    ("layout_state NAMES every member, in cell order",
     check_layout_state_names_every_member),
    ("the leaving window takes its SOURCE record with it",
     check_the_leaving_window_takes_its_source_record_with_it),
    ("a member that closes ORGANICALLY reshapes the grid too",
     check_an_organic_close_reshapes_the_grid),
]


def main() -> int:
    print("=== LAYOUT MEMBER GATE ===")
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
        print(f"LAYOUT MEMBER GATE FAILED — {failed} check(s).")
        return 1
    print("LAYOUT MEMBER GATE PASSED — a grid can lose one window, and the "
          "window keeps its life.")
    return 0


def test_layout_member():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
