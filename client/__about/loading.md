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

## Why it left, and when (task 203)

`hideLayLoading(why)` now takes a reason and hands it to
`noteReturnDone(why)` in [Connection](connection.md) — the last hop of the
return stopwatch, and the one the owner actually watches. `settleTick` passes
`"picture settled"` or `"settle cap"`, because *"the picture stood still"* and
*"we ran out of patience"* are different bugs and only one of them is this
module's fault. The call is guarded on `typeof noteReturnDone === "function"`:
this module is loaded by the audit harness too, with no connection.js in scope.

## The overlay leaves when the work does — at BOTH ends (2026-08-12)

Two changes from the round that measured his loading overlay (median 3,443 ms
per layout return, 1,800 ms of it after the server had already logged the
windows landed):

- **`settleStreamReset()`** — a layout region change now ends the encoder
  session BEFORE `layout_state` goes out (server-side), so a fresh `config`
  lands moments later and the stream this module is judging is REPLACED
  mid-overlay. The watcher is re-armed on that news and waits for the new
  session's own first painted frame (`sessionDrew`, [Render](render.md)) —
  never for a clock, and never for `video.readyState`, which a torn-down
  element can still answer 2 to while showing a FROZEN old picture. A frozen
  picture is exactly what `settleTick` scores as settled, which is how the
  cube would have left over a PC still moving windows. `SETTLE_CATCHUP_MS`
  therefore no longer runs at all on that path; it stays 650 ms for the cases
  with no new session (a focus that does not move the crop, JPEG), where its
  original job — a stale pre-move frame — is unchanged.
- **`LOADING_MIN_MS` is 0.** The owner deleted the floor by name: *"what
  700-millisecond floor? no floor is needed at all ... we must not produce
  this counter-effect where the user waits BECAUSE OF the loading
  animation"*. What it protected — a jarring blink — is bought by the fade
  instead (`LOADING_FADE_MS`, 500 ms, matched in `client/layouts.css`), which
  is allowed where a floor is not because it runs OVER the picture it
  uncovers: he sees the screen progressively through it. The overlay stops
  swallowing taps at the START of that fade (`pointer-events` on the closed
  rule), or it would be the same floor with better manners.

Gate: `tests/test_picture_hold.py` — the real module in node, with a scripted
video element and a planted stale frame.
