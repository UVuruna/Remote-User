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
6. **Known accepted limitations (v1):** UAC-elevated windows ignore injected input unless the server runs elevated (silent failure — UIPI); the browser session does not survive tablet screen lock.

## Testing Notes

- Gesture disambiguation (tap vs drag vs scroll) can only be tuned on a **real touch device** — do not assume defaults are right.
- Test Unicode injection against real targets (VSCode, browser inputs) — VK_PACKET has known quirks in some apps (e.g. Windows Terminal surrogate-pair bugs).
- After long-running capture sessions, verify frame latency fresh — restart before measuring (see root CLAUDE.md profiling section).
