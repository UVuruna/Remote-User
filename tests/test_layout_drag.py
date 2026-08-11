"""A ROW DRAGGED ONTO ANOTHER IS A GRID — the server half of the list's gesture.

The FINDING here is the absence, not the feature. `layout_merge` and
`layout_reorder` shipped whole on 2026-08-07 — the client drag block, the
protocol, `LayoutRegistry.merge`/`.reorder` — and until 2026-08-09 not one test
file in this project mentioned either name. `tests/test_layout_protocol.py`,
the fail-closed gate for the whole layout protocol, had no merge, no reorder,
no drag and no hold in it. So when the owner reported the gesture dead on his
phone (task 162 — the arming was defeated on the CLIENT by a jitter test with
zero tolerance), nothing on this side could say whether the server half had
ever worked at all. That is the process failure this file answers.

Its own file rather than another section of the layout gate, for the plain
reason that file is at THE STRUCTURE LAW's ceiling — and because the boundary
is real: what lives here is the LIST'S OWN GESTURES, the two things a finger
can do to the order and the membership of layouts that already exist. The
phone's half of the same gesture — when a press becomes a hold — is gated
purely in tests/test_hold_gesture.py.

The fixtures are the layout gate's own (`install_fakes`, `drive`, the fake
desk): one Windows model, imported rather than copied, so a change to how the
desk is faked can never leave these two gates disagreeing about it.

Run:  .venv\\Scripts\\python tests/test_layout_drag.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_layout_protocol import (  # noqa: E402
    PLACED, WIN_A, WIN_B, drive, fresh_conn, install_fakes, sent_of,
    window_manager,
)

import uia  # noqa: E402  (after the import above, which puts server/ on the path)

WIN_C, WIN_D, WIN_E = 0x30, 0x40, 0x50
GRID_OF_SIZE = {1: None, 2: "2", 3: "3-top", 4: "4"}


def build_layouts(specs, track: bool = False):
    """One layout per `(name, [hwnd, …])`, created through the REAL dispatcher
    — so the registry these checks act on is the one the phone's own messages
    really produce, never a hand-built object."""
    install_fakes(track_placement=track)
    # A grid of four needs four windows on the desk. `prune()` asks user32
    # itself (`IsWindow`) rather than the patched `is_alive` — deliberately,
    # since 2026-08-05: a CLOAKED window is not a closed one. So the fake desk
    # has to know about these, or every layout past the first two is pruned the
    # moment it is created and the merge under test has nothing to merge.
    window_manager.user32.alive.update({WIN_C, WIN_D, WIN_E})
    conn, layouts = fresh_conn(), window_manager.LayoutRegistry()
    for name, hwnds in specs:
        _, conn, layouts = drive([{
            "type": "layout_create",
            "mode": "solo" if len(hwnds) == 1 else "grid",
            "grid": GRID_OF_SIZE[len(hwnds)], "orient": "landscape",
            "name": name,
            "slots": [{"hwnd": h, "tab": None, "x": 0.5, "y": 0.5} for h in hwnds],
        }], conn, layouts)
    return conn, layouts


def names_of(layouts) -> list[str]:
    return [lay.name for lay in layouts.layouts]


# ═══════════════════════ DROPPING ON A ROW: A GRID ═══════════════════════
def check_a_drop_makes_every_grid_size() -> bool:
    """1+1 → 2, 1+2 → 3, 1+3 → 4. The dragged layout DISAPPEARS (his answer to
    the first question, and the only one consistent with a window belonging to
    exactly one layout), its member joins the target's, and the phone is told."""
    ok = True
    for others, want in (([WIN_B], "2"), ([WIN_B, WIN_C], "3-top"),
                         ([WIN_B, WIN_C, WIN_D], "4")):
        conn, layouts = build_layouts([("Carried", [WIN_A]), ("Target", others)])
        ws, conn, layouts = drive(
            [{"type": "layout_merge", "source": 0, "target": 1}], conn, layouts)
        label = f"1+{len(others)}"
        if len(layouts.layouts) != 1:
            print(f"  DETAIL {label}: {len(layouts.layouts)} layouts left, "
                  f"expected the dragged one to be gone")
            ok = False
            continue
        lay = layouts.layouts[0]
        if lay.name != "Target":
            print(f"  DETAIL {label}: the surviving layout is {lay.name!r}")
            ok = False
        if lay.members != others + [WIN_A]:
            print(f"  DETAIL {label}: members are {lay.members}, expected "
                  f"{others + [WIN_A]}")
            ok = False
        if lay.template != want:
            print(f"  DETAIL {label}: grid became {lay.template!r}, expected {want!r}")
            ok = False
        if not sent_of(ws, "layout_state"):
            print(f"  DETAIL {label}: the phone was never answered")
            ok = False
    return ok


def check_a_three_takes_the_shape_the_phone_named() -> bool:
    """1+2 is the ONE size with a choice — which edge the single window takes —
    so the phone may name it. A phone that names nothing, or names a shape of
    the wrong SIZE (an old page, a field lost on the way), must still get a
    working three rather than a layout with a cell nobody is in."""
    ok = True
    for grid, want in (("3-left", "3-left"), ("3-right", "3-right"),
                       (None, "3-top"), ("4", "3-top")):
        conn, layouts = build_layouts([("Carried", [WIN_A]),
                                       ("Pair", [WIN_B, WIN_C])])
        msg = {"type": "layout_merge", "source": 0, "target": 1}
        if grid:
            msg["grid"] = grid
        _, conn, layouts = drive([msg], conn, layouts)
        got = layouts.layouts[0].template if layouts.layouts else None
        if got != want:
            print(f"  DETAIL the phone asked for {grid!r} and got {got!r}, "
                  f"expected {want!r}")
            ok = False
    return ok


def check_a_full_layout_refuses_and_says_so() -> bool:
    """FOUR is the ceiling. The phone greys a full row while a drag is in
    flight so the refusal is visible before the finger arrives — but the server
    may never lean on that: a fifth window would land in no cell at all. The
    refusal must leave BOTH layouts exactly as they were and reach the phone in
    words, or the row silently springs back and he simply tries again."""
    conn, layouts = build_layouts(
        [("Carried", [WIN_A]), ("Full", [WIN_B, WIN_C, WIN_D, WIN_E])])
    ws, conn, layouts = drive(
        [{"type": "layout_merge", "source": 0, "target": 1}], conn, layouts)
    if len(layouts.layouts) != 2:
        print(f"  DETAIL the merge went through anyway: {names_of(layouts)}")
        return False
    if layouts.layouts[1].members != [WIN_B, WIN_C, WIN_D, WIN_E]:
        print("  DETAIL a refused merge still changed the full layout's members")
        return False
    if not sent_of(ws, "toast"):
        print("  DETAIL the refusal was silent — the row just springs back")
        return False
    return bool(sent_of(ws, "layout_state"))


def check_a_row_dropped_on_itself_changes_nothing() -> bool:
    """The drop target under the finger IS the row being carried — reachable on
    any list, and a merge of a layout with itself would double its members."""
    conn, layouts = build_layouts([("Only", [WIN_A])])
    ws, conn, layouts = drive(
        [{"type": "layout_merge", "source": 0, "target": 0}], conn, layouts)
    return (len(layouts.layouts) == 1 and layouts.layouts[0].members == [WIN_A]
            and bool(sent_of(ws, "toast")))


def check_the_indices_shift_with_the_source_that_disappeared() -> bool:
    """The dragged layout is POPPED out of the list, so every index above it
    slides down by one — the target's included. The focus that follows a merge
    must land ON the merged layout and not on its neighbour, in BOTH
    directions, because the phone then frames whatever index it is given."""
    ok = True
    for src, dst, want_names, want_active in ((0, 2, ["B", "C"], 1),
                                              (2, 0, ["A", "B"], 0)):
        conn, layouts = build_layouts([("A", [WIN_A]), ("B", [WIN_B]),
                                       ("C", [WIN_C])])
        ws, conn, layouts = drive(
            [{"type": "layout_merge", "source": src, "target": dst}], conn, layouts)
        if names_of(layouts) != want_names:
            print(f"  DETAIL {src}->{dst}: the list is {names_of(layouts)}, "
                  f"expected {want_names}")
            ok = False
            continue
        states = sent_of(ws, "layout_state")
        told = states[-1]["active"] if states else None
        if conn["active"] != want_active or told != want_active:
            print(f"  DETAIL {src}->{dst}: focused {conn['active']} and told the "
                  f"phone {told}, expected {want_active}")
            ok = False
        elif len(layouts.layouts[want_active].members) != 2:
            print(f"  DETAIL {src}->{dst}: the focused layout is not the merged "
                  f"one ({layouts.layouts[want_active].members})")
            ok = False
    return ok


# ═══════════════════ DROPPING IN A GAP: THE ORDER ONLY ═══════════════════
def check_reorder_moves_the_row_and_nothing_on_the_pc() -> bool:
    """Dropping BETWEEN two rows only re-orders the list. `before` is a GAP in
    the list as the PHONE sees it, so once the source is popped out every gap
    above it has slid down by one — that correction is the whole of `reorder`,
    and every case here is a gap a finger can really be over: both ends, the
    middle, an index past the end, and the two no-ops of dropping a row back
    where it already was. Nothing may move on the PC either — `PLACED` stays
    empty, which is what "nothing on the PC moves" means in rects."""
    ok = True
    for source, before, want in ((0, 2, ["B", "A", "C"]),
                                 (2, 0, ["C", "A", "B"]),
                                 (0, 3, ["B", "C", "A"]),
                                 (1, 1, ["A", "B", "C"]),
                                 (1, 2, ["A", "B", "C"]),
                                 (0, 99, ["B", "C", "A"])):
        conn, layouts = build_layouts([("A", [WIN_A]), ("B", [WIN_B]),
                                       ("C", [WIN_C])], track=True)
        PLACED.clear()
        ws, conn, layouts = drive(
            [{"type": "layout_reorder", "source": source, "before": before}],
            conn, layouts)
        if names_of(layouts) != want:
            print(f"  DETAIL reorder({source}, {before}) -> {names_of(layouts)}, "
                  f"expected {want}")
            ok = False
        if PLACED:
            print(f"  DETAIL reorder({source}, {before}) moved windows on the "
                  f"PC: {PLACED}")
            ok = False
        if not sent_of(ws, "layout_state"):
            print(f"  DETAIL reorder({source}, {before}) never answered the phone")
            ok = False
    return ok


def check_a_reorder_keeps_the_focus_on_the_same_layout() -> bool:
    """THE FOCUS RIDES ON AN INDEX, AND A REORDER MOVES INDICES (found
    2026-08-09 while wiring the phone's side of this list; the handler shipped
    on 2026-08-07 with no index bookkeeping at all). `conn["active"]` is a
    plain POSITION in the registry's list, so dragging a row into a new place
    while a layout was focused left the server believing a DIFFERENT layout
    was active: the phone framed one layout while the bar's ✕ would have
    offered to close another one's windows.

    Asserted by IDENTITY, never by number — "active is still 1" is exactly the
    claim that stayed true all through the bug. Every case here is a drop a
    finger can really make: the focused row carried over its neighbours and
    under them, and a stranger's row carried across the focused one in both
    directions."""
    ok = True
    for source, before, active in ((0, 3, 0), (2, 0, 2),   # the focused row moves
                                   (0, 3, 1), (2, 0, 1),   # another row jumps it
                                   (1, 1, 2)):             # a drop that changes nothing
        conn, layouts = build_layouts([("A", [WIN_A]), ("B", [WIN_B]),
                                       ("C", [WIN_C])])
        _, conn, layouts = drive([{"type": "layout_focus", "index": active}],
                                 conn, layouts)
        was = layouts.layouts[conn["active"]]
        ws, conn, layouts = drive(
            [{"type": "layout_reorder", "source": source, "before": before}],
            conn, layouts)
        now = (layouts.layouts[conn["active"]]
               if conn["active"] is not None
               and 0 <= conn["active"] < len(layouts.layouts) else None)
        label = f"focus {active}, reorder({source}, {before})"
        if now is not was:
            print(f"  DETAIL {label}: the server now calls "
                  f"{getattr(now, 'name', None)!r} active — the phone is "
                  f"showing {was.name!r}")
            ok = False
            continue
        # …and the phone must be TOLD that index, pointing at that same layout
        # in the very frame it arrives in.
        states = sent_of(ws, "layout_state")
        told = states[-1]["active"] if states else None
        listed = (states[-1]["layouts"][told]["name"]
                  if told is not None and told < len(states[-1]["layouts"])
                  else None)
        if told != conn["active"] or listed != was.name:
            print(f"  DETAIL {label}: told the phone {told} ({listed!r}), "
                  f"server holds {conn['active']} ({was.name!r})")
            ok = False
    return ok


# ═══════════════════ THE ⭐: WHICH ROW IS THE TRUNK ═══════════════════
def build_with_a_torn_off_tab(cell: int = 0, process: str = "code.exe"):
    """Three layouts, the REAL way: the window a tab was torn OUT of, an
    unrelated one, and the tab itself — now its own window, with the layout
    remembering where it came from. Only Windows is faked; `resolve_slot`,
    `LayoutRegistry.create` and `state()` all run for real.

    That pair is the ONLY shape in which the star can be true at all, which is
    why it is built rather than asserted about.

    `cell` is WHICH slot of the new layout the tab lands in, and it is the
    whole of task 173 (2026-08-09): `create` stored ONE source, taken from the
    first slot, so a tab extracted into cell 2, 3 or 4 of a grid left no record
    at all — the ⭐ and the ✕ chooser's warning both under-reported on exactly
    the layouts they exist for. Cell 0 is the shape that always worked; cell 1
    is the shape that never did."""
    conn, layouts = build_layouts([("Trunk", [WIN_A]), ("Plain", [WIN_B])])
    window_manager.user32.alive.add(WIN_C)
    # The extraction itself is Windows' job (a menu command or a SendInput
    # drag) and cannot run here — WIN_C is the window it would have produced.
    window_manager.window_at_hwnd = lambda hwnd: {
        "hwnd": hwnd, "title": "Remote User - Visual Studio Code",
        "process": process, "icon": None}
    # `Layout.process` is read via wm._process_name at create, not from the
    # dict above — the harness pins it to code.exe (test_layout_protocol:148),
    # so the app under test is steered here (task 201's Chrome variant).
    window_manager._process_name = lambda hwnd, p=process: p
    uia.extract_tab = lambda rect, x, y, info, name=None: WIN_C
    tab_slot = {"hwnd": WIN_A, "tab": {"name": "prompt.txt"},
                "x": 0.3, "y": 0.02}
    plain_slot = {"hwnd": WIN_D, "tab": None, "x": 0.5, "y": 0.5}
    slots = [tab_slot] if cell == 0 else [plain_slot, tab_slot]
    ws, conn, layouts = drive([{
        "type": "layout_create", "mode": "solo" if cell == 0 else "grid",
        "grid": None if cell == 0 else "2", "orient": "landscape",
        "name": "Branch", "slots": slots,
    }], conn, layouts)
    return ws, conn, layouts


def stars_of(ws) -> dict:
    """{layout name: is it starred} out of the last frame the phone got."""
    states = sent_of(ws, "layout_state")
    return {lay["name"]: lay.get("parent")
            for lay in (states[-1]["layouts"] if states else [])}


def check_the_star_marks_the_trunk_and_nothing_else() -> bool:
    """⭐ = THE TRUNK, NOT A BRANCH (owner decision 2026-08-09, task 169). The
    mark says: closing a window of THIS layout would take another layout's
    content with it. A star on the wrong row is worse than no star, so all
    three states are asserted in one build — the parent, the branch that came
    out of it, and an ordinary layout that has nothing to do with either."""
    ok = True
    ws, conn, layouts = build_with_a_torn_off_tab()
    got = stars_of(ws)
    want = {"Trunk": True, "Plain": False, "Branch": False}
    if got != want:
        print(f"  DETAIL the stars are {got}, expected {want}")
        ok = False
    # A layout that holds BOTH the window and the tab torn out of it is not a
    # parent of anyone: closing that pair together surprises nobody, and the
    # mark is about OTHER layouts losing their content. (`Trunk` is dragged
    # onto `Branch`, so the survivor carries the source AND the window.)
    names = names_of(layouts)
    ws, conn, layouts = drive([{"type": "layout_merge",
                                "source": names.index("Trunk"),
                                "target": names.index("Branch")}], conn, layouts)
    merged = stars_of(ws)
    if any(merged.values()):
        print(f"  DETAIL a self-contained pair is starred: {merged}")
        ok = False
    return ok


def deps_of(ws) -> dict:
    """{layout name: the names it would destroy} out of the last frame."""
    states = sent_of(ws, "layout_state")
    return {lay["name"]: lay.get("dependents")
            for lay in (states[-1]["layouts"] if states else [])}


def check_a_tab_in_a_LATER_cell_is_recorded_too() -> bool:
    """TASK 173 (2026-08-09): the star under-reported, and the reason was one
    line in `create` — `source` was a single handle taken from the FIRST slot,
    so a tab extracted into cell 2, 3 or 4 of a grid left no record at all. The
    layout whose window it came out of then wore no ⭐, and (task 171) the ✕
    chooser would have offered to close it without a word about what that
    destroys — on precisely the grids the mark exists for.

    Both shapes are asserted in ONE run, because a fixture that can only build
    the shape that already worked is a fixture that proves the old behaviour:
    cell 0 is the tab-as-first-member layout that has always been recorded,
    cell 1 is the one that never was. The claim is made by RELATION — which
    layout NAME is destroyed by which — never by a handle or an index, because
    handles are what the phone is never told and indices are what a reorder
    moves."""
    ok = True
    for cell in (0, 1):
        ws, conn, layouts = build_with_a_torn_off_tab(cell)
        got = stars_of(ws)
        want = {"Trunk": True, "Plain": False, "Branch": False}
        if got != want:
            print(f"  DETAIL a tab in cell {cell}: the stars are {got}, "
                  f"expected {want}")
            ok = False
        # …and the registry really holds one record per extracted MEMBER, so
        # `project()` still asks about the first member and nothing else.
        branch = next((l for l in layouts.layouts if l.name == "Branch"), None)
        if branch is None or list(branch.sources.values()) != [WIN_A]:
            print(f"  DETAIL a tab in cell {cell}: the branch remembers "
                  f"{getattr(branch, 'sources', None)}, expected the trunk")
            ok = False
    return ok


def check_the_phone_is_told_WHICH_layouts_a_close_would_destroy() -> bool:
    """TASK 171 (owner 2026-08-09): the ✕ chooser's close option must NAME the
    layouts that die with these windows, before he taps. The phone cannot know
    it — the relation lives in `Layout.sources` on the PC and no title on the
    phone spells it — so `layout_state` carries the NAMES.

    Names, not a count: "1 other layout" is a number, and what he needs before
    an irreversible tap is WHICH. Asserted against the layout that really holds
    the source window, so it cannot pass by counting."""
    ok = True
    ws, conn, layouts = build_with_a_torn_off_tab(1)
    got = deps_of(ws)
    want = {"Trunk": ["Branch"], "Plain": [], "Branch": []}
    if got != want:
        print(f"  DETAIL the dependents are {got}, expected {want}")
        ok = False
    # A SECOND branch out of the same trunk is a second name, not a second
    # star: the sentence he reads has to list both or it is not the truth.
    window_manager.user32.alive.add(WIN_E)
    uia.extract_tab = lambda rect, x, y, info, name=None: WIN_E
    ws, conn, layouts = drive([{
        "type": "layout_create", "mode": "solo", "orient": "landscape",
        "name": "Second branch",
        "slots": [{"hwnd": WIN_A, "tab": {"name": "CLAUDE.md"},
                   "x": 0.4, "y": 0.02}],
    }], conn, layouts)
    got = deps_of(ws)
    if sorted(got.get("Trunk") or []) != ["Branch", "Second branch"]:
        print(f"  DETAIL two branches, one trunk: {got}")
        ok = False
    # …and a branch that LEAVES stops being named. The record is per member,
    # so removing the layout that holds the extracted window must clear it —
    # otherwise the warning names a layout that no longer exists.
    names = names_of(layouts)
    ws, conn, layouts = drive(
        [{"type": "layout_remove", "index": names.index("Branch")}],
        conn, layouts)
    got = deps_of(ws)
    if (got.get("Trunk") or []) != ["Second branch"]:
        print(f"  DETAIL a removed branch is still named: {got}")
        ok = False
    return ok


def check_a_chrome_pair_never_stars() -> bool:
    """TASK 201 (owner correction 2026-08-10, his screenshot: a Chrome "DOMY"
    layout wore the ⭐): a Chrome or Explorer tab moved to its own window is a
    fully independent window — closing the origin destroys nothing — so the
    extraction still RECORDS its source (the record serves `project()` too),
    but neither the star nor the ✕ warning may fire. Only VS Code's torn-out
    content depends on its origin (PARENT_CLOSE_APPS). The same build as the
    VS Code pair, process swapped — so this check and the trunk check can
    only diverge on the app rule itself."""
    ok = True
    ws, conn, layouts = build_with_a_torn_off_tab(process="chrome.exe")
    got = stars_of(ws)
    want = {"Trunk": False, "Plain": False, "Branch": False}
    if got != want:
        print(f"  DETAIL a Chrome pair is starred: {got}, expected {want}")
        ok = False
    deps = deps_of(ws)
    if any(deps.values()):
        print(f"  DETAIL a Chrome close warns about: {deps}")
        ok = False
    # …while the source is still REMEMBERED (project() needs it) — the rule
    # scoped the STAR, never the record.
    branch = next((l for l in layouts.layouts if l.name == "Branch"), None)
    if branch is None or list(branch.sources.values()) != [WIN_A]:
        print("  DETAIL the Chrome branch forgot its source entirely")
        ok = False
    return ok


CHECKS = [
    ("a row dropped on another makes every grid size (1+1, 1+2, 1+3)",
     check_a_drop_makes_every_grid_size),
    ("a three takes the shape the phone named, and a sane one when it named none",
     check_a_three_takes_the_shape_the_phone_named),
    ("a FULL layout refuses the drop and says so",
     check_a_full_layout_refuses_and_says_so),
    ("a row dropped on ITSELF changes nothing",
     check_a_row_dropped_on_itself_changes_nothing),
    ("the indices shift with the source that disappeared",
     check_the_indices_shift_with_the_source_that_disappeared),
    ("reorder moves the row in the list and NOTHING on the PC",
     check_reorder_moves_the_row_and_nothing_on_the_pc),
    ("a reorder keeps the focus on the SAME layout, not on the same number",
     check_a_reorder_keeps_the_focus_on_the_same_layout),
    ("the ⭐ marks the trunk and nothing else",
     check_the_star_marks_the_trunk_and_nothing_else),
    ("a tab extracted into a LATER cell is recorded too",
     check_a_tab_in_a_LATER_cell_is_recorded_too),
    ("the phone is told WHICH layouts a close would destroy",
     check_the_phone_is_told_WHICH_layouts_a_close_would_destroy),
    ("a Chrome pair never stars — only VS Code has the parent dependency",
     check_a_chrome_pair_never_stars),
]


def main() -> int:
    print("=== LAYOUT DRAG GATE ===")
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
        print(f"LAYOUT DRAG GATE FAILED — {failed} check(s).")
        return 1
    print("LAYOUT DRAG GATE PASSED — a row dropped on another makes a grid, "
          "one dropped in a gap only moves.")
    return 0


def test_layout_drag():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
