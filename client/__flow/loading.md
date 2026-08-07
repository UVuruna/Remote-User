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
        still = mean |Δrgb| of a 64x36 thumbnail vs the previous < SETTLE_DIFF
        hits  = still ? hits + 1 : 0
        IF past SETTLE_MAX_MS  OR  (hits >= SETTLE_STABLE_HITS AND up > LOADING_MIN_MS):
            hideLayLoading()

hideLayLoading():
    cross-fade out (CSS), keep spinning through the fade, then cancel the rAF
```
