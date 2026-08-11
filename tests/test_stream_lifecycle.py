"""Stream Lifecycle Gate: a client that is gone leaves NOTHING behind.

Regression proof for the live failure of 2026-08-07, found in the owner's own
`%LOCALAPPDATA%\\RemoteUser\\server.log` while his mouse juddered:

    12:05:11,822  Client authenticated: port=56482
    12:05:12,730  dxcam: Frame buffer build(start): 3840x2160     <- open_session
    12:05:12,732  Client disconnected: port=56482                 <- 910 ms later
    12:05:12,951  H.264 session opened - 1 active                 <- 219 ms TOO LATE
    12:05:21,218  WARNING Client stream backlog - resetting ...   <- and every ~7 s
                  ...for the next four hours, 1,890 times, with no phone
                  connected at all and ffmpeg.exe on 12,924 s of CPU.

The mechanism: cancelling `await asyncio.to_thread(manager.open_session, ...)`
does not stop the worker thread. ffmpeg spawned anyway, the session registered
anyway, and the coroutine that would have closed it never learned its name --
so it was unreachable forever. It held `_sessions` non-empty (capture could
never stop) and its `push` callback kept overflowing a queue nobody drained,
logging a "reset" that nothing could act on.

What is proven here -- with the REAL `H264Session`, the REAL `H264Manager` and
the REAL `web._stream_h264` loop, and NO dxcam, NO ffmpeg and NO 4K (a fake
process on the same pipe contract, a fake frame source):

1. Every way a connection can end -- cancelled mid-open (the live bug), a
   clean close, a 4409 takeover / network death mid-stream, an exception in
   the send path, server stop -- returns the active count to ZERO, terminates
   the encoder and stops capture.
2. No reset ever fires for a client with no live socket, even when its encoder
   keeps writing.
3. ...and the reset still DOES fire for a live client that is merely slow --
   without this the gate would pass with the feature deleted.

Run:  .venv\\Scripts\\python tests/test_stream_lifecycle.py
"""

import asyncio
import logging
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import h264_streamer  # noqa: E402
import web  # noqa: E402
from config import SETTINGS  # noqa: E402


# ── The fake encoder ────────────────────────────────────────────────────────
# Same pipe contract as ffmpeg, none of the cost: the owner's CPU is already
# saturated by the bug this file exists to kill.

def _box(name: bytes, payload: bytes) -> bytes:
    return (len(payload) + 8).to_bytes(4, "big") + name + payload


# ftyp + moov(avcC) -- the smallest thing `_moov_end` can walk and
# `_codec_string` can read. The avcC payload spells avc1.4D4033, which is what
# the owner's PC really produced in the log above.
INIT_SEGMENT = (_box(b"ftyp", b"isom" + bytes(4) + b"isom")
                + _box(b"moov", _box(b"avcC", bytes([1, 0x4D, 0x40, 0x33]))))
FRAGMENT = _box(b"moof", bytes(64)) + _box(b"mdat", bytes(2048))


class _Pipe:
    """Blocking byte pipe with an EOF, standing in for ffmpeg's stdout."""

    def __init__(self):
        self._cv = threading.Condition()
        self._buf = bytearray()
        self._eof = False

    def feed(self, data: bytes) -> None:
        with self._cv:
            if self._eof:
                return
            self._buf += data
            self._cv.notify_all()

    def eof(self) -> None:
        with self._cv:
            self._eof = True
            self._cv.notify_all()

    def read(self, n: int) -> bytes:
        with self._cv:
            while not self._buf and not self._eof:
                self._cv.wait(0.05)
            data = bytes(self._buf[:n])
            del self._buf[:len(data)]
            return data


class _Stdin:
    def write(self, data): return len(data)
    def close(self): pass


class FakeFfmpeg:
    """Replaces `subprocess.Popen` inside h264_streamer.

    `head_delay` is the whole point: it is the window between "the encoder was
    asked for" and "the encoder answered" -- 219 ms wide on the owner's PC, and
    the window the live failure fell into. `ignore_terminate` models an encoder
    that keeps writing after we asked it to stop, which is what the second
    defence (the push guard) has to survive."""

    instances: list["FakeFfmpeg"] = []
    head_delay = 0.0
    frag_interval = 0.01
    ignore_terminate = False

    def __init__(self, cmd, **kwargs):
        FakeFfmpeg.instances.append(self)
        self.cmd = cmd
        self.terminated = False
        self._out = _Pipe()
        self._stop = threading.Event()
        self.stdin = _Stdin()
        self.stdout = self._out
        self.stderr = iter(())          # `for line in stderr` ends at once
        self._thread = threading.Thread(target=self._produce, daemon=True)
        self._thread.start()

    def _produce(self) -> None:
        if self._stop.wait(FakeFfmpeg.head_delay):
            self._out.eof()
            return
        self._out.feed(INIT_SEGMENT)
        while not self._stop.wait(FakeFfmpeg.frag_interval):
            self._out.feed(FRAGMENT)
        self._out.eof()

    def terminate(self) -> None:
        self.terminated = True
        if not FakeFfmpeg.ignore_terminate:
            self._stop.set()

    def kill(self) -> None:
        self.terminate()

    def force_stop(self) -> None:
        """Test teardown -- nothing this file starts may outlive it."""
        self._stop.set()
        self._out.eof()
        self._thread.join(timeout=2)


class FakeSource:
    """Replaces `RawFrameSource`: no dxcam, no monitor, no 4K buffer."""

    def __init__(self):
        self.width, self.height = 3840, 2160
        self.stream_w, self.stream_h = 3840, 2160
        self.monitor_index = 0
        self.running = False
        self.starts = 0
        self.sinks: list = []

    # Task 155 gave `config` a monitors list read off the capture source
    # (monitor_api.config_fields -> output_count); a fake that models the
    # interface must model this too, or every config send dies mid-gate.
    @staticmethod
    def output_count() -> int:
        return 1

    def start(self) -> None:
        self.running = True
        self.starts += 1

    def stop(self) -> None:
        self.running = False

    def add_sink(self, sink) -> None:
        self.sinks.append(sink)

    def remove_sink(self, sink) -> None:
        if sink in self.sinks:
            self.sinks.remove(sink)


class FakeWs:
    """Only what `_stream_h264` touches. `on_bytes` is how a check makes the
    socket die, hang or explode at exactly the moment it wants to."""

    def __init__(self, on_bytes=None):
        self.client = "test-phone"
        self.texts: list = []
        self.chunks = 0
        self.closed_code = None
        self._on_bytes = on_bytes

    async def send_text(self, text: str) -> None:
        self.texts.append(text)

    async def send_bytes(self, data: bytes) -> None:
        self.chunks += 1
        if self._on_bytes is not None:
            await self._on_bytes(self)

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code


class DeafOwner(h264_streamer.SessionOwner):
    """The first defence, switched off — a claim that accepts every session and
    remembers none, which is precisely the pre-2026-08-07 world: the manager
    registers the session, and nothing anywhere can ever name it again. Used by
    exactly one check, to prove the second defence stands without the first."""

    def take(self, manager, session) -> bool:
        return True


class ResetWatch(logging.Handler):
    """Counts the backlog warning at its real source -- the `web` logger --
    so a check can prove it never fired, or that it still does."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.resets = 0

    def emit(self, record) -> None:
        if "stream backlog" in record.getMessage():
            self.resets += 1


# ── Harness ─────────────────────────────────────────────────────────────────

def install_fakes() -> None:
    h264_streamer.subprocess.Popen = FakeFfmpeg
    h264_streamer.RawFrameSource = FakeSource
    # `_send_config` asks Windows for the Tailscale address (a subprocess) --
    # a stream test must not depend on the machine's VPN state.
    web.pairing.get_tailscale_ip = lambda: None
    # A short queue makes an overflow reachable in a test's lifetime; the
    # shipped 256 is ~4 s of full-bitrate video. SETTINGS is frozen (THE CONFIG
    # SECTION LAW) — object.__setattr__ is the documented way past it, and only
    # a test may use it.
    object.__setattr__(SETTINGS, "h264_queue_chunks", 4)
    object.__setattr__(SETTINGS, "h264_head_timeout", 3.0)


def fresh_manager() -> h264_streamer.H264Manager:
    FakeFfmpeg.instances.clear()
    FakeFfmpeg.head_delay = 0.0
    FakeFfmpeg.frag_interval = 0.01
    FakeFfmpeg.ignore_terminate = False
    return h264_streamer.H264Manager("h264_test")


def watch_resets() -> ResetWatch:
    watch = ResetWatch()
    logging.getLogger("web").addHandler(watch)
    return watch


def settled(manager, watch, expect_resets: bool = False) -> bool:
    """The one verdict every check ends on: nothing counted, nothing running,
    nothing left encoding, and (unless asked for) nothing reset."""
    logging.getLogger("web").removeHandler(watch)
    for proc in FakeFfmpeg.instances:
        proc.force_stop()
    ok = (len(manager._sessions) == 0
          and manager._source.running is False
          and all(p.terminated for p in FakeFfmpeg.instances)
          and bool(FakeFfmpeg.instances))       # the encoder really did spawn
    return ok and (watch.resets > 0 if expect_resets else watch.resets == 0)


async def _drain(task) -> None:
    """Let a cancelled task and the thread it abandoned both finish. The
    thread is the whole subject here -- checking too early would find the
    fixed and the broken code identical."""
    await asyncio.gather(task, return_exceptions=True)
    for _ in range(100):
        await asyncio.sleep(0.02)
        if all(p.terminated for p in FakeFfmpeg.instances):
            return


# ── The checks ──────────────────────────────────────────────────────────────

def check_cancel_mid_open_leaves_nothing() -> bool:
    """THE live bug. The socket dies while ffmpeg is still starting: the
    coroutine is cancelled at the `await`, the thread runs on and finishes an
    encoder nobody asked for any more."""
    manager, watch = fresh_manager(), watch_resets()
    FakeFfmpeg.head_delay = 0.5          # the 219 ms window, widened

    async def run():
        task = asyncio.create_task(web._stream_h264(FakeWs(), manager, "t", {}))
        await asyncio.sleep(0.15)        # inside to_thread(open_session)
        assert FakeFfmpeg.instances, "the encoder should already be starting"
        task.cancel()
        await _drain(task)

    asyncio.run(run())
    return settled(manager, watch)


def check_clean_close_leaves_nothing() -> bool:
    """The ordinary end: the phone closes and the socket raises."""
    manager, watch = fresh_manager(), watch_resets()

    async def die(ws):
        if ws.chunks >= 2:
            raise web.WebSocketDisconnect(1000)

    async def run():
        await asyncio.wait_for(
            web._stream_h264(FakeWs(on_bytes=die), manager, "t", {}), timeout=10)
        for _ in range(50):
            await asyncio.sleep(0.02)

    asyncio.run(run())
    return settled(manager, watch)


def check_takeover_mid_stream_leaves_nothing() -> bool:
    """A 4409 eviction, or a phone whose Wi-Fi simply went quiet: the task is
    cancelled with a session fully open and streaming."""
    manager, watch = fresh_manager(), watch_resets()

    async def run():
        ws = FakeWs()
        task = asyncio.create_task(web._stream_h264(ws, manager, "t", {}))
        for _ in range(150):
            await asyncio.sleep(0.02)
            if ws.chunks >= 2:
                break
        assert ws.chunks >= 2, "the stream never got going"
        task.cancel()
        await _drain(task)

    asyncio.run(run())
    return settled(manager, watch)


def check_send_path_exception_leaves_nothing() -> bool:
    """An exception in the send path -- the one exit that is neither a close
    nor a cancellation."""
    manager, watch = fresh_manager(), watch_resets()

    async def boom(ws):
        raise RuntimeError("send failed")

    async def run():
        await asyncio.wait_for(
            web._stream_h264(FakeWs(on_bytes=boom), manager, "t", {}), timeout=10)
        for _ in range(50):
            await asyncio.sleep(0.02)

    asyncio.run(run())
    return settled(manager, watch)


def check_server_stop_leaves_nothing() -> bool:
    """Server stop while an encoder is mid-spawn. `shutdown()` cannot stop a
    session it has not been told about yet -- the late arrival must refuse to
    register itself into a manager the process has finished with."""
    manager, watch = fresh_manager(), watch_resets()
    FakeFfmpeg.head_delay = 0.5

    async def run():
        task = asyncio.create_task(web._stream_h264(FakeWs(), manager, "t", {}))
        await asyncio.sleep(0.15)
        await asyncio.to_thread(manager.shutdown)
        task.cancel()
        await _drain(task)

    asyncio.run(run())
    return settled(manager, watch)


def check_a_dead_client_is_never_reset() -> bool:
    """The second defence, ALONE — which means the first one has to be taken
    away for the length of this check.

    That is not artificial: "the reset path must never loop on a client with no
    live socket" is a rule in its own right, and a rule only tested through
    another rule's fix is untested. So `DeafOwner` recreates the world of
    2026-08-07 exactly — a session that really does leak, really keeps
    encoding, and really keeps calling `push` — and the queue guard has to be
    the thing that keeps the log silent. Not one of the 1,890 warnings may be
    written here."""
    manager, watch = fresh_manager(), watch_resets()
    FakeFfmpeg.frag_interval = 0.005      # far faster than a 4-deep queue drains
    manager.new_owner = DeafOwner         # defence 1 disabled ON PURPOSE

    async def run():
        ws = FakeWs()
        task = asyncio.create_task(web._stream_h264(ws, manager, "t", {}))
        for _ in range(150):
            await asyncio.sleep(0.02)
            if ws.chunks >= 2:
                break
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        # A full second of an encoder shouting into a queue nobody reads.
        await asyncio.sleep(1.0)

    asyncio.run(run())
    logging.getLogger("web").removeHandler(watch)
    leaked = len(manager._sessions)
    manager.shutdown()                    # this check's own mess, cleaned here
    for proc in FakeFfmpeg.instances:
        proc.force_stop()
    # `leaked == 1` is not a wish — it is the proof that the check really did
    # build an orphan, so it can never quietly decay into testing nothing.
    return watch.resets == 0 and leaked == 1


def check_a_live_slow_client_still_resets() -> bool:
    """...and the feature is still there. A phone that is merely SLOW must
    still have its session reset -- otherwise every check above would pass
    with the backlog path deleted, which is not a gate."""
    manager, watch = fresh_manager(), watch_resets()
    FakeFfmpeg.frag_interval = 0.005

    async def crawl(ws):
        await asyncio.sleep(0.3)          # a phone that cannot keep up

    async def run():
        task = asyncio.create_task(
            web._stream_h264(FakeWs(on_bytes=crawl), manager, "t", {}))
        for _ in range(200):
            await asyncio.sleep(0.02)
            if watch.resets:
                break
        task.cancel()
        await _drain(task)

    asyncio.run(run())
    return settled(manager, watch, expect_resets=True)



CHECKS = [
    ("cancelled mid-open — the 2026-08-07 orphan — leaves nothing",
     check_cancel_mid_open_leaves_nothing),
    ("a clean close leaves nothing", check_clean_close_leaves_nothing),
    ("a 4409 takeover / silent network death leaves nothing",
     check_takeover_mid_stream_leaves_nothing),
    ("an exception in the send path leaves nothing",
     check_send_path_exception_leaves_nothing),
    ("server stop mid-spawn leaves nothing", check_server_stop_leaves_nothing),
    ("a client with no live socket is NEVER reset",
     check_a_dead_client_is_never_reset),
    ("a live but slow client still IS reset",
     check_a_live_slow_client_still_resets),
]


def main() -> int:
    install_fakes()
    print("=== STREAM LIFECYCLE GATE ===")
    failed = 0
    for name, fn in CHECKS:
        started = time.monotonic()
        try:
            ok = fn()
        except Exception as e:            # a crashing check is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  ({time.monotonic() - started:.1f}s)")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"STREAM LIFECYCLE GATE FAILED — {failed} check(s).")
        return 1
    print("STREAM LIFECYCLE GATE PASSED — a client that is gone leaves nothing behind.")
    return 0


def test_stream_lifecycle():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
