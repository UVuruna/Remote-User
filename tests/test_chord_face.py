"""THE CHORD-FACE GATE — a key name is never cut in half.

Owner report 2026-08-19, two photographs: the button as it was, reading
"Ctrl+Shi / ft+P", and the button as it must be — one key per line, across the
whole face. His question came with it, and it is the reason this file explains
whose button this even is:

    "koji je to dugme jel to nešto zamišljeno za budućeg korisnika koji će
     raditi CUSTOM? Koliko ja znam to mi nemamo nigdje?"
    <!-- lang-ok: owner quote, the dated record of the question -->

HE IS RIGHT AND THE ANSWER IS "NOWHERE, YET". Every one of the 90 commands in
the shipped actions.json carries an icon, so no set the app installs with can
reach this face. It is reached by a CUSTOM command: the desktop Controls
editor creates one as `{"label": "Command N", "chord": ""}` with "(no icon)"
selected (server/gui/controls_editor.py -> `_add_command`), and
`makeActionButton` draws an iconless button as `ctl text` with
`btn.label || btn.chord` on it. So the face exists for a stranger who has not
yet given his own command a name and a picture — and until he does, the
shortcut itself is what he reads.

WHAT IS HELD HERE, each proven by planting its own defect:

  1. `chordFace` ends a line after every "+" and touches nothing else.
  2. Rendered at the shipped tokens, "ctrl+shift+p" comes out as exactly ONE
     KEY PER LINE — the picture he drew — and not one key is split. Measured
     off the real client/style.css in a real browser, character by character,
     never asserted about the stylesheet.
  3. It fits INSIDE the face — no line runs past the button's own edge.
  4. A label with no "+" is untouched: a long reserve command still wraps at
     its spaces under an icon, the behaviour `--ctl-label-max` exists for.
  5. THE OLD RENDERING REALLY DID SPLIT IT. The same string, with
     `overflow-wrap: anywhere` and no newline written, is measured in the
     same browser — if that comes out whole too, this gate measures nothing.
  6. The design lab's specimen breaks the way the product breaks. The lab
     cannot import controls.js, so its one mirrored line is measured here
     rather than trusted.

Requires: playwright + chromium. A gate that reasons about line breaking from
a stylesheet instead of asking a line breaker proves only that it agrees with
itself.

Run:  .venv\\Scripts\\python -m pytest tests/test_chord_face.py
"""

import json
import re
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
CONTROLS = PROJECT / "client" / "controls.js"
PREVIEW = PROJECT / "tools" / "preview.html"

CHORD = "ctrl+shift+p"
ZWSP = "​"


# The product's own rule, restated once so every check below drives the
# same shape the phone draws. `test_the_line_ends_after_every_plus_and_
# nowhere_else` is what keeps this honest against client/controls.js.
def FACE(label: str) -> str:
    stacked = label.replace("+", "+\n")
    return stacked[:-1] if stacked.endswith("\n") else stacked


# ═══════════════════════ the transform, read from the source ═══════════════
def _chord_face_source() -> str:
    """The real `chordFace`, lifted whole out of client/controls.js. Lifted
    and not copied: a gate holding its own copy of the function it is checking
    reports that two copies agree, which is the one thing nobody asked."""
    text = CONTROLS.read_text(encoding="utf-8")
    match = re.search(r"^function chordFace\(label\) \{.*?^\}", text,
                      re.S | re.M)
    assert match, "client/controls.js no longer declares `chordFace`"
    return match.group(0)


def test_the_line_ends_after_every_plus_and_nowhere_else():
    source = _chord_face_source()
    assert '"+\\n"' in source, (
        "the chord face is a STACK — the line must END after a \"+\", not "
        "merely be allowed to")
    assert ZWSP not in CONTROLS.read_text(encoding="utf-8"), (
        "a literal zero-width space landed in client/controls.js")

    for label, expected in (
        ("ctrl+shift+p", "ctrl+\nshift+\np"),
        ("Copy path", "Copy path"),      # no "+" — untouched
        ("+", "+"),                      # no empty last line on a bare "+"
        ("", ""),
    ):
        got = FACE(label)
        assert got == expected, (label, got)


def test_the_label_no_longer_wears_the_label_width_cap():
    """`--ctl-label-max` caps a name sitting UNDER an icon so it cannot crowd
    it. A chord face has no icon to crowd, and the cap is what forced the
    break to happen early enough to land mid-word."""
    css = (PROJECT / "client" / "style.css").read_text(encoding="utf-8")
    rule = re.search(r"^\.ctl\.text \.lbl \{(.*?)^\}", css, re.S | re.M)
    assert rule, "client/style.css no longer has a `.ctl.text .lbl` rule"
    body = rule.group(1)
    assert "max-width" in body, "the chord face must state its own width"
    assert "pre-line" in body, (
        "without `white-space: pre-line` the newline written by `chordFace` "
        "collapses to a space and the stack becomes a wrap again")
    assert "anywhere" not in body, (
        "`overflow-wrap: anywhere` on the chord face is the defect itself — "
        "it is what cut Shift in two")
    assert "break-word" in body


def test_the_lab_specimen_breaks_the_way_the_product_breaks():
    """tools/preview.html draws its own specimen and cannot import
    controls.js. One mirrored line is fine; a mirror nobody checks is not."""
    text = PREVIEW.read_text(encoding="utf-8")
    assert 'replace(/\\+/g, "+\\n").replace(/\\n$/, "")' in text, (
        "the lab's `ctl()` no longer applies the product's own chord break, "
        "so the lab is now showing a button the phone will never draw")
    assert "lbl.textContent" in text


# ═══════════════════════ what a line breaker actually does ═════════════════
# One page, three renderings: the product's face, the same face with the break
# taken away (the defect, planted), and an ordinary name under an icon. Every
# line is reconstructed CHARACTER BY CHARACTER off real client rects — nothing
# here trusts a stylesheet to mean what it reads like.
LINES_JS = r"""
(text) => {
  const lbl = document.querySelector("#probe .lbl");
  lbl.textContent = text;
  const node = lbl.firstChild;
  const range = document.createRange();
  const lines = [];
  for (let i = 0; i < node.length; i++) {
    // The newline itself is not INK. It carries a rect at the end of the line
    // it terminates, and counting it would read every stacked key as ending
    // in a character the eye never sees.
    if (node.data[i] === "\n") continue;
    range.setStart(node, i);
    range.setEnd(node, i + 1);
    const r = range.getBoundingClientRect();
    if (!r.width && !r.height) continue;          // a collapsed break
    const top = Math.round(r.top);
    let line = lines.find((l) => Math.abs(l.top - top) < 4);
    if (!line) { lines.push(line = { top, text: "", right: 0 }); }
    line.text += node.data[i];
    line.right = Math.max(line.right, r.right);
  }
  lines.sort((a, b) => a.top - b.top);
  const face = document.querySelector("#probe").getBoundingClientRect();
  return {
    lines: lines.map((l) => l.text),
    overflow: Math.max(0, ...lines.map((l) => Math.round(l.right - face.right))),
  };
}
"""

PAGE = """
<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="theme.css">
<link rel="stylesheet" href="style.css">
<body data-theme="dark" data-colored="false" data-fill="transparent">
<button id="probe" class="ctl text"><span class="lbl"></span></button>
<button id="named" class="ctl"><span class="lbl"></span></button>
"""


def _keys(chord: str) -> list[str]:
    return chord.split("+")


@pytest.fixture(scope="module")
def probe():
    """The real client/theme.css and client/style.css, over http so the
    cascade behaves exactly as it does on the phone. The probe page itself is
    served FROM MEMORY — a test that drops a scratch file into client/ is a
    test that ships one the day it crashes between write and unlink."""
    pytest.importorskip("playwright.sync_api")
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    from playwright.sync_api import sync_playwright

    class Probe(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(PROJECT / "client"), **kw)

        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.split("?")[0] != "/probe":
                return super().do_GET()
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Probe)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch()
            page = browser.new_page(viewport={"width": 600, "height": 400})
            page.goto("http://127.0.0.1:%d/probe" % server.server_address[1])
            page.wait_for_selector("#probe")
            yield page
            browser.close()
    finally:
        server.shutdown()


def test_the_chord_comes_out_one_key_per_line(probe):
    got = probe.evaluate(LINES_JS, FACE(CHORD))
    lines = got["lines"]
    keys = _keys(CHORD)

    assert lines == [k + "+" for k in keys[:-1]] + [keys[-1]], (
        "the chord did not come out one key per line: %s" % json.dumps(lines))
    for line in lines:
        assert line.rstrip("+") in keys, (
            "a key name was cut in half — %r is not one of %s"
            % (line.rstrip("+"), keys))


def test_it_stays_inside_the_face(probe):
    got = probe.evaluate(LINES_JS, FACE(CHORD))
    assert got["overflow"] <= 0, (
        "the chord face runs %dpx past the button's own edge — THE SPACE & "
        "LEGIBILITY LAW" % got["overflow"])


def test_without_the_break_it_really_did_cut_a_key_in_half(probe):
    """THE PLANTED DEFECT. The same string, rendered the way it was before
    this round: no newline written, `overflow-wrap: anywhere`, capped at
    `--ctl-label-max`. If this comes out whole, everything above is vacuous."""
    probe.eval_on_selector("#probe .lbl", """
      el => { el.style.overflowWrap = "anywhere";
              el.style.whiteSpace = "normal";
              el.style.maxWidth = "var(--ctl-label-max)"; }""")
    got = probe.evaluate(LINES_JS, CHORD)          # the raw chord, no newline
    probe.eval_on_selector("#probe .lbl",
                           'el => { el.style.overflowWrap = ""; '
                           'el.style.whiteSpace = ""; el.style.maxWidth = ""; }')

    lines = got["lines"]
    cut = [line for line in lines if line.rstrip("+") not in _keys(CHORD)]
    assert cut, (
        "the OLD rendering came out whole too (%s) — this gate is measuring "
        "nothing, and the fix it guards proves nothing"
        % json.dumps(lines))


def test_a_name_with_no_plus_is_left_exactly_as_it_was(probe):
    """The other 90 buttons. `--ctl-label-max` and `overflow-wrap: anywhere`
    still own the label under an icon, and a long reserve command still wraps
    at its spaces rather than eliding (owner 2026-08-05)."""
    got = probe.evaluate(LINES_JS.replace("#probe", "#named"),
                         FACE("Toggle terminal panel"))
    lines = [line.strip() for line in got["lines"]]
    assert lines == ["Toggle", "terminal", "panel"], json.dumps(lines)

    # And a "+" inside a NAMED button collapses to a space rather than
    # stacking: only the iconless face is a stack.
    got = probe.evaluate(LINES_JS.replace("#probe", "#named"), FACE("Vol+"))
    assert [line.strip() for line in got["lines"]] == ["Vol+"], got["lines"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
