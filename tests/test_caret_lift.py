"""THE KEYBOARD LIFTS THE PICTURE ONLY IF NEEDED, ONLY BY THE SHORTFALL.

Why this gate exists, and why it is a GATE rather than a note. The owner has
asked for the opposite thing twice, and both times he was right:

  2026-08-03  "the keyboard should push the view up"          -> built
  2026-08-07  "izbaci tekst koji se kuca iz vidokruga"         -> withdrawn,
              because the row he was watching left at the top   kbShift = 0
  2026-08-07  "najoptimalnije rešenje bilo bi da naš program prepozna gde se
              nalazi, koja je pozicija na ekranu, kursora koji kuca"

So a fixed rule is wrong by construction — "always lift" and "never lift" are
each wrong half the time — and the only defensible behaviour is the one that
reads where the caret really is and moves the least it can get away with.

And it lifts the PICTURE, never the filler. His screenshot of the first
attempt showed everything moving, "zaključno sa ovim delom koji nije deo naše
aplikacije". Here the answer is canvas pixels added to the view transform, so
the canvas and the colour behind it cannot move — the geometry below is what
proves the amount is right.

Runs client/caret.js WHOLE in node: it is pure by design, and a rule that can
be executed is a rule that can be proven. The dictation round is the precedent
(client/voice.js) — and the round before it is the warning: a rule that lived
where no gate could run it shipped half-done and cost a release.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CLIENT = Path(__file__).resolve().parent.parent / "client" / "caret.js"

# A phone-ish canvas. The numbers are only a stage for the geometry; every
# check states the situation it is putting the caret in.
CANVAS_H = 1800
KEYBOARD_H = 700          # keyboard top at y = 1100
# The picture aspect-fits the FULL canvas (owner 2026-08-02 — no reserved
# margins), so normalized 1.0 is the canvas height. Getting this wrong is not a
# detail: the first version of this fixture put the picture in the top 1000 px
# of an 1800 px canvas, and a caret at 0.95 of the monitor then sat at 950 px —
# comfortably ABOVE a keyboard whose top is 1100. The check that should have
# proven the whole feature was asking about a caret nothing was covering.
VIEW = {"scale": float(CANVAS_H), "tx": 0.0, "ty": 0.0}
KEYBOARD_TOP = CANVAS_H - KEYBOARD_H              # 1100 px


def run(calls: list[dict]) -> list[float]:
    """Evaluate caretLift() for each call, in one node process."""
    if not shutil.which("node"):
        raise AssertionError("node is required for the caret lift gate")
    work = Path(tempfile.mkdtemp(prefix="ru_caret_gate_"))
    script = work / "run.js"
    script.write_text(
        f"const {{ caretLift }} = require({json.dumps(str(CLIENT))});\n"
        f"const calls = {json.dumps(calls)};\n"
        "console.log(JSON.stringify(calls.map(c => caretLift(c))));\n",
        encoding="utf-8")
    try:
        out = subprocess.run([shutil.which("node"), str(script)],
                             capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def call(caret, *, keyboard=KEYBOARD_H, unknown="cover", ty=0.0):
    return {"caret": caret, "view": {**VIEW, "ty": ty},
            "canvasHeight": CANVAS_H, "keyboardHeight": keyboard,
            "unknownMode": unknown}


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def test_a_caret_at_the_top_never_moves_the_picture():
    """His 2026-08-07 complaint, exactly: the box is near the top, and lifting
    would carry the very text he is watching off the screen."""
    (lift,) = run([call({"x": 0.5, "y": 0.05, "w": 0.001, "h": 0.02})])
    assert lift == 0, f"a caret at the top of the screen lifted the picture by {lift}px"


def test_a_caret_under_the_keyboard_is_rescued():
    """His 2026-08-03 complaint, exactly: the box is at the bottom and the
    keyboard sits on it."""
    (lift,) = run([call({"x": 0.5, "y": 0.95, "w": 0.001, "h": 0.02})])
    assert lift > 0, "a caret buried under the keyboard was left there"


def test_it_lifts_by_the_shortfall_and_not_by_the_keyboard():
    """The heart of it. The 2026-08-03 version lifted by the keyboard's whole
    height, which is what made it intolerable."""
    # bottom lands at 1120 px — 20 px below the keyboard's top edge.
    caret = {"x": 0.5, "y": 1100 / CANVAS_H, "w": 0.001, "h": 20 / CANVAS_H}
    (lift,) = run([call(caret)])
    # bottom 1120 + margin 14 - keyboard top 1100 = 34
    assert lift == 34, f"expected the 34px shortfall, lifted {lift}"
    assert lift < KEYBOARD_H, "it lifted by the keyboard height again"


def test_the_caret_ends_up_above_the_keyboard():
    """Whatever the arithmetic, the ROW must be visible afterwards — that is
    the only thing he actually asked for."""
    caret = {"x": 0.5, "y": 0.90, "w": 0.001, "h": 0.03}
    (lift,) = run([call(caret)])
    after = (caret["y"] + caret["h"]) * VIEW["scale"] - lift
    assert after <= CANVAS_H - KEYBOARD_H, (
        f"after a {lift}px lift the caret bottom is still at {after}, "
        f"below the keyboard top {CANVAS_H - KEYBOARD_H}")


def test_it_never_pushes_the_row_off_the_top():
    """The failure that got the whole feature withdrawn. When the strip above
    the keyboard is too short, we lift what it can take and leave the rest
    covered — a covered row beats a missing one."""
    # A keyboard leaving a 50 px strip: shorter than the caret row plus the
    # margins, so the shortfall CANNOT be paid in full.
    caret = {"x": 0.5, "y": 0.5, "w": 0.001, "h": 0.02}
    (lift,) = run([call(caret, keyboard=CANVAS_H - 50)])
    top_after = caret["y"] * VIEW["scale"] - lift
    # `>= 0` is NOT the bar, and writing it that way is how this check first
    # passed with the clamp deliberately removed: without the clamp the row
    # lands at exactly 0 — jammed against the top edge, no line of context
    # above it, which is the very thing he described when the 2026-08-03 lift
    # was withdrawn. The bar is the margin the rule itself promises.
    margin = int(CLIENT.read_text(encoding="utf-8")
                 .split("CARET_TOP_MARGIN_PX =")[1].split(";")[0].strip())
    assert top_after >= margin, (
        f"the caret was pushed to {top_after}px, inside the {margin}px top margin "
        f"the rule promises — a rescued row with nothing above it is not rescued")


def test_no_keyboard_means_no_lift():
    """A stale caret must never move a picture nobody is typing on."""
    (lift,) = run([call({"x": 0.5, "y": 0.99, "w": 0.001, "h": 0.02}, keyboard=0)])
    assert lift == 0, f"lifted {lift}px with no keyboard on screen"


def test_an_unknown_caret_obeys_his_switch_and_defaults_to_covering():
    """Some apps expose no caret. An app that cannot say where it is typing is
    never guessed at — he decides, and the default is what he chose to live
    with when there was no caret at all."""
    covered, lifted = run([
        call(None, unknown="cover"),
        call(None, unknown="lift"),
    ])
    assert covered == 0, f"an unknown caret lifted by {covered}px on the default"
    assert lifted > 0, "his explicit 'lift' fallback did nothing"


def test_the_lift_follows_the_view_and_not_the_monitor():
    """He pans and pinch-zooms. The same PC caret is at a different place on
    HIS screen after a pan, and the lift must be computed from where it is NOW."""
    caret = {"x": 0.5, "y": 0.5, "w": 0.001, "h": 0.02}
    home, panned = run([call(caret, ty=0.0), call(caret, ty=400.0)])
    assert home == 0, "the caret was clear at home and still lifted"
    assert panned > 0, (
        "the same caret panned down under the keyboard was not rescued — "
        "the rule is reading the monitor instead of the view")


def test_the_rule_is_pure():
    """It must be runnable whole by this gate — that is the entire reason it
    lives in its own file. A DOM reference here would put the rule back where
    the previous dictation fix died: true, and unprovable."""
    src = CLIENT.read_text(encoding="utf-8")
    block = src.split("CARET_LIFT_START")[1].split("CARET_LIFT_END")[0]
    for banned in ("document", "window.", "canvas.", "fetch(", "send("):
        assert banned not in block, f"the rule reaches for {banned!r} — it is no longer pure"


def test_the_margins_are_named_constants_carrying_their_reasoning():
    """Two magic numbers decide whether he can read the row he is typing in.
    They are his to tune, so they must be findable and explained."""
    src = CLIENT.read_text(encoding="utf-8")
    for name in ("CARET_LIFT_MARGIN_PX", "CARET_TOP_MARGIN_PX"):
        assert f"const {name} =" in src, f"{name} is not a named constant"
        before = src.split(f"const {name} =")[0]
        assert len(before.rsplit("//", 1)[-1].splitlines()) >= 2 or "//" in before[-400:], (
            f"{name} carries no reasoning")


CHECKS = [
    ("a caret at the top never moves the picture",
     test_a_caret_at_the_top_never_moves_the_picture),
    ("a caret under the keyboard is rescued",
     test_a_caret_under_the_keyboard_is_rescued),
    ("it lifts by the SHORTFALL, not by the keyboard",
     test_it_lifts_by_the_shortfall_and_not_by_the_keyboard),
    ("the row really ends up above the keyboard",
     test_the_caret_ends_up_above_the_keyboard),
    ("it never pushes the row off the top",
     test_it_never_pushes_the_row_off_the_top),
    ("no keyboard on screen means no lift", test_no_keyboard_means_no_lift),
    ("an unknown caret obeys his switch, and covers by default",
     test_an_unknown_caret_obeys_his_switch_and_defaults_to_covering),
    ("the lift follows the VIEW, so a pan is respected",
     test_the_lift_follows_the_view_and_not_the_monitor),
    ("the rule is pure, so this gate can run it whole", test_the_rule_is_pure),
    ("the margins are named and explained",
     test_the_margins_are_named_constants_carrying_their_reasoning),
]


def main() -> int:
    failed = []
    print("\n=== CARET LIFT GATE ===")
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed.append(f"{name}: {e}")
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nCARET LIFT GATE FAILED — {len(failed)} check(s).", file=sys.stderr)
        return 1
    print("\nCARET LIFT GATE PASSED — the picture rises only when the caret "
          "would be covered, and only by the shortfall.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
