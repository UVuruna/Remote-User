"""Live Clock Gate: a starved player is caught, slowed BEFORE it is ever
flushed, and a flush that must still happen never repeats often enough to
turn a freeze into a blank screen.

TASK 151 (2026-08-10), after two earlier fixes for the SAME symptom went back
out on the SAME night for shipping three streaming changes in one window
(0.0.375's revert — commit 581244b): the 0.0.367 starve-recovery fix
(a9db36b) was real and caught his freeze, but it flushed the decoder on every
recovery, and on a link that genuinely cannot keep up (4K/60fps/20Mbps) that
fired every second — the 0.0.373 fix for THAT (3b7b477) rate-limited the
flush to once per 4s and added a never-blank canvas guard, but all three
landed together and the owner could not attribute any of it, so all three
came out. This build returns them as ONE mechanism, deliberately: slow the
player down BEFORE ever reaching for a flush (`liveRegulate`), and even the
flush that does become necessary is rate-limited (`LIVE_UNFREEZE_MIN_GAP_MS`).

Both live in the pure module client/live-clock.js (no DOM, no socket, no
video element — the caret.js/voice.js/view-anchor.js pattern), which is what
lets this gate drive the WHOLE mechanism in node against a REALISTIC DRIFT
RAMP taken from his own server log (task 151, 2026-08-09 report) rather than
asserting on a `<video>` element's mood:

    behind: +0.34 -> -0.01 -> -0.14 -> -0.96 -> -4.92 -> -9.09 -> -13.62
            -> -21.03 -> -24.90                              (over ~6 min)

A rule about a RAMP cannot be proven by one call — the same reasoning
test_voice_dedup.py's header gives for driving whole partial sequences rather
than single calls.

Run:  .venv\\Scripts\\python tests/test_live_clock.py
Requires: node on PATH — a HARD requirement (the test_voice_dedup.py /
test_view_anchor.py precedent: this gate runs the REAL client/live-clock.js
rules). Never skip it silently.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MODULE = PROJECT / "client" / "live-clock.js"
RENDER = PROJECT / "client" / "render.js"
STATE = PROJECT / "client" / "state.js"
INDEX = PROJECT / "client" / "index.html"

# His own log, task 151 (2026-08-09) — the SAME ramp the build's header
# quotes. Checkpoints only; the drive loop below interpolates between them so
# the mechanism is exercised at a realistic tick rate, not just at the nine
# points his 15s report happened to land on.
RAMP_CHECKPOINTS = [0.34, -0.01, -0.14, -0.96, -4.92, -9.09, -13.62, -21.03, -24.90]
RAMP_TOTAL_MS = 360_000   # ~6 minutes, matching "in ~6 min" above
RAMP_STEP_MS = 250        # a plausible onMseUpdateEnd/unfreezeIfStarved cadence

# Mirrors client/state.js's own values — the wiring checks below pin that
# state.js really carries these, so a drift between the two can never go
# unnoticed.
MAX_BEHIND_S = 0.5
STARVED_S = -0.2


def fail(msg: str) -> None:
    raise AssertionError(msg)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        fail("node is required for this gate (it runs the REAL "
             "client/live-clock.js rules) — install Node.js. Never skip a "
             "gate silently.")
    return node


def _module() -> str:
    """The WHOLE of client/live-clock.js — proves the exported surface this
    gate depends on is still there before wasting a node process on it."""
    text = MODULE.read_text(encoding="utf-8")
    for needed in ("function liveAction", "function liveSeekTarget",
                   "function liveRegulate", "LIVE_UNFREEZE_MIN_GAP_MS",
                   "LIVE_RATE_DEGRADE_HOLD_MS", "LIVE_SLOW_RATE"):
        if needed not in text:
            fail(f"{needed!r} left client/live-clock.js — the gate cannot "
                 "find what it must test")
    return text


def _run(script_body: str):
    """Runs client/live-clock.js plus `script_body` (which must end by
    printing one JSON line) in a fresh node process — the test_voice_dedup.py
    pattern, so every case starts from a clean interpreter."""
    script = f"{_module()}\n{script_body}\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.mjs"
        path.write_text(script, encoding="utf-8")
        out = subprocess.run([_node(), str(path)], capture_output=True,
                              text=True, timeout=60)
    if out.returncode != 0:
        fail(f"node failed:\n{out.stderr}")
    return json.loads(out.stdout.strip().splitlines()[-1])


# ═══════════════════════════ THE TRUTH TABLE ═══════════════════════════
def check_the_truth_table_matches_his_six_cases() -> None:
    """The exact six cases from his log (a9db36b's original test, restored
    here under the new module): the healthy band, the edge, ordinary lag, his
    -11.1s freeze, a hair of negative jitter, and a lighter starve."""
    out = dict(_run(f"""
console.log(JSON.stringify([
  ['healthy', liveAction(0.20, {MAX_BEHIND_S}, {STARVED_S})],
  ['at the edge', liveAction(0.49, {MAX_BEHIND_S}, {STARVED_S})],
  ['drifted', liveAction(0.80, {MAX_BEHIND_S}, {STARVED_S})],
  ['his freeze', liveAction(-11.1, {MAX_BEHIND_S}, {STARVED_S})],
  ['just past zero', liveAction(-0.05, {MAX_BEHIND_S}, {STARVED_S})],
  ['starved', liveAction(-0.5, {MAX_BEHIND_S}, {STARVED_S})],
]));
"""))
    want = {"healthy": "live", "at the edge": "live", "drifted": "seek_forward",
            "his freeze": "starved", "just past zero": "live", "starved": "starved"}
    for label, expect in want.items():
        got = out.get(label)
        if got != expect:
            fail(f"liveAction() for {label!r} = {got!r}, want {expect!r}")


def check_seek_target_never_lands_before_the_buffer_starts() -> None:
    """A starve deep enough that end - target would land BEFORE the buffer's
    own start must clamp there instead — landing outside the buffer would
    throw a real InvalidStateError on `video.currentTime =`."""
    out = _run("""
console.log(JSON.stringify({
  clamped: liveSeekTarget(10, 10.3, 0.45),
  ordinary: liveSeekTarget(0, 20, 0.45),
}));
""")
    if out["clamped"] != 10:
        fail(f"a starve deeper than the buffer's own start was not clamped "
             f"to it: got {out['clamped']!r}")
    if abs(out["ordinary"] - 19.55) > 1e-9:
        fail(f"the ordinary landing formula (end - target) changed: "
             f"got {out['ordinary']!r}")


# ═══════════════════════════ THE REGULATOR ═══════════════════════════
def check_the_regulator_engages_before_any_flush_is_permitted() -> None:
    """A starve held at -1s behind, ticked every 100ms: the rate must drop to
    LIVE_SLOW_RATE on the FIRST negative tick — long before a seek is ever
    allowed — and a seek may not fire until the hold (2s) has elapsed."""
    log = _run("""
let state = { rate: 1, degradedSince: 0, lastFixAt: 0 };
const log = [];
let now = 0;
for (let i = 0; i < 30; i++) {
  now += 100;
  const reg = liveRegulate({ behind: -1, now, starved: true, rate: state.rate,
                              degradedSince: state.degradedSince, lastFixAt: state.lastFixAt });
  log.push({ now, rate: reg.rate, seek: reg.seek });
  state.rate = reg.rate;
  state.degradedSince = reg.degradedSince;
  if (reg.seek) state.lastFixAt = now;
}
console.log(JSON.stringify(log));
""")
    if log[0]["rate"] != 0.97:
        fail("the rate did not drop on the very FIRST negative tick — "
             f"degradation must start immediately: {log[0]!r}")
    first_seek = next((e for e in log if e["seek"]), None)
    if first_seek is None:
        fail("a starve held at -1s behind for 3s never produced a rescue "
             "seek at all")
    if first_seek["now"] < 2000 + 100:
        fail("a seek fired before the 2s degrade-hold elapsed — the "
             f"regulator did not engage BEFORE the flush: {first_seek!r}")
    if first_seek["rate"] != 0.97:
        fail(f"a seek fired while the rate was not already slowed: {first_seek!r}")


def check_backward_seek_never_fires_more_than_once_per_4s() -> None:
    """A PERMANENT deep starve — exactly his 4K/60fps/20Mbps case, the one
    that turned a freeze into a blue screen pre-task-130 — over 60 real
    seconds. However many ticks report the player still starved, the seek
    itself may fire no more than once every LIVE_UNFREEZE_MIN_GAP_MS."""
    seek_times = _run("""
let state = { rate: 1, degradedSince: 0, lastFixAt: 0 };
let now = 0;
const seekTimes = [];
for (let i = 0; i < 600; i++) {
  now += 100;
  const reg = liveRegulate({ behind: -5, now, starved: true, rate: state.rate,
                              degradedSince: state.degradedSince, lastFixAt: state.lastFixAt });
  state.rate = reg.rate;
  state.degradedSince = reg.degradedSince;
  if (reg.seek) { seekTimes.push(now); state.lastFixAt = now; }
}
console.log(JSON.stringify(seekTimes));
""")
    if len(seek_times) < 2:
        fail("a permanent 60s starve never repeated a rescue seek at all — "
             "the rate-limit cannot be proven without at least two firings")
    for prev, cur in zip(seek_times, seek_times[1:]):
        gap = cur - prev
        if gap < 4000:
            fail(f"two backward seeks fired {gap}ms apart (< 4000ms): "
                 f"{prev} then {cur}")


def check_rate_recovers_once_behind_climbs_back_above_the_threshold() -> None:
    out = _run("""
let reg = liveRegulate({ behind: -1, now: 1000, starved: true, rate: 1,
                          degradedSince: 0, lastFixAt: 0 });
const afterDrop = reg.rate;
reg = liveRegulate({ behind: 0.5, now: 2000, starved: false, rate: reg.rate,
                      degradedSince: reg.degradedSince, lastFixAt: 0 });
console.log(JSON.stringify({ afterDrop, afterRecover: reg.rate,
                              degradedSinceAfterRecover: reg.degradedSince }));
""")
    if out["afterDrop"] != 0.97:
        fail(f"the rate did not drop when behind went negative: {out!r}")
    if out["afterRecover"] != 1:
        fail(f"the rate did not recover once behind climbed back above the "
             f"recover threshold: {out!r}")
    if out["degradedSinceAfterRecover"] != 0:
        fail("degradedSince was not cleared on recovery — a LATER starve "
             f"would think it had been degraded since the old episode: {out!r}")


def check_the_hysteresis_band_holds_whatever_was_decided_before() -> None:
    """Between 0 and LIVE_RATE_RECOVER_S neither edge is crossed — a
    threshold sitting exactly where the slowdown engages would let the rate
    flap every sample while the drift hovers near zero."""
    out = _run("""
let reg = liveRegulate({ behind: -1, now: 1000, starved: true, rate: 1,
                          degradedSince: 0, lastFixAt: 0 });
reg = liveRegulate({ behind: 0.1, now: 1500, starved: false, rate: reg.rate,
                      degradedSince: reg.degradedSince, lastFixAt: 0 });
console.log(JSON.stringify({ rate: reg.rate }));
""")
    if out["rate"] != 0.97:
        fail(f"the hysteresis band did not hold the slow rate at 0.1s "
             f"behind (between 0 and the recover threshold): {out!r}")


# ═══════════════════════ THE REALISTIC RAMP (his own log) ═══════════════════
def check_the_realistic_ramp_from_his_own_log() -> None:
    """Drives client/live-clock.js against his exact task-151 drift ramp,
    interpolated to a real tick rate, and proves the three things a fix for
    this bug must be true of AT ONCE:

      1. the starve is caught (today's shipped rule — the one this gate
         replaces — never classifies a negative `behind` as anything, so it
         would sit doing nothing while this same ramp runs to -24.9s)
      2. no two backward seeks fire less than 4000ms apart, across the WHOLE
         6-minute ramp, however long the starve persists
      3. the rate regulator is ALREADY slow at the tick immediately before
         the first seek fires — proving it engaged before the flush, not on
         the same call as a side door around the hold
    """
    checkpoints = json.dumps(RAMP_CHECKPOINTS)
    out = _run(f"""
const checkpoints = {checkpoints};
const totalMs = {RAMP_TOTAL_MS};
const stepMs = {RAMP_STEP_MS};
const segMs = totalMs / (checkpoints.length - 1);

let state = {{ rate: 1, degradedSince: 0, lastFixAt: 0 }};
let now = 0;
let sawStarved = false;
const seekTimes = [];

for (let seg = 0; seg < checkpoints.length - 1; seg++) {{
  const a = checkpoints[seg], b = checkpoints[seg + 1];
  for (let t = 0; t < segMs; t += stepMs) {{
    now += stepMs;
    const behind = a + (b - a) * (t / segMs);
    const act = liveAction(behind, {MAX_BEHIND_S}, {STARVED_S});
    if (act === 'starved') sawStarved = true;
    const reg = liveRegulate({{ behind, now, starved: act === 'starved',
      rate: state.rate, degradedSince: state.degradedSince, lastFixAt: state.lastFixAt }});
    state.rate = reg.rate;
    state.degradedSince = reg.degradedSince;
    if (reg.seek) {{ seekTimes.push(now); state.lastFixAt = now; }}
  }}
}}
console.log(JSON.stringify({{ sawStarved, seekTimes }}));
""")
    if not out["sawStarved"]:
        fail("liveAction() never classified any sample of his own -24.9s "
             "ramp as 'starved' — this is the exact freeze the shipped rule "
             "(behind > 0.5 only) could never catch: RED against today's "
             "code, and it must be GREEN here")
    if not out["seekTimes"]:
        fail("no rescue seek ever fired across the whole ramp — a starve "
             "this deep and this long must eventually be recovered")
    for prev, cur in zip(out["seekTimes"], out["seekTimes"][1:]):
        gap = cur - prev
        if gap < 4000:
            fail(f"two backward seeks fired {gap}ms apart across his ramp "
                 f"(< 4000ms): {prev} then {cur} — this is exactly the "
                 "failure that turned his freeze into a blank screen (task 130)")


def check_the_ramp_proves_engagement_precedes_the_first_seek() -> None:
    """The same ramp, this time reading the rate the tick BEFORE the first
    seek: it must already be LIVE_SLOW_RATE, which is only possible if
    degradation began at least LIVE_RATE_DEGRADE_HOLD_MS earlier."""
    checkpoints = json.dumps(RAMP_CHECKPOINTS)
    out = _run(f"""
const checkpoints = {checkpoints};
const totalMs = {RAMP_TOTAL_MS};
const stepMs = {RAMP_STEP_MS};
const segMs = totalMs / (checkpoints.length - 1);

let state = {{ rate: 1, degradedSince: 0, lastFixAt: 0 }};
let now = 0;
const rateBefore = [];
let firstSeekAt = -1;

for (let seg = 0; seg < checkpoints.length - 1 && firstSeekAt === -1; seg++) {{
  const a = checkpoints[seg], b = checkpoints[seg + 1];
  for (let t = 0; t < segMs && firstSeekAt === -1; t += stepMs) {{
    now += stepMs;
    const behind = a + (b - a) * (t / segMs);
    const act = liveAction(behind, {MAX_BEHIND_S}, {STARVED_S});
    const rateThisTick = state.rate;
    const reg = liveRegulate({{ behind, now, starved: act === 'starved',
      rate: state.rate, degradedSince: state.degradedSince, lastFixAt: state.lastFixAt }});
    if (reg.seek) {{
      firstSeekAt = now;
      console.log(JSON.stringify({{ rateBeforeThisCall: rateThisTick }}));
    }}
    state.rate = reg.rate;
    state.degradedSince = reg.degradedSince;
  }}
}}
if (firstSeekAt === -1) console.log(JSON.stringify({{ rateBeforeThisCall: null }}));
""")
    if out["rateBeforeThisCall"] is None:
        fail("no seek ever fired across the ramp — cannot prove engagement "
             "order (see the sibling ramp check for why a seek must fire)")
    if out["rateBeforeThisCall"] != 0.97:
        fail("the rate was NOT already slowed on the tick before the first "
             f"seek fired: {out!r} — the regulator must engage strictly "
             "before any flush, never on the same call")


# ═══════════════════════════ THE WIRING ═══════════════════════════
def check_render_js_actually_calls_the_module() -> None:
    """A pure function nobody calls is a feature that does not exist (the
    actions.json lesson, 2026-08-07). render.js's applyLiveDecision — the one
    place both call sites (onMseUpdateEnd, unfreezeIfStarved) funnel through
    — must run all three exported functions."""
    src = RENDER.read_text(encoding="utf-8")
    m = re.search(r"function applyLiveDecision\([^)]*\)\s*\{(.*?)\n\}", src, re.S)
    if not m:
        fail("applyLiveDecision() left client/render.js — the gate cannot "
             "find the wiring it must prove")
    body = m.group(1)
    for needed in ("liveAction(", "liveRegulate(", "liveSeekTarget("):
        if needed not in body:
            fail(f"applyLiveDecision() no longer calls {needed!r} — the "
                 "mechanism would be dead code that looks alive")
    for site in ("onMseUpdateEnd", "unfreezeIfStarved"):
        m2 = re.search(rf"function {site}\([^)]*\)\s*\{{(.*?)\n\}}", src, re.S)
        if not m2 or "applyLiveDecision(" not in m2.group(1):
            fail(f"{site}() no longer runs applyLiveDecision() — the two "
                 "call sites this mechanism needs would drift apart again "
                 "(exactly the class of bug this whole file exists to catch)")


def check_the_never_blank_guard_is_still_wired_to_readystate() -> None:
    """The 0.0.373 half of this build: redraw() must still skip the clear
    when the decoder has nothing AND a real frame was drawn before."""
    src = RENDER.read_text(encoding="utf-8")
    m = re.search(r"function redraw\(\)\s*\{(.*?)\n\}", src, re.S)
    if not m:
        fail("redraw() left client/render.js")
    body = m.group(1)
    if "everDrew" not in body or "readyState < 2" not in body:
        fail("redraw() no longer skips the clear on a starved decoder once "
             "a real frame has been drawn — the never-blank guard is gone "
             "again (the exact regression 581244b's revert caused)")
    if "everDrew = true" not in src:
        fail("nothing in render.js ever sets everDrew — the guard would "
             "clear to the background colour on the very first gap")


def check_the_page_loads_the_module_before_render() -> None:
    html = INDEX.read_text(encoding="utf-8")
    live = html.find("/static/live-clock.js")
    render = html.find("/static/render.js")
    if live == -1:
        fail("index.html never loads live-clock.js")
    if not -1 < live < render:
        fail("live-clock.js must load BEFORE render.js — applyLiveDecision "
             "calls it")


def check_the_module_stays_pure() -> None:
    """This gate runs the module WHOLE in node — possible only while it
    touches no DOM, no socket, no bridge, no video element (the caret.js
    rule)."""
    code = "\n".join(ln for ln in MODULE.read_text(encoding="utf-8").splitlines()
                     if not ln.lstrip().startswith(("//", "*", "/*")))
    for banned in ("document", "window.", "video.", "send(", "Android", "fetch("):
        if banned in code:
            fail(f"client/live-clock.js reaches for {banned!r} — it is no "
                 "longer pure and this gate can no longer prove it")


def check_state_js_carries_the_thresholds_this_module_is_fed() -> None:
    """LIVE_TARGET_BEHIND_S / LIVE_STARVED_S / LIVE_UNFREEZE_TICK_MS stay in
    client/state.js (shared with reportLiveDrift's log line) — this gate
    pins that render.js is really feeding the module real numbers, not
    literals that quietly drifted from state.js."""
    text = STATE.read_text(encoding="utf-8")
    m = re.search(r"const LIVE_TARGET_BEHIND_S = ([\d.]+);", text)
    if not m:
        fail("LIVE_TARGET_BEHIND_S is no longer a named constant in state.js")
    if float(m.group(1)) < 0.3:
        fail(f"LIVE_TARGET_BEHIND_S = {m.group(1)} lands with under 0.3s of "
             "headroom — his log showed 0.1s (six frames at 60fps) turning "
             "one late chunk into a starved player")
    if "const LIVE_STARVED_S = " not in text:
        fail("LIVE_STARVED_S left client/state.js — liveAction has nothing "
             "to classify a starve against")
    if "const LIVE_UNFREEZE_TICK_MS = " not in text:
        fail("LIVE_UNFREEZE_TICK_MS left client/state.js — the "
             "waiting/stalled backstop tick would have no interval")


def check_the_min_gap_is_named_and_exactly_4000ms() -> None:
    """rules/CODE.md: no magic numbers — and this one is pinned to an exact
    value by the plan this build implements (never more than one flush per
    4000ms), so it is checked as a literal rather than a range."""
    text = MODULE.read_text(encoding="utf-8")
    m = re.search(r"const LIVE_UNFREEZE_MIN_GAP_MS = (\d+);", text)
    if not m:
        fail("LIVE_UNFREEZE_MIN_GAP_MS is no longer a named constant in "
             "live-clock.js")
    if int(m.group(1)) != 4000:
        fail(f"LIVE_UNFREEZE_MIN_GAP_MS = {m.group(1)}, the task pins this "
             "at exactly 4000")


CHECKS = [
    ("the truth table matches his six cases",
     check_the_truth_table_matches_his_six_cases),
    ("a seek target never lands before the buffer's own start",
     check_seek_target_never_lands_before_the_buffer_starts),
    ("the regulator engages before any flush is permitted",
     check_the_regulator_engages_before_any_flush_is_permitted),
    ("a backward seek never fires more than once per 4s (permanent starve)",
     check_backward_seek_never_fires_more_than_once_per_4s),
    ("the rate recovers once behind climbs back above the threshold",
     check_rate_recovers_once_behind_climbs_back_above_the_threshold),
    ("the hysteresis band holds whatever was decided before",
     check_the_hysteresis_band_holds_whatever_was_decided_before),
    ("the realistic ramp from his own log: starved, caught, rate-limited",
     check_the_realistic_ramp_from_his_own_log),
    ("the ramp proves engagement precedes the first seek",
     check_the_ramp_proves_engagement_precedes_the_first_seek),
    ("render.js actually calls the module (both call sites)",
     check_render_js_actually_calls_the_module),
    ("the never-blank guard is still wired to readyState",
     check_the_never_blank_guard_is_still_wired_to_readystate),
    ("the page loads the module before render.js",
     check_the_page_loads_the_module_before_render),
    ("the module stays pure, so this gate can run it whole",
     check_the_module_stays_pure),
    ("state.js carries the thresholds this module is fed",
     check_state_js_carries_the_thresholds_this_module_is_fed),
    ("the min gap is named and exactly 4000ms",
     check_the_min_gap_is_named_and_exactly_4000ms),
]


def main() -> int:
    print("\n=== LIVE CLOCK GATE ===")
    if shutil.which("node") is None:
        print("LIVE CLOCK GATE FAILED — node is required (it runs the REAL "
              "client/live-clock.js rules) and is not on PATH. Never skip a "
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
        print(f"\nLIVE CLOCK GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nLIVE CLOCK GATE PASSED — the picture never goes blank, and "
          "when it stops it starts again by itself.")
    return 0


def test_live_clock():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
