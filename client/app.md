# Client App

**Script:** [Client App (script)](app.js)

## Purpose
The entire client behavior for Phase 1: connect + authenticate, render incoming JPEG frames to the canvas (letterboxed), and translate taps into `pointer_down`/`pointer_up` messages with coordinates normalized 0–1 within the remote monitor.

## Connections

### Uses
- [Web Layer](../server/web.md) — WebSocket `/ws`

### Used by
- [index.html](index.html) — loaded as the page's only script

## Functions
- `drawFrame(blob)`: `createImageBitmap` → letterboxed draw; records `drawRect` for coordinate mapping
- `toRemote(clientX, clientY)`: tap position → 0–1 within the drawn frame, `null` on the letterbox padding
- `connect()`: WebSocket lifecycle — sends `auth` on open, schedules reconnect (2 s) on close
- Pointer handlers: `pointerdown`/`pointerup` → JSON messages (Phase 1: left button only; gestures arrive in Phase 2)
