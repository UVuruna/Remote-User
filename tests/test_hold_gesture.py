"""A HOLD IS A CONTACT THAT STAYED PUT — the layout list's drag, armed.

Why this gate exists, and why it drives SEQUENCES rather than calls.

Owner report 2026-08-09 (task 162): he held his finger on a layout row without
moving it, meaning to pick it up and drop it on another one to make a grid, and
the layout simply OPENED. The gesture was not missing — the client drag block,
`layout_merge`, `layout_reorder` and the registry's `merge`/`reorder` all
shipped on 2026-08-07, and the panel's own subtitle promises the gesture in
words. It was defeated on the phone, twice over:

  1. the row's `pointermove` handler cleared the 380 ms hold timer on ANY
     movement, with zero tolerance — and a finger resting on a capacitive
     digitizer never stands still, so the timer essentially never survived;
  2. `keepFocus` fires its tap on `pointerup` with no duration test, and its
     stolen-tap rescue fires for any `pointercancel` under 18 px — while
     Chrome on Android hands out that cancel at ~8 dp, the moment it decides
     the touch is a scroll. Both land inside the rescue window.

And the reason it shipped broken and STAYED broken is this file's real subject:
grepping every test in the project for `layout_merge`, `layout_reorder`,
`mergeLayouts`, `holdTimer` or `dragEnd` returned nothing at all. The phone's
arming logic was not extractable, which is exactly why it was never tested. So
it is a pure module now — client/hold-gesture.js, the client/view-anchor.js and
client/cursor-shapes.js pattern — and this gate runs it WHOLE in node against
the sequence the bug is made of: a finger resting on glass for 400 ms, sampled
at ~60 Hz, wandering the way a real contact patch wanders. A rule about jitter
cannot be proven by one call.

The wiring checks that follow are the other half: a pure function nobody calls
is a feature that does not exist (the actions.json lesson, 2026-08-07). They
pin that the row really asks this module, that the tap really refuses a press
that lasted, that the capture happens before the arm, and that the row refuses
the browser's own pan while a drag can still reach a row below the fold.

Run:  .venv\\Scripts\\python tests/test_hold_gesture.py
Requires: node on PATH — a HARD requirement (registered fail-closed in
setup/build.py, the test_view_anchor.py precedent). Never skip it silently.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MODULE = PROJECT / "client" / "hold-gesture.js"
LAYOUTS_JS = PROJECT / "client" / "layouts.js"
LAYOUTS_CSS = PROJECT / "client" / "layouts.css"
INDEX = PROJECT / "client" / "index.html"

# The product's own limits, so the sequences below are driven at the numbers
# the owner's phone really runs (read from the page, never re-typed here — a
# gate that carries its own copy of a constant stops testing the product the
# day somebody tunes it).
SRC = LAYOUTS_JS.read_text(encoding="utf-8")


def _const(name: str) -> float:
    m = re.search(rf"const {name} = (\d+(?:\.\d+)?)\s*;", SRC)
    if not m:
        raise AssertionError(f"client/layouts.js no longer defines {name}")
    return float(m.group(1))


HOLD_MS = _const("HOLD_DRAG_MS")
SLOP = _const("HOLD_DRAG_SLOP")


def run(calls: list[dict]) -> list[str]:
    """Evaluate pressVerdict() for each call, in one node process."""
    node = shutil.which("node")
    if not node:
        raise AssertionError(
            "node is required for the hold gesture gate (it runs the REAL "
            "client/hold-gesture.js rule) — install Node.js. Never skip a "
            "gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_hold_gate_"))
    script = work / "run.js"
    script.write_text(
        f"const {{ pressVerdict }} = require({json.dumps(str(MODULE))});\n"
        f"const calls = {json.dumps(calls)};\n"
        "console.log(JSON.stringify(calls.map(c => pressVerdict("
        "c.down, c.at, c.ms, c.slop, c.hold))));\n",
        encoding="utf-8")
    try:
        out = subprocess.run([node, str(script)], capture_output=True,
                             text=True, timeout=60)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


DOWN = {"x": 200.0, "y": 400.0}


def sequence(samples):
    """`samples` are (ms, dx, dy) from where the finger landed."""
    return [{"down": DOWN, "at": {"x": DOWN["x"] + dx, "y": DOWN["y"] + dy},
             "ms": ms, "slop": SLOP, "hold": HOLD_MS} for ms, dx, dy in samples]


# ═════════════════════ THE SEQUENCE THE BUG IS MADE OF ═════════════════════
# A FINGER RESTING ON GLASS, sampled at ~60 Hz for 400 ms — one frame apart,
# which is the rate a WebView actually delivers coalesced pointermoves at.
#
# Why these numbers are realistic, stated plainly because the whole gate rests
# on it: a capacitive digitizer does not report "the finger", it reports the
# CENTROID of a contact patch. That patch pulses with the blood in the
# fingertip and spreads as the finger settles under its own weight, so the
# reported point drifts by a pixel or two per frame and wanders several pixels
# over half a second — and it drifts in a CURVE (the finger rolls), never as
# random noise about a fixed point, which is why this table walks a small loop
# instead of jittering ±1 around zero. The single worst excursion here is
# ~4.1 px of straight-line travel; the product allows 12.
#
# THE HONEST LIMIT, and it is a real one: there is no Android device in this
# loop. The amplitude below is a reasoned model of a resting fingertip, not a
# measurement of the owner's own tablet, and Chrome's real scroll slop on his
# device is likewise unmeasured here. What this gate proves is that the RULE
# tolerates jitter of this order and still refuses real travel; what it cannot
# prove is that 12 px is the right number for his glass. If a hold still fails
# to arm on the device, the constant is the thing to move — not this rule.
RESTING_FINGER = [
    (0, 0.0, 0.0), (16, 1.0, 0.0), (33, 1.0, -1.0), (50, 2.0, -1.0),
    (66, 2.0, 0.0), (83, 3.0, 1.0), (100, 2.0, 2.0), (116, 1.0, 2.0),
    (133, 0.0, 3.0), (150, -1.0, 3.0), (166, -2.0, 2.0), (183, -2.0, 1.0),
    (200, -3.0, 1.0), (216, -3.0, 0.0), (233, -4.0, -1.0),  # the patch shifts
    (250, -3.0, -2.0), (266, -2.0, -3.0), (283, -1.0, -3.0),
    (300, 0.0, -4.0), (316, 1.0, -4.0), (333, 2.0, -3.0), (350, 3.0, -2.0),
    (366, 4.0, -1.0), (383, 4.0, 0.0), (400, 3.0, 1.0),
]

# A DELIBERATE DRAG: the same start, then a real 20 px pull downward — a
# finger going somewhere, at a speed a person scrolling a list really uses.
REAL_TRAVEL = [
    (0, 0.0, 0.0), (16, 0.0, 1.0), (33, 1.0, 2.0), (50, 1.0, 4.0),
    (66, 1.0, 7.0), (83, 2.0, 11.0), (100, 2.0, 15.0), (116, 2.0, 18.0),
    (133, 3.0, 20.0), (200, 3.0, 20.0), (400, 3.0, 20.0),
]


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def check_a_resting_finger_still_arms_the_hold() -> None:
    """THE REPORTED BUG. Every frame of a 400 ms rest must stay a candidate,
    and the moment the hold delay passes it must be a HOLD. The old rule
    answered 'drag' at the very first sample — one pixel."""
    verdicts = run(sequence(RESTING_FINGER))
    for (ms, dx, dy), got in zip(RESTING_FINGER, verdicts):
        want = "hold" if ms >= HOLD_MS else "tap"
        if got != want:
            raise AssertionError(
                f"a resting finger at {ms} ms ({dx:+}, {dy:+} px) was read as "
                f"{got!r}, expected {want!r} — the hold cannot arm")


def check_zero_tolerance_is_gone() -> None:
    """The exact defect, named on its own so it can never come back quietly: a
    single pixel of wander, 20 ms in, is not somebody dragging."""
    (got,) = run(sequence([(20, 1.0, 0.0)]))
    if got != "tap":
        raise AssertionError(
            f"one pixel of jitter was read as {got!r} — this is the 2026-08-09 "
            "bug exactly")


def check_a_real_drag_never_arms_the_hold() -> None:
    """A finger that travels is scrolling or carrying, and it must be DRAG
    from the frame it crosses the slop onward — including well past the hold
    delay, because 'stood still again' does not undo travel that already
    belonged to another gesture."""
    verdicts = run(sequence(REAL_TRAVEL))
    crossed = False
    for (ms, dx, dy), got in zip(REAL_TRAVEL, verdicts):
        travel = (dx ** 2 + dy ** 2) ** 0.5
        if travel > SLOP:
            crossed = True
        if crossed and got != "drag":
            raise AssertionError(
                f"a finger {travel:.1f} px from where it landed was read as "
                f"{got!r} at {ms} ms, expected 'drag'")
        if not crossed and got == "drag":
            raise AssertionError(
                f"the gesture was called a drag at {travel:.1f} px, inside the "
                f"{SLOP:.0f} px slop")
    if not crossed:
        raise AssertionError("the drag fixture never crosses the slop at all")
    if verdicts[-1] != "drag":
        raise AssertionError(
            "a drag that stood still past the hold delay armed the hold — "
            "travel that already happened cannot be un-travelled")


def check_a_quick_tap_stays_a_tap() -> None:
    """60 ms and a pixel: the ordinary tap that opens a layout, and the thing
    the fix must not cost him."""
    (got,) = run(sequence([(60, 1.0, 1.0)]))
    if got != "tap":
        raise AssertionError(f"a 60 ms press was read as {got!r}, not a tap")


def check_a_long_press_stops_being_a_tap() -> None:
    """The other half of the bug (the `keepFocus` path): once the press has
    lasted the hold delay it is a HOLD, so the row's tap guard has something
    to refuse. Without this the layout opens under his finger even with the
    timer fixed."""
    for ms in (HOLD_MS, HOLD_MS + 120, 2000):
        (got,) = run(sequence([(ms, 0.0, 0.0)]))
        if got != "hold":
            raise AssertionError(
                f"a {ms:.0f} ms press with no travel was read as {got!r} — the "
                "row's tap guard would still open the layout")


def check_the_slop_is_a_circle_not_a_box() -> None:
    """Straight-line travel, never per-axis: 9 px across and 9 px down is
    12.7 px of real movement. A per-axis test lets that through, and a
    diagonal is exactly how a thumb leaves a row."""
    diag, edge, inside = run(sequence([
        (100, 9.0, 9.0),            # 12.73 px — past the 12 px slop
        (100, SLOP, 0.0),           # exactly the slop — still a rest
        (100, 8.0, 8.0),            # 11.3 px — inside it
    ]))
    if diag != "drag":
        raise AssertionError(
            f"a 12.7 px diagonal was read as {diag!r} — the slop is being "
            "measured per axis")
    if edge != "tap" or inside != "tap":
        raise AssertionError(
            f"a contact at or inside the slop was read as {edge!r}/{inside!r} "
            "— the boundary itself must still be a rest")


# ═════════ the wiring — the rule the page actually runs ═════════
def _code(text: str) -> str:
    """The same text with its COMMENTS removed.

    Found while planting the defects these checks exist to catch, and worth
    the four lines: a check that greps a body must not be answered by the
    PROSE explaining that body. The comment over the fix names
    `setPointerCapture` and `touch-action: none` in the course of explaining
    them, so an index over the raw text found the comment, not the code — and
    two checks below could not go red with the defect planted in front of
    them. A tooth that cannot fail is not a tooth."""
    stripped = "\n".join(re.sub(r"//.*$", "", ln) for ln in text.splitlines())
    return re.sub(r"/\*.*?\*/", "", stripped, flags=re.S)


def _timer_body() -> str:
    m = re.search(r"holdTimer = setTimeout\((.*?)\}, HOLD_DRAG_MS\)", SRC, re.S)
    if not m:
        raise AssertionError(
            "the layout list's hold timer left client/layouts.js (or stopped "
            "using HOLD_DRAG_MS) — the gesture has no arming step any more")
    return _code(m.group(1))


def check_the_row_asks_this_module_instead_of_clearing_on_any_move() -> None:
    """The root cause, pinned where it happened. The pointermove handler may
    only drop the hold on a DRAG verdict — a bare `clearTimeout` with no test
    in front of it is the 2026-08-09 bug rewritten."""
    m = re.search(r'row\.addEventListener\("pointermove"(.*?)const stop =',
                  SRC, re.S)
    if not m:
        raise AssertionError(
            "the layout row's pointermove handler is gone from client/layouts.js")
    body = _code(m.group(1))
    if "pressVerdict(" not in body or "PRESS_DRAG" not in body:
        raise AssertionError(
            "the row no longer asks pressVerdict() — it decides for itself "
            "again, which is how the hold stopped arming (task 162)")
    if body.index("pressVerdict(") > body.index("clearTimeout"):
        raise AssertionError(
            "the hold timer is cleared BEFORE the verdict is asked — the test "
            "in front of it is the whole fix")


def check_the_tap_refuses_a_press_that_lasted() -> None:
    """The second, independent path. `keepFocus` is shared with the gamepad
    (CLAUDE.md constraint 12) and its stolen-tap rescue is constraint 9, so it
    must NOT be changed — the refusal belongs to the row, where the hold's own
    limits are known."""
    m = re.search(r"const row = layRow\((.*?)ren, asp\);", SRC, re.S)
    if not m:
        raise AssertionError("the layout list's rows are no longer built by layRow")
    tap = _code(m.group(1))
    if "HOLD_DRAG_MS" not in tap or "press" not in tap:
        raise AssertionError(
            "the row's tap does not refuse a press that lasted the hold delay "
            "— keepFocus fires on pointerup with no duration test, so the "
            "layout opens under his hold anyway (task 162)")
    if "if (drag) return;" not in tap:
        raise AssertionError(
            "the row's tap no longer refuses a press that became a drag")


def check_the_capture_happens_before_the_arm() -> None:
    """The latent bug beside it: `setPointerCapture` throws NotFoundError for a
    pointer that is already gone. It used to run AFTER `drag` was assigned, so
    the throw left `drag` non-null with no gesture in flight — and the tap
    guard reads `drag`, which made EVERY row in the list dead until the panel
    was reopened."""
    body = _timer_body()
    if "setPointerCapture" not in body:
        raise AssertionError("the arm no longer captures the pointer")
    if body.index("setPointerCapture") > body.index("drag = {"):
        raise AssertionError(
            "`drag` is armed BEFORE the pointer is captured — a capture that "
            "throws then leaves every row in the list dead")
    if "try {" not in body or "catch" not in body:
        raise AssertionError(
            "the capture is not wrapped — a throw would abort the arm halfway, "
            "with the row already lifted")


def check_a_row_refuses_the_pan_and_the_drag_can_still_reach_the_fold() -> None:
    """The third defeat, and the trade it forces. `.lay-item` must declare its
    own `touch-action` — the page-level one in style.css does not reach past
    `.lay-card`, which is a scroll container, so Chrome owned the vertical
    gesture and ended the carry with a pointercancel. Taking the browser's pan
    away costs list scrolling, so the drag must scroll the card itself near its
    edges; a fix that only did the first half would trade one broken gesture
    for another."""
    css = LAYOUTS_CSS.read_text(encoding="utf-8")
    m = re.search(r"\.lay-item \{(.*?)\n\}", css, re.S)
    if not m or not re.search(r"^\s*touch-action:\s*none;", _code(m.group(1)),
                              re.M):
        raise AssertionError(
            "`.lay-item` no longer declares `touch-action: none` — the browser "
            "takes the carried row away as a scroll (task 162)")
    m = re.search(r"function dragMoveTo\(clientY\) \{(.*?)\n  \}", SRC, re.S)
    if not m:
        raise AssertionError("dragMoveTo() left client/layouts.js")
    if "requestAnimationFrame" not in _code(m.group(1)):
        raise AssertionError(
            "a drag in flight no longer starts the edge auto-scroll — with the "
            "row's own pan refused, a drop target below the fold is "
            "unreachable")
    if "scrollTop" not in SRC or "cancelAnimationFrame" not in SRC:
        raise AssertionError(
            "the edge auto-scroll does not scroll the card, or never stops — "
            "it must die with the drag")


def check_one_number_answers_one_question() -> None:
    """The process half of the fix. `MOVE_TAP_SLOP` — the Move handle's own
    tap-versus-drag tolerance, written the SAME DAY this gesture shipped with
    none — must be the same number, by derivation and not by coincidence, so
    the two cannot drift apart again."""
    if not re.search(r"const MOVE_TAP_SLOP = HOLD_DRAG_SLOP\s*;", SRC):
        raise AssertionError(
            "MOVE_TAP_SLOP is a second, independent copy of the slop again — "
            "one digitizer asking one question must have one number")


def check_the_page_loads_the_module_before_layouts() -> None:
    html = INDEX.read_text(encoding="utf-8")
    hold = html.find("/static/hold-gesture.js")
    layouts = html.find("/static/layouts.js")
    if hold == -1:
        raise AssertionError("index.html never loads hold-gesture.js")
    if not -1 < hold < layouts:
        raise AssertionError(
            "hold-gesture.js must load BEFORE layouts.js — the rows call "
            "pressVerdict()")


def check_the_module_stays_pure() -> None:
    """This gate runs the module WHOLE in node — possible only while it
    touches no DOM, no timer, no socket (the caret.js / view-anchor.js rule)."""
    code = "\n".join(ln for ln in MODULE.read_text(encoding="utf-8").splitlines()
                     if not ln.lstrip().startswith(("//", "*", "/*")))
    for banned in ("document", "window.", "send(", "Android", "fetch(",
                   "setTimeout", "performance."):
        if banned in code:
            raise AssertionError(
                f"client/hold-gesture.js reaches for {banned!r} — it is no "
                "longer pure and this gate can no longer prove it")


CHECKS = [
    ("a resting finger still arms the hold (the reported bug)",
     check_a_resting_finger_still_arms_the_hold),
    ("one pixel of jitter is not a drag", check_zero_tolerance_is_gone),
    ("a real 20 px drag never arms the hold",
     check_a_real_drag_never_arms_the_hold),
    ("a 60 ms tap is still a tap", check_a_quick_tap_stays_a_tap),
    ("a press that lasted stops being a tap",
     check_a_long_press_stops_being_a_tap),
    ("the slop is a circle, not a box", check_the_slop_is_a_circle_not_a_box),
    ("the row asks THIS rule instead of clearing on any move",
     check_the_row_asks_this_module_instead_of_clearing_on_any_move),
    ("the row's tap refuses a press that lasted (keepFocus untouched)",
     check_the_tap_refuses_a_press_that_lasted),
    ("the pointer is captured BEFORE the drag is armed",
     check_the_capture_happens_before_the_arm),
    ("a row refuses the browser's pan, and a drag still reaches the fold",
     check_a_row_refuses_the_pan_and_the_drag_can_still_reach_the_fold),
    ("one slop constant, derived — not two that can drift",
     check_one_number_answers_one_question),
    ("the page loads the module before layouts.js",
     check_the_page_loads_the_module_before_layouts),
    ("the module stays pure, so this gate can run it whole",
     check_the_module_stays_pure),
]


def main() -> int:
    print("\n=== HOLD GESTURE GATE ===")
    if shutil.which("node") is None:
        print("HOLD GESTURE GATE FAILED — node is required (it runs the REAL "
              "client/hold-gesture.js rule) and is not on PATH. Never skip a "
              "gate silently.")
        return 1
    failed = 0
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nHOLD GESTURE GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nHOLD GESTURE GATE PASSED — a resting finger picks the row up, "
          "and a travelling one never does.")
    return 0


def test_hold_gesture():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
