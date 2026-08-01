# Input Geometry — Flow

**About:** [description](../__about/input-geometry.md)

## Algorithm — cursor-offset calibration + coordinate mapping

```mermaid
flowchart TB
    TOUCH[touch sample arrives] --> LOCKED{fingerRadiusPx already locked?}
    LOCKED -- yes --> SKIP[ignore — already calibrated]
    LOCKED -- no --> BOGUS{radius <= 2px?}
    BOGUS -- yes --> IGNORE[ignore — bogus 0/1 default]
    BOGUS -- no --> TRACKMAX[fingerMaxPx = max seen so far]
    TRACKMAX --> COUNT{sample count >= CURSOR_CALIB_SAMPLES?}
    COUNT -- no --> WAIT[keep sampling]
    COUNT -- yes --> LOCK[fingerRadiusPx = fingerMaxPx]
    LOCK --> RECOMPUTE[computeBaseRect + clampView + redraw]

    MOVE[finger moves] --> OFFSET[offsetDistancePx = clamp radius+MARGIN, MIN, MAX]
    OFFSET --> DIAG{hand?}
    DIAG -- right --> UL[up-left diagonal, 315deg]
    DIAG -- left --> UR[up-right diagonal, 45deg]
    UL --> CLAMPPT[toRemoteClamped]
    UR --> CLAMPPT
    CLAMPPT --> SEND[sendCursor -> pointer_move]
```

Pseudocode:

    ON each touch sample (while not yet calibrated):
        IF contact radius <= 2px → ignore (bogus reading)
        fingerMaxPx = max(fingerMaxPx, radius)
        IF sample count reached CURSOR_CALIB_SAMPLES:
            fingerRadiusPx = fingerMaxPx   # lock for the session
            recompute edge margin, clamp view, redraw

    offsetDistancePx():
        base = fingerRadiusPx is unset ? FALLBACK : fingerRadiusPx + MARGIN
        RETURN clamp(base, MIN, MAX)

    offsetRemote(fingerPoint):
        d = offsetDistancePx() in canvas px
        dx = (hand == "left" ? +d : -d) * sqrt(1/2)
        dy = -d * sqrt(1/2)
        RETURN toRemoteClamped(fingerPoint + (dx, dy))

    toRemoteMaybeOffset(point, isTouch):
        RETURN isTouch ? offsetRemote(point) : toRemoteClamped(point)   # mouse/pen: no offset
