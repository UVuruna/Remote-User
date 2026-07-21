# Screen Streamer

**Script:** [Screen Streamer (script)](capture.py)

## Purpose
Owns the capture thread: grabs frames from the selected monitor via dxcam (DXGI Desktop Duplication), crops to the client's current viewport (region-of-interest streaming — sharp zoom at constant bandwidth), downscales when the result is wider than `max_stream_width`, encodes to JPEG (OpenCV), and hands bytes + covered region to a callback. This is a hot path — no per-frame allocations beyond what cropping/encoding requires.

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
- `set_viewport(x, y, w, h)`: monitor-normalized region the client wants; clamped; tuple write is atomic (single writer, no lock)
- `switch_monitor(index)`: swaps the capture source (call while stopped); `output_count()` reports how many outputs dxcam sees
- `take_screenshot()`: full-monitor native-resolution copy of the next frame (blocking — worker threads only)
- `_crop(frame)`: applies the viewport with a minimum-size guard; returns the frame slice + the actual normalized region
- `_loop()`: capture → crop → optional `cv2.resize` (INTER_AREA) → `cv2.imencode` → callback(jpeg, region)
