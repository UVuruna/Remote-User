# server/

The PC side of Remote User: captures the screen, streams it over WebSocket as H.264 (JPEG fallback), streams the cursor position, and injects mouse/keyboard input received from the tablet client. Two entry points around one core: `gui_main.py` (the desktop app — what the installed EXE runs) and `main.py` (headless CLI for dev).

## Files

| File | Tier | One line |
|------|------|----------|
| `main.py` | Trivial | CLI entry point — bootstrap + `ServerController(console_pairing=True).run_blocking()`, nothing else |
| `gui_main.py` | Standard | desktop entry point — bootstrap + Qt + `MainWindow`; `--selfcheck` is the build's frozen-exe smoke test — [about](__about/gui_main.md) |
| `bootstrap.py` | Standard | process init shared by both entry points — DPI awareness → logging → user settings, in that order — [about](__about/bootstrap.md) |
| `server_core.py` | Algorithmic | the whole server stack as one start/stoppable component — [about](__about/server_core.md) · [flow](__flow/server_core.md) |
| `config.py` | Algorithmic | single source of every tunable value — code defaults + user settings JSON — [about](__about/config.md) · [flow](__flow/config.md) |
| `capture.py` | Algorithmic | dxcam ownership — capture thread, screenshots, monitor switching; JPEG and H.264 front-ends — [about](__about/capture.md) · [flow](__flow/capture.md) |
| `h264_streamer.py` | Algorithmic | H.264 streamer — one shared capture, one ffmpeg process per client — [about](__about/h264_streamer.md) · [flow](__flow/h264_streamer.md) |
| `encoders.py` | Algorithmic | H.264 encoder auto-detection — NVENC → QuickSync → AMF → libx264, verified by test-encoding — [about](__about/encoders.md) · [flow](__flow/encoders.md) |
| `input_injector.py` | Algorithmic | Win32 `SendInput` injection + the `InjectionMonitor` self-check tripwire — [about](__about/input_injector.md) · [flow](__flow/input_injector.md) |
| `web.py` | Algorithmic | FastAPI app — the WebSocket protocol handler, HTTP routes, stream dispatch — [about](__about/web.md) · [flow](__flow/web.md) |
| `presence.py` | Algorithmic | is the owner still working with us, and whose desk are we on — heartbeat, the `away` reason, the excursion hold, and the rule that local input at THIS PC outranks all of it — [about](__about/presence.md) · [flow](__flow/presence.md) |
| `focus_guard.py` | Algorithmic | WHERE typed input lands — the layout is a fence for the phone's keyboard, the desktop gets a pin, and a window that steals focus mid-dictation is named in the log and handed the focus straight back — [about](__about/focus_guard.md) · [flow](__flow/focus_guard.md) |
| `agents.py` | Algorithmic | which agent tools are LIVE on this PC and in which project — the process table answers what UI Automation could not, so the Claude set appears by itself instead of being ticked by hand — [about](__about/agents.md) · [flow](__flow/agents.md) |
| `layout_api.py` | Algorithmic | the phone's layout protocol — pick, list, create, focus, aspect, state — [about](__about/layout_api.md) · [flow](__flow/layout_api.md) |
| `traffic.py` | Standard | every byte to and from the phone, sampled per second and recorded — the owner's instrument for "does it run while the screen is off" — [about](__about/traffic.md) |
| `window_manager.py` | Standard | window layouts (Phase F+ step 1) — enumerate/hit-test/arrange/raise windows, app icons, the session-scoped `LayoutRegistry` — [about](__about/window_manager.md) |
| `uia.py` | Algorithmic | tab layer (Phase F+ step 2) — UIA tab hit-test + extraction to a window (app command / Explorer path / SendInput drag) — [about](__about/uia.md) · [flow](__flow/uia.md) |
| `pairing.py` | Standard | token generation, LAN/Tailscale IP discovery, QR code — [about](__about/pairing.md) |
| `monitors.py` | Standard | physical monitor rects in virtual-desktop coordinates — [about](__about/monitors.md) |
| `clipboard.py` | Standard | screenshot frames into the Windows clipboard as CF_DIB — [about](__about/clipboard.md) |
| `updates.py` | Standard | desktop update discovery via GitHub Releases — [about](__about/updates.md) |

### `gui_main.py` / `gui/` — Desktop App
PySide6 window (status, in-window QR, settings) + tray around the server core; `--minimized` starts in the tray. See [GUI (subfolder)](gui/___gui.md).

Action sets for the radial wheels are defined in [actions.json](../ACTIONS.md) at the project root (hand-edited by the owner) and served by [Web Layer](__about/web.md).

## Connections

### Uses
- [Client (folder)](../client/___client.md) — static files served to the tablet

### Used by
- Desktop app: `python server/gui_main.py` (what the packaged EXE runs — see [Setup (folder)](../setup/___setup.md))
- Headless dev CLI: `python server/main.py` (venv: `.venv`)
- [Tests (folder)](../tests/___tests.md) — `test_input_pipeline.py` drives the real [Web Layer](__about/web.md) app end to end
- [Setup (folder)](../setup/___setup.md) — packages `gui_main.py` as the PyInstaller entry point

## Design Decisions

- **Frames and input share one WebSocket.** JPEG mode: a per-client queue of size 1 drops stale frames when the tablet lags. H.264 mode: bytes are a continuous stream and can never be dropped individually — a client that falls a whole queue behind gets its session reset (fresh init segment + keyframe) instead of accumulating latency.
- **One ffmpeg per client, capture shared** — each client's stream starts with its own init segment and keyframe (no mid-stream joining), and capture+encode run only while at least one client is connected.
- **No input before auth** — the socket closes (4401) unless the first message is a valid `auth` within 5 s.
- **Downscale before encode** — a 4K monitor at native resolution is ~216 Mbps of JPEG; capped at `max_stream_width` (1600 px). With H.264 the same screen streams natively at ~3.6 Mbps.
- **The client draws the cursor** — DXGI frames never contain the pointer, so the server streams `GetCursorPos` (normalized, on change) and the client renders a virtual cursor.
- **DPI awareness is declared in `bootstrap.py`, called first by both entry points** — a root architecture constraint (see project [CLAUDE.md](../CLAUDE.md)).
- **`main.py` stays a one-line-of-logic Trivial file.** `server_core.py` owns everything the CLI used to wire inline (stream-mode decision, injector, pairing, uvicorn) precisely so both entry points — CLI and GUI — share one implementation; `main.py`'s only job left is the console-pairing flag.
