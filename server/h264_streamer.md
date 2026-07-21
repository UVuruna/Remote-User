# H.264 Streamer

**Script:** [H.264 Streamer (script)](h264_streamer.py)

## Purpose
The primary streaming path: a live **H.264** stream encoded by ffmpeg (hardware when available), output as **fragmented MP4 (fMP4)** that the browser/WebView decodes with Media Source Extensions. Inter-frame compression makes a static screen nearly free — measured live on the same mostly-static screen: **~3.6 Mbps at native 4K** (3840×2160) and ~1.5 Mbps at 1600×900, versus **~37 Mbps** for JPEG at 1600×900. Native resolution is the default (`h264_max_width`) — zoom stays sharp with no region streaming.

**One ffmpeg process per client.** One [Screen Capture](capture.md) `RawFrameSource` grabs and downscales each frame once; every connected client runs its own `H264Session`. That gives each stream a fresh init segment and keyframe at connect time — no mid-stream joining problem — and a slow client resets alone without disturbing others. Hardware encoder sessions are cheap; the encoder itself is verified once at startup by [Encoders](encoders.md).

## How a session flows

```
OPEN:  spawn ffmpeg (rawvideo stdin → fMP4 stdout, unbuffered pipes)
       register a FrameSink with the shared RawFrameSource
       accumulate stdout until the init segment (ftyp+moov) is complete
       parse the avcC box → codec string "avc1.PPCCLL" → client's config
STREAM: feed thread — newest frame from the sink → ffmpeg stdin
        read thread — every flushed fMP4 fragment → on_data (→ WebSocket)
END (stop / ffmpeg exit / parse error): on_end fires exactly once
        → the web layer closes the session and opens a fresh one
```

The codec string is **parsed from the actual stream, never guessed** — whatever profile/level the chosen encoder produced is exactly what the client passes to `addSourceBuffer`.

## Classes

### H264Session
One client's encoder. `start()` blocks until the init segment is parsed (raises after `h264_head_timeout` — the web layer turns that into a toast + close). `stop()` is idempotent, fast, and callable from any thread: detach sink, close stdin, terminate ffmpeg; daemon threads unwind on their own and fire `on_end` once.

- fMP4 flags: `frag_keyframe+empty_moov+default_base_moof`, `-frag_duration` below one frame interval and `-flush_packets 1` — one promptly-flushed fragment per encoded frame (latency)
- `bufsize=0` on the pipes so each fragment is read the moment ffmpeg flushes it (a buffered pipe would batch 32 KB before returning — ~130 ms of hidden latency at 2 Mbps)

### H264Manager
What the [Web Layer](web.md) talks to (duck interface shared with `JpegStreamer`; `mode = "h264"`):

- `open_session(on_data, on_end)` / `close_session(session)`: session registry; capture **starts with the first client and stops with the last** — nothing runs while nobody is watching
- `switch_to(index)`: ends every session (owners reopen automatically and resend `config`) and swaps the capture monitor
- `take_screenshot()`, `width/height/monitor_index`, `output_count()`: delegated to the source
- `shutdown()`: server teardown

## Connections

### Uses
- [Config](config.md) — fps, bitrate, GOP, fragment size, head timeout
- [Encoders](encoders.md) — chosen encoder + its low-latency args
- [Screen Capture](capture.md) — `RawFrameSource` + `FrameSink`

### Used by
- [Main](main.md) — constructs the manager when an encoder is verified
- [Web Layer](web.md) — per-connection session loop

## Notes
- Region-of-interest streaming (send only the zoomed area) is intentionally dropped on this path — inter-frame compression already makes the full-frame stream cheap, so the crop/re-init complexity is not worth it. The JPEG fallback keeps it.
- Frames the sink drops (encoder slower than capture) compress the video timeline slightly; the client chases the live edge, so this never accumulates as latency.
