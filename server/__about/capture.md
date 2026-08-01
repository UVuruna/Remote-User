# Screen Capture

**Script:** [Screen Capture (script)](../capture.py) ·
**Flow:** [diagram](../__flow/capture.md)

## Purpose
Owns dxcam (DXGI Desktop Duplication) — the one place in the project that touches the camera. `BaseCapture` carries everything every streaming path needs (camera lifecycle, the capture thread, screenshots, monitor switching, downscale math); two front-ends specialize it for the two streaming modes. dxcam allows only one camera instance per output, so exactly one front-end exists per process — [Server Core](server_core.md) picks JPEG or H.264 at startup depending on whether an encoder was verified.

## Connections

### Uses
- [Config](config.md) — monitor index, target fps, JPEG quality, downscale cap

### Used by
- [Server Core](server_core.md) — constructs `JpegStreamer` when no H.264 encoder exists
- [H.264 Streamer](h264_streamer.md) — `H264Manager` owns a `RawFrameSource`; each `H264Session` registers a `FrameSink`

## Classes

### BaseCapture
Camera lifecycle + the capture thread + the screenshot service. Subclasses implement `_process(frame)`, called from the capture thread for every grabbed frame.

- `width`, `height`, `monitor_index`: native pixel size of the captured monitor (the injector maps coordinates against this — never the stream size)
- `start()` / `stop()`: dxcam video-mode capture + the `_loop` thread; `start()` resets-and-retries once when dxcam refuses with "Capture is already running" (a `stop()` racing a fast reconnect left the internal flag set and killed the NEW session — live 2026-07-29); `stop()` tolerates dxcam's bare raise on double-stop
- `switch_monitor(index)`: swaps the camera (call while stopped); failure keeps the previous camera
- `output_count()`: static — how many outputs dxcam sees
- `take_screenshot(timeout=2.0)`: full-monitor native-resolution copy of the next captured frame; blocking (worker threads only)

### JpegStreamer
The fallback path (used when no H.264 encoder/ffmpeg exists): crop to the client viewport → downscale → JPEG-encode → `on_frame(jpeg, region)` callback. `mode = "jpeg"` is the duck-interface discriminator the web layer branches on.

- `set_viewport(x, y, w, h)`: monitor-normalized region the client wants (region-of-interest streaming — sharp zoom at constant bandwidth); clamped to the monitor bounds; the tuple write is atomic (single writer, no lock needed)
- `switch_to(index)`: stop → swap monitor → start, as the one blocking operation the web layer calls

### FrameSink
Latest-frame handoff to one encoder session. The capture thread `offer()`s every frame's raw BGR bytes; the consumer `take(timeout)`s the newest and misses the rest. Drops happen BEFORE encoding, so the encoded output stream never corrupts — this is what lets a slow encoder session lag without affecting others.

### RawFrameSource
The H.264 front-end: resizes each captured frame once (to `stream_w`×`stream_h`, capped at `h264_max_width` and even-rounded for yuv420) and offers the same immutable bytes to every registered sink.

- `_stream_size()`: monitor size capped at `h264_max_width` (default 3840 — native 4K), even-rounded
- `add_sink(sink)` / `remove_sink(sink)`: session registration (lock-guarded list)
- `stream_w`, `stream_h`: the encoded size, recomputed on monitor switch
