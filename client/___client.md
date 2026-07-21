# client/

The tablet side of Remote User — a plain web page served by the PC server and opened in Chrome on the Android device. No framework, no build step: three static files.

## Files

### `index.html` — Page Shell
Canvas + status pill + the bottom-right control cluster (RIGHT / DRAG / SCROLL / ⌨ / MON / SNAP / ENTER) + PAN (top-left) + action-set launchers and the radial-wheel overlay (bottom-left) + the hidden keyboard-capture input. Viewport locked (no browser zoom/scroll — pinch drives the local zoom).

### `app.js` — Client Logic
WebSocket connection, frame rendering, tap-to-click. See [Client App](app.md).

### `load_test.js` — Load-Order Test
Node harness that executes `app.js` top-to-bottom with DOM stubs — catches script-killing load-time errors (TDZ, missing elements) that a syntax check cannot. **Run `node client/load_test.js` before every client commit.** Born from a real failure: a `let` declared below its first load-time use killed the page before it ever connected.

### `style.css` — Styling
Design tokens per root DESIGN.md (dark surface, one accent), gradient status pill (connecting / connected / disconnected). Buttons are **see-through** (low-opacity fill, no backdrop blur — the screen stays visible behind them) with an icon + text label each, kept legible by icon/text shadows. Control pad is a 2-column grid that lifts above the soft keyboard via the `--kb` variable. `touch-action: none` everywhere.

## Connections

### Uses
- [Server (folder)](../server/___server.md) — WebSocket endpoint `/ws`, frames in, input out

### Used by
- Served at `/` and `/static` by the [Web Layer](../server/web.md)

## Design Decisions

- **Letterbox-aware coordinate mapping** — taps are mapped through the drawn image rect (including the zoom/pan transform), so normalized coordinates stay correct regardless of tablet aspect ratio; taps on the padding are ignored.
- **Clicks fire on release, not on press** — a clean single-finger tap sends down+up together; any finger travel or a second finger cancels the click. This is what makes pinch zoom safe: zooming can never leak a click to the PC.
- **Modifier buttons over timed gestures** (owner decision) — game-style corner buttons held with one finger change what the other finger means (right click / drag / scroll). No long-press timers, no ambiguity with pinch.
- **Region streaming** — when zoomed, the client reports its visible region and receives native-resolution crops instead of upscaled downsampled frames; bandwidth stays constant, zoom stays sharp.
- **Visibility-gated session** (owner security decision) — the socket closes the moment the page is hidden (tab switch, screen lock) and reconnects on return; the PC is never controllable while the owner isn't looking.
- **Token from the URL** (`?token=…`, delivered by the QR code) is sent as the first WebSocket message — the server accepts nothing before it.
- **Auto-reconnect** every 2 s on close; the status pill is the only UI chrome.
