"""A ROW MUST NOT STEAL THE SCROLL — task 227b.

Owner report 2026-08-11: entry rows in the creation panel (client/
layout-create.js's `entryRow`/`recentRow`) selected the instant a finger
LANDED, which made the list impossible to scroll — because they used the
page's ordinary button activator (`keepFocus`, controls.js), which calls
`e.preventDefault()` on `pointerdown` to guarantee real click activation, and
that same call is what stops the browser from ever recognising the touch as
a scroll. `keepRowTap` (layout-create.js) exists to be the one row activator
that never does that: it lets the browser decide, and only fires on RELEASE
once total travel stayed under `ROW_TAP_SLOP` (12px), reusing the real
`pressVerdict` from hold-gesture.js rather than a second copy of that rule
(constraint 9).

This gate extracts the REAL `keepRowTap` source out of layout-create.js
(between the `ROW_TAP_GATE_START`/`_END` markers — never a re-typed copy)
and runs it, whole, in node against the real `hold-gesture.js`, with a fake
`el` whose only job is to record the listeners `addEventListener` attaches —
exactly the `test_grid_icons.py`/`test_view_anchor.py` extract-and-run
pattern, applied to a DOM-wiring function instead of a pure one.

Three things have to hold, each proven by a scenario a planted defect breaks:

1. A tap (down, up, no real travel) selects.
2. A DRAG (down, move past `ROW_TAP_SLOP`, up) selects NOTHING — the owner's
   whole complaint.
3. A pointercancel under slop still selects — the Android edge-gesture rescue
   (constraint 9) survives on a row exactly as it does on every other button.
4. `pointerdown` never calls `preventDefault` — the actual mechanism of the
   bug: a row that still prevents it would keep stealing the scroll even if
   the tap/drag arithmetic above were perfect.

Run:  .venv\\Scripts\\python tests/test_row_tap.py
Requires: node on PATH — a HARD requirement (the test_grid_icons.py
precedent). Never skip it silently.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CLIENT = PROJECT / "client"
HOLD_GESTURE = CLIENT / "hold-gesture.js"
ROW_TAP = CLIENT / "row-tap.js"

START, END = "// ROW_TAP_GATE_START", "// ROW_TAP_GATE_END"

# EVERY LIST A FINGER MAY SCROLL (owner report 2026-08-15). His ruling was
# about the process, not the notification-voice card he happened to catch it
# in: a fix that lands in one panel and not in the four others carrying the
# same code is not a fix. So the row builders are NAMED here, and a builder
# that goes back to `keepFocus` fails this gate instead of waiting for him to
# find it on the device. Each entry: file → the substrings that must appear
# inside a `keepRowTap(` call somewhere in that file's rows.
#
# The rule for adding one: if a finger might legitimately begin a SCROLL on
# it — a row of any list, or any control inside a card that scrolls — it is a
# row. Ordinary buttons keep `keepFocus`, and anything needing transient user
# activation (a file picker, the IME) MUST keep it.
ROW_SITES = {
    "layout-create.js": ["keepRowTap(main"],       # the creation lists
    "layout-new.js": ["keepRowTap(main"],          # the New source's recents
    "layouts.js": ["keepRowTap(main", "keepRowTap(shape", "keepRowTap(gear"],
    "layout-settings.js": ["keepRowTap(main"],     # add-member candidates
    "dictation-card.js": ["keepRowTap(btn", "keepRowTap(more"],
    "notify.js": ["keepRowTap(btn"],               # the voice list
    "claude-panels.js": ["keepRowTap(row"],        # model / effort options
    "panels.js": ["keepRowTap(row", "keepRowTap(b"],
    "phone-panel.js": ["keepRowTap(beeps"],
    "set-editor.js": ["keepRowTap(cell"],
}


def _extract_block() -> str:
    text = ROW_TAP.read_text(encoding="utf-8")
    m = re.search(re.escape(START) + r"(.*?)" + re.escape(END), text, re.S)
    assert m, (
        f"{ROW_TAP} no longer carries the {START}/{END} markers — "
        "this gate would silently stop testing the real keepRowTap")
    return m.group(1)


def run(scenario: dict) -> dict:
    """One scenario = a sequence of pointer events against `keepRowTap`.
    Returns {tapped: bool, downCalls: int, preventDefaultCalls: int}."""
    if not shutil.which("node"):
        raise AssertionError(
            "node is required for the row-tap gate (it runs the REAL "
            "client/layout-create.js `keepRowTap`) — install Node.js. "
            "Never skip a gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_row_tap_gate_"))
    script = work / "run.js"
    block = _extract_block()
    hold = HOLD_GESTURE.read_text(encoding="utf-8")
    script.write_text(
        hold + "\n" +
        block + "\n" +
        "const listeners = {};\n"
        "let preventDefaultCalls = 0;\n"
        "const el = {\n"
        "  addEventListener(type, fn) { listeners[type] = fn; },\n"
        "};\n"
        "let tapped = 0;\n"
        "keepRowTap(el, () => { tapped += 1; });\n"
        f"const events = {json.dumps(scenario['events'])};\n"
        "for (const ev of events) {\n"
        "  const e = Object.assign({\n"
        "    pointerId: ev.id, clientX: ev.x, clientY: ev.y,\n"
        "    preventDefault() { preventDefaultCalls += 1; },\n"
        "  });\n"
        "  const handler = listeners[ev.type];\n"
        "  if (handler) handler(e);\n"
        "}\n"
        "console.log(JSON.stringify({ tapped, preventDefaultCalls }));\n",
        encoding="utf-8")
    try:
        out = subprocess.run([shutil.which("node"), str(script)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def ev(type_, x=100, y=100, id_=1):
    return {"type": type_, "x": x, "y": y, "id": id_}


def test_a_plain_tap_selects():
    result = run({"events": [ev("pointerdown"), ev("pointerup")]})
    assert result["tapped"] == 1, "an ordinary tap must select"


def test_a_drag_past_slop_selects_nothing():
    # 30px of real travel — a scroll, not a tap.
    result = run({"events": [
        ev("pointerdown", x=100, y=100),
        ev("pointermove", x=100, y=130),
        ev("pointerup", x=100, y=130),
    ]})
    # PLANTED-DEFECT PROOF: drop the `pointermove` listener (never track
    # travel) and this comes back `tapped: 1` — the exact bug reported: the
    # owner cannot scroll because every drag over a row still selects it.
    assert result["tapped"] == 0, "a drag must never select a row"


def test_a_tiny_wander_still_taps():
    # 5px — a resting finger's own wander (hold-gesture.js's own reasoning),
    # well under the 12px slop.
    result = run({"events": [
        ev("pointerdown", x=100, y=100),
        ev("pointermove", x=103, y=103),
        ev("pointerup", x=103, y=103),
    ]})
    assert result["tapped"] == 1, "a still finger's own wander must not cancel the tap"


def test_pointercancel_under_slop_still_selects():
    # The Android edge-gesture rescue (constraint 9): a touch the system
    # stole and ended with pointercancel, but barely travelled, still counts.
    result = run({"events": [
        ev("pointerdown", x=100, y=100),
        ev("pointercancel", x=102, y=101),
    ]})
    # PLANTED-DEFECT PROOF: remove the pointercancel listener entirely and
    # this comes back `tapped: 0` — a row near a screen edge would simply
    # never register a tap the system stole and rescued everywhere else.
    assert result["tapped"] == 1, "an under-slop pointercancel must still select"


def test_pointercancel_past_slop_selects_nothing():
    result = run({"events": [
        ev("pointerdown", x=100, y=100),
        ev("pointercancel", x=140, y=100),
    ]})
    assert result["tapped"] == 0, "a real-travel cancel (a system swipe) must not select"


def test_pointerdown_never_prevents_default():
    # THE ACTUAL MECHANISM of the reported bug: `keepFocus` preventDefaults on
    # pointerdown to guarantee touch activation, and that is exactly what
    # stops the browser from ever starting a scroll gesture on the element.
    result = run({"events": [ev("pointerdown")]})
    # PLANTED-DEFECT PROOF: add `e.preventDefault()` back into the pointerdown
    # handler (the `keepFocus` behaviour this function exists to NOT have) and
    # this count goes to 1 — silently reintroducing the exact bug reported,
    # even if the slop arithmetic above still passes every other check.
    assert result["preventDefaultCalls"] == 0, (
        "keepRowTap's pointerdown must never call preventDefault — that is "
        "what stops the browser from starting a scroll on the row")


def test_every_named_list_uses_the_row_activator():
    # THE OWNER'S OWN POINT (2026-08-15): "ne mogu da ti dam primedbu na
    # problem ... a da ga sredite samo na jednom mestu a ne svuda gde se on
    # provlači u aplikaciji" (lang-ok: owner quote). The arithmetic checks
    # above prove the RULE; this one proves it is actually WORN by every list
    # a finger can scroll. A panel that quietly goes back to `keepFocus`
    # steals the scroll again exactly as the voice card did, and no amount of
    # green arithmetic would say so.
    # PLANTED-DEFECT PROOF: change any one of these call sites back to
    # `keepFocus(` and this check names that file and that call.
    for name, needles in ROW_SITES.items():
        text = (CLIENT / name).read_text(encoding="utf-8")
        calls = [ln.strip() for ln in text.splitlines() if "keepRowTap(" in ln]
        assert calls, f"client/{name} builds rows but calls keepRowTap nowhere"
        joined = "\n".join(calls)
        for needle in needles:
            assert needle in joined, (
                f"client/{name}: no keepRowTap call matching {needle!r} — a "
                "row of a scrollable list went back to keepFocus, which "
                "preventDefaults on pointerdown and kills the scroll")


def test_the_row_activator_lives_in_its_own_module():
    # It lived inside layout-create.js until 2026-08-15, which is precisely
    # why four other panels never got it: a rule inside one panel's file is
    # read only by somebody already in that file (the hold-gesture.js lesson,
    # repeated). Nothing may define a SECOND copy.
    definers = [p.name for p in sorted(CLIENT.glob("*.js"))
                if "function keepRowTap(" in p.read_text(encoding="utf-8")]
    assert definers == ["row-tap.js"], (
        f"keepRowTap must be defined once, in client/row-tap.js — found in "
        f"{definers}")


CHECKS = [
    test_a_plain_tap_selects,
    test_a_drag_past_slop_selects_nothing,
    test_a_tiny_wander_still_taps,
    test_pointercancel_under_slop_still_selects,
    test_pointercancel_past_slop_selects_nothing,
    test_pointerdown_never_prevents_default,
    test_every_named_list_uses_the_row_activator,
    test_the_row_activator_lives_in_its_own_module,
]


if __name__ == "__main__":
    if not shutil.which("node"):
        print("SKIP-FAIL — node not on PATH (hard requirement)", file=sys.stderr)
        sys.exit(1)
    for check in CHECKS:
        check()
        print(f"PASS — {check.__name__}")
    print("PASS — test_row_tap")
