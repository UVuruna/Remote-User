# Screen Streamer

**Script:** [Screen Streamer (script)](capture.py)

## Purpose
Owns the capture thread: grabs frames from the selected monitor via dxcam (DXGI Desktop Duplication), downscales when the monitor is wider than `max_stream_width`, encodes to JPEG (OpenCV), and hands bytes to a callback. This is a hot path — no per-frame allocations beyond what encoding requires.

## Connections

### Uses
- [Config](config.md) — monitor index, fps, quality, downscale cap

### Used by
- [Main](main.md) — constructs it with `FrameHub.push_threadsafe` as the callback

## Classes

### ScreenStreamer

#### Attributes
- `width`, `height`: native pixel size of the captured monitor (used by the injector for coordinate mapping — always the real size, never the downscaled stream size)

#### Methods
- `start()`: begins dxcam video-mode capture and the encode loop thread
- `stop()`: joins the thread and releases the camera
- `_loop()`: capture → optional `cv2.resize` (INTER_AREA) → `cv2.imencode` → callback
