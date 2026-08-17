# Screen Capture

**Script:** [Screen Capture (script)](../capture.py) ·
**Flow:** [diagram](../__flow/capture.md)

## Purpose
Owns dxcam (DXGI Desktop Duplication) — the one place in the project that touches the camera. `BaseCapture` carries everything every streaming path needs (camera lifecycle, the capture thread, screenshots, monitor switching, downscale math); two front-ends specialize it for the two streaming modes. dxcam allows only one camera instance per output, so exactly one front-end exists per process — [Server Core](server_core.md) picks JPEG or H.264 at startup depending on whether an encoder was verified.

## Connections

### Uses
- [Config](config.md) — monitor index, target fps, JPEG quality, downscale cap
- [Capture Recovery](capture_recovery.md) — the abandon/re-enumerate rungs `rebuild_camera()` drives

### Used by
- [Server Core](server_core.md) — constructs `JpegStreamer` when no H.264 encoder exists
- [H.264 Streamer](h264_streamer.md) — `H264Manager` owns a `RawFrameSource`; each `H264Session` registers a `FrameSink`

## Classes

### BaseCapture
Camera lifecycle + the capture thread + the screenshot service. Subclasses implement `_process(frame)`, called from the capture thread for every grabbed frame.

- `width`, `height`, `monitor_index`: native pixel size of the captured monitor (the injector maps coordinates against this — never the stream size)
- `start()` / `stop()`: dxcam video-mode capture + the `_loop` thread; `start()` resets-and-retries once when dxcam refuses with "Capture is already running" (a `stop()` racing a fast reconnect left the internal flag set and killed the NEW session — live 2026-07-29); when the RESET itself cannot work — the camera's own thread is parked and cannot be stopped (the owner's blue screen, below) — `start()` escalates straight to `rebuild_camera()` instead of raising the identical error a second time; `stop()` tolerates dxcam's bare raise on double-stop
- `switch_monitor(index)`: swaps the camera (call while stopped); failure keeps the previous camera
- `output_count()`: static — how many outputs dxcam sees
- `take_screenshot(timeout=2.0)`: full-monitor native-resolution copy of the next captured frame; blocking (worker threads only)

### JpegStreamer
The fallback path (used when no H.264 encoder/ffmpeg exists): crop to the client viewport → downscale → JPEG-encode → `on_frame(jpeg, region)` callback. `mode = "jpeg"` is the duck-interface discriminator the web layer branches on.

- `set_viewport(x, y, w, h)`: monitor-normalized region the client wants (region-of-interest streaming — sharp zoom at constant bandwidth); clamped to the monitor bounds; the tuple write is atomic (single writer, no lock needed)
- `switch_to(index)`: stop → swap monitor → start, as the one blocking operation the web layer calls

### FrameSink
Latest-frame handoff to one encoder session. The capture thread `offer()`s every frame's raw **I420** bytes (task 130 — see `RawFrameSource._process`); the consumer `take(timeout)`s the newest and misses the rest. Drops happen BEFORE encoding, so the encoded output stream never corrupts — this is what lets a slow encoder session lag without affecting others.

### RawFrameSource
The H.264 front-end: resizes each captured frame once (to `stream_w`×`stream_h`, capped at the encoder width and even-rounded for yuv420), converts it to **I420**, and offers the same immutable bytes to every registered sink.

- `_process(frame)`: resize → `cv2.cvtColor(..., COLOR_BGR2YUV_I420)` → `tobytes()`. I420 is FASTER than bgr24, not merely smaller (task 130, measured on the owner's own 4K monitor: 4.30 ms vs 5.56 ms per frame, 12.44 MB vs 24.88 MB) — the copy dominates, so halving the bytes more than pays for a conversion ffmpeg was doing in swscale on the CPU anyway. One decision with the `-pix_fmt yuv420p` INPUT flag in [H.264 Streamer](h264_streamer.md); a mismatch does not fail, it produces a picture in the wrong colours.
- `_stream_size()`: monitor size capped at `max_width`, even-rounded, never upscaled. The shipped default is **2560** (task 130): at 4K60 that is 0.33 GB/s of raw pixels instead of 1.49, which is the starvation the phone's `behind` went negative behind (task 151). The honest cost: H.264 always streams the full frame, so this also caps what a deep client-side zoom can resolve. Screenshots are unaffected (native, straight off the camera).
- `raise_limits(fps, width)`: THE PHONE MAY RAISE THE CEILING (owner decision, task 131). The desktop card is a DEFAULT, not a wall — lowering is free (it lives in the client's own ffmpeg), raising needs the shared camera to grab faster or wider. Returns True when capture must be rebuilt; `None`/`None` hands the desktop its numbers back. Safe because one device at a time is a hard rule (4409).
- `capture_fps` / `max_width`: the desktop's numbers, or the higher ones a client raised them to
- `add_sink(sink)` / `remove_sink(sink)`: session registration (lock-guarded list)
- `stream_w`, `stream_h`: the encoded size, recomputed on monitor switch and on every raise

## The frame clock and the rebuild ladder (owner's blue screen, 2026-08-16)

He connected, built a layout, everything on the control path worked — and the canvas stayed blue the whole time. dxcam's DXGI duplication had lost access (`0x887A0026`) and then parked its own recovery thread in a bare retry loop that never gives up and never checks a stop flag; it reports the failure at INFO to its own logger, so from the outside a dead camera looks exactly like a healthy idle one. Full mechanism and log: [Capture Recovery](capture_recovery.md).

`BaseCapture` now keeps its own honest clock instead of trusting dxcam to say anything:

- `_last_frame_ts`: stamped at every real frame (`_loop`) and at every fresh `start()` — a fresh start is not a stall
- `frame_age()`: seconds since the last frame really arrived — the one fact [Capture Recovery](capture_recovery.md)'s `CaptureGuard` judges by
- `rebuild_camera(_already_stopped=False)`: REPLACES the camera without asking the old one for permission. Ends only the local `_loop` thread (never the camera's own `stop()`, which is the ten-second join that cannot succeed against a parked thread — that is exactly what this escapes), then hands the old camera to `capture_recovery.abandon_camera()` and tries a plain reopen; if that fails, `capture_recovery.reenumerate_dxgi()` rebuilds dxcam's factory and it tries once more. Returns True only when a camera that genuinely produced a frame is in place — proven by `_fresh_camera()` calling `grab()`, not merely constructing one. `rebuild_lock`-guarded and safe to call from `start()`'s own escalation or from the guard's thread.
- `_on_geometry_changed()`: hook for front-ends (`RawFrameSource`) that cache sizes derived from the monitor, so a rebuilt camera's dimensions propagate even though nothing else about the pipeline changed

`CaptureGuard` (in [Capture Recovery](capture_recovery.md)) is the thread that watches `frame_age()` and calls `rebuild_camera()` — owned by [H.264 Streamer](h264_streamer.md)'s `H264Manager`, not by `BaseCapture` itself, so the phone can be told through the same manager that owns the socket.

## Monitor ownership — `_OWNERS` (task 193)
dxcam's factory is a **singleton per output**: a second `dxcam.create(0)` does not create anything, it hands back the camera the first caller still holds. That is the desktop half of "changing the bitrate kills the whole app" — `Apply & restart` gives the old server thread 10 s and then builds the new one anyway, so the new `RawFrameSource` inherits the dying run's camera and is then stopped by that run's own `finally`. Dated in his log, 2026-08-11 00:32:48–58.

So ownership is explicit: `_open()` **evicts** whoever still holds the monitor before creating, and `close()` **releases** the dxcam instance — releasing being the only thing that makes the factory build a genuinely new camera.

- `close()`: stop AND release, idempotent, safe from any thread. Distinct from `stop()`, which is the IDLE cycle (nobody watching; the instance is deliberately kept for the client seconds away).
- `start()` on a closed capture raises — a superseded run must never steal the monitor back from the live server.

## `on_display_change(diff)` — a monitor arrived, or the one we capture left

Subscribed by [Server Core](server_core.md) to the process's one
[Display Watch](display_watch.md). Two duties, and neither is the other's:

1. **Re-enumerate.** `dxcam.DXFactory` builds its `Output` objects ONCE, at
   import, for the life of the process (constraint 30, measured — it cost a
   3.8-hour dead picture). A monitor plugged in after start is therefore
   invisible to every `dxcam.create()` this process will ever make until the
   factory is rebuilt. `capture_recovery.reenumerate_dxgi()` is that rebuild
   and it already existed for constraint 30 — this is its second **caller**,
   never a second copy. A re-enumeration that does not happen is logged rather
   than swallowed: the new monitor stays invisible until a restart, and that
   is worth a line in his log.

2. **Move the picture.** When the monitor being CAPTURED is one of the ones
   that vanished, waiting for [Capture Recovery](capture_recovery.md)'s
   `CaptureGuard` means waiting out `STALL_SECONDS` on a camera whose output
   is never coming back. Capture is moved to a surviving monitor instead —
   never to an index that just went — and WHICH monitor is said out loud,
   because a picture that silently changes what it shows is its own bug
   report. `switch_monitor` documents "must be called while stopped", so the
   JPEG front-end's own `switch_to` is used where it exists and the same three
   steps are taken around it where it does not.

Never raises: one bad subscriber must not silence the others
(`display_watch`'s own rule).

Gate: `tests/test_log_wiring.py` (0b24/6) — including the other half, that a
change sparing the captured monitor moves nothing at all.
