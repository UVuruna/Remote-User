# Flow — the loading cube

```
showLayLoading(text):
    stop judging any previous operation
    backstop timer = LOADING_MAX_MS
    open on the NEXT cube face, start the rAF spin

layout_progress  → cubeNext()          # a momentum burst per finished window

layout_state     → settleLayLoading()  # the server is done — the SCREEN may not be
    wait SETTLE_CATCHUP_MS             # the picture here is still the old one
    every SETTLE_SAMPLE_MS:
        # task 194: a FRACTION of changed pixels, not a whole-frame mean —
        # tolerates real local motion (a blinking caret, an agent typing)
        # instead of demanding near-perfect stillness before it counts.
        frac  = changedFraction(64x36 thumbnail, previous sample)
        still = isSettled(frac)   # frac < SETTLE_MOTION_FRAC
        hits  = still ? hits + 1 : 0
        IF past SETTLE_MAX_MS  OR  (hits >= SETTLE_STABLE_HITS AND up > LOADING_MIN_MS):
            hideLayLoading()       # SETTLE_MAX_MS is now "a few seconds" (was 4s)

hideLayLoading():
    cross-fade out (CSS), keep spinning through the fade, then cancel the rAF
```
