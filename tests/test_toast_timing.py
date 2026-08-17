"""THE TOAST TIMING GATE — how long a notice stands depends on how much of it
there is to read.

OWNER DECISION 2026-08-17, and the rule is his own idea rather than a request
we interpreted: *"koliko stoji vidljiv zavisi od količine teksta u njemu"*
(lang-ok: owner quote — the sentence this gate exists to hold).

Before it, every toast stood exactly 2500 ms and then faded for 450 ms — just
under three seconds for "Reconnecting…" and the same three seconds for a whole
sentence naming a window and what the PC refused to do with it. One number
cannot be right for both, and the cost fell entirely on the long ones: those
are the notices that actually say something, and they were the ones half-read.

What is held here, each proven by planting its own defect:

  1. The duration really depends on the text — a long notice stands strictly
     longer than a short one. (Planting a constant return breaks this and
     nothing else, which is the point: it is the whole feature.)
  2. It is MONOTONE. More text may never mean less time, at any length.
  3. The floor is the old 2500 ms, so nothing this app already says got
     SHORTER this round — a change that quietly clipped existing notices would
     be a regression wearing an improvement's name.
  4. There is a ceiling. A rule with no cap turns one long refusal into a pill
     sitting over his controls for half a minute; the pill is a glance.
  5. The real page really USES it: `showToast`'s timer must be driven by the
     function, not by a constant that happens to sit beside it.

It runs the SHIPPED function, extracted from client/chrome.js between its own
markers and evaluated whole in node — never a copy re-typed here, which would
prove this file to itself while the page did something else (the actions.json
lesson of 2026-08-07).

Run:  .venv\\Scripts\\python tests/test_toast_timing.py
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import run_checks  # noqa: E402

CHROME = Path(__file__).resolve().parent.parent / "client" / "chrome.js"

# The constants and the function, taken as SOURCE TEXT. The block is bounded by
# the first constant's name and the closing brace of the function, so an edit
# that renames or moves either one fails loudly here instead of silently
# testing nothing.
_BLOCK = re.compile(r"(const TOAST_NOTICE_MS.*?\n}\n)", re.S)


def _durations(lengths):
    """Run the real `toastDuration` over texts of the given lengths."""
    src = CHROME.read_text(encoding="utf-8")
    match = _BLOCK.search(src)
    if not match:
        raise AssertionError(
            "toastDuration/TOAST_* not found in client/chrome.js — the gate "
            "must fail loudly rather than measure a function it cannot see")
    work = Path(tempfile.mkdtemp(prefix="ru_toast_gate_"))
    try:
        script = work / "run.js"
        script.write_text(
            match.group(1)
            + "\nconst lens = " + json.dumps(list(lengths)) + ";\n"
            + "console.log(JSON.stringify(lens.map(n => toastDuration('x'.repeat(n)))));\n",
            encoding="utf-8")
        node = shutil.which("node")
        if not node:
            raise AssertionError("node is required for this gate")
        out = subprocess.run([node, str(script)], capture_output=True,
                             text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(f"node failed: {out.stderr.strip()}")
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def check_a_long_notice_stands_longer_than_a_short_one() -> bool:
    """THE FEATURE ITSELF. "Reconnecting…" is a glance; a sentence naming a
    window and a refusal is a thing to read, and it must be given the time."""
    short, long_ = _durations([13, 90])
    return long_ > short


def check_more_text_never_means_less_time() -> bool:
    """Monotone at every length, including across both clamps — a curve that
    dipped anywhere would mean some longer notice standing for less time than
    a shorter one, which is exactly the state his rule forbids."""
    lens = [0, 1, 5, 13, 30, 60, 90, 140, 200, 400, 2000]
    ds = _durations(lens)
    return all(b >= a for a, b in zip(ds, ds[1:]))


def check_nothing_this_app_says_got_shorter() -> bool:
    """The floor is the old constant exactly, so this round could not have
    clipped a notice that used to be readable. Checked at zero length, which
    is the worst case the arithmetic can produce."""
    return _durations([0])[0] >= 2500


def check_it_has_a_ceiling() -> bool:
    """A pill is a glance, never a page: an enormous text may not nail it over
    the controls. Driven with an absurd length on purpose — the clamp must
    hold at any input, not only at realistic ones."""
    return _durations([100000])[0] <= 12000


def check_the_page_really_uses_it() -> bool:
    """A FUNCTION NOBODY CALLS IS NOT A FEATURE. `showToast`'s own timer must
    be driven by `toastDuration(text)`; a literal there would leave this whole
    gate measuring an unused helper."""
    src = CHROME.read_text(encoding="utf-8")
    body = src[src.index("function showToast("):]
    body = body[:body.index("\n}\n")]
    return "toastDuration(text)" in body


CHECKS = [
    ("a long notice stands longer than a short one",
     check_a_long_notice_stands_longer_than_a_short_one),
    ("more text never means less time",
     check_more_text_never_means_less_time),
    ("nothing this app already says got shorter",
     check_nothing_this_app_says_got_shorter),
    ("it has a ceiling",
     check_it_has_a_ceiling),
    ("the page really uses it",
     check_the_page_really_uses_it),
]


def main() -> int:
    return run_checks("TOAST TIMING GATE", CHECKS,
                      "a notice stands as long as there is to read")


def test_toast_timing():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
