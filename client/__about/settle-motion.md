# Settle motion (phone) — is the streamed picture still moving?

[← client](../___client.md) · code: [settle-motion.js](../settle-motion.js) ·
used by: [Loading](loading.md)

The pure MOTION METRIC the loading cube's settle watcher judges the streamed
picture by. Split out of `client/loading.js` on 2026-08-11 (owner report,
task 194) so it can be a genuinely pure module — no DOM, no canvas, no socket
(the view-anchor.js / cursor-shapes.js pattern) — and `tests/test_loading_
settle.py` can run it whole in node with synthetic frames instead of only
ever being exercised live on a real device.

## The rule it exists for (task 194: "traje predugo ... radi kontra uslugu")

The overlay works AGAINST him when it insists on near-perfect stillness. The
OLD metric (before this split) was a whole-thumbnail MEAN of |Δr|+|Δg|+|Δb|
per sample, and only counted a "still" hit once that mean fell under a fixed
threshold. A blinking caret is a tiny patch and washes out in a mean over a
64×36 thumbnail's 2,304 samples — but his agents actively typing or
scrolling inside a member window is real, ongoing, LOCAL motion covering a
real share of the thumbnail, and it kept the mean above threshold for the
entire watch window almost every time. By the time `layout_state` arrives,
the server has ALREADY verified placement (`server/window_manager.py`
`wait_landed`) — this side does not need to prove the windows landed, only
that watching the raw stream a moment longer would not have looked any
better.

- `changedFraction(data, prev)` — the fraction of sampled pixels whose
  per-pixel RGB delta sum exceeds `CHANGE_PIXEL_DIFF` (18). No baseline yet
  (`prev` null, or a size mismatch) always returns `1` — never settled.
- `isSettled(frac)` — true once that fraction is under `SETTLE_MOTION_FRAC`
  (0.06, 6%): a MOTION threshold, not absolute stillness. A caret blink or a
  terminal's own cursor is a few percent of the frame and reads as settled;
  a window actually sliding into place changes a large share of it and still
  does not.

## Used by
- [Loading](loading.md) — `settleStill()` calls both functions each sample
  tick; `client/index.html` loads this module immediately before
  `loading.js` so they are in scope as page globals.

See [Loading](loading.md) for the OTHER half of task 194 (the hard cap
`SETTLE_MAX_MS` shortened to a real "a few seconds", and the excursion-
restore path in `client/connection.js` that was missing its re-arm).
