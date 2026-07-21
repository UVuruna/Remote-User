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
`cursor` messages carry the PC pointer position (monitor-normalized) — capture frames never include it. `drawCursor` renders a classic arrow at a fixed screen size (independent of zoom) through the same drawn-rect transform as the image; positions outside 0–1 (cursor on another monitor) draw nothing.

## Touch modes (toggles)
A single `touchMode` decides what one finger does; tapping a mode button toggles it, only one is active, two fingers always pinch-zoom:
- `click` (default) → tap = left click
- `right` → tap = right click
- `drag` → press-move-release = left drag
- `scroll` → move = wheel (with momentum fling)
- `hover` → move = cursor only, no click (triggers hover UI like "show more")
- `pan` (the top-left **Move**) → move = local view pan, no PC interaction

`setMode` / `refreshModeButtons` keep the single-active state and mirror it onto every `[data-mode]` button.

## Control groups
Two groups (bottom-left/right), each showing one category from the server's [actions.json](../ACTIONS.md). Landscape = D-pad cross via CSS grid areas (`up/left/right/down/center`), portrait = column (media query). The small dashed **centre** button opens the category wheel.

- `renderGroup(side)` builds a group's buttons from its current category
- `makeActionButton(btn, pos)` dispatches on button kind: built-in mode (`BUILTINS`), chord, or special key
- `keepFocus(el, onTap)` — every control uses this so a tap never steals focus from the hidden keyboard input

## Category wheel (tap-based)
`openWheel(side)` lays the categories on a circle in screen centre; **tap** an item to select (no hold, no drag), the centre **✕** or a backdrop tap cancels. `closeWheel` tears it down.

## Keyboard
A **visible bar at the top** (shown while focused) so you can see what you type/dictate; printable characters via value **diffing** (IME/autocorrect-proof), structural keys via `keydown`. The `keyboard` built-in toggles focus; focus/blur clears the bar and mirrors state onto every `[data-action="keyboard"]` button.

## Phone → PC image
The `upload` built-in opens a hidden `<input type="file" accept="image/*">` (gallery/camera on Android); `change` POSTs the file to `/upload?token=…`; the server puts it in the PC clipboard and the result is shown as a toast.

## Viewport / keyboard fit
`updateViewport()` sizes the canvas to `visualViewport` (fits the screen above the keyboard instantly) and publishes `--kb` (keyboard height, lifts the groups) and `--vtop` (top offset, keeps the corners visible).

## Connection
`auth` on open; handles `config` (monitor size + stream mode + codec — full reset of view, bitmaps and the MSE pipeline; arrives after auth and after every stream restart), `cursor` (virtual-cursor position), `actions` (categories + default group indices), `toast`. Socket closes when the page hides (owner security decision); a watchdog interval reconnects when visible; MSE is torn down on every close and rebuilt from the next `config`.

## Connections

### Uses
- [Web Layer](../server/web.md) — WebSocket `/ws`

### Used by
- [index.html](index.html) — the page's only script
