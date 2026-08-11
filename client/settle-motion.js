// THE MOTION METRIC the loading cube's settle watcher judges the streamed
// picture by — split out of client/loading.js on 2026-08-11 (task 194) so it
// can be a genuinely PURE module (no DOM, no canvas, no socket — the
// view-anchor.js / cursor-shapes.js pattern) and this gate can run it whole
// in node with synthetic frames instead of only ever exercising it live on
// a real device.
//
// TASK 194 — "traje predugo ... radi kontra uslugu" (it takes too long, it
// works against him). The OLD metric (in loading.js, before this split) was
// a whole-thumbnail MEAN of |Δr|+|Δg|+|Δb| per sample, and only counted a
// "still" hit once that mean fell under a fixed threshold. A blinking caret
// is a tiny patch and washes out in a mean over 2,304 samples (a 64x36
// thumbnail) — but his agents actively typing/scrolling inside a member
// window is real, LOCAL, ongoing motion covering a real share of the
// thumbnail, and it kept the mean above threshold for the ENTIRE watch
// window almost every time. By the time `layout_state` arrives the server
// has ALREADY verified placement (server/window_manager.py wait_landed) —
// this side does not need to prove the windows landed, only that watching
// the raw stream a moment longer would not have looked any better.
//
// So the metric is the FRACTION of pixels that changed past a per-pixel
// noise floor, not the average size of the change: a caret blink or a
// terminal's own cursor is a few percent of the frame and reads as settled,
// while a window actually sliding into place changes a large share of it
// and still does not. See client/loading.js's settleTick()/SETTLE_MAX_MS for
// the other half of the fix (the hard cap shortened to a real "a few
// seconds") and client/connection.js's excursion-restore branch for the
// "misses places it should cover" half.
"use strict";

// A pixel counts as "changed" past this per-pixel RGB delta sum.
const CHANGE_PIXEL_DIFF = 18;
// Below this fraction of changed pixels the picture is "mostly settled" — a
// MOTION threshold, not absolute stillness.
const SETTLE_MOTION_FRAC = 0.06;

/** Fraction of sampled pixels that changed more than the per-pixel noise
 *  floor between two RGBA sample buffers of equal length. No baseline yet
 *  (`prev` null/undefined, or a size mismatch) is never "settled" — there is
 *  nothing to compare against, so this reads as still moving. */
function changedFraction(data, prev) {
  if (!prev || data.length !== prev.length) return 1;
  let changed = 0;
  const pixels = data.length / 4;
  for (let i = 0; i < data.length; i += 4) {
    const d = Math.abs(data[i] - prev[i]) +
              Math.abs(data[i + 1] - prev[i + 1]) +
              Math.abs(data[i + 2] - prev[i + 2]);
    if (d > CHANGE_PIXEL_DIFF) changed++;
  }
  return pixels ? changed / pixels : 0;
}

/** True once the changed-pixel fraction is small enough to call the picture
 *  settled — MOSTLY still, on purpose (see the header above), never
 *  perfectly still. */
function isSettled(frac) {
  return frac < SETTLE_MOTION_FRAC;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { changedFraction, isSettled, CHANGE_PIXEL_DIFF, SETTLE_MOTION_FRAC };
}
