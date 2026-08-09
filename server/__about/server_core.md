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
- [Update Handover](update_handover.md) — `announce()` in `__init__`, beside the two `repair_stranded()` calls: the same discipline, applied to something a previous run ended ON PURPOSE

### Used by
- `main.py` (script) — CLI entry, `run_blocking()`
- [Desktop Entry Point](gui_main.md) / `gui/main_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — `start()`/`stop()` from Qt buttons, `state`/`info` polled by a timer

## Classes

### ServerInfo
Snapshot the GUI reads: `mode`, `encoder`, `monitor_width`/`height`, `port`, `token`, `qr_url` (Tailscale-preferred), `lan_url`, `tailscale_ip`, live `ServerStats` (client count).

### ServerController
One instance per process; states `"stopped" → "starting" → "running" → "stopped"`, or `"failed"` with `.error` set — the GUI polls this, never silent.

`self.loop` is the server's own asyncio loop, published while it runs (`None` otherwise) so code on OTHER threads can reach a connected phone. Exactly one caller today: [Update Handover](update_handover.md)'s last message before the process exits — the Qt thread has no other way to speak to a WebSocket.

- `start()` — non-blocking, spawns a daemon thread running `asyncio.run(_serve(gen))`; no-op while already alive
- **`self._generation` — only the CURRENT run may touch shared state.** `stop()` gives up after its timeout and clears `_thread` (by design: a drain that will not finish must never hold the owner hostage), so a run can outlive its own stop — his log of 2026-08-09 has run A unwinding at `19:15:52`, 38 s after run B was already serving. Unguarded, that ghost's own teardown wrote `state = "stopped"` over a running server (the STOPPED pill he photographed under a live phone), called `release_windows()` on the LIVE layout and shut the LIVE encoder down. Every run now carries the number `start()` gave it; `_run` writes `stopped`/`failed` only while it is still that number, and `_serve`'s `finally` clears `_uvicorn`/`loop` and releases windows only then — a superseded run logs a warning and tears down nothing but its own stream. Gate: `tests/test_server_generation.py`, fail-closed in `build.py` (0x/6), each defence proven by planting its own defect.
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
