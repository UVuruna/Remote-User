"""TAP HAS ONE MEANING EVERYWHERE — the phone half (owner correction
2026-08-13, overruling his own ballot's first reading the same day: *"if I
tapped on something in that layout it IS ALREADY in that layout"*).

`tests/test_layout_claim.py` proves the SERVER sends `member_hwnds` — the
plain fact this file's subject depends on. This file proves the PHONE reacts
to it correctly, extracted and run WHOLE in node (the
`test_grid_icons.py`/`test_row_tap.py` precedent — never a re-typed copy):

1. `startTapSource()` arms the SAME way whether or not a layout is focused —
   there is no second, "claim" arming path any more (the thing removed this
   round). Proven by driving the REAL, unconditional function while
   `layoutActive` is set to a focused layout.
2. `handleLayoutOffer` — the REAL reply handler — refuses with a toast and
   creates NOTHING when the tap landed on a window that is already a member
   of the focused layout (`msg.target`, no `msg.tab`, hwnd in
   `layouts[layoutActive].member_hwnds`).
3. The SAME handler proceeds into the ordinary creation flow (a slot is
   pushed, the panel opens) when the tap landed on a TAB of a member window —
   `msg.tab` present makes the refusal impossible whatever the hwnd is,
   because a tab is never itself a member.
4. The SAME handler ALSO proceeds into the ordinary creation flow when the
   tap landed on a window that is NOT a member of the focused layout (a
   foreign window standing over the region) — exactly as it would at the
   desktop.

Run:  .venv\\Scripts\\python tests/test_layout_claim_arm.py
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
LAYOUT_CREATE = PROJECT / "client" / "layout-create.js"


def _source() -> str:
    return LAYOUT_CREATE.read_text(encoding="utf-8")


def _harness(layout_active, member_hwnds, extra_js) -> str:
    """Common globals every scenario needs: a fake `layouts` array (with or
    without a focused entry) and the REAL `layout-create.js` source in full —
    never an extracted fragment for this file, because the subject is TWO
    real functions (`startTapSource`, `handleLayoutOffer`) calling several
    others (`newCreation`, `armNextTap`, `slotFromOffer`,
    `tapTargetIsExistingMember`, …) DEFINED IN THAT FILE, which a partial
    extraction would have to re-declare and could silently drift from.

    Only EXTERNAL dependencies (functions this file imports from elsewhere —
    `closeLayoutPanel`, `showToast`, `svg`, `keepFocus`, `send`, `document`)
    are stubbed BEFORE the real source loads. `renderCreationPanel` is the
    one function DEFINED here that is deliberately overridden AFTER the real
    source runs (a plain reassignment, not a second `function` declaration —
    two same-named function declarations in one scope silently pick the
    LAST one textually, so a stub declared before the real source would just
    be shadowed and prove nothing): it draws the whole slot panel through
    grid/icon modules this harness does not load, and every check below only
    needs to know WHETHER it was reached, never what it would have drawn."""
    lay_line = (
        "null" if layout_active is None else
        "{ name: 'Work', member_hwnds: " + json.dumps(member_hwnds) + " }"
    )
    return (
        "let layoutArm = false;\n"
        "let creating = null;\n"
        "const toasts = [];\n"
        "function showToast(t) { toasts.push(t); }\n"
        "function closeLayoutPanel() {}\n"
        "function closeMiniRadial() {}\n"
        "function hideLayLoading() {}\n"
        "function showLayLoading() {}\n"
        "const LOADING_CUBE = 'cube';\n"
        "const LOADING_FULL = 'full';\n"
        f"let layoutActive = {json.dumps(layout_active)};\n"
        f"const layouts = layoutActive === null ? [] : [{lay_line}];\n"
        "function svg() { return ''; }\n"
        "function keepFocus() {}\n"
        "function send() {}\n"
        "const document = { getElementById: () => "
        "({ classList: { toggle() {} } }) };\n"
        "const window = { innerHeight: 900, innerWidth: 400 };\n"
        + _source() + "\n"
        "let rendered = 0;\n"
        "renderCreationPanel = () => { rendered += 1; };\n"
        + extra_js + "\n"
    )


def run(script_body: str) -> dict:
    if not shutil.which("node"):
        raise AssertionError(
            "node is required for the layout-claim-arm gate (it runs the "
            "REAL client/layout-create.js) — install Node.js. Never skip a "
            "gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_claim_arm_gate_"))
    script = work / "run.js"
    script.write_text(script_body, encoding="utf-8")
    try:
        out = subprocess.run([shutil.which("node"), str(script)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ═══════════════ 1. arming is ONE path, focused layout or not ═══════════════
def test_tap_arms_the_same_way_whether_or_not_a_layout_is_focused():
    for layout_active, hwnds in ((None, []), (0, [1, 2])):
        result = run(_harness(layout_active, hwnds, "startTapSource();"
                              "console.log(JSON.stringify({armed: layoutArm,"
                              " hasCreating: creating !== null, toasts}));"))
        assert result["armed"] is True, (
            f"startTapSource() must always arm (layoutActive={layout_active}): {result}")
        assert result["hasCreating"] is True, (
            "a tap session must always exist once armed")
        assert result["toasts"] == ["Tap a window or tab on the screen…"], (
            f"the ORDINARY arm toast — no separate 'claim' wording, "
            f"whether or not a layout is focused: {result}")
    # PLANTED-DEFECT PROOF (run by hand for this round): reintroducing the
    # removed branch — `if (layoutActive !== null) { startClaimTap(...); return; }`
    # at the top of `startTapSource` — makes the `layoutActive: 0` case above
    # come back with `hasCreating: false` (a claim session sets no `creating`
    # at all), which is exactly the regression this check exists to catch.


# ═══════════ 2. a tap on the member window itself creates nothing ══════════
def test_a_tap_on_a_member_window_refuses_and_creates_nothing():
    body = _harness(0, [0x10, 0x20], (
        "handleLayoutOffer({ target: { hwnd: 0x10, title: 'Vibe Coder',"
        " process: 'code.exe' }, tab: null, x: 0.5, y: 0.5 });"
        "console.log(JSON.stringify({ hasCreating: creating !== null,"
        " toasts, rendered }));"
    ))
    result = run(body)
    assert result["hasCreating"] is False, (
        f"a refused tap must leave no session armed: {result}")
    assert result["rendered"] == 0, (
        f"the creation panel must never open on a refused tap: {result}")
    assert len(result["toasts"]) == 1 and "already in this layout" in result["toasts"][0], (
        f"the refusal must be said in his own terms: {result}")
    # PLANTED-DEFECT PROOF: delete `tapTargetIsExistingMember`'s call inside
    # `handleLayoutOffer` and this comes back `rendered: 1` — the creation
    # panel opening on a window that is already the layout he is looking at,
    # exactly his report.


# ═══ 3. a tap on a TAB of a member window still starts a new layout ═══════
def test_a_tap_on_a_tab_still_starts_a_new_layout():
    body = _harness(0, [0x10, 0x20], (
        "handleLayoutOffer({ target: { hwnd: 0x10, title: 'Vibe Coder',"
        " process: 'code.exe' },"
        " tab: { name: 'prompt.txt' }, x: 0.5, y: 0.5 });"
        "console.log(JSON.stringify({ hasCreating: creating !== null,"
        " slots: creating ? creating.slots.length : 0,"
        " toasts, rendered }));"
    ))
    result = run(body)
    assert result["hasCreating"] is True and result["slots"] == 1, (
        f"a tab under the finger must still seed a new layout: {result}")
    assert result["toasts"] == [], (
        f"a tab tap is never refused: {result}")
    assert result["rendered"] == 1, (
        f"the ordinary creation panel must open: {result}")
    # PLANTED-DEFECT PROOF: drop the `msg.tab` guard from
    # `tapTargetIsExistingMember` (treat every hwnd match as a refusal
    # whether or not a tab rode along) and this comes back with NO slot
    # pushed and a toast instead — a tab inside his own layout would become
    # untappable, which is the one thing his correction explicitly allows.


# ═ 4. a tap on a foreign, non-member window still starts a new layout ══════
def test_a_tap_on_a_foreign_window_still_starts_a_new_layout():
    body = _harness(0, [0x10, 0x20], (
        "handleLayoutOffer({ target: { hwnd: 0x99, title: 'Calculator',"
        " process: 'calc.exe' }, tab: null, x: 0.5, y: 0.5 });"
        "console.log(JSON.stringify({ hasCreating: creating !== null,"
        " slots: creating ? creating.slots.length : 0,"
        " toasts, rendered }));"
    ))
    result = run(body)
    assert result["hasCreating"] is True and result["slots"] == 1, (
        f"a foreign window must still seed a new layout, exactly like the "
        f"desktop tap: {result}")
    assert result["toasts"] == [], f"a foreign window is never refused: {result}"
    assert result["rendered"] == 1


CHECKS = [
    test_tap_arms_the_same_way_whether_or_not_a_layout_is_focused,
    test_a_tap_on_a_member_window_refuses_and_creates_nothing,
    test_a_tap_on_a_tab_still_starts_a_new_layout,
    test_a_tap_on_a_foreign_window_still_starts_a_new_layout,
]


if __name__ == "__main__":
    if not shutil.which("node"):
        print("SKIP-FAIL — node not on PATH (hard requirement)", file=sys.stderr)
        sys.exit(1)
    for check in CHECKS:
        check()
        print(f"PASS — {check.__name__}")
    print("PASS — test_layout_claim_arm")
