# Input Injector

**Script:** [Input Injector (script)](../input_injector.py) ·
**Flow:** [diagram](../__flow/input_injector.md)

## Purpose
Injects mouse and keyboard input with Win32 `SendInput` through raw ctypes structs. Client coordinates arrive normalized 0–1 within the displayed monitor; this module maps them to the 0–65535 absolute range of the entire virtual desktop (`MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK`), which is what `SendInput` requires on multi-monitor systems.

**Precondition:** the process must already be per-monitor DPI aware ([Bootstrap](bootstrap.md) declares it) — otherwise Windows silently rescales the injected coordinates.

**UIPI — the proven silent killer, defended twice (2026-07-29):** Windows discards ALL injected input from a non-elevated process — `SendInput` still returns success — whenever an ELEVATED window has focus (or the lock screen / a UAC secure desktop is up). Live failure: an elevated VSCode held focus and every phone session went completely dead — stream fine, zero errors anywhere. Defense one is operational (the packaged app runs elevated, `--uac-admin`, see [Setup (folder)](../../setup/___setup.md)); defense two is this module's `InjectionMonitor` — the only reliable detector is the EFFECT, since Windows never reports the failure.

## Connections

### Uses
- [Config](config.md) — the injection-verify thresholds (`inject_verify_min_jump`/`_tolerance`/`_streak`)

### Used by
- [Server Core](server_core.md) — constructs it with the captured monitor's pixel rect
- [Web Layer](web.md) — dispatches every `pointer_*`/`click`/`scroll`/`key_*`/`chord` message here; polls `take_input_alarm()` for the cursor-stream toast

## Classes

### InjectionMonitor
Pure decision logic of the injection self-check (no Win32 calls — the pure-logic shape is what lets the build gate pin it without touching a real cursor). Detects eaten injection by its EFFECT: see the [flow doc](../__flow/input_injector.md).

### InputInjector
Maps monitor-normalized coordinates to virtual-desktop absolutes and injects.

#### Attributes
- `monitor_rect`: (left, top, width, height) of the captured monitor in real pixels
- `virtual_rect`: the whole virtual desktop, from `GetSystemMetrics`

#### Methods
- `move(x_norm, y_norm)`: absolute cursor move; also verifies the PREVIOUS move lazily (reads `GetCursorPos` once per call, no sleeps on the hot path) and feeds `InjectionMonitor` — see the flow doc for the lazy-verify timing
- `take_input_alarm()`: returns-and-clears the alarm flag; polled by the web layer's cursor loop and forwarded to the phone as a visible toast
- `button_down(x_norm, y_norm, button)` / `button_up(...)`: move + press/release in one injected event (`left`/`right`/`middle`/`x1`/`x2`, from `BUTTON_FLAGS`)
- `click(button)`: down+up at the CURRENT cursor position, no move; two presses inside Windows' double-click time land as a double click naturally
- `press(button, down)`: one half of a CLICK/HOLD button (owner 2026-08-04 — the phone's Click/Right/Middle and the side Btn 4/Btn 5 behave like a real mouse): DOWN when the finger lands, UP when it lifts, at the current cursor — a tap is a click, a held finger drags/selects
- `wheel(x_norm, y_norm, ticks)`: moves the cursor to the gesture point first (the wheel targets the window under the cursor), then scrolls by `ticks × WHEEL_DELTA`
- `type_text(text)`: arbitrary Unicode via `KEYEVENTF_UNICODE` (VK_PACKET) — one down+up per UTF-16 code unit, so surrogate pairs (emoji) work
- `press_key(name)`: structural keys (Enter, Backspace, Tab, Escape, Delete, Home/End, Page Up/Down, arrows, Space, Insert) by VK code from `VK_CODES`; an unknown name logs and injects nothing
- `press_chord(chord)`: a combination like `"ctrl+c"` or `"ctrl+win+alt+1"` — all tokens but the last are modifiers held down while the final key taps, released in reverse order; an unknown modifier or key logs and emits nothing (no half-pressed keys)
- `cursor_norm()`: the inverse mapping — current `GetCursorPos` normalized to the captured monitor, for the client-drawn virtual cursor (capture frames never contain the pointer); values fall outside 0–1 on another monitor, `None` when Windows refuses the read (secure desktop / UAC prompt)
- `set_monitor_rect(rect)`: called when the streamed monitor changes

## Module-level data and helpers
- `VK_CODES`: name → virtual-key code for structural keys (`enter`, `backspace`, `tab`, `escape`/`esc`, `delete`/`del`, `insert`, `home`, `end`, `pageup`, `pagedown`, `space`, arrow keys, `` ` ``/`backquote` — VSCode's terminal chord; media keys incl. `medianext`/`mediaprev`/`mediastop` (the Media set's reserve commands); `/`/`slash` — VK_OEM_2, VSCode's comment chord `ctrl+/`, also a reserve; `minus`/`-` and `plus`/`=` — the main-row OEM keys for the layout font-zoom chords `ctrl+minus`/`ctrl+plus`, owner 2026-08-05). Every reserve command a set's pool offers must have its token here — a chord the injector cannot press is a dead button on the phone
- `MODIFIER_VKS`: `ctrl`/`control`, `alt`, `shift`, `win`/`meta`/`super` → VK code
- `BUTTON_FLAGS`: `left`/`right`/`middle`/`x1`/`x2` → `(down flag, up flag, mouseData)` — imported directly by [Web Layer](web.md) to validate the client's `button` field. The three main buttons own a flag pair each and carry `mouseData = 0`; the two SIDE buttons (owner 2026-08-05 — Btn 4 / Btn 5, Windows' XBUTTON1/XBUTTON2) share ONE flag pair and name themselves in `mouseData`, which is why every send passes it through. A wrong `mouseData` would press the other side button with no error at all, so the mapping is pinned in `tests/test_input_pipeline.py`
- `vk_for_key(token)`: a single chord token (a single letter/digit, a name in `VK_CODES`, a bare modifier, or `f1`–`f24`) → VK code, or `None`
