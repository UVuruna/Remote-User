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
                 quality: dict | None = None):
        """on_data(bytes) / on_end() are called from the read thread and must
        be cheap and thread-safe (the web layer bridges them to asyncio).
        quality = this client's overrides from the phone's quality panel
        (owner spec 2026-08-05): {"fps": int, "res": "full"|"2/3"|"1/2",
        "bitrate": "high"|"mid"|"low"}. fps 0 / "full" / "high" mean "no
        override" — the desktop Settings defaults apply. None = all
        defaults."""
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

    def _ffmpeg_cmd(self) -> list[str]:
        # Quality overrides downscale / drop fps INSIDE this client's own
        # ffmpeg (capture and other clients stay untouched); dimensions must
        # stay even for yuv420p.
        chain = []
        num, den = {"2/3": (2, 3), "1/2": (1, 2)}.get(
            self._quality.get("res"), (1, 1))
        if den != num:
            chain.append(f"scale=trunc(iw*{num}/{den}/2)*2:trunc(ih*{num}/{den}/2)*2")
        fps = int(self._quality.get("fps") or 0)
        if 0 < fps < SETTINGS.target_fps:
            chain.append(f"fps={fps}")
        filters = ["-vf", ",".join(chain)] if chain else []
        bitrate = config.bitrate_for_level(self._quality.get("bitrate"))
        return [
            SETTINGS.ffmpeg_path, "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}", "-r", str(SETTINGS.target_fps),
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
                     owner: SessionOwner | None = None) -> H264Session:
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
                                  quality=quality)
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
            logger.info("H.264 session opened — %d active, codec %s, %dx%d",
                        len(self._sessions), session.codec, session.width, session.height)
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

    def _stop_source_if_idle(self) -> None:
        """Caller holds `_lock`. Capture runs only while a session needs it."""
        if not self._sessions and self._source_running:
            self._source.stop()
            self._source_running = False

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
            if self._source_running:
                self._source.stop()
                self._source_running = False
