# Client App

**Script:** [Client App (script)](app.js)

## Purpose
All tablet behavior: connect + authenticate, render the stream (H.264 via MSE, or JPEG), draw the virtual cursor, gestures, the two configurable D-pad control groups, and keyboard capture.

## Rendering
`streamMode` comes from the server's `config` and picks the pixel source; everything else (view transform, gestures, coordinates) is shared.

**H.264 (primary):** binary WebSocket chunks are one continuous fragmented-MP4 stream, appended in order into a MediaSource `SourceBuffer` (codec string supplied by the server, parsed from the live init segment). The offscreen `<video>` decodes; a `requestAnimationFrame` loop draws it onto the canvas through the view transform. Staying live:

```
ON each append completed:
    IF buffered end − currentTime > 0.5 s  → jump currentTime to just behind the end
    IF buffered history > 16 s             → remove all but the last 8 s
```

An append failure (quota, codec hiccup) never freezes silently — the socket closes and auto-reconnect brings a fresh stream.

**JPEG (fallback, two layers):** a **base** bitmap (the last full-monitor frame) is drawn under everything; when zoomed, the **detail** bitmap (the sharp region crop) is drawn on top, so motion never flashes blank. `onFrame` sorts each frame into base vs detail by its region header. Only this mode sends `viewport` requests.

## Virtual cursor
`cursor` messages carry the PC pointer position (monitor-normalized) — capture frames never include it. `drawCursor` renders a classic arrow at a fixed screen size (independent of zoom) through the same drawn-rect transform as the image; positions outside 0–1 (cursor on another monitor) draw nothing. The arrow is also drawn **optimistically** on every `move`/`drag` send (`sendCursor`) so it tracks with zero round-trip lag; the server `cursor` echo then corrects it.

### Finger offset (the pointer is always diagonally ABOVE the finger)
The PC cursor is placed at **finger + offset** in a **fixed handedness diagonal** (owner decision 2026-07-26, replacing the radial-angle system — the pointer must never sit under or beside the finger):

- **Direction** comes from `config.hand` (the desktop app's Settings): right-handed → **315°, up-LEFT** of the finger; left-handed → **45°, up-RIGHT**. Never changes during use — the pointer's position relative to the finger is always the same, so aiming becomes muscle memory.
- **Distance** is constant per session, calibrated once: `sampleFinger` takes the **MAX** touch contact radius (`PointerEvent.width/height`, CSS px) over the first `CURSOR_CALIB_SAMPLES` touches and locks it — max, not median, because a light press under-reports contact size and would hide the pointer. `offsetDistancePx` = radius + `CURSOR_OFFSET_MARGIN`, clamped to `[MIN, MAX]`. `CURSOR_OFFSET_FALLBACK` is used until measured and for non-touch pointers (mouse/pen in dev get **no** offset). **Settings → Calibrate** (`startCalibration`, the `calibrate` built-in) re-arms the measurement.
- **Edge margin** (`computeBaseRect`): the image is fitted into the canvas MINUS one offset-component of margin on the sides the offset points *away from* (right-handed: right + bottom; left-handed: left + bottom). The finger can then travel PAST the image edge, so the pointer reaches every corner of the PC screen — without the margin the far edges are physically unreachable. The margin follows the calibrated distance, and `clampView` clamps zoom-panning against the same reduced rect so far edges stay reachable when zoomed.

## Touch modes (toggles)
A single `touchMode` decides what one finger does; tapping a mode button toggles it, only one is active, two fingers always pinch-zoom:
- `move` (default) → the finger only steers the PC cursor (offset so the hand never covers it) — it never clicks
- `drag` → press-move-release = left drag
- `scroll` → move = wheel (with momentum fling)
- `pan` (the top-left **Move**) → move = local view pan, no PC interaction

**Nothing on the canvas is a tap** (owner decision 2026-07-26): the flow is always *steer the pointer, then press a button*. Left AND right clicks are explicit built-in buttons (`click {button}` — down+up at the current cursor position; two fast presses = double click). `setMode` / `refreshModeButtons` keep the single-active state and mirror it onto every `[data-mode]` button.

**Ghost-pointer self-heal:** Android WebView occasionally loses a `pointerup`/`pointercancel`; a stale `pointers` entry then turned every later tap into a "pinch" until refresh. Every `pointerdown` with `isPrimary` wipes pointer/pinch/primary state first — a new primary pointer guarantees no other finger is really down.

## Control groups
Two groups (bottom-left/right), each showing one category from the server's [actions.json](../ACTIONS.md). Landscape = D-pad cross via CSS grid areas (`up/left/right/down/center`), portrait = column (media query). The small dashed **centre** button opens the category wheel.

- `renderGroup(side)` builds a group's buttons from its current category
- `makeActionButton(btn, pos)` dispatches on button kind: built-in mode (`BUILTINS`), chord, or special key
- `keepFocus(el, onTap)` — every control uses this; the tap never steals focus from the keyboard capture field. The action fires on **pointerup** (where a touch grants the transient user activation the file picker and IME focus need) **plus a `pointercancel` rescue**: Android claims touches that start near screen edges and ends them with a `pointercancel`, so an up-only handler simply never ran — on the real device that killed every button while the code looked correct (owner report 2026-07-26). A cancel whose travel stayed under `CANCEL_TAP_SLOP` is the stolen tap and still fires; a cancel after real travel is a system home/back swipe crossing the button and never acts. Both cases are locked in by [Tests (folder)](../tests/___tests.md)

## Category wheel (tap-based)
`openWheel(side)` lays the categories on a circle in screen centre; **tap** an item to select (no hold, no drag), the centre **✕** or a backdrop tap cancels. `closeWheel` tears it down.

## Keyboard
An **invisible `<textarea>`** (`opacity:0` — never `display:none`, mobile browsers cannot focus that): what you type/dictate is watched in the focused box on the streamed PC screen itself (owner 2026-07-22 — a mirror bar only duplicated it). A textarea so the phone IME offers **↵ (new row)** instead of a Send/Go key; ↵ and IME-committed `"\n"` both become **Shift+Enter** on the PC (new row — messengers keep typing), while the real Enter is the D-pad **Enter** button. Printable characters via value **diffing** (IME/autocorrect-proof, `sendTyped` splits out newlines), structural keys via `keydown`. The `keyboard` built-in toggles focus; focus/blur clears the field and mirrors state onto every `[data-action="keyboard"]` button.

## Phone → PC image
The `upload` built-in opens a hidden `<input type="file" accept="image/*">` (gallery/camera on Android); `change` POSTs the file to `/upload?token=…`; the server puts it in the PC clipboard and pastes it into the focused box itself (Ctrl+V injected) — the toast confirms "Image pasted on the PC".

## Viewport / keyboard fit
`updateViewport()` sizes the canvas to `visualViewport` (fits the screen above the keyboard instantly) and publishes `--kb` (keyboard height, lifts the groups) and `--vtop` (top offset, keeps the corners visible).

## "Access from anywhere" wizard
`config.tailscale_url` (null until the PC signs in to Tailscale) drives a banner + full-screen guided overlay: **1)** Google Play deep link to the Tailscale app, **2)** sign in with the same account and switch it ON, **3)** the page polls `GET /ping` on the Tailscale address (no-cors — an opaque success proves reachability) every 3 s and, the moment the phone joins the mesh, marks the step green and offers the permanent works-anywhere link (with a save/home-screen hint). The banner auto-appears **once per device** (owner 2026-07-26 — "ok once, not constantly"; a `localStorage` flag remembers the offer) and never when the page already runs on the Tailscale address; afterwards the wizard stays reachable via **Settings → Anywhere** (the `anywhere` built-in).

## In-app update
`config.app_version` (what the PC runs) is compared with `Android.appVersion()` (what this shell is) — numerically, inside the APK only. A newer PC shows the `#update-banner` pill; tapping it calls `Android.update(origin + "/app.apk")` — the shell opens the system browser on the SAME PC's APK, Android installs over (same signature). The phone never checks the internet for updates; the PC is its update source.

## Connection
`auth` on open; handles `config` (monitor size + stream mode + codec + tailscale_url + app_version — full reset of view, bitmaps and the MSE pipeline; arrives after auth and after every stream restart), `cursor` (virtual-cursor position), `actions` (categories + default group indices), `toast`. Socket closes when the page hides (owner security decision) and reconnects **immediately** on `visibilitychange`/`pageshow` (waiting out the 2 s watchdog swallowed the first taps after every app switch); `send()` on a dead socket also triggers an instant reconnect. Inside the APK, every `config` hands `tailscale_url` to the shell via `Android.setTailscaleUrl` — that is how the app learns the works-anywhere address it probes on start. MSE is torn down on every close and rebuilt from the next `config`.

## Connections

### Uses
- [Web Layer](../server/web.md) — WebSocket `/ws`

### Used by
- [index.html](index.html) — the page's only script
