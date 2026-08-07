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
  with the previous sample.
- Sampling only STARTS after `SETTLE_CATCHUP_MS`: the encoder and the link run
  a few hundred ms behind the PC, so two identical samples of a STALE picture
  once read as "settled" — the cube left and the frames showing the windows
  rising arrived right after it.
- `LOADING_MIN_MS` stops a flash; `SETTLE_MAX_MS` and `LOADING_MAX_MS` are the
  two backstops, for a screen that never stills and a server that never answers.
- The cube keeps spinning THROUGH the fade-out — a frozen cube during the fade
  is exactly the stutter the smooth exit is meant to remove. Every showing
  opens on the next cube face (top → left → back → right → front → bottom).

## Used by
- [Layouts](layouts.md) — every creation, focus, reshape and merge
- [Connection](connection.md) — `layout_state` → `settleLayLoading()`,
  `layout_progress` → `cubeNext()`
