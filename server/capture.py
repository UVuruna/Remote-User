"""Screen capture and JPEG encoding.

A dedicated thread grabs frames from the selected monitor via dxcam (DXGI
Desktop Duplication), optionally crops to the client's current viewport
(region-of-interest streaming — this is what keeps zoom sharp without raising
bandwidth), downscales when the result is wider than `max_stream_width`,
encodes to JPEG with OpenCV, and hands the bytes plus the covered region to a
callback. The callback must be cheap and thread-safe — the web layer uses it
to fan frames out to connected clients.
"""

import logging
import threading

import cv2
import dxcam

from config import SETTINGS

logger = logging.getLogger(__name__)

FULL_REGION = (0.0, 0.0, 1.0, 1.0)
MIN_REGION_PX = 64  # never crop below this many pixels per axis


class ScreenStreamer:
    def __init__(self, on_frame):
        """on_frame: callable(jpeg: bytes, region: tuple[float, float, float, float])
        invoked from the capture thread; region is the monitor-normalized
        (x, y, w, h) rectangle the frame covers."""
        self._on_frame = on_frame
        self._camera = dxcam.create(output_idx=SETTINGS.monitor_index, output_color="BGR")
        if self._camera is None:
            raise RuntimeError(f"dxcam could not open monitor {SETTINGS.monitor_index}")
        self.monitor_index = SETTINGS.monitor_index
        self.width, self.height = self._camera.width, self._camera.height
        self._viewport = FULL_REGION  # written by the web layer, read by the capture thread
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, SETTINGS.jpeg_quality]
        self._thread: threading.Thread | None = None
        self._running = False
        self._shot_request = threading.Event()
        self._shot_ready = threading.Event()
        self._shot_frame = None
        logger.info("Capture ready — monitor %d (%dx%d)", SETTINGS.monitor_index, self.width, self.height)

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

    @staticmethod
    def output_count() -> int:
        """Number of dxcam-visible outputs (info lines like 'Device[0] Output[0]: …')."""
        return dxcam.output_info().count("Output[")

    def switch_monitor(self, index: int) -> bool:
        """Swaps the capture source. Must be called while stopped."""
        camera = dxcam.create(output_idx=index, output_color="BGR")
        if camera is None:
            logger.error("dxcam could not open monitor %d", index)
            return False
        self._camera = camera
        self.monitor_index = index
        self.width, self.height = camera.width, camera.height
        self._viewport = FULL_REGION
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
        self._camera.stop()

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

    def _loop(self) -> None:
        while self._running:
            frame = self._camera.get_latest_frame()  # blocks until a new frame
            if self._shot_request.is_set():
                self._shot_request.clear()
                self._shot_frame = frame.copy()  # dxcam reuses its ring buffer
                self._shot_ready.set()
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
                continue
            self._on_frame(jpeg.tobytes(), region)
