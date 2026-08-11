# Live Clock — the picture never goes blank, and when it stops it starts again by itself

**Script:** [Live Clock (script)](../live-clock.js) · **Flow:** [Live Clock (flow)](../__flow/live-clock.md)

## Purpose

The live-edge decision table (`liveAction`) plus the slow-before-flush
playbackRate regulator (`liveRegulate`) that recovers a starved H.264 player
without ever flushing the decoder often enough to turn a freeze into a blank
screen. Task 151 (2026-08-10) — the owner's own promise for this build.

## Why it exists — two earlier fixes for the SAME bug, both reverted the same night

His log (task 122, 2026-08-09) named the freeze exactly: `behind` (the MSE
live-edge drift, `buffered.end - currentTime`) went negative and pinned at
-11 s for two solid minutes. Two fixes followed, and both went back out on
0.0.375 (commit 581244b) because they shipped together and nothing could be
attributed:

| Commit | What it did | What broke |
|---|---|---|
| a9db36b (0.0.367) | Caught the starve, seeking straight back to the live edge | The seek FLUSHES the decoder; on a link that cannot keep up (4K/60fps/20Mbps) it fired every second — his report the same night, in translation: the screen disappears and a generic blue picture takes its place |
| 3b7b477 (0.0.373) | Rate-limited the flush to once per 4s + a never-blank canvas guard | Landed beside two OTHER streaming changes (I420 pixel format, the same starve fix) in one window — his instruction, in translation: fix things one at a time and report what happens |
| 581244b (0.0.375) | Reverted ALL of it, including the parts that were right | The freeze came back, deliberately — better than a screen he could not use |

This build returns the mechanism as **ONE deliberate change**, in its own
build, exactly as the owner's revert instruction required.

## The mechanism — three steps, a flush is the LAST resort

1. **SLOW DOWN.** The moment `behind` goes negative, `liveRegulate` drops
   `playbackRate` to `LIVE_SLOW_RATE` (0.97) — letting the buffer refill under
   ordinary playback, no decoder disruption at all. This alone recovers most
   ordinary hiccups.
2. **ONLY IF THAT DOES NOT RECOVER IT** for `LIVE_RATE_DEGRADE_HOLD_MS` (2s)
   does a backward (rescue) seek become eligible at all — never on the same
   call that degradation started.
3. **AND EVEN THEN**, no more than one seek per `LIVE_UNFREEZE_MIN_GAP_MS`
   (4000ms), however often the starve keeps being reported — the exact rule
   3b7b477 introduced and 581244b withdrew along with everything else.

[Render](render.md)'s never-blank `redraw()` guard (`everDrew`) is the
backstop for whatever these three steps cannot close in time: the picture
stops instead of vanishing.

## Key Functions

- `liveAction(behind, maxBehindS, starvedS)` — the truth table: `"live"` (do
  nothing), `"seek_forward"` (`behind > maxBehindS` — ordinary catch-up, jump
  ahead unconditionally, predates task 122), `"starved"` (`behind < starvedS`
  — the freeze; NEVER answered by an immediate seek here). Takes its
  thresholds as parameters (`LIVE_MAX_BEHIND_S` / `LIVE_STARVED_S`,
  [State](state.md)) rather than reading a global, so it stays provable in
  isolation.
- `liveSeekTarget(bufferStart, bufferEnd, targetBehindS)` — where a catch-up
  lands: `end - target`, clamped to never land before the buffer's own start
  (a starve deep enough to underflow that would throw a real
  `InvalidStateError` on `video.currentTime =`).
- `liveRegulate({behind, now, starved, rate, degradedSince, lastFixAt})` —
  the regulator. Keeps no state of its own; the caller
  ([Render](render.md)'s `applyLiveDecision`) carries `rate` / `degradedSince`
  / `lastFixAt` across calls and feeds them back in, which is what makes a
  fresh node interpreter reproduce it exactly, call for call — the property
  `tests/test_live_clock.py` depends on to drive a multi-minute drift ramp.
  Returns `{rate, degradedSince, seek}`.
- `liveHoldFrame({mode, readyState, seeking, everDrew})` — the never-blank
  guard's own truth table (added 2026-08-11, his first night on v0.0.105):
  whether `redraw()` must HOLD the last picture this frame — clear nothing,
  draw nothing. `seeking` is the column his blue flashes forced in: while he
  dictated, the regulator's own catch-up seeks fired ~3×/s (`jumps=41
  starves=3 in 15s` in his log, against `jumps=0` everywhere else — dictation
  types word by word, so the PC screen changes in bursts and the frame-count
  media clock swings), and assigning `currentTime` raises the element's
  `seeking` flag synchronously while `readyState` can still read
  HAVE_CURRENT_DATA with no paintable frame — so the old readyState-only
  guard let the clear land and `drawImage()` silently painted nothing: one
  background-coloured frame per unlucky seek. Holds on `seeking ||
  readyState < 2`, never before the session's first frame (a fresh canvas is
  correct there — holding would show the PREVIOUS stream's pixels), never in
  JPEG mode (bitmaps, no decoder state).
- `liveCatchUp({late, now, lateSince, lastLateAt, lastJumpAt})` — the FORWARD
  catch-up's own budget (task 216, 2026-08-11). Same shape and same memory
  discipline as `liveRegulate`. Returns `{lateSince, lastLateAt, jump}`.
- `liveResizePlan({width, height, nextWidth, nextHeight, everDrew})` — whether
  the canvas's drawing buffer may be re-initialised at all this call, and
  whether the pixels on it must be carried across. Returns
  `{resize, preserve}`.

## Task 216 — the hole the hold-frame fix left open, and the thrash under it

His report of 2026-08-11 ~10:12: the blue flash SURVIVED v0.0.106, which
already carried `liveHoldFrame`. Two things were wrong, and only one of them
is a streaming problem.

**1. The clear that was never behind the guard.** Assigning
`canvas.width` / `canvas.height` re-initialises the drawing buffer to
transparent black — per the HTML spec, EVEN when the value assigned is the
one already there. [Render](render.md)'s `updateViewport()` assigned both
unconditionally, and it runs on every window resize, every `visualViewport`
resize AND scroll, and on every IME inset the Android shell pushes
(`window.__imeHeight`) — i.e. constantly while he dictates. That wipe was
invisible for as long as `redraw()` repainted inside the same task, before
the browser composited. `liveHoldFrame` then gave `redraw()` permission to
paint NOTHING, and every overlap of an inset push with a seek in flight left
a transparent canvas standing for one composited frame — which shows the
page's own background colour. **The guard did not fail to cover the wipe; the
guard is what made the wipe visible.** `liveResizePlan` is the rule that
closes it: never clear unless a new picture is provably about to exist — no
resize when the size did not change, and the old pixels carried over the seam
when it genuinely did.

**2. The frequency that made every gap visible.** His 10:11:55 telemetry:
`jumps=36 starves=2 in 15s`, with `jumps=0` in every neighbouring window.
`jumps` counts the FORWARD catch-up, which carried no budget at all — the
reasoning being that it was never what caused the blue screen. Dictation
types word by word, the PC screen changes in bursts, the frame-count media
clock swings across `LIVE_MAX_BEHIND_S` on nearly every sample, and the
decoder was flushed ~2.4 times a second. `liveCatchUp` gives it the same two
teeth the rescue seek has, one notch shorter: the lateness must have survived
`LIVE_JUMP_HOLD_MS` (400ms) and at most one jump per `LIVE_JUMP_MIN_GAP_MS`
(1500ms) — ~36 in 15s becomes at most 10.

**The episode ends on a healthy STRETCH, not on one healthy sample**, and
this gate's own burst check is what forced that. The first version cleared
`lateSince` on any non-late sample; against a drift shaped like his (late
300ms, clear 100ms, endlessly) it then never accrued its hold and never
caught up AT ALL — a picture drifting further behind forever, traded for a
flash. Damping must SPACE the flushes, never abolish them.

## Design Decisions

- **Pure by design** (no DOM, no socket, no video element — the
  [Caret](caret.md) / [Voice](voice.md) / [View Anchor](view-anchor.md)
  pattern): the gate runs the WHOLE mechanism in node against a realistic
  drift ramp taken from his own server log, rather than asserting on a
  `<video>` element's mood.
- **The regulator engages structurally before any flush is permitted.**
  `heldLongEnough` requires `now - degradedSince >= LIVE_RATE_DEGRADE_HOLD_MS`,
  and `degradedSince` is set to `now` on the FIRST negative-drift call — so a
  seek can never fire on the same call that degradation began. This is
  proven, not merely asserted: the gate reads the rate on the tick
  immediately before the first seek and requires it already be
  `LIVE_SLOW_RATE`.
- **A hysteresis band (0 to `LIVE_RATE_RECOVER_S`) holds whatever the
  previous call decided.** A threshold sitting exactly where the slowdown
  engages would let the rate flap once a tick while the drift hovers near
  zero — the exact class of stutter step 1 exists to avoid.
- **`liveAction`'s thresholds live in [State](state.md), not here.**
  `LIVE_MAX_BEHIND_S` / `LIVE_STARVED_S` are shared with `reportLiveDrift`'s
  log line, so a single source of truth feeds both the decision and the
  evidence a session's own server log carries. This module owns only the
  regulator's OWN numbers (`LIVE_SLOW_RATE`, `LIVE_RATE_RECOVER_S`,
  `LIVE_RATE_DEGRADE_HOLD_MS`, `LIVE_UNFREEZE_MIN_GAP_MS`,
  `LIVE_JUMP_HOLD_MS`, `LIVE_JUMP_MIN_GAP_MS`), which nothing outside it
  reads.
- **The cost of task 216's damping is stated, not hidden**: up to
  `LIVE_JUMP_MIN_GAP_MS` of extra latency before a genuine lag is corrected.
  His peak that morning was 0.52s behind, so the picture stays under a second
  late while the flush count falls by ~3.6×.
- **`liveResizePlan` lives HERE and not in render.js** even though it is
  about a canvas: it is the same rule as `liveHoldFrame` — when may pixels be
  thrown away — and the gate can only drive it whole while it stays pure.
  render.js owns the side effects (`keepCanvasPixels` / `restoreCanvasPixels`,
  the actual `canvas.width =`), exactly as it owns `video.currentTime`.
- **One decision function, two call sites, never two copies of the rule.**
  [Render](render.md)'s `applyLiveDecision` is the single place that runs
  `liveAction`/`liveRegulate`/`liveSeekTarget` and performs the side effects
  they decide on; both `onMseUpdateEnd` (fires on every MSE chunk) and
  `unfreezeIfStarved` (the `waiting`/`stalled` events plus a 1s backstop
  tick, for a stall that arrives with no append at all) call through it, so
  the rate/flush budget can never drift between them the way separate copies
  did before.

## Honest limit

Only a real device on a link that genuinely cannot sustain the chosen
setting proves the FEEL of this — the ramp gate proves the mechanism's
timing guarantees (caught, rate-limited, engagement order) against his own
recorded numbers, not what 60fps/20Mbps actually looks like in his hand.

## Used by

- [Render](render.md) — `applyLiveDecision`, called from `onMseUpdateEnd` and
  `unfreezeIfStarved`
- `tests/test_live_clock.py` — the gate, fail-closed in `setup/build.py`
  (0y/6)
- `tests/_audit_js.py` (`LIVE_CLOCK_BLANK_JS`, `LIVE_CLOCK_DRIFT_JS`) — the
  live-page half of the proof, driven by `tests/test_layout_audit.py`
