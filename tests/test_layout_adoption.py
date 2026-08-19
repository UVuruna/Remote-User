"""LAYOUT ADOPTION LIFECYCLE GATE — an adopted window survives the session,
not one visit to its layout.

Owner report 2026-08-13 (defect 1, the fourth-round correction of task 202):
an agent's HTML report opened while he watched a layout; he tapped "show it in
the layout" and it appeared, exactly as designed. His NEXT sentence is what
this file holds: "it only drew it in those dimensions and opened the page in
those dimensions, but when you switch to another layout or the desktop and
come back, it restores the old one that should be there and this new window
just stands there, nowhere put INTO A LAYOUT." (translated)

THE CAUSE: `LayoutRegistry.focus()` re-places MEMBERS on every focus and never
looked at `lay.adopted` at all — worse, every path that stopped a layout being
shown (focusing another one, choosing Desktop) called `Layout.release_adopted()`
unconditionally, which moves the popup back to wherever Windows first put it
(usually outside the region) and FORGETS it. A mere switch was being treated
as the popup's session ending, which is a different question from the one
`test_session_residue.py` already answers next door — that file asks what must
be true once the PHONE is truly gone; this one asks what must be true when the
SAME layout is shown again, mid-session, which is exactly the gap four rounds
of `test_layout_popup.py` never had to close because none of them ever
refocused a layout twice. Its own file by RESPONSIBILITY, matching the split
`test_session_residue.py` made from `test_layout_popup.py` for the same
reason.

THE FIX, in two parts:
  * `Layout.drop_adopted_topmost()` — leaves the topmost band but leaves
    `adopted`/`adopted_home` standing, used by `focus()`'s switch-away pass and
    by `minimize_members()`'s ordinary (session-still-running) Desktop tap.
  * `LayoutRegistry.focus()` now re-contains every surviving adopted window on
    its way out, the same way it already re-places members.
  * `minimize_members(session_end=True)` — the ONE path that still restores
    the popup home and forgets it, because that path is `presence.leave_session`
    and constraint 23 (nothing of ours outlives the SESSION) genuinely applies
    there. Checks 1-3 prove the light path keeps the adoption; check 4 proves
    the true end still lets go of it, so the two cannot be confused for one
    another by a future edit.

Defect 2 (the chip's own wording) is proven by check 5: the "layout" chip's
yes used to read "Show in layout" beside "X opened" and was reported as an
offer to CREATE a layout — its yes has only ever MOVED the window in.

NOTHING HERE TOUCHES THE OWNER'S DESKTOP: the fake desk is `test_layout_popup`'s
own, shared rather than copied, exactly like `test_session_residue.py`.

Run:  .venv\\Scripts\\python tests/test_layout_adoption.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import run_checks, window_manager  # noqa: E402
from test_layout_popup import (  # noqa: E402
    LEDGER, MONITOR, POPUP, RECTS, STRANGER, ask, desk,
)

CLIENT_DIR = Path(__file__).resolve().parent.parent / "client"


def _adopt_popup(reg, conn):
    """His tap through the real chip flow: POPUP ends up in `lay.adopted`,
    centered in the layout's region — the same setup `test_layout_popup.py`
    itself uses for every "yes" check."""
    ask(reg, conn, act="layout")
    lay = reg.layouts[0]
    assert POPUP in lay.adopted, "setup failed: POPUP was never adopted"
    return lay


def check_switching_to_another_layout_does_not_forget_it() -> bool:
    """The exact sentence he wrote: switch to ANOTHER layout, and the adopted
    window must not be abandoned — merely lowered out of the topmost band,
    same as every ordinary member of a layout that is not shown right now."""
    reg, conn = desk(fg=POPUP)
    lay = _adopt_popup(reg, conn)
    before = RECTS[POPUP]
    # A second, unrelated layout to switch to.
    other = window_manager.Layout("Other", "app.exe", [STRANGER], None,
                                  "portrait", 0.5)
    reg.layouts.append(other)
    reg.focus(1, conn["ratio"], MONITOR)
    if POPUP not in lay.adopted:
        print("  DETAIL switching layouts forgot the adopted window")
        return False
    if POPUP in LEDGER:
        print("  DETAIL it stayed in the always-on-top band for a layout "
              "the phone is no longer showing")
        return False
    if RECTS[POPUP] != before:
        print(f"  DETAIL it was moved ({before} -> {RECTS[POPUP]}) on a mere "
              f"switch — nothing may move without being asked or the session "
              f"truly ending")
        return False
    return True


def check_it_returns_when_its_own_layout_is_focused_again() -> bool:
    """The other half of the same sentence: switch BACK, and it must reappear
    in the picture — this is the part `focus()` never did at all before the
    fix, whatever `release_adopted` did or did not forget.

    The region compared against is MEASURED from the members' own post-focus
    rects, never the fixture's `REGION` constant: `focus()` computes its own
    geometry from `grids.layout_region`, which need not equal the union the
    members merely started at (constraint 13 — measured, never remembered —
    applies to this check's own assumptions just as much as to the code)."""
    reg, conn = desk(fg=POPUP)
    lay = _adopt_popup(reg, conn)
    other = window_manager.Layout("Other", "app.exe", [STRANGER], None,
                                  "portrait", 0.5)
    reg.layouts.append(other)
    reg.focus(1, conn["ratio"], MONITOR)          # away
    reg.focus(0, conn["ratio"], MONITOR)           # back
    if POPUP not in LEDGER:
        print("  DETAIL it did not re-enter the always-on-top band")
        return False
    ax, ay, aw, ah = RECTS[lay.members[0]]
    bx, by, bw, bh = RECTS[lay.members[1]]
    rx, ry = min(ax, bx), min(ay, by)
    rw = max(ax + aw, bx + bw) - rx
    rh = max(ay + ah, by + bh) - ry
    x, y, w, h = RECTS[POPUP]
    if not (rx <= x and ry <= y and x + w <= rx + rw and y + h <= ry + rh):
        print(f"  DETAIL it is back on top but outside the region: "
              f"{RECTS[POPUP]} not inside ({rx}, {ry}, {rw}, {rh})")
        return False
    return True


def check_desktop_keeps_the_adoption_too() -> bool:
    """His words named BOTH ways back: "another layout OR the desktop". An
    ordinary Desktop tap (the session keeps running) must behave exactly like
    switching layouts — lowered, not forgotten."""
    reg, conn = desk(fg=POPUP)
    lay = _adopt_popup(reg, conn)
    before = RECTS[POPUP]
    reg.minimize_members()                         # the phone's Desktop tap
    if POPUP not in lay.adopted or RECTS[POPUP] != before:
        print(f"  DETAIL Desktop forgot or moved it: adopted={POPUP in lay.adopted} "
              f"rect {before} -> {RECTS[POPUP]}")
        return False
    reg.focus(0, conn["ratio"], MONITOR)
    return POPUP in LEDGER


def check_a_true_session_end_still_lets_it_go() -> bool:
    """Contrast check: `presence.leave_session` calls
    `minimize_members(session_end=True)`, and THAT is where constraint 23 is
    real — nothing of ours may outlive the app not being up. Proves the flag
    actually switches behaviour rather than the light path silently winning
    everywhere (which would make check 3 pass by accident of a no-op).

    POPUP here was adopted through HIS TAP (`act="layout"`), which never
    records `adopted_home` — he asked for that placement, so `release_adopted`
    deliberately does not undo it behind his back (see the field's own
    docstring). What a true session end still owes it is being FORGOTTEN and
    dropped out of the topmost band; the home-restore half is
    `test_session_residue.py`'s question, proven there over a member's own
    dialog, the kind of adoption that DOES carry a home to restore."""
    reg, conn = desk(fg=POPUP)
    lay = _adopt_popup(reg, conn)
    reg.minimize_members(session_end=True)
    if lay.adopted:
        print("  DETAIL still remembered as adopted after a true session end")
        return False
    if POPUP in LEDGER:
        print("  DETAIL still in the always-on-top band after a true "
              "session end")
        return False
    return True


def check_the_chip_names_the_act_it_performs() -> bool:
    """Defect 2: the wording, not the placement. His report — "X opened" /
    "Show in layout" read as an offer to CREATE a layout; the yes has only
    ever MOVED the window into the one he is already watching. Read straight
    from the shipped source rather than re-typed here, so a future reword of
    either chip is caught the moment the two collide again."""
    src = (CLIENT_DIR / "window-offer.js").read_text(encoding="utf-8")
    layout_yes = re.search(r'\blayout:\s*\{.*?yes:\s*"([^"]+)"', src, re.S)
    new_yes = re.search(r'\blayout_new:\s*\{.*?yes:\s*"([^"]+)"', src, re.S)
    if not layout_yes or not new_yes:
        print("  DETAIL could not find WIN_OFFER_WORDS in the shipped source")
        return False
    if layout_yes.group(1) == new_yes.group(1):
        print("  DETAIL both chips share one yes label again — one question "
              "for two different acts is the whole defect")
        return False
    if "layout" in layout_yes.group(1).lower():
        print(f"  DETAIL {layout_yes.group(1)!r} still reads like an offer "
              f"to make a layout, exactly what he misread")
        return False
    if "make" not in new_yes.group(1).lower():
        print(f"  DETAIL {new_yes.group(1)!r} no longer names its own "
              f"creating act")
        return False
    return True


CHECKS = [
    ("switching to another layout leaves the adoption standing",
     check_switching_to_another_layout_does_not_forget_it),
    ("it re-contains and re-enters the topmost band on its own layout's "
     "next focus", check_it_returns_when_its_own_layout_is_focused_again),
    ("an ordinary Desktop tap keeps the adoption too",
     check_desktop_keeps_the_adoption_too),
    ("a true session end still restores it home and forgets it",
     check_a_true_session_end_still_lets_it_go),
    ("the chip's wording names the act it performs, not just the event",
     check_the_chip_names_the_act_it_performs),
]


def test_gate():
    assert run_checks(
        "LAYOUT ADOPTION LIFECYCLE", CHECKS,
        "an adopted window across a layout switch, Desktop, and the chip "
        "that creates the adoption") == 0


if __name__ == "__main__":
    raise SystemExit(run_checks(
        "LAYOUT ADOPTION LIFECYCLE", CHECKS,
        "an adopted window across a layout switch, Desktop, and the chip "
        "that creates the adoption"))
