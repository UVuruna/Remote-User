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

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    liveAction, liveSeekTarget, liveRegulate,
    LIVE_SLOW_RATE, LIVE_RATE_RECOVER_S, LIVE_RATE_DEGRADE_HOLD_MS,
    LIVE_UNFREEZE_MIN_GAP_MS,
  };
}
