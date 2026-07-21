# CLAUDE.md — Remote User

Project-specific guidance. Inherits ALL rules from the root [CLAUDE.md](../../CLAUDE.md).

---

## What This Project Is

Remote control of the Windows PC from an Android tablet/phone over LAN. The PC runs a Python server (screen capture + input injection); the tablet runs **no native app** — it opens a web page served by the PC. Full architecture and design decisions: [Remote User](README.md). Phase status: [Roadmap](ROADMAP.md).

## Tech Stack (decided — do not relitigate without owner approval)

- **Server:** Python 3.13, FastAPI + uvicorn (HTTP page + WebSocket), `dxcam` (DXGI screen capture), `ctypes` → Win32 `SendInput` (input injection), `qrcode` (pairing)
- **Client:** vanilla HTML/CSS/JS (PWA), Pointer Events, canvas rendering — no framework, no build step
- **Streaming v1:** JPEG per frame over WebSocket binary messages; H.264+MSE is the upgrade path, not the starting point

## Architecture Constraints

1. **One monitor per view.** The client always displays and controls exactly one monitor; a switch button changes which. Client coordinates are ALWAYS normalized 0–1 within the displayed monitor; the server maps them to that monitor's rect. Never send virtual-desktop-wide coordinates.
2. **The server process must declare DPI awareness** (`DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2`) before any capture or injection — otherwise Windows silently rescales injected coordinates.
3. **No input before auth.** The WebSocket handler rejects every message until a valid token arrives. This is a hard security rule (Remote Mouse CVE class), not a nice-to-have.
4. **Unicode text goes through `KEYEVENTF_UNICODE`** (VK_PACKET), never through virtual-key mapping. Special keys (Enter, Backspace, arrows, Tab, Esc) go through VK codes. Two distinct protocol messages: `key_text` vs `key_special`.
5. **Client keyboard capture:** hidden focusable `<input>` (`opacity:0`, NOT `display:none`) with `autocapitalize/autocorrect/autocomplete/spellcheck` disabled; printable characters via input-event diffing, structural keys via `keydown`. Never trust `keydown.key` for printable characters (Android IME).
6. **Input mechanics are modifier buttons, not timed gestures** (owner decision, 2026-07-21): tap = left click on clean release; corner buttons held with one finger modify what the other finger does (RIGHT → right click, DRAG → mouse drag, SCROLL → wheel). Two fingers on the canvas = local pinch zoom/pan, which never sends clicks. Do not reintroduce long-press/timer gestures.
7. **Session lives only while the owner is looking** (owner security decision): the client closes the WebSocket when the page is hidden (tab backgrounded / screen locked) and reconnects on return. UAC-elevated windows still ignore injected input unless the server runs elevated (silent failure — UIPI).

## Protocol

- Client → server (JSON text): `auth {token}`, `pointer_down/pointer_up {x, y, button}`, `pointer_move {x, y}`, `scroll {x, y, ticks}`, `viewport {x, y, w, h}`, `key_text {text}`, `key_special {key}`, `chord {chord}`, `monitor_switch {}`, `screenshot {}`. Coordinates are always 0–1 within the displayed monitor.
- Server → client: `config {monitor_width, monitor_height}` JSON text (after auth and after a monitor switch — client must fully reset its view), `actions {sets}` (radial-wheel shortcut sets from `actions.json`, after auth), `toast {text}` (user-facing notice shown on the status pill), then binary frames: **16-byte header (4 × float32 LE — monitor-normalized x, y, w, h of the region the frame covers) + JPEG bytes**.
- **Chord shortcuts** (`ctrl+c`, `ctrl+win+alt+1`): sets live in the owner-edited `actions.json` (see [ACTIONS.md](ACTIONS.md)), re-read on every connection. The client renders launcher pills + radial wheels; it never hardcodes shortcuts. Custom-set editing UI and login/setup belong to the future desktop GUI, not the web client (owner decision).
- Region streaming: when zoomed, the client requests its visible region (`viewport`); the server crops the 4K frame to it before downscaling — zoom stays sharp at constant bandwidth. Full frame = region (0, 0, 1, 1).

## Testing Notes

- Gesture disambiguation (tap vs drag vs scroll) can only be tuned on a **real touch device** — do not assume defaults are right.
- Test Unicode injection against real targets (VSCode, browser inputs) — VK_PACKET has known quirks in some apps (e.g. Windows Terminal surrogate-pair bugs).
- After long-running capture sessions, verify frame latency fresh — restart before measuring (see root CLAUDE.md profiling section).
