# H.264 Streamer

**Script:** [H.264 Streamer (script)](h264_streamer.py)

## Purpose
The responsive streaming path: captures the monitor with dxcam and encodes a live **H.264** stream via ffmpeg (hardware when available), output as **fragmented MP4 (fMP4)** so the browser/WebView decodes it with Media Source Extensions. Inter-frame compression makes a static screen nearly free — measured ~2 Mbps for a mostly-static 1600×900 screen, versus ~48 Mbps for the JPEG-per-frame path.

Pipeline (three daemon threads around an ffmpeg subprocess):

```
dxcam BGR frame → (downscale to max_stream_width, even dims) → ffmpeg stdin (rawvideo)
   → ffmpeg encodes (auto-detected encoder, low-latency args) → fMP4 on stdout → on_data callback
```

- `_feed_loop`: writes raw frames into ffmpeg stdin
- `_read_loop`: drains fMP4 bytes from stdout to the callback (the stream)
- `_stderr_loop`: logs ffmpeg errors

## Connections

### Uses
- [Config](config.md) — monitor, fps, bitrate, downscale width
- [Encoders](encoders.md) — chosen encoder + its low-latency args

### Used by
- [Main](main.md) / [Web Layer](web.md) — the H.264 path (JPEG streamer is the fallback)

## Classes

### H264Streamer
- `start()` / `stop()`: spawn/kill ffmpeg + capture threads (stop tolerates the stdin-closed-mid-write race)
- `width`/`height`: native monitor size (for input coordinate mapping); `stream_w`/`stream_h`: encoded size (even, downscaled)
- `on_data(bytes)`: fMP4 chunks — append straight to a client MSE SourceBuffer

## Notes
- fMP4 flags: `frag_keyframe+empty_moov+default_base_moof` with `-frag_duration`/`-flush_packets` for small, promptly-flushed fragments (lower latency).
- Region-of-interest streaming (send only the zoomed area) is intentionally dropped here — inter-frame compression already makes the full-frame stream cheap, so the crop/re-init complexity is not worth it.
