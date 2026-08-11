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
aplikacije". Here the answer is canvas pixels taken off the DRAWN RECT, so the
canvas and the colour behind it cannot move — the geometry below is what proves
the amount is right.

Runs client/caret.js WHOLE in node: it is pure by design, and a rule that can
be executed is a rule that can be proven. The dictation round is the precedent
(client/voice.js) — and the round before it is the warning: a rule that lived
where no gate could run it shipped half-done and cost a release.

═══ WHY THIS FIXTURE WAS REWRITTEN ON 2026-08-09 ═══

Five rounds of this bug shipped GREEN with the rise pinned at exactly zero on
his tablet, and this file is half the reason. It used to hand the rule a VIEW
TRANSFORM whose `scale` it set to 1800 — the canvas height — with a confident
paragraph explaining why that was the right number. `view.scale` is a ZOOM
FACTOR and is 1 at home; it can never hold 1800 in production. So the fixture
made `caret.y * scale` mean "canvas pixels", the rule agreed with it, and on
the real device the same expression put a caret at y=0.95 at 0.95 PIXELS from
the top of the screen: every caret was clear of every keyboard, forever.

The lesson is mechanical and it is the same one as task 149's Move handle: a
gate that invents its own value for a production variable proves the fixture to
itself. The rule now takes the rect the picture is DRAWN into, which is the
thing the owner actually looks at, and this file feeds it rects a real phone
produces — including a LETTERBOXED one, which the old fixture could not even
express.
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
KEYBOARD_TOP = CANVAS_H - KEYBOARD_H              # 1100 px

# THE PICTURE RECT, which is what production passes (render.js `drawnRect()`).
# `y` is where the top of the PC's picture lands on this canvas and `h` is how
# tall it is drawn — both in canvas px, both already carrying the zoom, the pan
# and the letterbox. A caret coordinate is 0..1 OF THIS RECT.
#
# FULL: a monitor whose aspect matches the phone — the picture fills the canvas
# and normalized 1.0 really is the canvas height.
FULL = {"x": 0.0, "y": 0.0, "w": 1000.0, "h": float(CANVAS_H)}
# LETTERBOXED: the ordinary case in layout focus. A region shorter than the
# screen is fitted and anchored, so the picture occupies 1500 px starting
# 150 px down, and the navy filler holds the rest. The old fixture had no way
# to say this at all, which is why nothing here was ever measured against it.
BOXED = {"x": 0.0, "y": 150.0, "w": 1000.0, "h": 1500.0}


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


def call(caret, *, keyboard=KEYBOARD_H, picture=FULL, **extra):
    """One call in exactly the shape render.js makes it — no more keys, no
    invented ones. `extra` exists only for the check that proves a retired
    argument cannot come back to life."""
    return {"caret": caret, "picture": picture,
            "canvasHeight": CANVAS_H, "keyboardHeight": keyboard, **extra}


def on_picture(caret, picture):
    """Where the caret's top and bottom land, in canvas px — the arithmetic the
    rule promises, written out here so a check can state the pixel it means."""
    return (picture["y"] + caret["y"] * picture["h"],
            picture["y"] + (caret["y"] + caret["h"]) * picture["h"])


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


def test_the_production_case_produces_a_real_number_of_pixels():
    """THE CHECK THE OLD FIXTURE COULD NOT MAKE, and the one that would have
    caught five green releases.

    Every value here is one production really passes: a caret near the bottom
    of the monitor, a 700 px keyboard on an 1800 px canvas, and the picture
    rect render.js hands over. The answer is asserted EXACTLY, because the
    failure being guarded is not "slightly wrong" — it is a rise of 0 dressed
    up as a working feature.
    """
    caret = {"x": 0.5, "y": 0.95, "w": 0.001, "h": 0.02}
    full, boxed = run([call(caret), call(caret, picture=BOXED)])
    # FULL: bottom at 0.97 * 1800 = 1746, + 14 margin - 1100 keyboard top = 660
    assert full == 660, f"expected a 660px rise on a full-canvas picture, got {full}"
    # LETTERBOXED: bottom at 150 + 0.97 * 1500 = 1605, + 14 - 1100 = 519. It
    # MUST differ from the full-canvas answer: the letterbox offset was dropped
    # entirely by the old arithmetic, so a check that could not tell these two
    # apart is a check that never looked at the picture.
    assert boxed == 519, f"expected a 519px rise on a letterboxed picture, got {boxed}"
    assert full != boxed, (
        "a letterboxed picture and a full-canvas one gave the same rise — the "
        "rule is not reading the rect the picture is drawn into")


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
    the only thing he actually asked for. Asked of the letterboxed picture too:
    a rescue that only works when the picture happens to fill the screen is not
    one, and layout focus is where he types."""
    caret = {"x": 0.5, "y": 0.90, "w": 0.001, "h": 0.03}
    for picture, lift in zip((FULL, BOXED),
                             run([call(caret), call(caret, picture=BOXED)])):
        _, bottom = on_picture(caret, picture)
        after = bottom - lift
        assert after <= KEYBOARD_TOP, (
            f"after a {lift}px lift the caret bottom is still at {after}, "
            f"below the keyboard top {KEYBOARD_TOP} (picture y={picture['y']})")


def test_it_never_pushes_the_row_off_the_top():
    """The failure that got the whole feature withdrawn. When the strip above
    the keyboard is too short, we lift what it can take and leave the rest
    covered — a covered row beats a missing one."""
    # A keyboard leaving a 50 px strip: shorter than the caret row plus the
    # margins, so the shortfall CANNOT be paid in full.
    caret = {"x": 0.5, "y": 0.5, "w": 0.001, "h": 0.02}
    (lift,) = run([call(caret, keyboard=CANVAS_H - 50)])
    top, _ = on_picture(caret, FULL)
    top_after = top - lift
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


def test_an_unknown_caret_never_moves_the_picture():
    """Some apps expose no caret. An app that cannot say where it is typing is
    never guessed at, and a guess is the expensive mistake: it costs him the
    row he IS looking at.

    The `unknownMode: "lift"` fallback was deleted on 2026-08-09 — declared on
    the page, assigned nowhere, never present in `config.ui`, so it had never
    once run. The second call proves it cannot come back by accident: a caller
    still passing the retired argument changes nothing.
    """
    plain, stale_caller = run([call(None), call(None, unknownMode="lift")])
    assert plain == 0, f"an unknown caret lifted the picture by {plain}px"
    assert stale_caller == 0, (
        "a retired `unknownMode` argument still moved the picture — the dead "
        "branch is back, and nothing on the desktop can switch it off")


def test_the_lift_follows_the_view_and_not_the_monitor():
    """He pans and pinch-zooms. The same PC caret is at a different place on
    HIS screen after a pan, and the lift must be computed from where it is NOW
    — which is exactly what the drawn rect carries."""
    caret = {"x": 0.5, "y": 0.5, "w": 0.001, "h": 0.02}
    panned_picture = {**FULL, "y": 400.0}
    home, panned = run([call(caret), call(caret, picture=panned_picture)])
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


def test_the_page_still_carries_the_keyboard_height_to_the_rule():
    """THE PLUMBING, not the arithmetic — and the half that was missing.

    A perfect rule fed a keyboard height of zero returns zero, which is what
    his tablet did for five rounds. `window.__imeHeight` is the shell's only
    way in; it was deleted as COLLATERAL by a revert of the streaming code it
    happened to sit next to, and nothing noticed because nothing checks a
    global nobody in the repo calls. This checks the whole chain exists, and
    that the receiver is no longer parked beside code with a different
    lifetime.
    """
    render = (CLIENT.parent / "render.js").read_text(encoding="utf-8")
    state = (CLIENT.parent / "state.js").read_text(encoding="utf-8")
    assert "window.__imeHeight = " in render, (
        "client/render.js no longer defines window.__imeHeight — the shell's "
        "keyboard height cannot reach the page, and every rise is 0 again")
    assert "let imeHeight" in state, "client/state.js lost the imeHeight variable"
    assert "Math.max(kbSelf, imeHeight)" in render, (
        "the shell's measurement is no longer folded into the keyboard height")
    assert "picture: pic" in render or "picture: drawnRect()" in render, (
        "render.js is not passing the drawn picture rect to the rule")
    # The receiver must sit with `updateViewport`, its only consumer — not down
    # among the MSE code, which is what let one revert take it away.
    assert render.index("window.__imeHeight = ") > render.index("function updateViewport"), (
        "the __imeHeight receiver moved away from updateViewport")
    assert render.index("window.__imeHeight = ") < render.index("function initMse"), (
        "the __imeHeight receiver is parked in the streaming code again — that "
        "adjacency is exactly what deleted it once already")
    kotlin = (CLIENT.parent.parent / "android" / "app" / "src" / "main" / "java"
              / "com" / "uvuruna" / "vibecoder" / "Insets.kt").read_text(encoding="utf-8")
    assert "__imeHeight(" in kotlin, "the shell no longer pushes the ime inset"
    assert "fun MainActivity.forgetImeInset" in kotlin, (
        "nothing resets the shell's pushed-inset memo, so a keyboard reopened "
        "at the same height after a page reload is never announced")


CHECKS = [
    ("a caret at the top never moves the picture",
     test_a_caret_at_the_top_never_moves_the_picture),
    ("a caret under the keyboard is rescued",
     test_a_caret_under_the_keyboard_is_rescued),
    ("the production case really produces pixels (full AND letterboxed)",
     test_the_production_case_produces_a_real_number_of_pixels),
    ("it lifts by the SHORTFALL, not by the keyboard",
     test_it_lifts_by_the_shortfall_and_not_by_the_keyboard),
    ("the row really ends up above the keyboard",
     test_the_caret_ends_up_above_the_keyboard),
    ("it never pushes the row off the top",
     test_it_never_pushes_the_row_off_the_top),
    ("no keyboard on screen means no lift", test_no_keyboard_means_no_lift),
    ("an unknown caret never moves the picture",
     test_an_unknown_caret_never_moves_the_picture),
    ("the lift follows the VIEW, so a pan is respected",
     test_the_lift_follows_the_view_and_not_the_monitor),
    ("the rule is pure, so this gate can run it whole", test_the_rule_is_pure),
    ("the margins are named and explained",
     test_the_margins_are_named_constants_carrying_their_reasoning),
    ("the keyboard height still reaches the rule (shell -> page -> rule)",
     test_the_page_still_carries_the_keyboard_height_to_the_rule),
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
