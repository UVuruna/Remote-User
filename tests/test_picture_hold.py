"""Picture Hold Gate: the screen never goes away, and the cube never lies.

Two halves of one round (2026-08-12), and they pull against each other, which
is exactly why they are gated together.

THE PICTURE (owner's largest blind wait). A quality change and a layout region
change both end one encoder and open another on the SAME monitor, and that
rebuild is 1.2–2.3 s. `initMse` cleared `everDrew`, so `redraw`'s never-blank
guard fell through and painted the flat theme colour for every one of those
milliseconds: no overlay, no pill change, no toast — the PC simply vanished and
came back. It is the same complaint as "A PICTURE THAT STOPPED BEATS NO
PICTURE" (owner 2026-08-09, render.js), arriving through the other door. The
last frame now HOLDS across a same-monitor swap.

THE CUBE. Holding that frame takes away the very thing that used to stop the
settle watcher from scoring on a stale picture: between the old session ending
and the new one decoding, nothing arrives, so the picture is frozen BY
DEFINITION — and three identical samples of a frozen picture is precisely what
`settleTick` counts as "settled". Left alone, the overlay would leave while the
PC was still moving windows, which is the one thing the owner has complained
about twice. So `settleStreamReset` re-arms the watcher on EVIDENCE: after a
new `config`, sampling starts at the new session's first decoded frame and not
one tick before.

AND THE FLOOR IS GONE (owner ruling 2026-08-12: "what 700-millisecond floor?
no floor is needed at all ... we must not produce this counter-effect where the
user waits BECAUSE OF the loading animation"). `LOADING_MIN_MS` is 0; what it
protected is bought by the 500 ms fade instead, which runs OVER the picture it
uncovers and — critically — stops swallowing taps at its START.

Driven in node against the REAL client/loading.js and the REAL
client/settle-motion.js, with a DOM shim and a scripted video element: a rule
about what happens over a second and a half of a stream cannot be proven by
reading the source. The render/connection/CSS halves are read from source,
because their subject is a call site.

Run:  .venv\\Scripts\\python tests/test_picture_hold.py
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
LOADING = PROJECT / "client" / "loading.js"
MOTION = PROJECT / "client" / "settle-motion.js"
RENDER = (PROJECT / "client" / "render.js").read_text(encoding="utf-8")
CONNECTION = (PROJECT / "client" / "connection.js").read_text(encoding="utf-8")
CSS = (PROJECT / "client" / "layouts.css").read_text(encoding="utf-8")
LOADING_SRC = LOADING.read_text(encoding="utf-8")

# The driver: a DOM shim thin enough to read, plus a video element a check can
# script frame by frame. `moving` decides what the fake canvas hands back —
# identical bytes (a still picture) or fresh ones (windows sliding).
DRIVER = r"""
const fs = require("fs");
const vm = require("vm");

const events = [];
const el = () => ({
  classList: { add: n => events.push(["class+", n, Date.now()]),
               remove: n => events.push(["class-", n, Date.now()]) },
  querySelector: () => ({ textContent: "" }),
  style: {},
});

const state = { moving: false, readyState: 2, painted: true, tick: 0 };
const sink = { drawImage() {}, getImageData() {
  // A still picture is the SAME bytes every time; a moving one differs in
  // most of its pixels, which is what settle-motion.js measures.
  state.tick++;
  const n = 64 * 36 * 4;
  const data = new Uint8ClampedArray(n);
  for (let i = 0; i < n; i += 4) {
    data[i] = state.moving ? (i + state.tick * 37) % 256 : 40;
    data[i + 1] = 40; data[i + 2] = 40; data[i + 3] = 255;
  }
  return { data };
} };

const ctx = {
  console, setInterval, clearInterval, setTimeout, clearTimeout,
  performance: { now: () => Date.now() },
  requestAnimationFrame: () => 1,
  cancelAnimationFrame: () => {},
  document: { getElementById: el, createElement: () => ({
    width: 0, height: 0, getContext: () => sink }) },
  module: { exports: {} },
  streamMode: "h264",
  video: { get readyState() { return state.readyState; } },
  get sessionDrew() { return state.painted; },
  baseBitmap: null,
  __state: state,
  __events: events,
};
ctx.window = ctx;
vm.createContext(ctx);
for (const f of process.argv.slice(3)) {
  vm.runInContext(fs.readFileSync(f, "utf8"), ctx, { filename: f });
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
const open = () => events.some(e => e[0] === "class+" && e[1] === "open") &&
  !events.some(e => e[0] === "class-" && e[1] === "open");

async function main() {
  const scenario = process.argv[2];
  const out = {};
  if (scenario === "stale-swap") {
    // The layout return: the overlay is up, the state frame armed the
    // watcher, and then the stream is replaced. Through the rebuild the
    // picture is frozen and the element has nothing decoded.
    ctx.showLayLoading("Working…");
    ctx.settleLayLoading();
    // THE REALISTIC HAZARD, not a convenient one: the element still reports
    // readyState 2 for the buffer of the session that just ended (video.load()
    // is asynchronous), and that picture is frozen because nothing is
    // arriving. Only "this session has painted" can tell the two apart.
    state.readyState = 2;
    state.painted = false;
    ctx.settleStreamReset();              // the new `config` landed
    await sleep(1400);                    // longer than catch-up + 3 hits
    out.openThroughRebuild = open();
    // The new session decodes, and the picture it shows is standing still.
    state.painted = true;
    const at = Date.now();
    for (let i = 0; i < 40 && open(); i++) await sleep(50);
    out.openAfterFrames = open();
    out.msToHide = Date.now() - at;
  } else if (scenario === "still-move") {
    // No stream swap: the watcher must still refuse a picture that is
    // MOVING, and leave promptly once it stops. No 700 ms floor either way.
    ctx.showLayLoading("Working…");
    state.moving = true;
    const at = Date.now();
    ctx.settleLayLoading();
    await sleep(1600);
    out.openWhileMoving = open();
    state.moving = false;
    for (let i = 0; i < 60 && open(); i++) await sleep(50);
    out.openAfterStill = open();
    out.totalMs = Date.now() - at;
  } else if (scenario === "no-floor") {
    // The picture is already still when the overlay opens: the only thing
    // that can hold it is the catch-up and three samples — never a floor.
    ctx.showLayLoading("Working…");
    const at = Date.now();
    ctx.settleLayLoading();
    for (let i = 0; i < 80 && open(); i++) await sleep(25);
    out.hidden = !open();
    out.msToHide = Date.now() - at;
    // `const` is lexical — it never lands on the context object.
    out.floor = vm.runInContext("LOADING_MIN_MS", ctx);
    out.fade = vm.runInContext("LOADING_FADE_MS", ctx);
  }
  console.log(JSON.stringify(out));
}
main();
"""


def drive(scenario: str) -> dict:
    node = shutil.which("node")
    if not node:
        raise AssertionError(
            "node is required for the picture-hold gate (it runs the REAL "
            "client/loading.js) — install Node.js. Never skip a gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_hold_gate_"))
    script = work / "drive.js"
    script.write_text(DRIVER, encoding="utf-8")
    try:
        out = subprocess.run(
            [node, str(script), scenario, str(MOTION), str(LOADING)],
            capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def check_a_frozen_picture_during_a_rebuild_is_not_settled():
    r = drive("stale-swap")
    assert r["openThroughRebuild"], (
        "the overlay left during the encoder rebuild — it scored three "
        "identical samples of a picture that was frozen because NOTHING was "
        "arriving, and uncovered a PC that is still moving windows")
    assert not r["openAfterFrames"], (
        "the overlay never left even once the new session was decoding a "
        "still picture — the re-arm waits for something that never comes")
    print(f"  a frozen rebuild holds the cube; the new session's own still "
          f"picture releases it in {r['msToHide']} ms")


def check_a_moving_picture_still_holds_and_a_still_one_still_releases():
    r = drive("still-move")
    assert r["openWhileMoving"], (
        "a picture in real motion no longer holds the overlay — the whole "
        "rule (owner 2026-08-03) is that it lasts as long as the WORK does")
    assert not r["openAfterStill"], "the overlay never leaves at all"
    print(f"  motion holds it, stillness releases it ({r['totalMs']} ms total)")


def check_there_is_no_floor_and_the_fade_carries_it():
    r = drive("no-floor")
    assert r["floor"] == 0, (
        f"LOADING_MIN_MS is {r['floor']} — the owner rejected the floor by "
        "name (2026-08-12): the animation may cover time, never add it")
    assert r["hidden"], "the overlay never left on an already-still picture"
    assert r["msToHide"] < 1400, (
        f"{r['msToHide']} ms to leave an already-still picture — something is "
        "still waiting on itself")
    # The fade is what the floor used to buy, and the two sides must agree.
    css = re.search(r"#lay-loading\s*{[^}]*transition:\s*opacity\s*(\d+)ms",
                    CSS, re.S)
    assert css, "the overlay's fade transition is gone from layouts.css"
    assert int(css.group(1)) == r["fade"] == 500, (
        f"fade mismatch: css={css.group(1)}ms js={r['fade']}ms — a JS timer "
        "that outlives the CSS fade freezes the cube mid-dissolve")
    # …and it must not swallow taps while it fades. `pointer-events` belongs
    # on the CLOSED rule, which takes effect the instant the class comes off.
    closed = CSS[CSS.index("#lay-loading {"):CSS.index("#lay-loading.open")]
    assert "pointer-events: none" in closed, (
        "the fading overlay still eats pointer events — that is the 700 ms "
        "floor again, with better manners")
    print(f"  no floor (left in {r['msToHide']} ms), a 500 ms fade, and it "
          "stops eating taps when the fade STARTS")


def check_the_last_frame_holds_across_a_same_monitor_swap():
    assert re.search(r"function initMse\(codec, keepPicture\)", RENDER), \
        "initMse no longer takes keepPicture — every swap blanks the canvas"
    assert re.search(r"if \(!keepPicture\) everDrew = false", RENDER), \
        "initMse clears everDrew unconditionally again: redraw()'s never-blank " \
        "guard falls through and paints the theme colour for the whole rebuild"
    assert "initMse(msg.codec, samePicture)" in CONNECTION, \
        "the config handler no longer decides whether the picture may be kept"
    # The question has to be asked BEFORE the answer is overwritten.
    asked = CONNECTION.index("const samePicture")
    written = CONNECTION.index("monitor = { w: msg.monitor_width")
    assert asked < written, (
        "samePicture is computed from a `monitor` that has already been "
        "replaced by the new one — it would always be true, monitor switch "
        "included, and a switch would show the previous screen's pixels")
    assert "monitorIndex ===" in CONNECTION[asked:written], (
        "a monitor SWITCH is not excluded — the old screen's picture would "
        "hold over the new one")
    assert "settleStreamReset()" in CONNECTION, \
        "the page never tells the watcher its stream was replaced"
    print("  the canvas keeps its last frame on a same-monitor swap, and only "
          "there")


def check_the_re_arm_waits_for_a_frame_and_not_for_a_clock():
    body = LOADING_SRC[LOADING_SRC.index("function streamHasPainted"):
                       LOADING_SRC.index("function showLayLoading")]
    assert "streamHasPainted()" in body, (
        "settleStreamReset no longer waits for a decoded frame — whatever it "
        "waits for instead is a timer, and the owner's rule is evidence")
    assert "sessionDrew" in body and "sessionDrew = false" in RENDER, (
        "the wait is back on `readyState` alone, which a stale element can "
        "still answer 2 to — the frozen old picture would be read as settled")
    assert "SETTLE_CATCHUP_MS" not in body, (
        "the re-arm restarted the catch-up timer: that is slower AND weaker "
        "than waiting for the frame that proves the stale picture is gone")
    print("  the re-arm's condition is a decoded frame, not a clock")


def main():
    print("PICTURE HOLD GATE - the screen never goes away, and the cube never lies")
    check_the_last_frame_holds_across_a_same_monitor_swap()
    check_the_re_arm_waits_for_a_frame_and_not_for_a_clock()
    check_a_frozen_picture_during_a_rebuild_is_not_settled()
    check_a_moving_picture_still_holds_and_a_still_one_still_releases()
    check_there_is_no_floor_and_the_fade_carries_it()
    print("OK - all picture hold checks passed")


if __name__ == "__main__":
    sys.exit(main())
