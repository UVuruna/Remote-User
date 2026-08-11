"""Screen capture — dxcam (DXGI Desktop Duplication) ownership.

`BaseCapture` owns everything every streaming path shares: opening a monitor,
the capture thread, native-resolution screenshots served from that thread,
monitor switching, and downscale math. Two front-ends build on it:

- `JpegStreamer` — the fallback path: crop to the client viewport (region-of-
  interest streaming keeps zoom sharp), downscale, JPEG-encode, hand the bytes
  and the covered region to a callback per frame.
- `RawFrameSource` — the H.264 path: downscale once and offer the raw BGR
  frame to per-client encoder sinks (see H.264 Streamer). A slow encoder
  misses frames BEFORE they are encoded, so its output stream stays valid.

dxcam allows only one camera instance per output — exactly one front-end may
exist per process; main.py picks JPEG or H.264 at startup.
"""

import logging
import threading

import cv2
import dxcam

from config import SETTINGS

logger = logging.getLogger(__name__)

FULL_REGION = (0.0, 0.0, 1.0, 1.0)
MIN_REGION_PX = 64  # never crop below this many pixels per axis

# WHICH CAPTURE OWNS WHICH MONITOR, RIGHT NOW (task 193, 2026-08-11).
#
# dxcam's factory is a SINGLETON PER OUTPUT: a second `dxcam.create(0)` does
# not create anything — it logs a warning and hands back the camera the first
# caller is still using. That is the whole "changing the bitrate in Settings
# kills the app" failure, and it is dated in the owner's own log:
#
#   00:32:48,546  User settings saved: {... 'h264_bitrate': '20M' ...}
#   00:32:48,551  uvicorn: Shutting down
#   00:32:58,558  ERROR  Server thread did not stop within 10s
#   00:32:58,817  RawFrameSource ready — monitor 0 (3840x2160)
#   00:32:58,817  WARNING dxcam: DXCamera instance already exists for
#                          device=0 output=0; returning existing instance.
#
# Apply & restart builds the NEW server before the old thread has unwound. The
# new RawFrameSource is therefore handed the OLD camera — and then the old
# run's own `finally` reaches `stream.shutdown()` and STOPS it, out from under
# the server that is now serving. The picture dies, ffmpeg gets no frames, and
# the next session cannot even write an init segment. Nothing in the log says
# "crash", which is exactly why this took so long to name.
#
# So ownership is explicit here rather than hoped for: whoever opens a monitor
# registers, and a new capture EVICTS the previous owner before it takes the
# camera (the new run is the authoritative one by construction — the old one is
# already shutting down). `close()` then RELEASES the dxcam instance, which is
# what makes the factory build a genuinely new one next time.
_OWNERS: dict[int, "BaseCapture"] = {}
_OWNERS_LOCK = threading.Lock()


def _even(n: int) -> int:
    return n - (n % 2)  # H.264 yuv420 needs even dimensions


class BaseCapture:
    """Camera lifecycle + capture thread + screenshot service shared by all
    streaming front-ends. Subclasses implement `_process(frame)`, called from
    the capture thread for every grabbed frame."""

    def __init__(self):
        self._closed = False
        self._camera = self._open(SETTINGS.monitor_index)
        self._claim(SETTINGS.monitor_index)
        self.monitor_index = SETTINGS.monitor_index
        self.width, self.height = self._camera.width, self._camera.height
        self._thread: threading.Thread | None = None
        self._running = False
        self._shot_request = threading.Event()
        self._shot_ready = threading.Event()
        self._shot_frame = None
        logger.info("%s ready — monitor %d (%dx%d)",
                    type(self).__name__, self.monitor_index, self.width, self.height)

    @staticmethod
    def _open(index: int):
        """Opens a monitor, EVICTING whatever capture still holds it.

        The eviction is the fix for task 193 (see the `_OWNERS` block above):
        dxcam hands a second caller the FIRST caller's camera, so without this
        an Apply & restart whose old server thread has not unwound yet gets a
        camera that the dying run is about to stop. Evicting first means the
        old owner is stopped and RELEASED — which is what makes dxcam's factory
        build a genuinely new instance below, instead of logging its warning
        and returning the corpse."""
        with _OWNERS_LOCK:
            previous = _OWNERS.get(index)
        if previous is not None:
            logger.warning(
                "Monitor %d is still held by a %s from a previous server run — "
                "closing it before opening a new capture (dxcam allows one "
                "instance per output)", index, type(previous).__name__)
            previous.close()
        camera = dxcam.create(output_idx=index, output_color="BGR")
        if camera is None:
            raise RuntimeError(f"dxcam could not open monitor {index}")
        return camera

    def _claim(self, index: int) -> None:
        with _OWNERS_LOCK:
            _OWNERS[index] = self

    def _disclaim(self) -> None:
        with _OWNERS_LOCK:
            for index, owner in list(_OWNERS.items()):
                if owner is self:
                    del _OWNERS[index]

    def close(self) -> None:
        """Stop AND give the dxcam instance up — the teardown that `stop()` is
        deliberately not.

        `stop()` is the idle cycle: nobody is watching, so the capture thread
        ends and the camera is stopped, but the instance is KEPT because the
        next client is seconds away. `close()` is the end of this capture's
        life (server stop, Apply & restart, eviction). Releasing is the only
        thing that makes dxcam's per-output singleton let go, and until it does
        the next `create()` silently returns THIS object.

        Idempotent, callable from any thread, and safe on a camera another path
        already released — every one of its callers runs in a teardown where
        something else may have got there first."""
        if self._closed:
            return
        self._closed = True
        self._disclaim()
        self.stop()
        try:
            if not self._camera.is_released:
                self._camera.release()
        except Exception as e:  # a camera that is already gone is the goal, not an error
            logger.warning("Camera release: %s", e)

    @staticmethod
    def output_count() -> int:
        """Number of dxcam-visible outputs (info lines like 'Device[0] Output[0]: …')."""
        return dxcam.output_info().count("Output[")

    def switch_monitor(self, index: int) -> bool:
        """Swaps the capture source. Must be called while stopped. On failure
        the previous camera stays in place."""
        try:
            camera = self._open(index)
        except RuntimeError as e:
            # The previous camera stays in place — the caller's contract since
            # this method existed, and the reason it returns a bool.
            logger.error("dxcam could not open monitor %d: %s", index, e)
            return False
        self._camera = camera
        self._disclaim()     # the monitor we are leaving is no longer ours
        self._claim(index)
        self.monitor_index = index
        self.width, self.height = camera.width, camera.height
        logger.info("Switched capture to monitor %d (%dx%d)", index, self.width, self.height)
        return True

    def take_screenshot(self, timeout: float = 2.0):
        """Full-monitor, native-resolution copy of the next captured frame.
        Blocking — call from a worker thread, never the event loop."""
        self._shot_ready.clear()
        self._shot_request.set()
        if not self._shot_ready.wait(timeout):
            logger.error("Screenshot timed out after %.1fs", timeout)
            return None
        return self._shot_frame

    def start(self) -> None:
        if self._closed:
            # A superseded run trying to start the camera it no longer owns.
            # Refusing loudly beats stealing it back from the live server.
            raise RuntimeError("this capture has been closed — its monitor belongs "
                               "to a newer capture now")
        # `capture_fps` is the desktop's rate unless a client raised it
        # (task 131); `BaseCapture` has no raise of its own, so this is
        # SETTINGS.target_fps for the JPEG path and every other subclass.
        fps = getattr(self, "capture_fps", SETTINGS.target_fps)
        try:
            self._camera.start(target_fps=fps, video_mode=True)
        except Exception as e:
            # dxcam keeps its internal "capturing" flag when a stop raced a
            # fast reconnect ("Capture is already running. Call stop()
            # first.") — the NEW session died instead of the stale capture
            # (live 2026-07-29 02:30:45). Reset once and retry; a second
            # failure raises loudly (No Error Masking, rules/CODE.md).
            logger.warning("dxcam start refused (%s) — resetting capture and retrying", e)
            try:
                self._camera.stop()
            except Exception as stop_err:  # dxcam raises bare on double-stop
                logger.warning("Camera reset stop: %s", stop_err)
            self._camera.start(target_fps=fps, video_mode=True)
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        try:
            if not self._camera.is_released:
                self._camera.stop()
        except Exception as e:  # dxcam raises bare on double-stop; log, don't crash shutdown
            logger.warning("Camera stop: %s", e)

    def _loop(self) -> None:
        while self._running:
            try:
                frame = self._camera.get_latest_frame()  # blocks until a new frame
            except Exception as e:
                # The camera went out from under us. That is the ORDINARY end
                # of an evicted capture (task 193): `close()` joins this thread
                # for two seconds and then releases anyway, so a grab already
                # blocked inside dxcam raises. It must end the loop quietly —
                # never take the process down, and never be mistaken for a
                # capture failure on a camera we still own.
                if not self._running or self._closed:
                    return
                logger.error("Capture grab failed: %s", e)
                raise
            if self._shot_request.is_set():
                self._shot_request.clear()
                self._shot_frame = frame.copy()  # dxcam reuses its ring buffer
                self._shot_ready.set()
            self._process(frame)

    def _process(self, frame) -> None:
        raise NotImplementedError


class JpegStreamer(BaseCapture):
    """JPEG-per-frame fallback path with region-of-interest streaming: crop to
    the client's viewport, downscale, encode, hand bytes to the callback."""

    mode = "jpeg"

    def __init__(self, on_frame):
        """on_frame: callable(jpeg: bytes, region: tuple[float, float, float, float])
        invoked from the capture thread; region is the monitor-normalized
        (x, y, w, h) rectangle the frame covers."""
        super().__init__()
        self._on_frame = on_frame
        self._viewport = FULL_REGION  # written by the web layer, read by the capture thread
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, SETTINGS.jpeg_quality]

    def set_viewport(self, x: float, y: float, w: float, h: float) -> None:
        """Called from the web layer when the client's visible region changes.
        Tuple assignment is atomic — no lock needed for this single writer."""
        x = min(max(x, 0.0), 1.0)
        y = min(max(y, 0.0), 1.0)
        w = min(max(w, 0.0), 1.0 - x)
        h = min(max(h, 0.0), 1.0 - y)
        if w == 0.0 or h == 0.0:
            logger.warning("Ignoring empty viewport request (%s, %s, %s, %s)", x, y, w, h)
            return
        self._viewport = (x, y, w, h)

    def switch_monitor(self, index: int) -> bool:
        ok = super().switch_monitor(index)
        if ok:
            self._viewport = FULL_REGION
        return ok

    def switch_to(self, index: int) -> bool:
        """Stop → swap monitor → start, as the one operation the web layer
        calls. Blocking — call from a worker thread."""
        self.stop()
        ok = self.switch_monitor(index)
        self.start()
        return ok

    def _crop(self, frame):
        """Crops the frame to the current viewport; returns (frame, actual region)."""
        vx, vy, vw, vh = self._viewport
        if (vx, vy, vw, vh) == FULL_REGION:
            return frame, FULL_REGION
        x1 = int(vx * self.width)
        y1 = int(vy * self.height)
        x2 = min(self.width, max(x1 + MIN_REGION_PX, int((vx + vw) * self.width)))
        y2 = min(self.height, max(y1 + MIN_REGION_PX, int((vy + vh) * self.height)))
        region = (
            x1 / self.width,
            y1 / self.height,
            (x2 - x1) / self.width,
            (y2 - y1) / self.height,
        )
        return frame[y1:y2, x1:x2], region

    def _process(self, frame) -> None:
        frame, region = self._crop(frame)
        h, w = frame.shape[:2]
        if w > SETTINGS.max_stream_width:
            scale = SETTINGS.max_stream_width / w
            frame = cv2.resize(
                frame, (SETTINGS.max_stream_width, round(h * scale)), interpolation=cv2.INTER_AREA
            )
        ok, jpeg = cv2.imencode(".jpg", frame, self._encode_params)
        if not ok:
            logger.error("JPEG encode failed for a %sx%s frame", w, h)
            return
        self._on_frame(jpeg.tobytes(), region)


class FrameSink:
    """Latest-frame handoff to one encoder session. The capture thread offers
    every frame (as raw I420 bytes since task 130 — see `RawFrameSource._process`);
    the consumer takes the newest and misses the rest — drops happen before
    encoding, so the encoded stream stays intact."""

    def __init__(self):
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._data: bytes | None = None

    def offer(self, data: bytes) -> None:
        with self._lock:
            self._data = data
        self._event.set()

    def take(self, timeout: float) -> bytes | None:
        """Newest offered frame bytes, or None when nothing arrived within timeout."""
        if not self._event.wait(timeout):
            return None
        with self._lock:
            data, self._data = self._data, None
            self._event.clear()
        return data


class RawFrameSource(BaseCapture):
    """H.264 front-end: downscales each captured frame once and offers its raw
    BGR bytes to every registered sink (one per encoder session). One snapshot
    per frame total — the bytes are immutable and shared by all sinks, and the
    dxcam ring buffer is never read asynchronously."""

    def __init__(self):
        super().__init__()
        self._sinks: list[FrameSink] = []
        self._sinks_lock = threading.Lock()
        # THE PHONE MAY RAISE THE CEILING (owner decision, task 131). The
        # desktop Settings card is the DEFAULT, not a cap: lowering below it is
        # free (it happens inside the client's own ffmpeg), but going ABOVE it
        # needs the capture itself to run faster or wider, and capture is
        # shared. That is affordable only because "one device at a time" is a
        # hard rule (4409) — there is exactly one client whose wish this can
        # be. `None` means "follow the desktop"; a number is that client's
        # raised request, and it is dropped the moment it stops asking.
        self.raised_fps: int | None = None
        self.raised_width: int | None = None
        self.stream_w, self.stream_h = self._stream_size()

    @property
    def capture_fps(self) -> int:
        """What the camera is actually asked to grab at — the desktop's rate,
        or the higher one a client raised it to."""
        return max(SETTINGS.target_fps, self.raised_fps or 0)

    @property
    def max_width(self) -> int:
        return max(SETTINGS.h264_max_width, self.raised_width or 0)

    def _stream_size(self) -> tuple[int, int]:
        """Monitor size capped at the encoder width, even-rounded (yuv420 needs
        even dimensions). Never UPSCALES: the cap is a ceiling on what is fed
        to the encoder, so a raise above the monitor's own size buys nothing
        and is simply the monitor."""
        w, h = self.width, self.height
        cap = self.max_width
        if w > cap:
            scale = cap / w
            w, h = cap, round(h * scale)
        return _even(w), _even(h)

    def raise_limits(self, fps: int | None, width: int | None) -> bool:
        """A client asks for more than the desktop allows (task 131). Returns
        True when capture really has to be rebuilt — the caller then restarts
        it, and the picture BLINKS, which is exactly what the phone's panel
        promises before he taps.

        Only ever called with the single connected client's wish, and called
        again with `None`/`None` when it stops wanting more, so the desktop's
        own numbers are never permanently overridden by a phone that left."""
        fps = fps if fps and fps > SETTINGS.target_fps else None
        width = width if width and width > SETTINGS.h264_max_width else None
        if (fps, width) == (self.raised_fps, self.raised_width):
            return False
        self.raised_fps, self.raised_width = fps, width
        self.stream_w, self.stream_h = self._stream_size()
        logger.info("Capture ceiling raised by the phone — fps=%s width=%s "
                    "(desktop: %d fps, %d px)", fps or "desktop", width or "desktop",
                    SETTINGS.target_fps, SETTINGS.h264_max_width)
        return True

    def switch_monitor(self, index: int) -> bool:
        ok = super().switch_monitor(index)
        if ok:
            self.stream_w, self.stream_h = self._stream_size()
        return ok

    def add_sink(self, sink: FrameSink) -> None:
        with self._sinks_lock:
            self._sinks.append(sink)

    def remove_sink(self, sink: FrameSink) -> None:
        with self._sinks_lock:
            if sink in self._sinks:
                self._sinks.remove(sink)

    def _process(self, frame) -> None:
        target = (self.stream_w, self.stream_h)
        if (frame.shape[1], frame.shape[0]) != target:
            frame = cv2.resize(frame, target, interpolation=cv2.INTER_AREA)
        elif frame.shape[1] % 2 or frame.shape[0] % 2:
            frame = frame[:self.stream_h, :self.stream_w]  # odd-sized monitor — trim to even
        # I420, NOT bgr24 — and it is FASTER, not merely smaller. Measured on
        # the owner's own 4K monitor (2026-08-09, after he found the app
        # spending 320% CPU at 60 fps with NVENC confirmed in his log):
        #
        #   bgr24  tobytes only          5.56 ms   24.88 MB per frame
        #   BGR->I420 convert + tobytes  4.30 ms   12.44 MB per frame
        #
        # The COPY dominates, so halving the bytes more than pays for the
        # conversion. And it is a conversion that happened ANYWAY: ffmpeg was
        # doing bgr24 -> yuv420p in swscale, on the CPU, for every frame, one
        # process later. Doing it here removes that AND halves the pipe —
        # 1.49 GB/s down to 0.75 at 4K60, per client.
        #
        # The ENCODING was never the problem: NVENC runs on the GPU. The
        # problem is that every pixel is CARRIED there by the CPU, and this is
        # the cheapest honest way to carry half as many. `_stream_size` already
        # guarantees the even dimensions I420 requires.
        #
        # RESTORED ALONE on 2026-08-11 (task 130). It first shipped in
        # 0.0.367 and was reverted wholesale in 0.0.375 — not because it was
        # wrong (it was measured, and a real ffmpeg accepted it at 4K with
        # NVENC) but because it went out beside two other changes to the
        # picture and nothing could be attributed. His rule: one at a time.
        # These two lines and the `-pix_fmt yuv420p` in h264_streamer's input
        # flags are ONE decision — a mismatch does not fail, it produces a
        # picture in the wrong colours.
        data = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420).tobytes()
        with self._sinks_lock:
            for sink in self._sinks:
                sink.offer(data)
