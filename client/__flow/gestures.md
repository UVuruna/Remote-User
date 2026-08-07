# Gestures — Flow

**About:** [description](../__about/gestures.md)

## Algorithm — pointer dispatch

```mermaid
%%{init: {'flowchart': {'subGraphTitleMargin': {'top': 0, 'bottom': 35}}}}%%
flowchart TB
    DOWN[pointerdown] --> PRIMARY{isPrimary?}
    PRIMARY -- yes --> WIPE[wipe pointers/pinch/primary — ghost self-heal]
    PRIMARY -- no --> KEEP[keep existing state]
    WIPE --> COUNT
    KEEP --> COUNT{pointers.size >= 2?}
    COUNT -- yes --> PINCH[beginPinch — every mode, layout focus included]
    COUNT -- no --> MODE{touchMode?}
    MODE -- drag --> DRAGSTART[pointer_down at toRemoteClamped position]
    MODE -- move --> MOVESTART[sendCursor at toRemoteClamped position]
    MODE -- scroll --> SCROLLSTART[track velocity baseline]
    MODE -- pan --> PANSTART[track local pan origin]

    MOVE[pointermove] --> ACTIVE{pinch active AND 2+ pointers?}
    ACTIVE -- yes --> RESCALE[recompute view.scale/tx/ty, clampView, redraw]
    ACTIVE -- no --> DISPATCH{primary.type?}
    DISPATCH -- drag --> DRAGMOVE[sendCursor]
    DISPATCH -- move --> MOVEMOVE[sendCursor]
    DISPATCH -- scroll --> SCROLLMOVE[accumulate ticks, send scroll]
    DISPATCH -- pan --> PANMOVE[translate view, clampView, redraw]

    UP[pointerup / pointercancel] --> ENDP[endPointer]
    ENDP --> ENDTYPE{primary.type?}
    ENDTYPE -- drag --> RELEASE[pointer_up]
    ENDTYPE -- scroll --> FLING[startScrollInertia]
```

Pseudocode:

    ON pointerdown:
        IF isPrimary → wipe pointers/pinch/primary (ghost-pointer self-heal)
        register this pointer
        IF 2+ pointers down → beginPinch(); RETURN
        primary = { id, type: touchMode }
        SWITCH touchMode:
            drag   → primary.pos = toRemoteClamped(point); send pointer_down
            move   → sendCursor(toRemoteClamped(point))
            scroll → prime velocity tracking at this point
            (pan handled entirely in pointermove via startX/startY)

    ON pointermove:
        IF pinch active AND 2+ pointers → rescale/translate view; RETURN
        IF not the primary pointer → RETURN
        SWITCH primary.type:
            drag/move → sendCursor(toRemoteClamped(point))
            scroll    → accumulate delta-Y into tick counter; send scroll ticks
            pan       → translate view by finger delta; clampView; redraw

    ON pointerup / pointercancel → endPointer:
        remove this pointer; drop pinch if under 2 pointers
        IF this was the primary:
            IF type == drag   → send pointer_up
            IF type == scroll → startScrollInertia(lastVelocity)
            primary = null

## The cursor-offset system is gone (owner 2026-08-02, remnants finished 2026-08-07)
The pointer sits exactly under the finger, the image aspect-fits the FULL
canvas, and a focused layout touches all four screen edges — no handedness
diagonal, no finger calibration, no reserved edge margin. Removed for good on
2026-08-07, along with `config.hand` and the `calibrate` action.
