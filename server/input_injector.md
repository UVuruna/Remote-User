# Input Injector

**Script:** [Input Injector (script)](input_injector.py)

## Purpose
Injects mouse input with Win32 `SendInput` through raw ctypes structs. Client coordinates arrive normalized 0–1 within the displayed monitor; this module maps them to the 0–65535 absolute range of the entire virtual desktop (`MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK`), which is what `SendInput` requires on multi-monitor systems.

**Precondition:** the process must already be per-monitor DPI aware ([Main](main.md) declares it) — otherwise Windows silently rescales the injected coordinates.

**Known limitation (accepted, v1):** UAC-elevated windows ignore injected input unless this process also runs elevated; the failure is silent (UIPI).

## Connections

### Uses
- Nothing project-internal (leaf module over user32)

### Used by
- [Web Layer](web.md) — dispatches `pointer_*` messages here
- [Main](main.md) — constructs it with the captured monitor's pixel rect

## Classes

### InputInjector

#### Attributes
- `monitor_rect`: (left, top, width, height) of the captured monitor in real pixels
- `virtual_rect`: the whole virtual desktop, from `GetSystemMetrics`

#### Methods
- `move(x_norm, y_norm)`: absolute cursor move
- `button_down(x_norm, y_norm, button)` / `button_up(...)`: move + press/release in one injected event (`left` / `right` / `middle`)
- `wheel(x_norm, y_norm, ticks)`: moves the cursor to the gesture point (the wheel targets the window under the cursor), then scrolls by `ticks` × `WHEEL_DELTA` (positive = up)
- `type_text(text)`: arbitrary Unicode via `KEYEVENTF_UNICODE` (VK_PACKET) — one down+up per UTF-16 code unit, so surrogate pairs (emoji) work
- `press_key(name)`: structural keys (Enter, Backspace, Tab, Escape, Delete, Home, End, arrows) by VK code from the `VK_CODES` map; unknown names are logged, never guessed
