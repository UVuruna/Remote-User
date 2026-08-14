"""H.264 streaming: one shared capture, one ffmpeg process per client.

`RawFrameSource` grabs and downscales each frame once. Every connected client
runs its own `H264Session` — a personal ffmpeg process — so each stream begins
with a fresh init segment and a keyframe: no mid-stream joining problem, and a
slow client resets alone without disturbing others. Hardware encoder sessions
are cheap; the encoder itself is detected once at startup (see Encoders).

Session output is fragmented MP4 (fMP4): `ftyp`+`moov` head first — the MSE
init segment, from whose `avcC` box the exact `avc1.PPCCLL` codec string is
parsed (never guessed) and sent to the client in `config` — then one
`moof`+`mdat` fragment per encoded frame.

`H264Manager` is what the web layer talks to: it tracks sessions, starts
capture when the first client arrives and stops it when the last one leaves
(nothing runs while nobody is watching), and orchestrates monitor switching.

`SessionOwner` is the rule that "nothing runs while nobody is watching" is
allowed to depend on — see its docstring for the live failure that proved a
plain `open_session()/close_session()` pair cannot carry it.
"""

import logging
import subprocess
import threading

import config
import encoders
from capture import FrameSink, RawFrameSource
from config import SETTINGS

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000
READ_CHUNK = 32768
# The lowest `-b:v` the cellular bitrate rule may ever ask for (T79). A
# JUDGEMENT, stated as one — see `H264Session._bitrate` for why 800 kbps is
# the generous end rather than the marginal one, and expect the owner to tune
# it on the real device.
BITRATE_FLOOR_BPS = 800_000
FEED_POLL_S = 0.5  # how often the feed thread re-checks _running while frames stall


def _moov_end(buf: bytes) -> int:
    """Byte length of the complete init segment (through the end of `moov`) if
    fully present in buf, else 0. Walks top-level MP4 boxes."""
    pos = 0
    while pos + 8 <= len(buf):
        size = int.from_bytes(buf[pos:pos + 4], "big")
        if size < 8:
            raise RuntimeError(f"Malformed MP4 box (size {size}) in ffmpeg output")
        if pos + size > len(buf):
            return 0
        if buf[pos + 4:pos + 8] == b"moov":
            return pos + size
        pos += size
    return 0


def _codec_string(head: bytes) -> str:
    """MSE codec string ("avc1.PPCCLL") read from the avcC box inside the moov.
    The client passes it to addSourceBuffer — parsed from the actual stream, so
    it is right for whatever profile/level the chosen encoder produced."""
    i = head.find(b"avcC")
    if i < 0 or i + 8 > len(head):
        raise RuntimeError("No avcC box in the ffmpeg init segment — cannot derive codec string")
    profile, compat, level = head[i + 5], head[i + 6], head[i + 7]
    return f"avc1.{profile:02X}{compat:02X}{level:02X}"


class H264Session:
    """One client's encoder: frames from a personal FrameSink → ffmpeg stdin,
    fMP4 chunks from stdout → on_data. on_end fires exactly once when the
    stream is over (stop(), ffmpeg exit, or a stream error) — the web layer
    reacts by opening a fresh session."""

    def __init__(self, source: RawFrameSource, encoder: str, on_data, on_end,
                 quality: dict | None = None, region: dict | None = None,
                 panel: dict | None = None):
        """on_data(bytes) / on_end() are called from the read thread and must
        be cheap and thread-safe (the web layer bridges them to asyncio).
        quality = this client's overrides from the phone's quality panel
        (owner spec 2026-08-05): {"fps": int, "res": "full"|"2/3"|"1/2",
        "bitrate": "high"|"mid"|"low"}. fps 0 / "full" / "high" mean "no
        override" — the desktop Settings defaults apply. None = all defaults.
        region = the monitor-normalized rect of the focused layout (owner
        order 2026-08-12: the phone must never decode pixels it does not
        show) — this encoder crops to it; None/full-frame means no crop.
        `self.region` afterwards holds the EFFECTIVE normalized rect of the
        even-rounded pixel crop (what `config.stream_region` tells the page),
        or None when nothing is cropped.
        panel = this device's REAL panel pixels, {"w": int, "h": int}, from
        the `auth` message (owner order 2026-08-12: "what is the point of the
        PC sending 4K if the Android device cannot receive it"). It is a
        CEILING on the encoded size — see `_scale_size`. None (an older page,
        a browser that sends no panel) means exactly the old behaviour."""
        self._source = source
        self._encoder = encoder
        self._on_data = on_data
        self._on_end = on_end
        self._quality = quality or {}
        self._sink = FrameSink()
        self._proc: subprocess.Popen | None = None
        self._running = False
        self._ended = threading.Event()
        self._head_ready = threading.Event()
        self._head_error: str | None = None
        self.codec: str | None = None
        self.width, self.height = source.stream_w, source.stream_h
        self._crop = self._crop_rect(region)
        self.region = ({"x": self._crop[2] / self.width,
                        "y": self._crop[3] / self.height,
                        "w": self._crop[0] / self.width,
                        "h": self._crop[1] / self.height}
                       if self._crop else None)
        self._panel = self._panel_size(panel)
        src = self._crop[:2] if self._crop else (self.width, self.height)
        self._scale = self._scale_size(*src)
        # What the encoder is really told to spend, and why (T79) — computed
        # here so `open_session` can LOG both beside the crop and the scale.
        # NOT precomputed into plain attributes. `_ffmpeg_cmd` needs this, and
        # binding it in `__init__` made the command depend on construction
        # ORDER rather than on the session's own inputs — which broke two
        # unrelated gates at once (`test_raw_pixel_cost.py`,
        # `test_quality_raise.py`) because both legitimately build a session
        # with `__new__` and set only the fields their subject needs. Two gates
        # failing on one coupling is a design answer, not a test problem: the
        # bitrate is DERIVED from `_quality`, `_crop`, `_scale` and the panel,
        # so it is a property over those, cached once because `_bitrate` is
        # asked for the command and again for the log and must give the same
        # answer to both.
        self._bitrate_cache: tuple[str, float] | None = None

    def _crop_rect(self, region: dict | None) -> tuple[int, int, int, int] | None:
        """(w, h, x, y) of the pixel crop on the encoded frame, or None for a
        full frame. Everything even-aligned: yuv420p subsamples chroma 2x2, so
        an odd size fails the encoder and an odd OFFSET shears the colours."""
        if not region:
            return None
        even = lambda v: int(v) // 2 * 2
        x = min(even(region.get("x", 0) * self.width), self.width - 2)
        y = min(even(region.get("y", 0) * self.height), self.height - 2)
        w = max(2, even(region.get("w", 1) * self.width))
        h = max(2, even(region.get("h", 1) * self.height))
        w = min(w, self.width - x)
        h = min(h, self.height - y)
        if x <= 0 and y <= 0 and w >= self.width and h >= self.height:
            return None  # the whole frame — nothing to crop
        return (w, h, x, y)

    @staticmethod
    def _panel_size(panel: dict | None) -> tuple[int, int]:
        """The device's real panel pixels, or (0, 0) — which caps nothing.
        Never invent: a page that says nothing, a browser with no such field,
        or a nonsense value must land in exactly the old behaviour."""
        if not panel:
            return (0, 0)
        try:
            w, h = int(panel.get("w") or 0), int(panel.get("h") or 0)
        except (TypeError, ValueError):
            return (0, 0)
        return (w, h) if w > 1 and h > 1 else (0, 0)

    def _scale_size(self, src_w: int, src_h: int) -> tuple[int, int] | None:
        """(w, h) the encoder must OUTPUT, or None to leave the crop at its own
        size.

        THE PANEL IS A CEILING (owner order 2026-08-12): "what is the point of
        the PC sending 4K if the Android device cannot receive it — a Redmi Pad
        is 1920x1200 and we send it 4K". Sending more pixels than the panel can
        light up is bitrate spent on detail that is thrown away in the phone's
        own downscale, on top of a decode the SoC may not manage at all.

        Three rules, and the SMALLEST factor wins:

        - the phone's own resolution step (2/3, 1/2) — unchanged, it composes
          here instead of being a second, competing scale filter;
        - the panel's LONG side against the crop's long side, and its SHORT
          against the crop's short. Long-to-long rather than width-to-width
          because the phone's rotation is locked to the layout's orientation
          (a tall quarter-width layout is watched on a tall phone), so the
          picture's long side really does land on the panel's long side. For
          his own case — a full 3840x2160 desktop on a 1920x1200 tablet — this
          is exactly his `min(crop width, panel width)`: 1920 wide;
        - NEVER above 1. A crop narrower than the panel is sent at its OWN
          size: upscaling here would spend bitrate to invent nothing, and it is
          why a focused layout now comes out SHARPER at the same bitrate.

        The aspect ratio of the crop is preserved (the height is derived from
        the chosen width), and both dimensions are even — yuv420p subsamples
        chroma 2x2, exactly as in `_crop_rect`.

        Takes the SOURCE size as an argument rather than reading the crop
        (T79): the bitrate reference below has to ask this same function what
        a FULL screen would come out as on this panel, and asking it is the
        only way the two can never disagree — a second copy of the ceiling
        arithmetic is exactly the drift this project keeps paying for."""
        num, den = {"2/3": (2, 3), "1/2": (1, 2)}.get(self._quality.get("res"), (1, 1))
        factor = num / den
        pw, ph = self._panel
        if pw and ph:
            factor = min(factor,
                         max(pw, ph) / max(src_w, src_h),
                         min(pw, ph) / min(src_w, src_h))
        if factor >= 1:
            return None
        w = max(2, int(round(src_w * factor)) // 2 * 2)
        h = max(2, int(round(src_h * w / src_w)) // 2 * 2)
        return None if (w, h) == (src_w, src_h) else (w, h)

    def _encoded_size(self) -> tuple[int, int]:
        """The pixels the encoder really produces per frame — the scale when
        there is one, else the crop, else the whole frame."""
        if self._scale:
            return self._scale
        return self._crop[:2] if self._crop else (self.width, self.height)

    def _reference_size(self) -> tuple[int, int]:
        """"A FULL SCREEN ON THIS PANEL" — the picture a ladder rung's number
        was written for. The same `_scale_size` the real size goes through,
        asked about the uncropped frame, so the client's own resolution step
        is inside BOTH sides of the ratio and cancels: a full-screen Data
        saver session comes out at factor 1.0 and is byte for byte what it is
        today."""
        full = (self.width, self.height)
        return self._scale_size(*full) or full

    @property
    def bitrate(self) -> str:
        """The `-b:v` string this session really uses. See `_bitrate`."""
        if getattr(self, "_bitrate_cache", None) is None:
            self._bitrate_cache = self._bitrate()
        return self._bitrate_cache[0]

    @property
    def bitrate_factor(self) -> float:
        """What the pixel arithmetic actually produced — 1.0 whenever nothing
        was scaled. Logged beside the number, because a bitrate that is never
        printed cannot be told apart from one that was simply not spent."""
        if getattr(self, "_bitrate_cache", None) is None:
            self._bitrate_cache = self._bitrate()
        return self._bitrate_cache[1]

    def _bitrate(self) -> tuple[str, float]:
        """THE BITRATE FOLLOWS THE PIXELS — on cellular only (T79).

        `-b:v`/`-maxrate` used to be the rung's flat number whatever the
        encoder was actually fed, so 20 Mbps on a quarter-size crop was the
        same ceiling as 20 Mbps on the full 4K. Two things kept that honest
        until now and both are stated rather than glossed over: `-maxrate` is
        a CEILING, so a static screen still costs its own ~3.6 Mbps and the
        waste only appears under motion; and `_scale_size` already equalises a
        full desktop and a 2x2 cell onto the panel, where the bits per pixel
        are IDENTICAL. The overspend lives exactly where the crop falls BELOW
        the panel and is therefore sent at its own small size — measured at
        roughly 2.2x the reference's bits per pixel — and the zoom crop (T76)
        is what turns that from an edge case into the normal one.

        The rules, in the owner's order:

        - ON WI-FI, NOTHING CHANGES. A focused layout coming out sharper at
          the same nominal quality is a FEATURE (see `_scale_size`), and it is
          not touched. "On cellular" is asked of `config.is_data_saver` — the
          saving profile the phone already sends over the existing path, never
          a new field.
        - the factor is encoded pixels over reference pixels, so the rungs
          keep meaning what they say;
        - DOWNWARD ONLY, absolutely: `min` against the rung's own number, so
          no arithmetic here can ever raise what the phone is not allowed to
          raise (task 131);
        - and a FLOOR, so a small crop cannot collapse into mush.

        `BITRATE_FLOOR_BPS` is a JUDGEMENT and is meant to be tuned on the
        real device. 800 kbps was chosen because it is generous rather than
        marginal at the sizes this can reach: his own quarter-width layout
        encodes 484x1048 at 10 fps, where 800 kbps is ~0.16 bits per pixel per
        frame — nearly double the ~0.096 the reference full screen gets at the
        same rung. So the floor never produces a picture worse than the one he
        already accepts, and every saving above it is real."""
        nominal = config.bitrate_for_level(self._quality.get("bitrate"))
        if not config.is_data_saver(self._quality.get("bitrate")):
            return nominal, 1.0
        ew, eh = self._encoded_size()
        rw, rh = self._reference_size()
        # The RAW ratio — deliberately not pre-clamped to 1. There is exactly
        # ONE downward-only clamp, on the line below, so the rule "never above
        # the rung" is enforced in one place a gate can drive; a second clamp
        # here would make that one unreachable and therefore unprovable, and
        # an unprovable rule is how this project's regressions ship. It also
        # keeps the LOGGED factor honest about what the arithmetic really
        # produced.
        factor = (ew * eh) / max(1, rw * rh)
        nominal_bps = config.bitrate_bps(nominal)
        applied = min(nominal_bps, max(BITRATE_FLOOR_BPS,
                                       int(nominal_bps * factor)))
        if applied >= nominal_bps:
            # NOTHING WAS REDUCED, so nothing may CHANGE — the rung's own
            # string goes to ffmpeg exactly as it always did. Returning
            # `str(nominal_bps)` here would be numerically identical and still
            # wrong: "a full-screen saver session is unchanged to the bit" is a
            # promise about what the encoder is handed and what the log prints,
            # not only about the arithmetic. It was measured, not reasoned —
            # `tests/test_quality_reset.py` holds the rung as the literal "2M"
            # on purpose (so a silent change to a shipped default fails there
            # by name with a readable number) and this turned it into
            # "2000000", failing two checks and the whole build.
            return nominal, factor
        return str(applied), factor

    def _ffmpeg_cmd(self) -> list[str]:
        # Quality overrides downscale / drop fps INSIDE this client's own
        # ffmpeg (capture and other clients stay untouched); dimensions must
        # stay even for yuv420p.
        chain = []
        # The crop comes FIRST (owner order 2026-08-12): the encoder never
        # sees the pixels outside the focused layout's region, so the phone
        # never decodes them — a quarter-width layout costs a quarter-width
        # decode, and every bit of the bitrate lands on what is watched. The
        # res/fps overrides below then apply to the CROP, exactly as the
        # phone's quality panel reads relative to what it is shown.
        if self._crop:
            w, h, x, y = self._crop
            chain.append(f"crop={w}:{h}:{x}:{y}")
        # ONE scale, right after the crop: the phone's resolution step and the
        # device-panel ceiling are already reconciled into a single size by
        # `_scale_size` (the smallest wins), so there is never a second filter
        # competing with the first. Numeric, not an `iw`/`ih` expression: we
        # know the crop exactly, and the real numbers can then be logged.
        if self._scale:
            chain.append("scale=%d:%d" % self._scale)
        # The rate frames really ARRIVE at — the desktop's, or the higher one
        # this client raised the capture to (task 131). Comparing against
        # SETTINGS.target_fps instead would insert an `fps` filter that THROWS
        # AWAY the very frames the raise was asked for.
        source_fps = getattr(self._source, "capture_fps", SETTINGS.target_fps)
        fps = int(self._quality.get("fps") or 0)
        if 0 < fps < source_fps:
            chain.append(f"fps={fps}")
        filters = ["-vf", ",".join(chain)] if chain else []
        # Decided in __init__ (T79) so the number and the factor that produced
        # it can be logged with the session — a bitrate that is never printed
        # cannot be told apart from a bitrate that was simply not spent.
        bitrate = self.bitrate
        return [
            SETTINGS.ffmpeg_path, "-hide_banner", "-loglevel", "error",
            # yuv420p in, not bgr24: capture.py hands us I420 (task 130 — half
            # the bytes through this pipe, and it removes the swscale
            # conversion ffmpeg used to do on the CPU for every frame). These
            # two lines are ONE decision with `RawFrameSource._process` — a
            # mismatch here does not fail, it produces a picture in the wrong
            # colours. Every encoder in `h264_encoder_order` takes yuv420p
            # natively, libx264 fallback included; it is the format they all
            # convert TO anyway.
            "-f", "rawvideo", "-pix_fmt", "yuv420p",
            "-s", f"{self.width}x{self.height}", "-r", str(source_fps),
            "-i", "pipe:0", "-an",
            *filters,
            "-c:v", self._encoder, *encoders.encoder_args(self._encoder),
            "-g", str(SETTINGS.h264_gop), "-pix_fmt", "yuv420p",
            "-b:v", bitrate, "-maxrate", bitrate,
            "-f", "mp4",
            "-movflags", "+frag_keyframe+empty_moov+default_base_moof",
            "-frag_duration", str(SETTINGS.h264_fragment_us),
            "-flush_packets", "1",
            "pipe:1",
        ]

    def start(self) -> None:
        """Spawns ffmpeg and blocks until the init segment is parsed (`codec`
        is set from it) — call from a worker thread. Raises RuntimeError when
        no valid head arrives within h264_head_timeout."""
        # bufsize=0 keeps the pipes raw and unbuffered: stdout.read() returns
        # each flushed fragment immediately instead of batching 32 KB (latency).
        self._proc = subprocess.Popen(
            self._ffmpeg_cmd(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW, bufsize=0,
        )
        self._running = True
        self._source.add_sink(self._sink)
        for target in (self._feed_loop, self._read_loop, self._stderr_loop):
            threading.Thread(target=target, name=f"h264-{target.__name__}", daemon=True).start()
        if not self._head_ready.wait(SETTINGS.h264_head_timeout):
            self.stop()
            raise RuntimeError("ffmpeg produced no init segment in time — see ffmpeg errors in log")
        if self._head_error:
            self.stop()
            raise RuntimeError(self._head_error)

    def stop(self) -> None:
        """Idempotent, callable from any thread, fast: detaches from the
        source and terminates ffmpeg; the daemon threads unwind on their own
        (read hits EOF → on_end fires)."""
        self._running = False
        self._source.remove_sink(self._sink)
        if self._proc:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            self._proc.terminate()

    def _feed_loop(self) -> None:
        while self._running:
            data = self._sink.take(FEED_POLL_S)
            if data is None:
                continue  # frames stalled (e.g. monitor switching) — re-check _running
            try:
                self._proc.stdin.write(data)
            except (BrokenPipeError, OSError, ValueError):
                break  # pipe closed by stop() mid-write — normal shutdown

    def _read_loop(self) -> None:
        """Phase 1: accumulate stdout until the init segment is complete, parse
        the codec string, emit the head. Phase 2: forward chunks as they come."""
        try:
            head = b""
            while self._running:
                chunk = self._proc.stdout.read(READ_CHUNK)
                if not chunk:
                    if not self._head_ready.is_set():
                        self._head_error = "ffmpeg exited before writing an init segment"
                        self._head_ready.set()
                    return
                if self._head_ready.is_set():
                    self._on_data(chunk)
                    continue
                head += chunk
                end = _moov_end(head)
                if not end:
                    continue
                self.codec = _codec_string(head[:end])
                self._on_data(head)  # init segment + any fragment bytes already read
                self._head_ready.set()
        except RuntimeError as e:
            logger.error("H.264 stream parse failed: %s", e)
            self._head_error = str(e)
            self._head_ready.set()
        finally:
            self._fire_end()

    def _stderr_loop(self) -> None:
        for line in self._proc.stderr:
            text = line.decode(errors="replace").strip()
            if text:
                logger.error("ffmpeg: %s", text)

    def _fire_end(self) -> None:
        if not self._ended.is_set():
            self._ended.set()
            self._on_end()


class SessionOwner:
    """One consumer's CLAIM on one session — the thing that survives an
    `asyncio.to_thread` cancellation.

    Cancelling `await asyncio.to_thread(manager.open_session, …)` does not stop
    the worker thread it started. ffmpeg still spawns, `open_session` still
    returns, the session still registers — and the coroutine that would have
    closed it never learned its name, because the `await` raised instead of
    assigning. That is the live failure of 2026-08-07: the phone's socket died
    18 ms after auth, 205 ms before its own encoder finished starting, and the
    orphan then ran for FOUR HOURS at native 4K with nobody on the other end,
    holding capture alive (`_sessions` was never empty again), burning 12,000
    seconds of CPU and writing 1,890 "stream backlog" warnings into the owner's
    log while his mouse juddered.

    So the claim is made BEFORE the thread starts and released by the
    consumer's own teardown — every way a connection can end: a clean close, a
    4409 takeover, network death with no close frame, an exception in the send
    path, server stop. The mutex settles the race in both directions:

    - `take()` first   → the session registers normally, and the later
      `release()` is what closes it;
    - `release()` first → `take()` refuses, and the manager closes the session
      it has just built instead of registering it.

    Either way, no session outlives its consumer, and `alive` is the flag the
    web layer's queue closure reads so a session nobody can hear is never
    "reset" on a dead client's behalf.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._alive = True
        self._manager: "H264Manager | None" = None
        self._session: H264Session | None = None

    @property
    def alive(self) -> bool:
        """False once the consumer is gone. Nothing may be queued for it and
        nothing may be reset on its behalf after that."""
        return self._alive

    def take(self, manager: "H264Manager", session: H264Session) -> bool:
        """Manager side, on the encoder thread: hand the finished session to
        its claim. False means the consumer already left — do NOT register it."""
        with self._lock:
            if not self._alive:
                return False
            self._manager, self._session = manager, session
            return True

    def release(self) -> None:
        """Consumer side: I am gone. Closes the session if one was registered
        and refuses every later `take()`. Idempotent, callable from any thread,
        and fast enough to run inside a `finally` mid-cancellation.

        `close_session` is deliberately called OUTSIDE this lock: it takes the
        manager's lock, and the encoder thread holds the manager's lock while
        calling `take()` — holding both here in the other order would be the
        one deadlock this design can have."""
        with self._lock:
            self._alive = False
            manager, session = self._manager, self._session
            self._manager = self._session = None
        if session is not None:
            manager.close_session(session)


class H264Manager:
    """The web layer's H.264 backend: session registry + capture lifecycle +
    monitor switching. All blocking methods are called via asyncio.to_thread."""

    mode = "h264"

    def __init__(self, encoder: str):
        self.encoder = encoder
        self._source = RawFrameSource()
        self._sessions: set[H264Session] = set()
        self._source_running = False
        self._shut_down = False
        self._lock = threading.Lock()
        # Consumers that are BETWEEN sessions and will open another at once —
        # see hold_source(). Its own lock: a hold must never wait behind an
        # open_session that is busy starting an encoder.
        self._holds: set = set()
        self._holds_lock = threading.Lock()

    @property
    def width(self) -> int:
        return self._source.width

    @property
    def height(self) -> int:
        return self._source.height

    @property
    def monitor_index(self) -> int:
        return self._source.monitor_index

    @property
    def stream_size(self) -> tuple[int, int]:
        """What the encoder is actually fed — the monitor capped at the
        desktop's Resolution setting. The phone shows this as its baseline."""
        return self._source.stream_w, self._source.stream_h

    def output_count(self) -> int:
        return RawFrameSource.output_count()

    def take_screenshot(self):
        """Native-resolution frame — only meaningful while a client is
        connected (capture idles otherwise and the request times out)."""
        return self._source.take_screenshot()

    @staticmethod
    def new_owner() -> SessionOwner:
        """A fresh claim for the caller to hand to `open_session`. Made on the
        caller's OWN thread, before the blocking open starts — that timing is
        the whole defence, so this must never be created inside the thread."""
        return SessionOwner()

    def open_session(self, on_data, on_end, quality: dict | None = None,
                     owner: SessionOwner | None = None,
                     region: dict | None = None,
                     panel: dict | None = None) -> H264Session:
        """Starts capture with the first client. Blocking (ffmpeg spawn + init
        segment wait). Raises RuntimeError when the encoder fails to start, or
        when the manager is already shut down.

        `owner` is the caller's claim (`new_owner()`). A session whose claim is
        already released — or one that finished starting after the server began
        shutting down — is CLOSED here and never registered: it has no consumer
        and nothing else would ever be able to name it (see `SessionOwner`).
        The returned object is then a dead session, which is exactly what the
        cancelled caller does with its unread result."""
        with self._lock:
            if self._shut_down:
                raise RuntimeError("the H.264 manager is shut down")
            if not self._source_running:
                self._source.start()
                self._source_running = True
            session = H264Session(self._source, self.encoder, on_data, on_end,
                                  quality=quality, region=region, panel=panel)
            try:
                session.start()
            except Exception:  # RuntimeError (no head) or OSError (Popen) — same cleanup
                self._stop_source_if_idle()
                raise
            if self._shut_down:
                return self._abandon(session, "the server is shutting down")
            if owner is not None and not owner.take(self, session):
                return self._abandon(session, "its client was already gone")
            self._sessions.add(session)
            crop = (" crop %dx%d+%d+%d" % session._crop) if session._crop else ""
            # The chosen scale, once per session, beside the crop: his own
            # server.log must show the REAL numbers the encoder was built with
            # (owner order 2026-08-12), not a claim that a cap exists.
            scale = (" scale %dx%d" % session._scale) if session._scale else " scale none"
            # …and the BITRATE beside them (T79). His own reason for wanting
            # it: without the applied number and the factor there is no way to
            # tell "the encoder did not spend because nothing moved" from "we
            # capped it".
            rate = " bitrate %s (x%.3f of the rung)" % (
                session.bitrate, session.bitrate_factor)
            logger.info("H.264 session opened — %d active, codec %s, %dx%d%s%s%s",
                        len(self._sessions), session.codec, session.width,
                        session.height, crop, scale, rate)
            return session

    def close_session(self, session: H264Session) -> None:
        """Only the connection that opened a session closes it. Stops capture
        when the last session goes (nothing runs while nobody watches)."""
        session.stop()
        with self._lock:
            self._sessions.discard(session)
            self._stop_source_if_idle()
            logger.info("H.264 session closed — %d active", len(self._sessions))

    def _abandon(self, session: H264Session, why: str) -> H264Session:
        """Caller holds `_lock`. A session that finished starting with nobody
        left to read it: terminate ffmpeg, leave the registry untouched, and
        SAY so — an abandoned session used to be indistinguishable from a
        working one in the log, for four hours (2026-08-07)."""
        session.stop()
        self._stop_source_if_idle()
        logger.warning("H.264 session abandoned during startup (%s) — closed, "
                       "not registered; %d active", why, len(self._sessions))
        return session

    def hold_source(self, hold: object) -> None:
        """"I am between sessions and I am opening another one right now" —
        keep capture running even though `_sessions` is momentarily empty.

        A quality change (the phone's bitrate/fps/resolution panel) can only be
        applied by a NEW ffmpeg, so the web layer's stream loop closes one
        session and opens the next. With one client — the normal case, "one
        device at a time" is a hard rule — that emptied `_sessions` and dxcam
        was torn down and rebuilt for a change that lives entirely inside one
        ffmpeg flag. The new encoder then has NO FRAMES until dxcam is back,
        and ffmpeg cannot write an init segment before it has encoded one: past
        `h264_head_timeout` the whole connection died (owner report 2026-08-10;
        his log, 20:30:21 close + `Frame buffer build(start)` → 20:30:42
        "ffmpeg produced no init segment in time" → the phone reconnecting).

        Idempotent by construction (a set of tokens, not a count), so no caller
        can leak or double-release one. NEVER a substitute for a session: only
        a live stream loop may hold, and it releases on every way it can end —
        capture still runs solely while somebody is watching."""
        with self._holds_lock:
            self._holds.add(hold)

    def release_source(self, hold: object) -> None:
        """Drop a hold and stop capture if that was the last thing keeping it.

        The stop is attempted WITHOUT waiting for `_lock`: this is called from
        the event loop, sometimes mid-cancellation, and `open_session` holds
        that lock for as long as an encoder takes to start. Skipping is safe —
        whoever holds it is inside `open_session`, and every exit of that
        method either registers a session (capture must keep running) or calls
        `_stop_source_if_idle` itself."""
        with self._holds_lock:
            self._holds.discard(hold)
        if self._lock.acquire(blocking=False):
            try:
                self._stop_source_if_idle()
            finally:
                self._lock.release()

    def _stop_source_if_idle(self) -> None:
        """Caller holds `_lock`. Capture runs only while a session needs it —
        or while a consumer is between two of its own (see `hold_source`)."""
        if self._sessions or not self._source_running:
            return
        with self._holds_lock:
            if self._holds:
                return
        self._source.stop()
        self._source_running = False

    def raise_limits(self, fps: int | None, width: int | None) -> bool:
        """THE PHONE MAY RAISE THE CEILING (owner decision, task 131).

        The desktop Settings card is the DEFAULT this client works from, and
        going BELOW it is free — that happens inside this client's own ffmpeg
        and touches nobody. Going ABOVE it is not: capture is shared, so the
        camera itself has to grab faster or wider, and everything currently
        encoding from it has to be rebuilt.

        That is affordable for exactly one reason, and it is a design rule
        rather than an accident: ONE DEVICE AT A TIME (4409). There is never a
        second client whose picture this could disturb.

        So the cost is real, bounded and honest: the picture BLINKS. The
        phone's quality panel says so on the raised steps before he taps —
        `capture.raise_limits` is the decision, this is the rebuild, and
        `stream_base` keeps telling the panel what the desktop itself is set
        to, so "raised" never quietly becomes the new normal.

        Blocking (dxcam teardown + rebuild) — call via asyncio.to_thread.
        Returns True when anything actually changed."""
        with self._lock:
            if not self._source.raise_limits(fps, width):
                return False
            for session in list(self._sessions):
                session.stop()          # every encoder is built for the old size
            if self._source_running:
                self._source.stop()
                self._source.start()    # same camera, new target fps / width
            return True

    def switch_to(self, index: int) -> bool:
        """Ends every session (their owners reopen automatically and resend
        config) and swaps the capture monitor. Blocking."""
        with self._lock:
            for session in list(self._sessions):
                session.stop()
            if self._source_running:
                self._source.stop()
                self._source_running = False
            return self._source.switch_monitor(index)

    def shutdown(self) -> None:
        """Server teardown: end everything — and stay ended. The flag is not
        cosmetic: a session already inside `session.start()` on its own thread
        finishes AFTER this returns, and without the flag it would register
        itself into a manager the process has finished with."""
        with self._lock:
            self._shut_down = True
            for session in list(self._sessions):
                session.stop()
            self._sessions.clear()
            self._source_running = False
            # close(), not stop() — the dxcam instance must be RELEASED here
            # (task 193). dxcam is a singleton per monitor, so a camera merely
            # stopped is still the one the NEXT server run is handed: Apply &
            # restart builds the new capture while this thread is still
            # unwinding, and the line below then stopped the picture the new
            # server had already started serving. His log, 2026-08-11 00:32:58:
            # "Server thread did not stop within 10s" and, a quarter of a
            # second later, dxcam's "instance already exists ... returning
            # existing instance". Releasing is what makes the next create() a
            # real create.
            self._source.close()
