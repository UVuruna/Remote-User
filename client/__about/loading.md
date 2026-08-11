# Loading (phone) — the cube, and when it may leave

[← client](../___client.md) · code: [loading.js](../loading.js) · flow: [__flow/loading.md](../__flow/loading.md)

The opaque overlay that covers every second in which the PC is actually moving
windows, and the watcher that decides when it may go. Split out of
[Layouts](layouts.md) on 2026-08-07 (THE STRUCTURE LAW). A clean seam: this
module knows nothing about layouts — only "work is happening" and "the
streamed picture has stopped moving".

## The rule it exists for (owner 2026-08-03, said more than once)
**The animation lasts as long as the WORK does — not until the server
answers.** `layout_state` only ARMS the watcher (`settleLayLoading`); the
overlay drops when the streamed screen actually stands still, so the user
never watches windows climb out of the taskbar.

- `settleStill()` samples a 64×36 thumbnail of the live frame and compares it
  with the previous sample via `changedFraction()`/`isSettled()` — two PURE
  functions (no DOM, no socket; exported for node like view-anchor.js /
  cursor-shapes.js) that ask what FRACTION of pixels changed, not how big the
  average change is.
- Sampling only STARTS after `SETTLE_CATCHUP_MS`: the encoder and the link run
  a few hundred ms behind the PC, so two identical samples of a STALE picture
  once read as "settled" — the cube left and the frames showing the windows
  rising arrived right after it.
- **Task 194** ("traje predugo ... radi kontra uslugu"): the old metric was a
  whole-thumbnail MEAN of |Δ| per channel, which required near-perfect
  stillness — a blinking caret washed out in the mean, but his agents
  actively typing/scrolling in a member window is real, local, ongoing
  motion that kept the mean above threshold for the whole watch window every
  time. `changedFraction()` counts the SHARE of pixels that moved past a
  per-pixel noise floor (`CHANGE_PIXEL_DIFF`); `isSettled()` calls it settled
  below `SETTLE_MOTION_FRAC` (6%) — a MOTION threshold, not absolute
  stillness, since the server has already verified placement
  (`window_manager.wait_landed`) by the time `layout_state` arrives. And
  because even that can stay above threshold on a genuinely busy screen,
  `SETTLE_MAX_MS` is now a real "a few seconds" (2.2 s) rather than the old
  5-second last resort.
- **Task 194, the other half** ("misses places it should cover"): every
  layout operation that moves real PC windows must call `showLayLoading()`
  before sending — `sendLayoutShape`/member-remove/creation/focus all do.
  The one that did not: `client/connection.js`'s excursion-restore path sent
  a corrective `layout_focus` from inside the `layout_state` handler AFTER
  `settleLayLoading()` had already armed against that same INTERIM (still
  desktop) frame — so the watcher could declare the idle picture "settled"
  and hide the cube before the real move even started, leaving the actual
  restore uncovered. Fixed by calling `showLayLoading()` again right after
  that `send()`, re-arming a fresh cycle only the real move's later
  `layout_state` can satisfy.
- `LOADING_MIN_MS` stops a flash; `SETTLE_MAX_MS` and `LOADING_MAX_MS` are the
  two backstops, for a screen that never stills and a server that never answers.
- The cube keeps spinning THROUGH the fade-out — a frozen cube during the fade
  is exactly the stutter the smooth exit is meant to remove. Every showing
  opens on the next cube face (top → left → back → right → front → bottom).

Gate: `tests/test_loading_settle.py` drives `changedFraction`/`isSettled`
whole in node with synthetic frames (local motion tolerated, large-area
motion still caught, no baseline never settles) and statically pins
`SETTLE_MAX_MS` to a real "a few seconds" and the connection.js restore path
to its re-arm — a pure function nobody calls, or a cap silently widened back
out, is a feature that does not exist.

## Used by
- [Layouts](layouts.md) — every creation, focus, reshape and merge
- [Connection](connection.md) — `layout_state` → `settleLayLoading()`,
  `layout_progress` → `cubeNext()`
