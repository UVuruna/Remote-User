# client/

The tablet side of Remote User — a plain web page served by the PC server and opened in Chrome on the Android device. No framework, no build step: three static files.

## Files

### `index.html` — Page Shell
Canvas + status pill, viewport locked (no browser zoom/scroll — pinch is reserved for the future local-zoom gesture).

### `app.js` — Client Logic
WebSocket connection, frame rendering, tap-to-click. See [Client App](app.md).

### `style.css` — Styling
Dark fullscreen canvas, gradient status pill (connecting / connected / disconnected), `touch-action: none` everywhere.

## Connections

### Uses
- [Server (folder)](../server/___server.md) — WebSocket endpoint `/ws`, frames in, input out

### Used by
- Served at `/` and `/static` by the [Web Layer](../server/web.md)

## Design Decisions

- **Letterbox-aware coordinate mapping** — taps are mapped through the drawn image rect (including the zoom/pan transform), so normalized coordinates stay correct regardless of tablet aspect ratio; taps on the padding are ignored.
- **Clicks fire on release, not on press** — a clean single-finger tap sends down+up together; any finger travel or a second finger cancels the click. This is what makes pinch zoom safe: zooming can never leak a click to the PC.
- **Token from the URL** (`?token=…`, delivered by the QR code) is sent as the first WebSocket message — the server accepts nothing before it.
- **Auto-reconnect** every 2 s on close; the status pill is the only UI chrome.
