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


def _even(n: int) -> int:
    return n - (n % 2)  # H.264 yuv420 needs even dimensions


class BaseCapture:
    """Camera lifecycle + capture thread + screenshot service shared by all
    streaming front-ends. Subclasses implement `_process(frame)`, called from
    the capture thread for every grabbed frame."""

    def __init__(self):
        self._camera = self._open(SETTINGS.monitor_index)
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
        camera = dxcam.create(output_idx=index, output_color="BGR")
        if camera is None:
            raise RuntimeError(f"dxcam could not open monitor {index}")
        return camera

    @staticmethod
    def output_count() -> int:
        """Number of dxcam-visible outputs (info lines like 'Device[0] Output[0]: …')."""
        return dxcam.output_info().count("Output[")

    def switch_monitor(self, index: int) -> bool:
        """Swaps the capture source. Must be called while stopped. On failure
        the previous camera stays in place."""
        camera = dxcam.create(output_idx=index, output_color="BGR")
        if camera is None:
            logger.error("dxcam could not open monitor %d", index)
            return False
        self._camera = camera
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
        self._camera.start(target_fps=SETTINGS.target_fps, video_mode=True)
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        try:
            self._camera.stop()
        except Exception as e:  # dxcam raises bare on double-stop; log, don't crash shutdown
            logger.warning("Camera stop: %s", e)

    def _loop(self) -> None:
        while self._running:
            frame = self._camera.get_latest_frame()  # blocks until a new frame
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
    every frame (as raw BGR bytes); the consumer takes the newest and misses
    the rest — drops happen before encoding, so the encoded stream stays intact."""

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
        self.stream_w, self.stream_h = self._stream_size()

    def _stream_size(self) -> tuple[int, int]:
        """Monitor size capped at h264_max_width, even-rounded (yuv420 needs
        even dimensions). Default cap streams native 4K — inter-frame
        compression keeps it cheap and zoom stays sharp."""
        w, h = self.width, self.height
        if w > SETTINGS.h264_max_width:
            scale = SETTINGS.h264_max_width / w
            w, h = SETTINGS.h264_max_width, round(h * scale)
        return _even(w), _even(h)

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
        data = frame.tobytes()  # the one copy: detaches from dxcam's ring buffer
        with self._sinks_lock:
            for sink in self._sinks:
                sink.offer(data)
