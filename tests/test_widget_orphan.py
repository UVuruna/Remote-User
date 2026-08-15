"""WIDGET ORPHAN GATE — nothing we unparent may become a visible window.

Owner report 2026-08-16, "FLASH sa otvaranjem nekog prozora u sredini": a
parentless `QWidget` IS a top-level window, not something merely window-LIKE.
There are two ways a widget of ours ends up without a parent, and both put a
real native window at Windows' default spot — the centre of the screen:

  1. TEARDOWN — `setParent(None)` on a VISIBLE child. It becomes a top-level
     window that instant, and `deleteLater()` only fires when the event loop
     comes back around; in that gap Qt creates the platform surface and sends
     `Show`. The flash is the window's whole life.
  2. CONSTRUCTION — a widget built bare and adopted later with `addWidget`.
     Anything that makes it visible in that span (`setCurrentRow`,
     `setCurrentIndex`, `show`) has the same effect.

The rule this gate holds is the fix for (1): `hide()` BEFORE `setParent(None)`.
It clears `WA_WState_Visible` while the widget is still a child, so the orphan
never gets a platform surface and there is nothing for Windows to show.

It is a SWEEP over every Qt module rather than a check on the one call site
that was reported — the same shape as `test_row_tap.py`'s panel sweep, and for
the same reason (constraint 28): a rule kept beside one call is read only by
somebody already standing there, and this codebase has paid for that twice.
So a NEW teardown written without the `hide()` fails the build here instead of
being found on his desk.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
GUI_DIR = PROJECT_DIR / "server" / "gui"

# `hide()` is the rule; `setVisible(False)` is the same act spelled the long
# way, and `takeAt`-style code sometimes reaches for it. Both are accepted.
HIDDEN = re.compile(r"\.(hide|setVisible)\s*\(\s*(False\s*)?\)")
UNPARENT = re.compile(r"(\w+)\s*\.setParent\s*\(\s*None\s*\)")


def _gui_files() -> list[Path]:
    return sorted(GUI_DIR.rglob("*.py"))


def check_every_unparent_hides_first() -> bool:
    """Every `x.setParent(None)` in `server/gui/` is preceded by hiding THAT
    SAME widget, on one of the two lines above it.

    Two lines rather than one because the idiomatic teardown loop reads
    `item = layout.takeAt(0)` / `widget = item.widget()` and a guard may sit
    between; more than that and the pairing stops being readable anyway.
    """
    problems: list[str] = []
    for path in _gui_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = UNPARENT.search(line)
            if match is None:
                continue
            name = match.group(1)
            window = lines[max(0, index - 2):index]
            if not any(HIDDEN.search(prev) and name in prev for prev in window):
                problems.append(
                    f"{path.relative_to(PROJECT_DIR)}:{index + 1}: "
                    f"`{name}.setParent(None)` with no `{name}.hide()` above it "
                    f"— a visible orphan is a window at the centre of his screen")
    for problem in problems:
        print(f"    {problem}")
    return not problems


def check_the_traffic_rows_are_the_reported_case() -> bool:
    """The site he reported is really covered by the sweep above — a sweep
    that no longer LOOKS at the reported file proves nothing about it, and a
    file moving out from under a gate is exactly how this project's gates have
    gone quietly blind before (the `test_lost_windows` lesson).
    """
    path = GUI_DIR / "traffic_window.py"
    if not path.exists():
        print(f"    {path.name} is gone — this gate's own subject moved")
        return False
    text = path.read_text(encoding="utf-8")
    if "setParent(None)" not in text:
        # The teardown was rewritten some other correct way (no unparenting at
        # all). Nothing left to hold here, and the sweep covers whatever came
        # in its place.
        return True
    return bool(re.search(
        r"widget\.hide\(\)\s*\n\s*widget\.setParent\(None\)", text))


CHECKS = [
    ("every unparent hides the widget first", check_every_unparent_hides_first),
    ("the reported traffic-row teardown is one of them",
     check_the_traffic_rows_are_the_reported_case),
]


def main() -> int:
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = bool(fn())
        except Exception as e:  # noqa: BLE001 — a gate reports, never hides
            ok = False
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    if failed:
        print(f"\nWIDGET ORPHAN GATE FAILED — {failed} check(s)")
        return 1
    print("\nWIDGET ORPHAN GATE PASSED — nothing we unparent is still visible "
          "when it becomes a window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
