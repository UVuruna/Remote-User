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
- [Capture Recovery](capture_recovery.md) — `CaptureGuard`, watching the source's frame clock and running the rebuild ladder when it stalls

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
- `open_session(on_data, on_end, quality, owner, region, panel)` / `close_session(session)`: session registry; capture starts with the first client and stops with the last — nothing runs while nobody is watching. A session whose claim is already released, or one that finished starting after `shutdown()`, is closed and never registered. `region` is the focused layout's monitor-normalized rect — the session CROPS to it (below); `panel` is the device's real panel pixels from `auth` — a CEILING on the encoded size (the panel cap, below)
- `hold_source(hold)` / `release_source(hold)`: "I am between sessions and I am opening another one right now" — capture keeps running even though `_sessions` is momentarily empty. It exists because a quality change can only be applied by a NEW ffmpeg (a bitrate lives inside the running one's flags), and with one client — "one device at a time" is a hard rule — closing the old session emptied `_sessions`, so dxcam was torn down and rebuilt for a change that never touched capture. The new encoder then had NO FRAMES, and ffmpeg cannot write an init segment before it has encoded one: past `h264_head_timeout` the open raised and the whole socket died (owner report 2026-08-10; his log at 20:30:21 shows the close and the `Frame buffer build(start)` on the same millisecond, and the failure 21 s later). Idempotent by construction — a SET of tokens, not a count, so no caller can leak or double-release one — and `release_source` attempts the stop **without waiting for `_lock`**, because it runs on the event loop, sometimes mid-cancellation, while `open_session` can hold that lock for as long as an encoder takes to start. Skipping is safe: every exit of `open_session` either registers a session (capture must run) or calls `_stop_source_if_idle` itself. A hold is NEVER a substitute for a session — only a live stream loop may take one, and `_stream_h264` gives it back on every way that loop can end
- `switch_to(index)`: ends every session (owners reopen automatically and resend `config`) and swaps the capture monitor. Stops the source DIRECTLY, so a hold cannot delay a monitor switch or `shutdown()`; only `_stop_source_if_idle` consults holds
- `take_screenshot()`, `width` / `height` / `monitor_index`, `output_count()`: delegated to the source
- `raise_limits(fps, width)`: THE PHONE MAY RAISE THE CEILING (owner decision, task 131). The desktop Settings card is the DEFAULT this client works from; going BELOW it is free (inside this client's own ffmpeg, touching nobody), going ABOVE it needs the shared camera to grab faster or wider — so every session is ended and capture is rebuilt, and THE PICTURE BLINKS ONCE. The phone's quality panel marks every such step with ↑ and says it will blink, before he taps. Affordable for exactly one reason, and it is a design rule rather than luck: **one device at a time** (4409) — there is never a second client whose picture a raise could disturb. Blocking; call via `asyncio.to_thread`. Gate: [`tests/test_quality_raise.py`](../../tests/___tests.md)
- `shutdown()`: server teardown — ends every session, **`close()`s** capture (release, not merely stop: dxcam is a singleton per monitor, so a stopped camera is still the one the next server run is handed — task 193, see [Screen Capture](capture.md) → Monitor ownership), and stays ended (`_shut_down`), because a session already inside `session.start()` on its own thread finishes AFTER `shutdown()` returns

### The blue-screen guard (owner report 2026-08-16)

`H264Manager.__init__` starts one [Capture Recovery](capture_recovery.md) `CaptureGuard` on its `RawFrameSource`, for the manager's whole life — capture can die in a way that raises nothing and logs nothing above INFO (dxcam parks in an endless output-recovery loop), and the only symptom the manager can see is that no frame ever arrives while sessions are open and the canvas stays the phone's blue `--canvas-bg`. Wiring:

- `_picture_is_wanted()`: the guard's `is_wanted` — true only when the manager is not shut down, capture is running, AND somebody is actually watching (a live session, or a hold between two sessions — see `hold_source` above). An idle server with capture deliberately stopped is not a stall, and rebuilding there would be a cure for nothing
- `on_capture_state`: a callable the manager exposes and the **web layer** sets, so the guard's up/down verdicts reach the connected phone's status pill without this module knowing anything about the wire — the same pattern [Capture Recovery](capture_recovery.md)'s `phone_notice` was built for
- `_announce_capture(ok, detail)`: the guard's `on_state` hook — forwards to `on_capture_state` if the web layer is currently listening, silently drops otherwise (nobody connected to tell)

A blue canvas that says nothing was half of what the owner actually lived through: the control path (layouts, app list) never touches capture, so everything else looked healthy while the one thing he wanted was dead and silent. See [Capture Recovery](capture_recovery.md) for the ladder itself and the full log.

Gates: [`tests/test_stream_lifecycle.py`](../../tests/___tests.md), fail-closed in `build.py` (0g/6), [`tests/test_quality_reset.py`](../../tests/___tests.md) for the hold and the re-open policy, [`tests/test_capture_handover.py`](../../tests/___tests.md) for the dxcam handover (task 193), [`tests/test_quality_raise.py`](../../tests/___tests.md) for the raise (task 131), [`tests/test_raw_pixel_cost.py`](../../tests/___tests.md) for the I420 pipe (task 130) and [`tests/test_return_timing.py`](../../tests/___tests.md) for the one-encoder return (task 203).

> **Note on lock scope:** `open_session` holds `_lock` across the blocking ffmpeg spawn, so `shutdown()` from another thread cannot interleave with it — the post-start `_shut_down` check is defence in depth for a future in which that scope narrows, not a path reachable today.

## Module functions
- `_moov_end(buf)`: byte length of the complete init segment (through `moov`) if fully buffered, else 0 — walks top-level MP4 boxes; raises on a malformed box
- `_codec_string(head)`: the MSE `avc1.PPCCLL` string read from the `avcC` box inside `moov` — parsed from the actual stream, never guessed, so it matches whatever profile/level the chosen encoder produced

## The region crop (owner order 2026-08-12)

The "full frame always" rule this path shipped with is GONE — his words:
"zašto bi telefon dekodirao nešto što ne vidi" (lang-ok: owner quote). The
full-frame stream was cheap on the WIRE (inter-frame compression), but the
DECODE it cost the phone was the full monitor's: a quarter-width layout on a
4K desktop still made the device decode 3840×2160@60, which is exactly what
drowned his tablet. `H264Session(region=...)` turns the focused layout's
monitor-normalized rect into a `crop=w:h:x:y` FIRST in this client's own
`-vf` chain (even-aligned by `_crop_rect` — yuv420p subsamples chroma 2×2, so
an odd size fails the encoder and an odd offset shears colours); `session
.region` afterwards holds the even-rounded crop's OWN normalization, which is
what `config.stream_region` tells the page to map the video onto. A crop that
resolves to the whole frame is no crop and no field — an old server's world.
The re-open on region change lives in the web layer (the quality-change
mechanism, reused): `layout_api.send_layout_state` is the choke point. Gate:
`tests/test_region_stream.py`, fail-closed in build.py (0ap/6).

**And since T76 (2026-08-14) the ZOOM feeds a `zoom` argument beside `region`
— NOT the same argument.** The `viewport` message the pinch has always sent
was discarded in H.264 mode, so a zoom magnified pixels that had already been
through the panel cap below, which is exactly the blurry picture the owner
reported.

**Corrected in place, T76 round 3 (2026-08-14).** The paragraph below
described the zoom as NARROWING the crop — feeding `region` a smaller rect
via `layout_api.stream_crop`. That was round 2, shipped and reverted the same
day: with no base layer under a crop-only stream a pan showed the canvas
background, a settled pan rebuilt ffmpeg (a 1–2 s stall) per step with no
throttle, and a decoder error caught in that storm reconnected with the zoom
erased. **The crop the encoder gets is now always exactly the focused
layout's region (or the full frame at the desktop) — `stream_crop(conn)` is
unchanged in what it returns.** What the settled pinch rect drives instead is
a NEW, separate `zoom` argument to `H264Session`/`_scale_size` — a quantized
power-of-two RESOLUTION step (`layout_api.zoom_step`, capped at
`ZOOM_MAX_STEP=8`) that raises the panel ceiling toward native, clamped there.
A pan that keeps the same step rebuilds nothing; only a step CROSSING resets
the session — panning inside a step is free, which round 2's per-pan rebuild
was not. `conn["stream_zoom"]` is the intention copy beside
`conn["stream_region"]`, read at the same choke point. See
[Layout API](layout_api.md) for the derivation and
[Zoom Crop](../../client/__about/zoom-crop.md) for the page's own half.

*(Round 2 reasoning, superseded above but kept as the record of what was
tried.)* "Nothing here changed: the region handed in is now
`layout_api.stream_crop(conn)` — the focused layout's region NARROWED by the
phone's settled visible rect, with the layout's region as a FLOOR the crop
can never widen past."

## The panel cap (owner order 2026-08-12, approved on a ballot)

His words: "what is the point of the PC sending 4K if the Android device
cannot receive it? A Redmi Pad is 1920×1200 and we send it 4K in desktop mode.
It should be downscaled ON THE PC to the resolution the Android device can
accept. And when Android zooms, that is a crop again."

`H264Session(panel={"w":…, "h":…})` — the device's REAL panel pixels, taken
from the `auth` message (`client/connection.js` sends `panel`, CSS px ×
`devicePixelRatio`; a SEPARATE field from `screen`, which stays CSS px and
means an aspect for layout placement — changing that meaning would have made
an older page's message unreadable). `_scale_size` reconciles it with the
phone's own resolution step into ONE size, and the smallest factor wins:

- the resolution step (2/3, 1/2) — unchanged, it just composes here instead
  of emitting a second, competing `scale=` filter;
- the panel's LONG side against the crop's long side, its SHORT against the
  short. Long-to-long because phone rotation is locked to the layout's
  orientation, so the picture's long side really does land on the panel's. For
  his own case — a full 3840×2160 desktop on a 1920×1200 tablet — this IS his
  `min(crop width, panel width)`: 1920 wide;
- **never above 1.** A crop narrower than the panel is sent at its own size:
  upscaling would spend bitrate inventing nothing, and not doing it is why a
  focused layout now comes out SHARPER at the same bitrate.

The height is derived from the chosen width (the crop's aspect is preserved)
and both dimensions are even, for the same yuv420p reason as the crop. The
chosen size is logged once per session beside the crop, so his own server.log
carries the real numbers. No panel field, or a nonsense one, caps nothing —
byte for byte the old command. The page mirrors the same arithmetic in
`client/decode-caps.js` (`panelScaledWidth`) for ONE reason: the decode
ceiling must judge the size that is really encoded. Nothing else on the page
needs it — `render.js` maps the video onto `stream_region` and reads the
video's own intrinsic pixels, so a smaller encode simply arrives smaller.
Gate: `tests/test_panel_scale.py`, fail-closed in build.py (0aq/6).

## Notes
- The zoomed-viewport request (`viewport`) is NO LONGER JPEG-only (T76,
  2026-08-14). It was, and this note said so as though it were a design
  decision — "a zoom is transient; a layout region is a state worth a session
  rebuild" — which is what made the reported blur unfindable for a whole
  round. A zoom the owner has finished is not transient: it is what he is
  looking at. The page now only sends the rect once the gesture has SETTLED
  (client/zoom-crop.js), and both sides refuse a change too small to be worth
  the blink, so the "transient" objection is answered by the settle rather
  than by discarding the message. **What the settled rect drives changed
  between T76's two rounds** (corrected in place, round 3, same day): round 2
  turned it into a NARROWER crop, rebuilt on every settled pan step with no
  base layer under it — condemned live (canvas background showing through a
  pan, a 1–2 s stall per step, a decoder-error storm that erased the zoom on
  reconnect). Round 3 keeps the crop fixed at the layout's region and turns
  the settled rect into a quantized resolution STEP instead — a pan inside
  the same step rebuilds nothing; only a step crossing does.
- Frames the sink drops (encoder slower than capture) compress the video timeline slightly; the client chases the live edge, so this never accumulates as latency.

## Per-client quality overrides (owner 2026-08-05, growing the 2026-08-02 full/reduced pair)
`H264Session(quality={"fps", "res", "bitrate"})` builds the `-vf` chain and
bitrate INSIDE that client's own ffmpeg — capture and other clients untouched:
`res` `"2/3"`/`"1/2"` scales both axes (`trunc(iw*n/d/2)*2` keeps dimensions
even for yuv420p; half per axis = quarter pixels, hence ⅔ as the middle
step), `fps` < `target_fps` appends an `fps=` filter, and `bitrate` goes
through `config.bitrate_for_level` — `"high"` (and `None`) is the desktop's
own bitrate, a ladder rung id is that rung's ABSOLUTE bitrate clamped to the
desktop's, and legacy `"mid"`/`"low"` are translated onto rungs (the
percentages `h264_bitrate_mid_pct` /
`_low_pct` are GONE). The phone offers the SAME four levels the desktop card
does and may pick any one AT OR BELOW the PC's (owner verdict 2026-08-12) —
see [Config](config.md) → The quality ladder. `"high"`/`0`/
`"full"` all mean "no override — the desktop Settings defaults". The base the
phone displays is published as `config.base` (`config.stream_base`, fed
by `H264Manager.stream_size`). The web layer resets the running session
when the client's `quality` message changes the dict; the loop reopens with
the new settings (same machinery as a monitor switch). Legacy
`quality {reduced: true}` maps in web.py to the saving profile.

## The bitrate follows the pixels — on cellular only (T79, 2026-08-14)

His question, in translation: for this house it does not matter that much, but
for MOBILE DATA it is very important that we optimise the BITRATE too.

`-b:v`/`-maxrate` used to be the rung's flat number whatever the encoder was
actually fed, so 20 Mbps on a quarter-size crop was the same ceiling as
20 Mbps on the full 4K. Two things kept that honest and both are stated rather
than glossed over: `-maxrate` is a CEILING, so a static screen still costs its
own ~3.6 Mbps and the waste only appears under motion; and the panel cap above
already equalises a full desktop and a 2×2 cell onto the panel, where the bits
per pixel are IDENTICAL. The overspend lives exactly where the crop falls
BELOW the panel and is therefore sent at its own small size — roughly 2.2× the
reference's bits per pixel — and a small layout crop is exactly that case.

**Corrected in place, T76 round 3 (2026-08-14):** this section originally
read "and the zoom crop (T76) is what turns that from an edge case into the
normal one" — true of round 2, where zooming NARROWED the crop and so pushed
MORE sessions below the panel, toward the floor. Round 3 zoom does the
opposite: it RAISES `_scale_size`'s ceiling (the `zoom` argument to
`_scale_size`, clamped at native — see the crop section above), so encoded
pixels rise toward — and can reach — the reference size as he zooms in, and
`_bitrate`'s factor rises toward 1 (the rung) rather than collapsing toward
the floor. `_reference_size` always asks `_scale_size` with `zoom=1`
specifically so this ratio still means "a full screen on this panel" and is
untouched by the zoom step. The floor still matters for an UNZOOMED small
layout crop; it is no longer what a deep zoom produces.

`H264Session._bitrate()` — the rules, in the owner's order:

- **On Wi-Fi nothing changes.** A focused layout coming out sharper at the
  same nominal quality is a FEATURE (see the panel cap) and it is untouched.
- **"On cellular" is not a new notion.** It is `config.is_data_saver(...)` —
  the saving profile the phone ALREADY sends over the existing path while the
  handset is on cellular (`client/quality.js` `effectiveQuality`, via the
  `Android.transport()` bridge). A `transport` field beside it would be a
  second answer to one question, and the two would drift the first time one of
  them moved. It correctly also covers the owner picking Data saver by hand.
- **The factor is encoded pixels over reference pixels**, where the reference
  is "a full screen on this panel" — `_reference_size()` asks the SAME
  `_scale_size` about the uncropped frame, so the client's own resolution step
  is inside both sides of the ratio and cancels. A full-screen Data saver
  session comes out at factor 1.0 and is byte for byte what it is today, which
  is what keeps the ladder's rungs meaning what they say.
- **Downward only, in ONE place.** The ratio is deliberately not pre-clamped
  to 1; there is a single `min` against the rung's own number, so the rule the
  phone may never break (task 131 — it may not raise the bitrate) is enforced
  where a gate can drive it. A second clamp would make that one unreachable
  and therefore unprovable.
- **A floor**, `BITRATE_FLOOR_BPS` = 800 kbps, so a small UNZOOMED crop
  cannot collapse into mush. It is a JUDGEMENT and is stated as one: at his
  own quarter-width layout (484×1048 at 10 fps) 800 kbps is ~0.16 bits per
  pixel per frame, nearly double the ~0.096 the reference full screen gets at
  the same rung — the generous end, not the marginal one. Expect it to be
  tuned on the real device. **Corrected in place, T76 round 3 (2026-08-14):**
  this floor was written to also cover "a deep zoom", back when zooming
  narrowed the crop and pushed it further below the floor. Round 3 zoom
  instead RAISES encoded pixels toward the reference as he zooms in, so a
  deep zoom now pushes the factor UP toward the rung, not down toward this
  floor — the floor's remaining job is the unzoomed small-crop case alone.
- **Logged.** The applied number and the factor ride the session's own log
  line beside the crop and the scale, because a bitrate that is never printed
  cannot be told apart from a bitrate that was simply not spent.

Measured, 3840×2160 source on a 1920×1200 panel, saving profile (10 fps,
½, `saver` = 2 Mbps): full screen → 1920×1080, ×1.000, 2,000,000 bps
(unchanged); his own quarter-width layout, UNZOOMED → 484×1048, ×0.244,
800,000 bps (the floor). **Corrected in place, T76 round 3 (2026-08-14):**
this line originally ended "a deep zoom → the same 800,000 bps floor" — that
was round 2, where zooming narrowed the crop further below the floor. Round
3 zoom raises the encoded size instead (`_scale_size`'s `zoom` argument), so
a deep zoom on that same quarter-width layout pushes the factor UP toward
the rung's own 2,000,000 bps as the resolution step climbs, never down
toward the floor. On Wi-Fi every one of those is the rung's own number,
untouched. Gate: `tests/test_zoom_crop.py`, fail-closed in `setup/gates.py`
(0b13/6).

**The re-open is the whole cost of a quality change, and it used to be paid
with the connection** (owner report 2026-08-10, his #1: changing the bitrate
brought the app down). Since then the gap is held (`hold_source`, above) so
capture is never recycled for it, and a re-open that still fails is retried
`h264_reopen_tries` times before the socket is given up — see
[Web Layer](web.md) → `_h264_loop`.
