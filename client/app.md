# Client App

**Script:** [Client App (script)](app.js)

## Purpose
All tablet behavior: connect + authenticate, render the stream, gestures, the two configurable D-pad control groups, and keyboard capture.

## Rendering (two layers)
Motion never flashes blank: a **base** bitmap (the last full-monitor frame) is kept in memory and drawn under everything; when zoomed, the **detail** bitmap (the sharp region crop) is drawn on top. Full native resolution is never streamed live — that would be ~200 Mbps; the base is the last whole-screen frame, the region refreshes while zoomed. `onFrame` sorts each incoming frame into base vs detail by its region header.

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
`auth` on open; handles `config` (monitor size — resets view + bitmaps), `actions` (categories + default group indices), `toast`. Socket closes when the page hides (owner security decision); a watchdog interval reconnects when visible.

## Connections

### Uses
- [Web Layer](../server/web.md) — WebSocket `/ws`

### Used by
- [index.html](index.html) — the page's only script
