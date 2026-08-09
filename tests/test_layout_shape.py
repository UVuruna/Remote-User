"""THE SHAPE OF AN EXISTING LAYOUT — the `layout_grid` gate.

Owner 2026-08-09, task 175: every act on a layout that already exists moved
under one common ⚙ icon, and one of those acts could not be performed AT ALL
before — a layout built portrait had to be DELETED and made again to become
landscape. The message it rides (`layout_grid {index, grid, orient}`) has
existed since 2026-08-07 for a THREE's arrangement.

THE FINDING IS THAT NOTHING DROVE IT. No test in this project mentioned
`layout_grid` or `set_grid` for two days — so "the server already has it" was a
claim about a NAME, not about a behaviour, and this round was about to build a
phone panel on top of it. That is the same absence tests/test_layout_drag.py
was written for on the same day, and it is why this file exists before the
panel's first screenshot rather than after his first report.

What it asserts is the RECTS. A shape change the phone shows and the PC ignores
is the Move handle's bug arriving in a new place (owner 2026-08-07, "uvek
ostavi centrirano" — lang-ok: owner quote), and a check on a stored value the
user cannot see proves nothing about a feature he judges by geometry.

WHY ITS OWN FILE (THE STRUCTURE LAW): tests/test_layout_protocol.py stands at
the ceiling — these checks put it at 1,018 lines — and the boundary is a real
one, the same seam test_layout_drag.py and test_layout_member.py were cut on:
what lives here is a layout CHANGING SHAPE without changing its membership.
The Windows model, the fake socket and the real-dispatcher runner are imported
from test_layout_protocol; nothing is copied.

Run:  .venv/Scripts/python tests/test_layout_shape.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import window_manager  # noqa: E402

from test_layout_protocol import (  # noqa: E402
    MON, PLACED, WIN_A, WIN_B, WIN_C, drive, install_fakes, sent_of,
)


# ═══════ the shape of an existing layout: orientation and arrangement ═══════
# Owner 2026-08-09, task 175: every act on an existing layout moved under one
# ⚙, and one of them could not be done AT ALL before — a layout built portrait
# had to be deleted and made again to become landscape. The message
# (`layout_grid {index, grid, orient}`) has existed since 2026-08-07 for a
# THREE's arrangement, and it was never gated: nothing in this project drove
# it, so "it already exists" was a claim about a name, not about a behaviour.
# What matters is that it MOVES THE WINDOWS — a shape change the phone shows
# and the PC ignores is the Move handle's bug in a new place (2026-08-07,
# "uvek ostavi centrirano"), so this asserts the RECTS.
def shape_run(members: int, grid: str | None, orient: str, msg: dict):
    """Create a layout, then one `layout_grid`. Returns (ws, layouts, rects)."""
    install_fakes(track_placement=True)
    slots = [{"hwnd": h, "tab": None, "x": 0.5, "y": 0.5}
             for h in [WIN_A, WIN_B, WIN_C][:members]]
    ws, conn, layouts = drive([
        {"type": "layout_create", "mode": "grid" if grid else "solo",
         "grid": grid, "orient": orient, "name": "Work", "slots": slots}])
    PLACED.clear()
    ws, conn, layouts = drive([dict(msg, index=0)], conn, layouts)
    return ws, layouts, [r for _, r in PLACED]


def check_the_shape_of_an_existing_layout_can_be_changed() -> bool:
    """His two cases. A THREE re-arranged (which edge its single window takes)
    and ANY layout turned portrait↔landscape — and in both the survivors must
    land on the cells of the NEW shape, read out of grids.py rather than
    restated here, so this check cannot agree with a wrong answer."""
    ok = True
    for members, grid, want_grid, want_orient, msg in (
        # the arrangement, at the size that has a choice at all
        (3, "3-top", "3-left", "landscape",
         {"type": "layout_grid", "grid": "3-left", "orient": "landscape"}),
        # the orientation, on a grid…
        (2, "2", "2", "portrait",
         {"type": "layout_grid", "grid": "2", "orient": "portrait"}),
        # …and on a SOLO layout, which the phone sends with an empty grid
        (1, None, None, "portrait",
         {"type": "layout_grid", "grid": "", "orient": "portrait"}),
    ):
        ws, layouts, rects = shape_run(members, grid, "landscape", msg)
        lay = layouts.layouts[0] if layouts.layouts else None
        label = f"{members} -> {msg.get('grid')!r}/{want_orient}"
        if lay is None or lay.template != want_grid or lay.orient != want_orient:
            print(f"  DETAIL {label}: became "
                  f"{getattr(lay, 'template', None)!r}/"
                  f"{getattr(lay, 'orient', None)!r}, expected "
                  f"{want_grid!r}/{want_orient!r}")
            ok = False
            continue
        aspect = (9 / 16) if want_orient == "portrait" else (16 / 9)
        region = window_manager.layout_region(
            window_manager._work_area(MON), aspect)
        cells = (window_manager._cells(region, want_grid, want_orient)
                 if want_grid else [region])
        if rects != [tuple(c) for c in cells]:
            print(f"  DETAIL {label}: the windows landed on {rects}, expected "
                  f"the {want_grid or 'solo'} cells {cells}")
            ok = False
        if not sent_of(ws, "layout_state"):
            print(f"  DETAIL {label}: the phone was never answered")
            ok = False
    # A shape of the WRONG SIZE is refused, not obeyed into a cell nobody is
    # in — and the refusal still turns the layout, because the orientation is
    # a separate question from the arrangement.
    ws, layouts, rects = shape_run(
        3, "3-top", "landscape",
        {"type": "layout_grid", "grid": "4", "orient": "portrait"})
    lay = layouts.layouts[0]
    if lay.template != "3-top" or lay.orient != "portrait":
        print(f"  DETAIL a three asked to become a four: {lay.template!r}/"
              f"{lay.orient!r}, expected '3-top'/'portrait'")
        ok = False
    # …AND THE RE-PLACE ORDER, at the method's own boundary. Planting its
    # removal proved every case above stays green without it: `focus` re-places
    # whenever `_standing` says the members are off their targets, which after
    # a shape change they always are. `place_pending` is for the case where
    # every member HAPPENS to stand on a cell of the new shape — the same
    # masking `drop_member`'s own boundary check exists for
    # (tests/test_layout_member.py).
    install_fakes()
    registry = window_manager.LayoutRegistry()
    registry.create(WIN_A, "grid", "3-top", [WIN_B, WIN_C], "landscape",
                    9 / 16, MON, "Work")
    settled = registry.layouts[0]
    settled.place_pending = False
    registry.set_grid(0, "3-left", "portrait")
    if not settled.place_pending:
        print("  DETAIL set_grid ordered no re-place — a shape change every "
              "member happens to satisfy would leave the windows as they were")
        ok = False
    return ok

CHECKS = [
    ("an existing layout's orientation and arrangement really move its windows",
     check_the_shape_of_an_existing_layout_can_be_changed),
]


def main() -> int:
    print("=== LAYOUT SHAPE GATE ===")
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
        print(f"LAYOUT SHAPE GATE FAILED — {failed} check(s).")
        return 1
    print("LAYOUT SHAPE GATE PASSED — a layout can be turned and re-arranged, "
          "and the windows really move.")
    return 0


def test_layout_shape():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
