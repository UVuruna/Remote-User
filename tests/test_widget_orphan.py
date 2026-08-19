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
# THE WHOLE SERVER TREE, not just server/gui/ (adversarial verifier, this same
# round): the glob was hard-coded to one directory, so a Qt module born
# anywhere else under server/ would be invisible to this sweep — a gate that
# silently stops covering new code is the failure mode this project has paid
# for more than once. Nothing outside server/gui/ builds a widget today; the
# point is that the sweep does not have to be edited on the day one does.
SWEPT_DIR = PROJECT_DIR / "server"

# The RECEIVER, not a bare name: `item.widget().setParent(None)` is the
# standard Qt teardown idiom and the first version of this pattern could not
# see it AT ALL (no match, therefore no complaint) — the worst kind of blind
# spot, because it reads as coverage. Captured whole so the hide() below must
# be on the SAME expression.
UNPARENT = re.compile(r"([A-Za-z_][\w.\[\]]*(?:\(\s*\))?[\w.\[\]()]*)"
                      r"\s*\.setParent\s*\(\s*None\s*\)")
# `hide()` is the rule; `setVisible(False)` is the same act spelled the long
# way. Built per receiver so `otherwidget.hide()` can never satisfy
# `widget.setParent(None)` — the original `name in prev` was plain substring
# containment, which the verifier broke with exactly that pair.
HIDDEN_TAIL = r"\s*\.\s*(?:hide\s*\(\s*\)|setVisible\s*\(\s*False\s*\))"


def _hidden_pattern(name: str) -> str:
    """`name.hide()` and nothing that merely CONTAINS `name`.

    The lookbehind is the whole point: without it `otherwidget.hide()` satisfies
    `widget.setParent(None)`, which is the false pass the adversarial verifier
    broke the first version of this gate with.
    """
    return r"(?<![\w.])" + re.escape(name) + HIDDEN_TAIL


def _swept_files() -> list[Path]:
    return sorted(SWEPT_DIR.rglob("*.py"))


def check_every_unparent_hides_first() -> bool:
    """Every `x.setParent(None)` under `server/` is preceded by hiding THAT
    SAME EXPRESSION, on one of the two lines above it.

    Two lines rather than one because the idiomatic teardown loop reads
    `item = layout.takeAt(0)` / `widget = item.widget()` and a guard may sit
    between; more than that and the pairing stops being readable anyway.

    The receiver is matched EXACTLY, never as a substring: `otherwidget.hide()`
    standing over `widget.setParent(None)` is not the promise this gate makes,
    and the first version of it accepted exactly that.
    """
    problems: list[str] = []
    for path in _swept_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = UNPARENT.search(line)
            if match is None:
                continue
            name = match.group(1)
            hidden = re.compile(_hidden_pattern(name))
            window = lines[max(0, index - 2):index]
            if not any(hidden.search(prev) for prev in window):
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


def _verdicts(text: str) -> list[tuple[str, bool]]:
    """The sweep's own arithmetic over a string — (receiver, hidden first?)."""
    out: list[tuple[str, bool]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = UNPARENT.search(line)
        if match is None:
            continue
        name = match.group(1)
        hidden = re.compile(_hidden_pattern(name))
        window = lines[max(0, index - 2):index]
        out.append((name, any(hidden.search(prev) for prev in window)))
    return out


def check_the_pattern_sees_what_it_claims() -> bool:
    """The sweep is held to its OWN reach, on planted snippets.

    Every case below was found by an independent adversarial verifier against
    the first version of this file, and each one was a SILENT pass — the worst
    kind, because a gate that sees nothing reports green exactly like a gate
    that saw everything and was satisfied.
    """
    cases: list[tuple[str, str, bool]] = [
        # (what it is, snippet, must the sweep be satisfied?)
        ("the plain teardown, hidden first",
         "widget.hide()\nwidget.setParent(None)", True),
        ("the plain teardown, NOT hidden",
         "widget.setParent(None)", False),
        ("setVisible(False) is the same act spelled long",
         "widget.setVisible(False)\nwidget.setParent(None)", True),
        # The idiom the first pattern could not see AT ALL.
        ("the takeAt idiom, hidden first",
         "item.widget().hide()\nitem.widget().setParent(None)", True),
        ("the takeAt idiom, NOT hidden",
         "item.widget().setParent(None)", False),
        # The substring hole: a hide() on a DIFFERENT variable.
        ("a hide() on another variable satisfies nothing",
         "otherwidget.hide()\nwidget.setParent(None)", False),
        ("an attribute receiver is matched whole",
         "self.row.hide()\nself.row.setParent(None)", True),
        ("a near-miss attribute does not stand in for it",
         "self.rows.hide()\nself.row.setParent(None)", False),
    ]
    ok = True
    for what, snippet, want in cases:
        verdicts = _verdicts(snippet)
        if not verdicts:
            print(f"    BLIND: the sweep does not see `{what}` at all")
            ok = False
            continue
        got = verdicts[0][1]
        if got != want:
            print(f"    WRONG: `{what}` — wanted {want}, got {got}")
            ok = False
    return ok


CHECKS = [
    ("every unparent hides the widget first", check_every_unparent_hides_first),
    ("the sweep really sees the idioms it claims",
     check_the_pattern_sees_what_it_claims),
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


def test_gate():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
