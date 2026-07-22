# client/

The phone side of Remote User — a plain web page served by the PC server, loaded inside the Android app's WebView. A plain Android **browser** never sees it: the server routes browsers by User-Agent to the install funnel (`install.html`), because on a phone the product is the app (owner rule — no half-working browser sessions). Desktop browsers still get the client for dev/testing. No framework, no build step.

## Files

### `index.html` — Page Shell
Canvas + offscreen `<video>` (the H.264/MSE decode surface) + status pill + Move (top-left) and Hide (top-right) corner buttons + two D-pad groups (bottom-left/right, filled from config) + the category-wheel overlay + the invisible keyboard-capture textarea. Viewport locked (no browser zoom/scroll — pinch drives the local zoom).

### `install.html` — Android Install Funnel
The ONLY page an Android browser ever sees (served at `/` by User-Agent when the APK exists). Full-screen, two steps: **Install** (downloads `/app.apk`) and **Open the app** — an `intent://pair?url=…` link that launches the app with THIS page's tokened URL, so pairing is one tap (nothing typed, nothing scanned; falls back to this same page when the app is missing). Self-contained (own inline styles).

### `app.js` — Client Logic
WebSocket connection, H.264 (MSE) or JPEG rendering, virtual cursor, cursor-steering gestures + the Click button. See [Client App](app.md).

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

- **Letterbox-aware coordinate mapping** — touches are mapped through the drawn image rect (including the zoom/pan transform), so normalized coordinates stay correct regardless of tablet aspect ratio; touches on the padding are ignored.
- **The finger steers, buttons act** (owner decision 2026-07-22) — the default gesture only moves the PC cursor; the explicit **Click** button presses at the current cursor position (twice fast = double click). Toggle modes (right / drag / scroll) change what one finger does; two fingers always pinch — zooming can never leak a click to the PC. No long-press timers, no tap-to-click ambiguity.
- **Ghost-pointer self-heal** — a lost `pointerup` (Android WebView under system gestures) used to freeze all input into phantom "pinches" until refresh; every new primary `pointerdown` wipes the pointer state first.
- **The stream mode is the server's call** — `config` says `h264` (fMP4 chunks appended into MSE, the video drawn onto the canvas every animation frame) or `jpeg` (bitmap per message). All gesture/zoom/coordinate logic is mode-independent; only the pixels' source differs.
- **Virtual cursor** — capture never contains the PC pointer; the server streams its position and the client draws a fixed-size arrow through the same view transform as the image.
- **Region streaming (JPEG mode only)** — when zoomed, the client reports its visible region and receives native-resolution crops instead of upscaled downsampled frames; bandwidth stays constant, zoom stays sharp. In H.264 mode inter-frame compression already makes the full frame cheap, so the client never sends `viewport`.
- **Visibility-gated session** (owner security decision) — the socket closes the moment the page is hidden (tab switch, screen lock) and reconnects on return; the PC is never controllable while the owner isn't looking.
- **Token from the URL** (`?token=…`, delivered by the QR code) is sent as the first WebSocket message — the server accepts nothing before it.
- **Guided "anywhere access" wizard** (owner principle: the app explains every step, never a human): when the server reports a `tailscale_url` and the page runs on the home address, a banner offers a one-time in-page wizard — Google Play deep link for the Tailscale app, a sign-in step, then the page polls `/ping` on the Tailscale address and hands over the permanent works-anywhere link the moment the phone joins. Dismissal lasts one session (it re-offers until completed); once the page runs on the Tailscale address the banner never shows.
- **Auto-reconnect** — instantly on return to the page (`visibilitychange`/`pageshow`, and any send on a dead socket), plus a 2 s watchdog; the status pill is the only UI chrome.
