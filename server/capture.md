# Screen Capture

**Script:** [Screen Capture (script)](capture.py)

## Purpose
Owns dxcam (DXGI Desktop Duplication) — the one place that touches the camera. A shared base class carries everything every streaming path needs (camera lifecycle, capture thread, screenshots, monitor switching, downscale math); two front-ends specialize it. Exactly one front-end exists per process (dxcam allows one camera per output) — [Main](main.md) picks JPEG or H.264 at startup.

## Connections

### Uses
- [Config](config.md) — monitor index, fps, quality, downscale cap

### Used by
- [Main](main.md) — constructs `JpegStreamer` when no H.264 encoder exists
- [H.264 Streamer](h264_streamer.md) — `H264Manager` owns a `RawFrameSource`; sessions consume `FrameSink`s

## Classes

### BaseCapture
Camera lifecycle + the capture thread + the screenshot service. Subclasses implement `_process(frame)`, called from the capture thread for every grabbed frame.

- `width`, `height`, `monitor_index`: native pixel size of the captured monitor (the injector maps coordinates against this — never the stream size)
- `start()` / `stop()`: dxcam video-mode capture + the `_loop` thread (stop tolerates dxcam's bare raise on double-stop)
- `switch_monitor(index)`: swaps the camera (call while stopped); failure keeps the old camera
- `output_count()`: how many outputs dxcam sees
- `take_screenshot()`: full-monitor native-resolution copy of the next frame (blocking — worker threads only)

### JpegStreamer
The fallback path (used when no H.264 encoder/ffmpeg exists): crop to the client viewport → downscale → JPEG encode → `on_frame(jpeg, region)` callback. This is a hot path — no per-frame allocations beyond what cropping/encoding requires.

- `set_viewport(x, y, w, h)`: monitor-normalized region the client wants (region-of-interest streaming — sharp zoom at constant bandwidth); clamped; tuple write is atomic (single writer, no lock)
- `switch_to(index)`: stop → swap monitor → start as one blocking operation (what the web layer calls)
- `mode = "jpeg"` — the duck-interface discriminator the web layer branches on

### FrameSink
Latest-frame handoff to one encoder session: the capture thread `offer()`s every frame's raw BGR bytes; the consumer `take()`s the newest and misses the rest. Drops happen **before** encoding, so the encoded stream stays valid — this is what lets a slow encoder lag without corrupting its output.

### RawFrameSource
The H.264 front-end: prepares each captured frame once and offers its bytes to every registered sink.

```
capture thread:  grab frame
                 → resize to stream_w×stream_h if capped (default: native)
                 → ONE tobytes() snapshot (detaches from the dxcam ring buffer;
                   immutable, shared by all sinks — one copy total per frame)
                 → FOR EACH sink: offer(bytes)
```

- `_stream_size()`: monitor size capped at `h264_max_width` (default 3840 — native 4K; H.264 inter-frame compression keeps it cheap and zoom stays sharp), even-rounded for yuv420
- `add_sink(sink)` / `remove_sink(sink)`: session registration (lock-guarded list)
- `stream_w`, `stream_h`: the encoded size — recomputed on monitor switch
