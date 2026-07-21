# Client App

**Script:** [Client App (script)](app.js)

## Purpose
The entire client behavior: connect + authenticate, render incoming JPEG frames to the canvas (letterboxed), pinch zoom + two-finger pan of the local view, and translate clean taps into `pointer_down`/`pointer_up` messages with coordinates normalized 0–1 within the remote monitor.

Gesture map:
- **One finger, no travel** → click on release (down + up at that point)
- **Two fingers** → pinch zoom around the midpoint + pan; no clicks are ever sent during/after a pinch
- Zoom is client-side only (max 6×) — the PC is untouched; zooming exists to hit small targets precisely

## Connections

### Uses
- [Web Layer](../server/web.md) — WebSocket `/ws`

### Used by
- [index.html](index.html) — loaded as the page's only script

## Functions
- `drawFrame(blob)`: `createImageBitmap` → `computeBaseRect` + `redraw`; keeps the last bitmap so gestures can redraw between frames
- `drawnRect()` / `clampView()`: the view transform (`scale`, `tx`, `ty`) applied over the letterbox rect; clamped so the zoomed frame always covers its zoom-1 area
- `toRemote(px, py)`: canvas point → 0–1 within the drawn frame (zoom-aware), `null` on the letterbox padding
- Pointer handlers: tap detection (travel threshold) vs pinch (anchor point under the finger midpoint stays fixed while scaling/panning)
- `connect()`: WebSocket lifecycle — sends `auth` on open, schedules reconnect (2 s) on close
