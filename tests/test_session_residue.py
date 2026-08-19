"""SESSION RESIDUE GATE — nothing of ours may outlive the session.

Owner decree 2026-08-13, absolute and general: while the app is not up —
closed, minimized, put in the background, anything that is not open — NO
manipulation of ours may remain on any window. No topmost, no forced holding
down, nothing. Everything we force on windows happens ONLY while the app is up.

His report is what forced it: pressing the Android home button minimized his
layout on the PC, and afterwards he could raise ONE window but the others
stayed nailed down. Then the app was closed entirely and they still would not
come back.

THE CAUSE WAS MEASURED, not reasoned. A controlled A/B built a real owner
window and a real owned dialog and ran OUR OWN leave sequence over both, with
one variable — is the dialog modal:

    modal up      after our minimize  iconic=True   enabled=False
                  after his restore   iconic=False  enabled=False   -> UNUSABLE
    control       after our minimize  iconic=True   enabled=True
                  (not modal)         after restore iconic=False    -> fine

A modal DISABLES its owner until it is answered — that is the whole of what
modal means to Windows — and Windows HIDES the owned dialog when the owner is
minimized (measured in the same run). So our leave sequence handed him back a
window he could raise and could not click, with the only thing that could
unblock it hidden underneath. Two acts of ours made it, and this file holds
both, plus the third residue found while fixing them:

  1. we minimized the owner of a live modal;
  2. we had parked that modal on the layout (constraint 19's owner-chain rule,
     which places WITHOUT asking) and never put it back;
  3. every member was left with its DWM transitions frozen for good — the
     freeze was left to `drop_topmost`, which does not undo it, and to
     `release_all`, which walks the ledger `drop_topmost` has just emptied.

Its own file rather than more of `test_layout_popup.py` (THE STRUCTURE LAW,
and by responsibility not line count): that gate asks WHOSE window this is and
where it should go while the phone watches. This one asks what must be TRUE
once the phone is gone — a different question, with a different failure mode,
and the desk harness is shared rather than copied.

NOTHING HERE TOUCHES THE OWNER'S DESKTOP: every Win32 call is answered by the
fake desk `test_layout_popup` builds.

Run:  .venv\\Scripts\\python tests/test_session_residue.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import (  # noqa: E402
    MEMBER_A, MEMBER_B, focus_guard, run_checks, window_manager,
)
from test_layout_popup import (  # noqa: E402
    DIALOG, DISABLED, FROZEN, HOME, LEDGER, MINIMIZED, PLACED, RECTS, desk,
)


def check_a_modal_dialog_is_put_back_where_windows_had_it() -> bool:
    """`_adopt_owned` moves a member's own dialog onto its parent WITHOUT
    asking — the owner chain is Windows' own statement about whose window this
    is, not a guess like every other rule there, which is why it needs no tap.
    It is still FORCED GEOMETRY, and forced geometry that outlives the session
    is exactly what he forbade: when the layout stops being shown, the dialog
    goes back where Windows had put it."""
    reg, conn = desk(fg=DIALOG)
    focus_guard.guard(reg, conn)
    lay = reg.layouts[0]
    if DIALOG not in lay.adopted or not PLACED:
        print(f"  DETAIL the dialog was never adopted/moved: {PLACED}")
        return False
    if RECTS[DIALOG] == HOME[DIALOG]:
        print("  DETAIL the dialog never actually moved — this check would "
              "pass on a program that does nothing at all")
        return False
    lay.release_adopted()
    if RECTS[DIALOG] != HOME[DIALOG]:
        print(f"  DETAIL left parked at {RECTS[DIALOG]}, "
              f"Windows had it at {HOME[DIALOG]}")
        return False
    if lay.adopted_home:
        print("  DETAIL the debt was paid but not forgotten — a stale rect "
              "would be re-applied to a window that has moved since")
        return False
    return True


def check_a_member_holding_a_modal_is_not_minimized() -> bool:
    """The measured half. A modal disables its owner, and Windows hides the
    dialog with the owner — so this member is left STANDING. It still leaves
    the always-on-top band (constraint 10 is not weakened by this rule), and
    every ordinary member is still minimized exactly as before."""
    reg, conn = desk(fg=MEMBER_A)
    DISABLED.add(MEMBER_A)
    LEDGER[MEMBER_A] = "exe"
    LEDGER[MEMBER_B] = "exe"
    reg.minimize_members()
    down = [h for h, cmd in MINIMIZED if cmd == window_manager.SW_MINIMIZE]
    if MEMBER_A in down:
        print("  DETAIL the member holding a modal was minimized anyway — "
              "he gets back a window he can raise and cannot click")
        return False
    if MEMBER_B not in down:
        print("  DETAIL an ordinary member stopped being minimized; the rule "
              "must cost nothing to the windows it is not about")
        return False
    if MEMBER_A in LEDGER:
        print("  DETAIL it was left in the always-on-top band (constraint 10)")
        return False
    return True


def check_no_member_is_left_with_its_transitions_frozen() -> bool:
    """We freeze the DWM minimize animation so the phone never watches windows
    slide away. That freeze is a manipulation like any other and it was never
    undone — a frozen window still WORKS, so this never reached him as its own
    report, which is precisely why a gate has to hold it instead of a user."""
    reg, conn = desk(fg=MEMBER_A)
    reg.minimize_members()
    left = [h for h, frozen in FROZEN.items() if frozen]
    if left:
        print(f"  DETAIL still frozen after the session ended: "
              f"{[hex(h) for h in left]}")
        return False
    return True


CHECKS = [
    ("a member's modal dialog is put back where Windows had it",
     check_a_modal_dialog_is_put_back_where_windows_had_it),
    ("a member holding a modal is left standing, not minimized",
     check_a_member_holding_a_modal_is_not_minimized),
    ("no member is left with its DWM transitions frozen",
     check_no_member_is_left_with_its_transitions_frozen),
]


def test_gate():
    assert run_checks("SESSION RESIDUE", CHECKS,
                       "what our leave sequence leaves behind") == 0


if __name__ == "__main__":
    raise SystemExit(run_checks("SESSION RESIDUE", CHECKS,
                                "what our leave sequence leaves behind"))
