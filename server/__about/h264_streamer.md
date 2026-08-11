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

### SessionOwner — the claim (live failure 2026-08-07)
One consumer's claim on one session, and the reason "nothing runs while nobody is watching" is now enforceable.

`await asyncio.to_thread(manager.open_session, …)` **cannot be cancelled.** Cancelling the awaiting task raises `CancelledError` at the `await` immediately, but the worker thread runs on: ffmpeg spawns, `open_session` returns, the session registers — and the coroutine that would have closed it never bound the name, so nothing anywhere could reach it again. The owner's server log dated it to the millisecond:

```
12:05:11,822  Client authenticated: port=56482
12:05:12,730  dxcam: Frame buffer build(start): 3840x2160    <- open_session, in the thread
12:05:12,732  Client disconnected: port=56482                <- the task is cancelled here
12:05:12,951  H.264 session opened - 1 active                <- 219 ms too late; the orphan
12:05:21,218  WARNING Client stream backlog - resetting ...  <- and every ~7 s after
```

That orphan held `_sessions` non-empty for four hours (so capture could never stop), reached 12,924 s of ffmpeg CPU at native 4K with no phone connected, and wrote 1,890 backlog warnings — while the owner's mouse juddered at his own desk.

So the claim is created on the CALLER's thread, before the encoder exists, and a mutex settles the race both ways round:

| Order | What happens |
|-------|--------------|
| `take()` then `release()` | the session registers normally; `release()` is what closes it |
| `release()` then `take()` | `take()` refuses; the manager `_abandon`s the session it just built — terminated, never registered, and SAID so in the log |

- `alive`: false once the consumer is gone. The [Web Layer](web.md)'s queue closure reads it, so a session nobody can hear is never "reset" on a dead client's behalf — the **second, independent** defence (either one alone stops the endless reset loop; both are needed, because only the claim stops the session leaking).
- `release()` is idempotent, callable from any thread, and fast enough to run inside a `finally` mid-cancellation. It calls `close_session` OUTSIDE its own lock: the encoder thread holds the manager's lock while calling `take()`, and taking both in the other order here is the one deadlock this design could have.

### H264Manager
What the [Web Layer](web.md) talks to (duck interface shared with `JpegStreamer`; `mode = "h264"`):

- `new_owner()`: a fresh `SessionOwner` for the caller to hand to `open_session`. Must be created on the caller's own thread — that timing IS the defence
- `open_session(on_data, on_end, quality, owner)` / `close_session(session)`: session registry; capture starts with the first client and stops with the last — nothing runs while nobody is watching. A session whose claim is already released, or one that finished starting after `shutdown()`, is closed and never registered
- `hold_source(hold)` / `release_source(hold)`: "I am between sessions and I am opening another one right now" — capture keeps running even though `_sessions` is momentarily empty. It exists because a quality change can only be applied by a NEW ffmpeg (a bitrate lives inside the running one's flags), and with one client — "one device at a time" is a hard rule — closing the old session emptied `_sessions`, so dxcam was torn down and rebuilt for a change that never touched capture. The new encoder then had NO FRAMES, and ffmpeg cannot write an init segment before it has encoded one: past `h264_head_timeout` the open raised and the whole socket died (owner report 2026-08-10; his log at 20:30:21 shows the close and the `Frame buffer build(start)` on the same millisecond, and the failure 21 s later). Idempotent by construction — a SET of tokens, not a count, so no caller can leak or double-release one — and `release_source` attempts the stop **without waiting for `_lock`**, because it runs on the event loop, sometimes mid-cancellation, while `open_session` can hold that lock for as long as an encoder takes to start. Skipping is safe: every exit of `open_session` either registers a session (capture must run) or calls `_stop_source_if_idle` itself. A hold is NEVER a substitute for a session — only a live stream loop may take one, and `_stream_h264` gives it back on every way that loop can end
- `switch_to(index)`: ends every session (owners reopen automatically and resend `config`) and swaps the capture monitor. Stops the source DIRECTLY, so a hold cannot delay a monitor switch or `shutdown()`; only `_stop_source_if_idle` consults holds
- `take_screenshot()`, `width` / `height` / `monitor_index`, `output_count()`: delegated to the source
- `raise_limits(fps, width)`: THE PHONE MAY RAISE THE CEILING (owner decision, task 131). The desktop Settings card is the DEFAULT this client works from; going BELOW it is free (inside this client's own ffmpeg, touching nobody), going ABOVE it needs the shared camera to grab faster or wider — so every session is ended and capture is rebuilt, and THE PICTURE BLINKS ONCE. The phone's quality panel marks every such step with ↑ and says it will blink, before he taps. Affordable for exactly one reason, and it is a design rule rather than luck: **one device at a time** (4409) — there is never a second client whose picture a raise could disturb. Blocking; call via `asyncio.to_thread`. Gate: [`tests/test_quality_raise.py`](../../tests/___tests.md)
- `shutdown()`: server teardown — ends every session, **`close()`s** capture (release, not merely stop: dxcam is a singleton per monitor, so a stopped camera is still the one the next server run is handed — task 193, see [Screen Capture](capture.md) → Monitor ownership), and stays ended (`_shut_down`), because a session already inside `session.start()` on its own thread finishes AFTER `shutdown()` returns

Gates: [`tests/test_stream_lifecycle.py`](../../tests/___tests.md), fail-closed in `build.py` (0g/6), [`tests/test_quality_reset.py`](../../tests/___tests.md) for the hold and the re-open policy, [`tests/test_capture_handover.py`](../../tests/___tests.md) for the dxcam handover (task 193), [`tests/test_quality_raise.py`](../../tests/___tests.md) for the raise (task 131), [`tests/test_raw_pixel_cost.py`](../../tests/___tests.md) for the I420 pipe (task 130) and [`tests/test_return_timing.py`](../../tests/___tests.md) for the one-encoder return (task 203).

> **Note on lock scope:** `open_session` holds `_lock` across the blocking ffmpeg spawn, so `shutdown()` from another thread cannot interleave with it — the post-start `_shut_down` check is defence in depth for a future in which that scope narrows, not a path reachable today.

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
phone displays is published as `config.base` (`config.stream_base`, fed
by `H264Manager.stream_size`). The web layer resets the running session
when the client's `quality` message changes the dict; the loop reopens with
the new settings (same machinery as a monitor switch). Legacy
`quality {reduced: true}` maps in web.py to the saving profile.

**The re-open is the whole cost of a quality change, and it used to be paid
with the connection** (owner report 2026-08-10, his #1: changing the bitrate
brought the app down). Since then the gap is held (`hold_source`, above) so
capture is never recycled for it, and a re-open that still fails is retried
`h264_reopen_tries` times before the socket is given up — see
[Web Layer](web.md) → `_h264_loop`.
