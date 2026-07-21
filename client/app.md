# Client App

**Script:** [Client App (script)](app.js)

## Purpose
The entire client behavior: connect + authenticate, render incoming JPEG frames to the canvas (letterboxed), pinch zoom + two-finger pan of the local view, and translate clean taps into `pointer_down`/`pointer_up` messages with coordinates normalized 0–1 within the remote monitor.

Gesture map (modifier-button mechanics — owner decision):
- **One finger, no travel** → left click on release
- **Hold RIGHT button + tap** → right click at the tap point
- **Hold DRAG button + finger** → real mouse drag (down / move / up)
- **Hold SCROLL button + finger** → wheel ticks, content follows the finger
- **Two fingers on the canvas** → pinch zoom around the midpoint + pan; no clicks are ever sent during/after a pinch
- Zoom view transform is client-side (max 6×), but the visible region is reported to the server (`viewport`) so zoomed frames arrive at native sharpness
- The session pauses whenever the page is hidden (tab background / screen lock) and reconnects on return — owner security decision

## Connections

### Uses
- [Web Layer](../server/web.md) — WebSocket `/ws`

### Used by
- [index.html](index.html) — loaded as the page's only script

## Functions
- `onFrame(buffer)`: parses the 16-byte region header + JPEG, draws the bitmap at the region's place under the current transform
- `computeBaseRect()`: letterbox rect from the real monitor aspect (server `config` message), independent of frame size
- `drawnRect()` / `clampView()`: the view transform (`scale`, `tx`, `ty`) applied over the letterbox rect; clamped so the zoomed frame always covers its zoom-1 area
- `currentViewport()` / `scheduleViewport()`: computes the visible monitor region (+15 % margin) and reports it to the server, throttled to 150 ms and >1 % change
- `toRemote(px, py)` / `toRemoteClamped(...)`: canvas point → 0–1 within the monitor; strict variant ignores the letterbox padding, clamped variant keeps drags alive over it
- Modifier buttons: pointer capture per button sets `modifiers.*`; releasing DRAG mid-drag finishes the drag safely
- Canvas handlers: modifier branches (drag / scroll) short-circuit before the tap/pinch flow, so pinch never fights the buttons
- `connect()`: WebSocket lifecycle — `auth` on open, `config` handling, reconnect (2 s) on close, and visibility gating (socket closes when the page hides, reconnects when it returns)
