# Server Core

**Script:** [Server Core (script)](../server_core.py) ·
**Flow:** [diagram](../__flow/server_core.md)

## Purpose
The whole server stack as one start/stoppable component, shared by both entry points — `main.py` (CLI, blocking on the calling thread) and the desktop GUI ([GUI (subfolder)](../gui/___gui.md), background thread, buttons). Owns everything `main.py` used to wire inline: the stream-mode decision (H.264 when a verified encoder exists, else JPEG), the input injector, pairing info, the uvicorn lifecycle, and teardown.

**Precondition:** the process is already per-monitor DPI aware ([Bootstrap](bootstrap.md) ran) before this module is imported.

## Connections

### Uses
- [Config](config.md) — every tunable read during `_serve()`
- [Encoders](encoders.md) — `detect_encoder()` decides the stream mode
- [Screen Capture](capture.md) — `JpegStreamer` (lazy import, JPEG branch only)
- [H.264 Streamer](h264_streamer.md) — `H264Manager` (lazy import, H.264 branch only)
- [Input Injector](input_injector.md) — built with the captured monitor's pixel rect
- [Web Layer](web.md) — `FrameHub`, `ServerStats`, `create_app()`
- [Pairing](pairing.md) — `generate_token()`, `pairing_urls()`, `show_pairing()`
- [Monitors](monitors.md) — `rect_for_size()` for the injector's initial rect

### Used by
- `main.py` (script) — CLI entry, `run_blocking()`
- [Desktop Entry Point](gui_main.md) / `gui/main_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — `start()`/`stop()` from Qt buttons, `state`/`info` polled by a timer

## Classes

### ServerInfo
Snapshot the GUI reads: `mode`, `encoder`, `monitor_width`/`height`, `port`, `token`, `qr_url` (Tailscale-preferred), `lan_url`, `tailscale_ip`, live `ServerStats` (client count).

### ServerController
One instance per process; states `"stopped" → "starting" → "running" → "stopped"`, or `"failed"` with `.error` set — the GUI polls this, never silent.

- `start()` — non-blocking, spawns a daemon thread running `asyncio.run(_serve())`; no-op while already alive
- `stop(timeout=10.0)` — force-exits uvicorn (`force_exit` + `should_exit`, NOT graceful shutdown — see the flow doc for why) and joins the thread; waits briefly for the uvicorn instance to exist first when stopping mid-startup, so the exit flags always have something to land on
- `run_blocking()` — CLI mode: runs `_serve()` on the calling thread until Ctrl+C/exit
- `console_pairing=True` prints the QR to the console (CLI); the GUI renders it in-window from `pairing.qr_png()` instead

## Windows never outlive the process (owner decree 2026-08-05)

- **`self.layouts` is created once per PROCESS**, not per server run, and
  handed to `create_app`. "Apply & restart" used to build a fresh empty
  registry — throwing away the owner's layouts AND the only in-memory list of
  which windows were still always-on-top.
- **`repair_stranded()` runs in `__init__`**, before anything of ours can
  raise a window: whatever a killed previous run left standing is put right
  first (see [Window Manager](window_manager.md) — the topmost ledger).
- **`foreground_lock.repair_stranded()` runs beside it** (round R2), and only
  then does `__init__` raise the lock if the owner's switch says so. It is
  applied HERE rather than in the window because both entry points build a
  controller and the headless CLI is entitled to the same setting — but it is
  deliberately NOT released by `release_windows()`, which also runs on every
  server stop. The lock belongs to the PROCESS; `gui_main.py` and `main.py`
  release it on the way out. See [Foreground Lock](foreground_lock.md).
- **`release_windows()` is THE exit call.** It drops the whole always-on-top
  band synchronously on the calling thread AND stops the foreground-hook
  listener ([Focus Hook](focus_hook.md) — a Win32 hook and its thread are the
  same kind of leftover as a stranded topmost window). It runs FIRST in
  `stop()` — ahead of `force_exit` and a join that can wait out its full 10 s
  while the server thread is mid-placement — and FIRST in `_serve`'s
  `finally`, ahead of the encoder teardown, so a hanging ffmpeg terminate
  cannot eat the one thing the owner notices. Every documented way out
  funnels here: tray Quit, server stop, Apply & restart, Ctrl+C, a console
  close/logoff, Qt's `aboutToQuit`, `atexit`. It is idempotent, and both
  halves are wrapped so nothing on the way out can raise.
- **`traffic.METER.start()`** begins sampling with the first server start and
  never stops: a stopped server has to read as a line of zeros on the owner's
  graph, never as a hole where anything could have happened.
- **Capture is on demand in both modes.** The unconditional `stream.start()`
  for JPEG is gone; [Web Layer](web.md)'s `FrameHub.subscribers` owns it now.
