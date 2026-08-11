// THE LIVE-EDGE CLOCK — one mechanism, task 151 (2026-08-10), after the
// 0.0.367 fix and the 0.0.373 blue-screen fix both went back on 0.0.375 for
// shipping three streaming changes in one window (his rule: fix one thing at
// a time and report what happened, because nothing can be attributed while
// three things move at once). All three return here together, as the
// owner's own build-order rule demands, because they are ONE idea: a
// starved player is caught, it is slowed BEFORE it is ever flushed, and a
// flush that must still happen is rate-limited so recovering from a freeze
// can never itself become the blue screen.
//
// Pure by design — no DOM, no socket, no video element (the caret.js /
// voice.js / view-anchor.js pattern) — so tests/test_live_clock.py can drive
// the WHOLE mechanism in node against a realistic drift ramp instead of
// asserting on a `<video>` element's mood. render.js owns every side effect
// (video.currentTime, video.playbackRate); this file only ever answers
// questions.
//
// ── THE PROBLEM, from his own log (task 122) ────────────────────────────
//
//   [live] behind=0.48s  0.47  0.47  0.49  0.02        healthy, riding the
//   [live] behind=-1.68s -4.08 -6.10 -8.44 -10.51        0.5 s threshold
//   [live] behind=-11.09 -11.09 -11.10 -11.10 -11.10   FROZEN, two minutes
//   [live] behind=0.26s                                only a session reset
//                                                        brought it back
//
// `behind` is `buffered.end - currentTime`: NEGATIVE means the player's own
// clock has run PAST the data it has, which is a starved decoder, not merely
// a late one. The single rule that shipped for months (`behind > 0.5s ->
// seek`) never matched a negative number, so the freeze was permanent by
// construction until the whole H.264 session was torn down and rebuilt.
//
// ── AND THE CURE MUST NOT BECOME THE DISEASE (task 130, his live report) ──
//
// A seek FLUSHES the decoder. The 0.0.367 fix recovered from a starve by
// seeking straight back to the live edge, and on a link that genuinely
// cannot sustain the setting (4K/60fps/20Mbps — ~3 GB/s of raw pixels, more
// than this pipeline can carry) that fired every second: the picture that
// was merely late was never shown at all, and "frozen" became "blank" —
// worse, not better. His report, live, that night: the picture disappears
// and a generic blue screen takes its place (lang-ok: owner report,
// paraphrased into English here — see commit 3b7b477 for his exact words).
//
// So a flush is now the LAST resort, never the first response:
//
//   1. SLOW DOWN. A starved player first gets `playbackRate` dropped to
//      LIVE_SLOW_RATE — letting the buffer refill under normal playback,
//      no decoder disruption at all. This is silent and reversible, and it
//      alone recovers an ordinary hiccup.
//   2. ONLY IF THAT DOES NOT RECOVER IT for LIVE_RATE_DEGRADE_HOLD_MS does a
//      backward seek become eligible at all.
//   3. AND EVEN THEN, at most one seek per LIVE_UNFREEZE_MIN_GAP_MS — a
//      pipeline that is genuinely starving must be allowed to STUTTER, never
//      forced back to blank by a seek fired every tick.
//
// render.js's never-blank redraw() guard is the backstop for what these
// three steps cannot close in time: the picture stops instead of vanishing,
// which is the owner's own promise for this build — it never goes blank,
// and when it stops it starts again by itself.
"use strict";

// The playbackRate a starved player is slowed to while it tries to recover
// on its own. Close enough to 1 that it is not itself perceptible as a
// stutter, far enough that the buffer visibly refills over a couple of
// seconds rather than never.
const LIVE_SLOW_RATE = 0.97;

// `behind` must climb back above this before the rate returns to normal.
// Not zero: a threshold sitting exactly where the slowdown engages would let
// the rate flap on every sample while the drift hovers near it. 0.3s is
// comfortably short of LIVE_TARGET_BEHIND_S (0.45, client/state.js) — the
// landing point a catch-up aims for — so "recovered" and "the ordinary
// healthy value" are not the same instant.
const LIVE_RATE_RECOVER_S = 0.3;

// A starve must survive the slowdown for this long, unrecovered, before a
// backward seek is even considered. This is what makes step 1 REAL rather
// than a formality the code walks through on its way to a flush anyway —
// most starves are short enough that the buffer refills inside this window
// and no seek ever fires.
const LIVE_RATE_DEGRADE_HOLD_MS = 2000;

// No more than one backward seek in this many ms, however often a starve is
// still being reported. A seek flushes the decoder; on a link that genuinely
// cannot keep up, seeking every tick is how a freeze becomes a blank screen
// (task 130, his live report the same night as the fix that caused it).
const LIVE_UNFREEZE_MIN_GAP_MS = 4000;

// ── THE FORWARD CATCH-UP IS A FLUSH TOO (task 216, his report 2026-08-11) ──
//
// Everything above governs the BACKWARD (rescue) seek. The ordinary forward
// catch-up — "I am more than half a second late, jump to the live edge" —
// carried no budget at all, on the reasoning that it was never what caused
// the blue screen. His own telemetry that morning says otherwise about its
// FREQUENCY: `jumps=36 starves=2 in 15s` while he dictated, with `jumps=0`
// in every neighbouring window. `jumps` counts exactly this seek. Dictation
// types word by word, so the PC screen changes in bursts, the frame-count
// media clock swings across the 0.5s threshold on nearly every sample, and
// the player was flushed ~2.4 times a second for fifteen seconds.
//
// A decoder flushed that often is a decoder that is almost never holding a
// paintable frame, which is what makes every OTHER gap in the pipeline
// visible. So the catch-up gets the same two teeth the rescue seek has, one
// notch shorter (it answers a real, ordinary lag and must not become a
// permanent drift):
//
//   HYSTERESIS — the lateness must have SURVIVED LIVE_JUMP_HOLD_MS. A single
//                burst-shaped sample crossing the line is jitter, not lag.
//   SPACING    — and at most one jump per LIVE_JUMP_MIN_GAP_MS.
//
// Cost, stated honestly: up to LIVE_JUMP_MIN_GAP_MS of extra latency before a
// genuine lag is corrected. His peak that morning was 0.52s behind, so the
// picture stays under a second late while the flush count falls from ~36 in
// 15s to at most 10.
const LIVE_JUMP_HOLD_MS = 400;
const LIVE_JUMP_MIN_GAP_MS = 1500;

/** THE TRUTH TABLE. `behind` is `buffered.end - currentTime`; `maxBehindS`
 *  and `starvedS` are the caller's own thresholds (client/state.js
 *  `LIVE_MAX_BEHIND_S` / `LIVE_STARVED_S`) — passed in, never read off a
 *  global, so this stays provable in isolation:
 *
 *    "live"         — do nothing, the drift is ordinary jitter
 *    "seek_forward" — too far BEHIND the live edge (jank, a slow link that
 *                     is otherwise healthy) — jump ahead, unconditionally;
 *                     this is the ordinary catch-up and predates task 122
 *    "starved"      — the clock has run PAST the data it has (behind is
 *                     very negative) — the freeze. NEVER answered by an
 *                     immediate seek here; see `liveRegulate`.
 */
function liveAction(behind, maxBehindS, starvedS) {
  if (behind < starvedS) return "starved";
  if (behind > maxBehindS) return "seek_forward";
  return "live";
}

/** Where a catch-up (forward OR the eventual starve recovery) lands: never
 *  past the start of what is actually buffered — a starve so deep that
 *  `end - targetBehindS` would land before the buffer even begins must clamp
 *  to the buffer's own start, or the "recovery" seek would itself throw. */
function liveSeekTarget(bufferStart, bufferEnd, targetBehindS) {
  return Math.max(bufferStart, bufferEnd - targetBehindS);
}

/** THE REGULATOR. Decides the playbackRate to apply THIS call and whether a
 *  rescue (backward) seek is due — the slow-down-before-flush order from the
 *  file header, expressed as one pure step so it can never drift between the
 *  two call sites that need it (`onMseUpdateEnd`, `unfreezeIfStarved`).
 *
 *  Keeps no state of its own — the caller carries `rate`/`degradedSince`/
 *  `lastFixAt` across calls and feeds them back in, which is what makes a
 *  fresh node interpreter reproduce this exactly, call for call, the way a
 *  real session would run it:
 *
 *    behind        — buffered.end - currentTime, THIS call
 *    now           — performance.now(), THIS call
 *    starved       — liveAction(...) === "starved" for this same `behind`
 *    rate          — the playbackRate currently applied (1 or LIVE_SLOW_RATE)
 *    degradedSince — ms timestamp the rate last dropped to LIVE_SLOW_RATE,
 *                    or 0 while it is currently 1 — the caller's memory of
 *                    step 1, fed back so degradation duration survives calls
 *    lastFixAt     — ms timestamp of the last backward seek, or 0 if none
 *                    fired yet this session — the rate-limit's memory
 *
 *  Returns { rate, degradedSince, seek } — `rate`/`degradedSince` are the
 *  caller's next-call memory; `seek` true means a rescue seek is due RIGHT
 *  NOW (the caller performs it and then sets its own `lastFixAt = now`). */
function liveRegulate({ behind, now, starved, rate, degradedSince, lastFixAt }) {
  let nextRate = rate;
  let nextDegradedSince = degradedSince;

  if (behind < 0) {
    // STEP 1: slow down THE MOMENT the drift turns negative — before a
    // starve has even had time to be classified as one. This is the
    // "engages before any flush is permitted" rule: degradation always
    // starts accruing well before LIVE_RATE_DEGRADE_HOLD_MS could ever let a
    // seek through.
    if (!nextDegradedSince) nextDegradedSince = now;
    nextRate = LIVE_SLOW_RATE;
  } else if (behind > LIVE_RATE_RECOVER_S) {
    nextRate = 1;
    nextDegradedSince = 0;
  }
  // Between 0 and LIVE_RATE_RECOVER_S: a hysteresis band. Neither edge is
  // crossed, so whatever the previous call decided holds — flapping the
  // rate once a second while the drift hovers near zero would itself be a
  // stutter, the exact thing step 1 exists to avoid.

  const heldLongEnough = nextDegradedSince > 0 &&
    (now - nextDegradedSince) >= LIVE_RATE_DEGRADE_HOLD_MS;
  const gapOk = lastFixAt === 0 || (now - lastFixAt) >= LIVE_UNFREEZE_MIN_GAP_MS;
  const seek = Boolean(starved) && heldLongEnough && gapOk;

  return { rate: nextRate, degradedSince: nextDegradedSince, seek };
}

/** THE CATCH-UP'S OWN BUDGET — whether the ordinary forward jump to the live
 *  edge may fire THIS call. Same shape as `liveRegulate` and for the same
 *  reason: no state of its own, the caller carries the memory and feeds it
 *  back, so a node interpreter reproduces a whole session call for call.
 *
 *    late        — liveAction(...) === "seek_forward" for this same `behind`
 *    now         — performance.now(), THIS call
 *    lateSince   — ms timestamp the current lateness EPISODE began, or 0
 *    lastLateAt  — ms timestamp of the most recent late sample, or 0
 *    lastJumpAt  — ms timestamp of the last forward jump, or 0 if none yet
 *
 *  Returns { lateSince, lastLateAt, jump }.
 *
 *  THE EPISODE ENDS ON A HEALTHY STRETCH, NOT ON ONE HEALTHY SAMPLE — and
 *  this gate's own burst-pattern check is what forced that (the first
 *  version cleared `lateSince` on any non-late sample, and against a drift
 *  shaped like his — late 300ms, clear 100ms, endlessly — it then never
 *  accrued its hold and never caught up AT ALL: a picture drifting further
 *  behind forever, traded for a flash. Damping must space the flushes, never
 *  abolish them). So the clock survives a dip and is cleared only once the
 *  drift has been healthy for LIVE_JUMP_HOLD_MS — hysteresis in both
 *  directions, off the one constant.
 *
 *  A jump RESETS the episode, so the next one must earn a fresh hold; that
 *  hold runs CONCURRENTLY with the spacing wait, which is why two jumps in a
 *  permanent lag land LIVE_JUMP_MIN_GAP_MS apart and not the sum. */
function liveCatchUp({ late, now, lateSince, lastLateAt, lastJumpAt }) {
  let nextLateSince = lateSince;
  let nextLastLateAt = lastLateAt;
  if (late) {
    if (!nextLateSince) nextLateSince = now;
    nextLastLateAt = now;
  } else if (nextLastLateAt && (now - nextLastLateAt) >= LIVE_JUMP_HOLD_MS) {
    nextLateSince = 0;
    nextLastLateAt = 0;
  }
  const heldLongEnough = nextLateSince > 0 &&
    (now - nextLateSince) >= LIVE_JUMP_HOLD_MS;
  const gapOk = !lastJumpAt || (now - lastJumpAt) >= LIVE_JUMP_MIN_GAP_MS;
  const jump = Boolean(late) && heldLongEnough && gapOk;
  return { lateSince: jump ? 0 : nextLateSince, lastLateAt: nextLastLateAt, jump };
}

/** PAINT-THEN-SWAP: whether the canvas's drawing buffer must be re-sized at
 *  all this call, and whether the pixels on it must be carried across.
 *
 *  THE HOLE THE 2026-08-11 HOLD-FRAME FIX LEFT OPEN, and the one that was
 *  really flashing (task 216). Assigning `canvas.width` / `canvas.height`
 *  RE-INITIALISES the bitmap to transparent black — per the HTML spec, even
 *  when the value assigned is the one already there. render.js's
 *  `updateViewport()` assigned both unconditionally, and it runs on every
 *  window resize, every visualViewport resize AND scroll, and every IME inset
 *  the Android shell pushes (`window.__imeHeight`) — i.e. constantly while he
 *  dictates. That wipe is invisible only because `redraw()` runs at the end of
 *  the same task and paints over it before the browser composites.
 *
 *  Then `liveHoldFrame` gave `redraw()` permission to paint NOTHING. Every
 *  overlap of "the shell pushed an inset" with "a seek is in flight" — and
 *  with 36 seeks in 15s that is most of them — left a transparent canvas
 *  standing for a frame, and a transparent canvas shows the page's own
 *  background colour: his blue flash. The guard did not fail to cover the
 *  wipe; the guard is what made the wipe visible.
 *
 *  The rule, therefore, is that nothing may clear before a new picture
 *  exists: don't resize when the size did not change, and when it genuinely
 *  did, carry the old pixels over the seam. */
function liveResizePlan({ width, height, nextWidth, nextHeight, everDrew }) {
  const resize = width !== nextWidth || height !== nextHeight;
  return { resize, preserve: resize && Boolean(everDrew) };
}

/** THE NEVER-BLANK GUARD'S OWN TRUTH TABLE — whether redraw() must HOLD the
 *  last picture (clear nothing, draw nothing) this frame.
 *
 *  `seeking` joined `readyState` on 2026-08-11, from the owner's first night
 *  on v0.0.105: blue FLASHES while he dictates. His log names the state —
 *  00:37–00:39, `jumps=41 starves=3 in 15s`, where every other session reads
 *  `jumps=0` — word-by-word dictation paints the PC screen in bursts, the
 *  frame-count media clock swings between starved and too-late, and the
 *  regulator seeks ~3×/s. Assigning currentTime raises the element's
 *  `seeking` flag synchronously, but readyState can still read
 *  HAVE_CURRENT_DATA while the flushed decoder has no frame to paint — so
 *  the old readyState-only guard let the clear land and drawImage() then
 *  silently painted nothing: one background-coloured frame per unlucky
 *  seek, exactly the "bljesak" he reported.
 *
 *  everDrew=false is never held: a fresh session SHOULD paint the page
 *  colour until its first frame — holding there would show stale pixels
 *  from the previous stream. JPEG mode paints bitmaps and has no decoder
 *  state to go empty — never held. */
function liveHoldFrame({ mode, readyState, seeking, everDrew }) {
  if (mode !== "h264" || !everDrew) return false;
  return Boolean(seeking) || readyState < 2;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    liveAction, liveSeekTarget, liveRegulate, liveCatchUp, liveResizePlan,
    liveHoldFrame,
    LIVE_SLOW_RATE, LIVE_RATE_RECOVER_S, LIVE_RATE_DEGRADE_HOLD_MS,
    LIVE_UNFREEZE_MIN_GAP_MS, LIVE_JUMP_HOLD_MS, LIVE_JUMP_MIN_GAP_MS,
  };
}
