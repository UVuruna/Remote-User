"""THE CUBE MAY NOT OVERSTAY — the loading-overlay settle gate (task 194).

Owner report: "traje predugo ... radi kontra uslugu" (it takes too long, it
works against him), plus "misses places it should cover". Two separate root
causes, found by reading the whole chain rather than guessing:

1. THE METRIC WAS TOO STRICT (client/loading.js, `settleStill()`). It
   compared a 64x36 thumbnail of the live frame against the previous one
   with a whole-frame MEAN of |Δr|+|Δg|+|Δb| per sample, and only counted a
   "still" hit once that mean fell under a fixed threshold. A blinking caret
   is a tiny patch and washes out in a mean over 2,304 samples — but his
   agents actively typing or scrolling inside a member window is real,
   ongoing, LOCAL motion covering a real share of the thumbnail, and it kept
   the mean above threshold for the ENTIRE watch window almost every time.
   By the time `layout_state` arrives the server has already verified
   placement (`window_manager.wait_landed`) — this side only owes him a
   moment to let the stream catch up, not a fight to see the picture stop
   moving completely. Fixed: the metric is now the FRACTION of pixels that
   changed past a per-pixel noise floor (`changedFraction`/`isSettled`, pure,
   the view-anchor.js/cursor-shapes.js pattern) — small local motion reads as
   settled, a real window move (a large share of the frame) does not — and
   the hard cap `SETTLE_MAX_MS` dropped from 4000 ms to 2200 ms, a real
   "a few seconds" after the server's own verified `layout_state`.

2. THE OVERLAY WAS MISSING ON A REAL PATH (client/connection.js, the
   `layout_state` handler's excursion-restore branch). It sent a corrective
   `layout_focus` to bring the phone back into the layout it was in before an
   excursion (gallery pick, permission dialog) — but `settleLayLoading()`,
   called earlier in the SAME handler, had already armed the settle watcher
   against the INTERIM (still-desktop) frame that arrived just before the
   correction. The watcher could declare that idle, unrelated picture
   "settled" and hide the cube before the real corrective move even started;
   the real move's OWN later `layout_state` then found the overlay already
   closed and `settleLayLoading()`'s own guard (`!layLoadingOpen`) made it a
   silent no-op — so he watched the actual restore bare, windows and all.
   Fixed: `showLayLoading()` is called again right after that `send()`,
   re-arming a fresh cycle (it clears any already-ticking settle timer) that
   only the real move's later `layout_state` can satisfy — mirroring the
   re-arm the visibilitychange handler already relies on for the sibling
   "coming back to the app" case a few lines below it.

THREE THINGS HAVE TO BE TRUE, and this gate proves each with its own planted
defect in mind (a check that cannot fail proves nothing):

  - LOCAL motion (a caret-sized patch) must still read as settled — proves
    the metric did not silently regress to "any change at all is motion".
  - LARGE-area motion must still read as NOT settled — proves the tolerance
    was not opened so wide a real window move would go uncaught.
  - No baseline (the first sample) is never settled — proves the "no data
    yet" case was not accidentally treated as stillness.
  - `SETTLE_MAX_MS` stays a real "a few seconds" (<= 3000 ms) — proves the
    hard cap was not silently widened back toward the old 4000 ms.
  - `settleStill()` in loading.js really calls the pure functions above, not
    a hand-rolled copy — a pure function nobody calls is a feature that does
    not exist (the actions.json lesson, 2026-08-07).
  - The connection.js excursion-restore branch calls `showLayLoading(` again
    after its `send({ type: "layout_focus"` — proves the missing re-arm was
    not merely fixed once and left unguarded for the next refactor to drop.

Run:  .venv\\Scripts\\python tests/test_loading_settle.py
Requires: node on PATH — a HARD requirement (the test_view_anchor.py
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
MODULE = PROJECT / "client" / "settle-motion.js"
LOADING = PROJECT / "client" / "loading.js"
CONNECTION = PROJECT / "client" / "connection.js"
INDEX = PROJECT / "client" / "index.html"


def run(calls: list[dict]) -> list[dict]:
    """Evaluate changedFraction()/isSettled() for each call, in one node
    process — the REAL client/settle-motion.js math, not a Python
    re-implementation that could quietly drift from it."""
    if not shutil.which("node"):
        raise AssertionError(
            "node is required for the loading-settle gate (it runs the REAL "
            "client/settle-motion.js math) — install Node.js. Never skip a "
            "gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_loading_gate_"))
    script = work / "run.js"
    script.write_text(
        f"const m = require({json.dumps(str(MODULE))});\n"
        f"const calls = {json.dumps(calls)};\n"
        "console.log(JSON.stringify(calls.map(c => {\n"
        "  const frac = m.changedFraction(\n"
        "    Uint8ClampedArray.from(c.data), c.prev ? Uint8ClampedArray.from(c.prev) : null);\n"
        "  return { frac, settled: m.isSettled(frac) };\n"
        "})));\n",
        encoding="utf-8")
    try:
        out = subprocess.run([shutil.which("node"), str(script)],
                             capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


# A 64x36 thumbnail's worth of RGBA samples (2,304 pixels), flat and boring —
# the "the desktop stopped moving" baseline every case perturbs.
W, H = 64, 36
PIXELS = W * H


def flat_frame(r=40, g=40, b=40):
    px = [r, g, b, 255] * PIXELS
    return px


def perturb(base, count, delta=200):
    """Flip `count` pixels' red channel hard, leave the rest untouched — a
    LOCAL patch of real change, sized as a fraction of the whole frame."""
    out = list(base)
    for i in range(count):
        out[i * 4] = (out[i * 4] + delta) % 256
    return out


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def check_local_motion_still_reads_as_settled() -> None:
    """A caret-sized patch (2% of the frame) — an agent's blinking cursor, a
    terminal's own caret — must not hold the overlay up forever."""
    base = flat_frame()
    local = perturb(base, int(PIXELS * 0.02))
    (result,) = run([{"data": local, "prev": base}])
    if not result["settled"]:
        raise AssertionError(
            f"a 2% local patch was NOT settled (frac={result['frac']:.3f}) — "
            "the overlay would overstay on a blinking caret again, task 194")


def check_large_area_motion_is_not_settled() -> None:
    """A real window sliding into place changes a large share of the frame —
    this must still read as moving, or a genuine restore would go uncovered."""
    base = flat_frame()
    big = perturb(base, int(PIXELS * 0.35))
    (result,) = run([{"data": big, "prev": base}])
    if result["settled"]:
        raise AssertionError(
            f"a 35% change WAS settled (frac={result['frac']:.3f}) — the "
            "tolerance opened so wide a real window move would be missed")


def check_no_baseline_is_never_settled() -> None:
    """The very first sample after arming has nothing to compare against —
    it must never count as a stillness hit."""
    base = flat_frame()
    (result,) = run([{"data": base, "prev": None}])
    if result["settled"]:
        raise AssertionError(
            "a first sample with no baseline read as settled — the overlay "
            "could vanish on its very first tick")


def check_settle_max_is_a_real_few_seconds() -> None:
    """Task 194: 4000 ms read as 'takes too long' after an already-verified
    layout_state. The cap must stay short — never silently widened back.
    `SETTLE_MAX_MS` stays in loading.js (it is not part of the pure motion
    metric), so this is a static read rather than a node run."""
    m = re.search(r"const SETTLE_MAX_MS\s*=\s*(\d+)", LOADING.read_text(encoding="utf-8"))
    if not m:
        raise AssertionError("SETTLE_MAX_MS left client/loading.js")
    value = int(m.group(1))
    if not (0 < value <= 3000):
        raise AssertionError(
            f"SETTLE_MAX_MS is {value} ms — expected a real 'a few seconds' "
            "(<= 3000 ms), not the old ~4-5 s wait")


def check_settle_still_runs_the_real_pure_functions() -> None:
    """A pure function nobody calls is a feature that does not exist — prove
    settleStill() in loading.js actually uses changedFraction()/isSettled()
    (from settle-motion.js) rather than a hand-rolled copy that could drift."""
    src = LOADING.read_text(encoding="utf-8")
    m = re.search(r"function settleStill\(\)\s*\{(.*?)\n\}", src, re.S)
    if not m:
        raise AssertionError("settleStill() left client/loading.js")
    body = m.group(1)
    if "changedFraction(" not in body or "isSettled(" not in body:
        raise AssertionError(
            "settleStill() no longer calls changedFraction()/isSettled() — "
            "the settle metric could have drifted back to a whole-frame mean")


def check_the_module_exports_the_pure_functions() -> None:
    src = MODULE.read_text(encoding="utf-8")
    if "module.exports = {" not in src or "changedFraction" not in src:
        raise AssertionError(
            "client/settle-motion.js no longer exports "
            "changedFraction/isSettled — this gate (and any future one) "
            "could no longer run the real math")
    for banned in ("document", "window.", "canvas.", "send(", "Android", "fetch("):
        if banned in src:
            raise AssertionError(
                f"client/settle-motion.js reaches for {banned!r} — it is no "
                "longer pure and this gate can no longer run it in node")


def check_the_page_loads_settle_motion_before_loading() -> None:
    html = INDEX.read_text(encoding="utf-8")
    motion = html.find("/static/settle-motion.js")
    loading = html.find("/static/loading.js")
    if motion == -1:
        raise AssertionError("index.html never loads settle-motion.js")
    if not -1 < motion < loading:
        raise AssertionError(
            "settle-motion.js must load BEFORE loading.js — settleStill() "
            "calls changedFraction()/isSettled() as page globals")


def check_the_excursion_restore_path_rearms_the_overlay() -> None:
    """The task-194 'misses' fix: connection.js's excursion-restore branch
    must call showLayLoading() again right after its corrective
    layout_focus send — otherwise the watcher armed against the interim
    (pre-correction) frame can hide the cube before the real move starts."""
    # Strip full-line `//` comments first — the fix's own explanatory comment
    # mentions "showLayLoading()" in prose, which would otherwise satisfy a
    # naive substring check even with the real call deleted.
    code_only = "\n".join(
        ln for ln in CONNECTION.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("//"))
    m = re.search(
        r"const back = layoutRestore\.index;.*?"
        r'send\(\{ type: "layout_focus", index: back \}\);'
        r"(.*?)\n\s*\} else if",
        code_only, re.S)
    if not m:
        raise AssertionError(
            "the excursion-restore branch (layoutRestore, layout_focus) "
            "left client/connection.js's layout_state handler in a shape "
            "this gate cannot find — update the gate alongside the refactor")
    after = m.group(1)
    if "showLayLoading(" not in after:
        raise AssertionError(
            "the excursion-restore branch sends a corrective layout_focus "
            "but never re-arms showLayLoading() afterward — the overlay can "
            "close on the interim frame before the real restore is covered "
            "(task 194)")


CHECKS = [
    ("a local patch (blinking caret) still reads as settled",
     check_local_motion_still_reads_as_settled),
    ("a large-area change (a real window move) is not settled",
     check_large_area_motion_is_not_settled),
    ("no baseline is never settled",
     check_no_baseline_is_never_settled),
    ("SETTLE_MAX_MS is a real 'a few seconds', not the old ~4-5 s wait",
     check_settle_max_is_a_real_few_seconds),
    ("settleStill() runs the real pure changedFraction/isSettled",
     check_settle_still_runs_the_real_pure_functions),
    ("the module exports the pure functions this gate depends on, and "
     "stays pure",
     check_the_module_exports_the_pure_functions),
    ("the page loads settle-motion.js before loading.js",
     check_the_page_loads_settle_motion_before_loading),
    ("the excursion-restore path re-arms the overlay after its own send",
     check_the_excursion_restore_path_rearms_the_overlay),
]


def main() -> int:
    print("\n=== LOADING SETTLE GATE ===")
    if shutil.which("node") is None:
        print("LOADING SETTLE GATE FAILED — node is required (it runs the "
              "REAL client/loading.js math) and is not on PATH. Never skip "
              "a gate silently.")
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
        print(f"\nLOADING SETTLE GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nLOADING SETTLE GATE PASSED — the cube leaves on real "
          "stillness, tolerates local motion, and covers the restore path.")
    return 0


def test_loading_settle():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
