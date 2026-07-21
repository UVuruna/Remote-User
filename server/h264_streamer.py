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
"""

import logging
import subprocess
import threading

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

    def __init__(self, source: RawFrameSource, encoder: str, on_data, on_end):
        """on_data(bytes) / on_end() are called from the read thread and must
        be cheap and thread-safe (the web layer bridges them to asyncio)."""
        self._source = source
        self._encoder = encoder
        self._on_data = on_data
        self._on_end = on_end
        self._sink = FrameSink()
        self._proc: subprocess.Popen | None = None
        self._running = False
        self._ended = threading.Event()
        self._head_ready = threading.Event()
        self._head_error: str | None = None
        self.codec: str | None = None
        self.width, self.height = source.stream_w, source.stream_h

    def _ffmpeg_cmd(self) -> list[str]:
        return [
            SETTINGS.ffmpeg_path, "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}", "-r", str(SETTINGS.target_fps),
            "-i", "pipe:0", "-an",
            "-c:v", self._encoder, *encoders.encoder_args(self._encoder),
            "-g", str(SETTINGS.h264_gop), "-pix_fmt", "yuv420p",
            "-b:v", SETTINGS.h264_bitrate, "-maxrate", SETTINGS.h264_bitrate,
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


class H264Manager:
    """The web layer's H.264 backend: session registry + capture lifecycle +
    monitor switching. All blocking methods are called via asyncio.to_thread."""

    mode = "h264"

    def __init__(self, encoder: str):
        self.encoder = encoder
        self._source = RawFrameSource()
        self._sessions: set[H264Session] = set()
        self._source_running = False
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

    def output_count(self) -> int:
        return RawFrameSource.output_count()

    def take_screenshot(self):
        """Native-resolution frame — only meaningful while a client is
        connected (capture idles otherwise and the request times out)."""
        return self._source.take_screenshot()

    def open_session(self, on_data, on_end) -> H264Session:
        """Starts capture with the first client. Blocking (ffmpeg spawn + init
        segment wait). Raises RuntimeError when the encoder fails to start."""
        with self._lock:
            if not self._source_running:
                self._source.start()
                self._source_running = True
            session = H264Session(self._source, self.encoder, on_data, on_end)
            try:
                session.start()
            except Exception:  # RuntimeError (no head) or OSError (Popen) — same cleanup
                if not self._sessions:
                    self._source.stop()
                    self._source_running = False
                raise
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
            if not self._sessions and self._source_running:
                self._source.stop()
                self._source_running = False
            logger.info("H.264 session closed — %d active", len(self._sessions))

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
        """Server teardown: end everything."""
        with self._lock:
            for session in list(self._sessions):
                session.stop()
            self._sessions.clear()
            if self._source_running:
                self._source.stop()
                self._source_running = False
