# H.264 Streamer

**Script:** [H.264 Streamer (script)](../h264_streamer.py) ·
**Flow:** [diagram](../__flow/h264_streamer.md)

## Purpose
The primary streaming path: a live H.264 stream encoded by ffmpeg (hardware when available), output as fragmented MP4 (fMP4) that the browser/WebView decodes with Media Source Extensions. Inter-frame compression makes a static screen nearly free — the project [CLAUDE.md](../../CLAUDE.md) records ~3.6 Mbps at native 4K vs ~37 Mbps for JPEG on the same mostly-static screen. Native resolution streams by default (`h264_max_width`); zoom stays sharp with no region-of-interest cropping needed on this path.

**One ffmpeg process per client.** One [Screen Capture](capture.md) `RawFrameSource` grabs and downscales each frame once; every connected client runs its own `H264Session` with a personal ffmpeg process, so each stream gets a fresh init segment and keyframe at connect time — no mid-stream-joining problem — and a slow client resets alone without disturbing others. The encoder itself is chosen once at startup by [Encoders](encoders.md); a hardware session is cheap to spin up per client.

## Connections

### Uses
- [Config](config.md) — target fps, bitrate, GOP, fragment size, head timeout, queue depth
- [Encoders](encoders.md) — the chosen encoder name + its low-latency ffmpeg args
- [Screen Capture](capture.md) — `RawFrameSource`, `FrameSink`

### Used by
- [Server Core](server_core.md) — constructs `H264Manager(encoder)` when `encoders.detect_encoder()` finds one
- [Web Layer](web.md) — the per-connection `_stream_h264` session loop

## Classes

### H264Session
One client's encoder: frames from a personal `FrameSink` → ffmpeg stdin (rawvideo), fMP4 chunks from stdout → `on_data`. `on_end` fires exactly once when the stream ends (`stop()`, ffmpeg exit, or a parse error) — the web layer reacts by opening a fresh session.

- `start()`: spawns ffmpeg (unbuffered pipes, `bufsize=0` — so each flushed fragment is read the moment it is written, not batched behind a 32 KB buffer) and blocks until the init segment is parsed; raises `RuntimeError` after `h264_head_timeout` with no head
- `stop()`: idempotent, callable from any thread — detaches the sink, closes stdin, terminates ffmpeg; the daemon threads unwind on their own
- fMP4 flags: `frag_keyframe+empty_moov+default_base_moof`, `-frag_duration` below one frame interval, `-flush_packets 1` — one promptly-flushed fragment per encoded frame

### H264Manager
What the [Web Layer](web.md) talks to (duck interface shared with `JpegStreamer`; `mode = "h264"`):

- `open_session(on_data, on_end)` / `close_session(session)`: session registry; capture starts with the first client and stops with the last — nothing runs while nobody is watching
- `switch_to(index)`: ends every session (owners reopen automatically and resend `config`) and swaps the capture monitor
- `take_screenshot()`, `width` / `height` / `monitor_index`, `output_count()`: delegated to the source
- `shutdown()`: server teardown — ends every session and stops capture

## Module functions
- `_moov_end(buf)`: byte length of the complete init segment (through `moov`) if fully buffered, else 0 — walks top-level MP4 boxes; raises on a malformed box
- `_codec_string(head)`: the MSE `avc1.PPCCLL` string read from the `avcC` box inside `moov` — parsed from the actual stream, never guessed, so it matches whatever profile/level the chosen encoder produced

## Notes
- Region-of-interest streaming (send only the zoomed area) is intentionally dropped on this path — inter-frame compression already makes the full-frame stream cheap, so the crop/re-init complexity isn't worth it. The JPEG fallback keeps it.
- Frames the sink drops (encoder slower than capture) compress the video timeline slightly; the client chases the live edge, so this never accumulates as latency.

## Per-client quality overrides (owner 2026-08-05, growing the 2026-08-02 full/reduced pair)
`H264Session(quality={"fps", "res", "bitrate"})` builds the `-vf` chain and
bitrate INSIDE that client's own ffmpeg — capture and other clients untouched:
`res` `"2/3"`/`"1/2"` scales both axes (`trunc(iw*n/d/2)*2` keeps dimensions
even for yuv420p; half per axis = quarter pixels, hence ⅔ as the middle
step), `fps` < `target_fps` appends an `fps=` filter, and `bitrate` goes
through `config.bitrate_for_level` — `"high"` is the desktop's own bitrate,
`"mid"`/`"low"` are PERCENTAGES of it (`h264_bitrate_mid_pct` /
`_low_pct`). Percentages, not the old absolute `"5M"`/`"1200k"`: fixed
numbers meant the desktop Bitrate combo applied only while the phone sat on
"High", so picking "Mid" silently discarded the PC's choice — half of the
owner's 2026-08-05 "the desktop settings do nothing" report. `"high"`/`0`/
`"full"` all mean "no override — the desktop Settings defaults". The base the
phone displays is published as `config.base` (`_stream_base` in web.py, fed
by `H264Manager.stream_size`). The web layer resets the running session
when the client's `quality` message changes the dict; the loop reopens with
the new settings (same machinery as a monitor switch). Legacy
`quality {reduced: true}` maps in web.py to the saving profile.
