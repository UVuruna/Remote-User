# Live Clock — Flow

**About:** [description](../__about/live-clock.md)

## The two call sites, one decision function

```
sourceBuffer "updateend"          video "waiting" / "stalled"
        │                          + a 1s backstop tick
        ▼                                  ▼
 onMseUpdateEnd()                 unfreezeIfStarved()
        │                                  │
        └───────────────┬──────────────────┘
                         ▼
              applyLiveDecision(behind, now)
                         │
          ┌──────────┬───┴────┬──────────┐
          ▼          ▼        ▼          ▼
    liveAction()  liveRegulate()  liveCatchUp()  liveSeekTarget()
   (truth table)  (rate + rescue  (forward jump   (landing math)
                   flush budget)   budget, 216)
```

## The truth table

```
behind < LIVE_STARVED_S ? ───────────────► "starved"
        │ no                      (the clock ran PAST the data —
        ▼                          his freeze, task 122)
behind > LIVE_MAX_BEHIND_S ? ────────────► "seek_forward"
        │ no                      (merely late — jump ahead,
        ▼                          unconditional, predates 122)
      "live"                              (do nothing)
```

## The regulator — three steps, in order, a flush is the LAST resort

```
behind < 0 ?
   │ yes ──► degradedSince ||= now      (STEP 1: engage — before a
   │         rate = LIVE_SLOW_RATE       starve is even classified)
   │ no
   ▼
behind > LIVE_RATE_RECOVER_S ?
   │ yes ──► rate = 1, degradedSince = 0
   │ no  ──► hold whatever was decided before   (hysteresis band)

heldLongEnough = degradedSince > 0
                 && (now - degradedSince) >= LIVE_RATE_DEGRADE_HOLD_MS
                                              (STEP 2: 2s of slowdown first)

gapOk = lastFixAt == 0
        || (now - lastFixAt) >= LIVE_UNFREEZE_MIN_GAP_MS
                                              (STEP 3: one flush per 4s)

seek = starved && heldLongEnough && gapOk
```

`seek === true` is the ONLY moment `applyLiveDecision` performs a backward
`video.currentTime =` — the flush 0.0.373 rate-limited and 0.0.375 reverted
along with everything else. Every other recovery happens through `rate`
alone, silently, with no decoder disruption.

## Why the regulator "engages before the flush" is provable, not just true

`degradedSince` is written on the very FIRST call where `behind < 0` —
**before** `liveAction` has even had a chance to classify that sample as
`"starved"` on a later call. `heldLongEnough` then requires
`LIVE_RATE_DEGRADE_HOLD_MS` (2s) to have passed since THAT write. So a seek
can structurally never fire on the same call that degradation began, and
`tests/test_live_clock.py`'s ramp check reads the rate on the tick
immediately before the first real seek and requires it already be
`LIVE_SLOW_RATE` — proving the order held against his own drift numbers, not
just against a hand-picked unit case.

## The forward catch-up's budget (task 216)

```
late = liveAction(...) === "seek_forward"

late ? ──► lateSince ||= now ; lastLateAt = now      (the episode opens)
   │ no
   ▼
(now - lastLateAt) >= LIVE_JUMP_HOLD_MS ? ──► lateSince = 0, lastLateAt = 0
                        (the episode closes on a healthy STRETCH — one
                         healthy sample must NOT close it, or a burst-shaped
                         drift never accrues its hold and never catches up)

heldLongEnough = lateSince > 0
                 && (now - lateSince) >= LIVE_JUMP_HOLD_MS     (400ms)
gapOk          = !lastJumpAt
                 || (now - lastJumpAt) >= LIVE_JUMP_MIN_GAP_MS (1500ms)

jump = late && heldLongEnough && gapOk      → and a jump RESETS lateSince,
                                              so the next one earns its own
                                              hold (concurrent with the gap)
```

His `jumps=36 ... in 15s` becomes at most 10, and each one is a decoder flush.

## The residual gap — `redraw()`'s never-blank guard

```
streamMode === "h264" && everDrew && (video.seeking || readyState < 2) ?
        │ yes ──► return    (keep the last picture — SKIP the clear)
        │ no
        ▼
   clear to canvasBg, draw the current frame if one is ready
   (everDrew = true on the first successful draw of a session)
```

## …and the clear that was never behind that guard (task 216)

```
updateViewport()   ← window resize · visualViewport resize AND scroll
      │              · every IME inset the shell pushes (__imeHeight)
      ▼
liveResizePlan({ width, height, nextWidth, nextHeight, everDrew })
      │
      ├─ resize false ─► the buffer is NOT touched at all
      │                  (assigning canvas.width wipes it to transparent
      │                   black even when the value is unchanged — and a
      │                   transparent canvas shows the PAGE's background:
      │                   his blue flash, on every overlap with a held frame)
      └─ resize true  ─► keepCanvasPixels() → canvas.width/height = …
                         → restoreCanvasPixels()      (paint-then-swap)
```

Whatever the regulator's three steps cannot close in time — the buffer is
still empty a moment after the rate dropped — lands here, and the picture
holds instead of flashing to the theme's background colour. `everDrew` is
reset to `false` in `initMse()`, so a brand-new session still clears
correctly before its first frame ever arrives.
