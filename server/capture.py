"""Screen capture and JPEG encoding.

A dedicated thread grabs frames from the selected monitor via dxcam (DXGI
Desktop Duplication), encodes each to JPEG with OpenCV, and hands the bytes to
a callback. The callback must be cheap and thread-safe — the web layer uses it
to fan frames out to connected clients.
"""

import logging
import threading

import cv2
import dxcam

from config import SETTINGS

logger = logging.getLogger(__name__)


class ScreenStreamer:
    def __init__(self, on_frame):
        """on_frame: callable(bytes) invoked from the capture thread for every JPEG."""
        self._on_frame = on_frame
        self._camera = dxcam.create(output_idx=SETTINGS.monitor_index, output_color="BGR")
        if self._camera is None:
            raise RuntimeError(f"dxcam could not open monitor {SETTINGS.monitor_index}")
        self.width, self.height = self._camera.width, self._camera.height
        self._stream_size: tuple[int, int] | None = None
        if self.width > SETTINGS.max_stream_width:
            scale = SETTINGS.max_stream_width / self.width
            self._stream_size = (SETTINGS.max_stream_width, round(self.height * scale))
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, SETTINGS.jpeg_quality]
        self._thread: threading.Thread | None = None
        self._running = False
        logger.info(
            "Capture ready — monitor %d (%dx%d), stream %s",
            SETTINGS.monitor_index, self.width, self.height,
            f"{self._stream_size[0]}x{self._stream_size[1]}" if self._stream_size else "native",
        )

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

    def _loop(self) -> None:
        while self._running:
            frame = self._camera.get_latest_frame()  # blocks until a new frame
            if self._stream_size:
                frame = cv2.resize(frame, self._stream_size, interpolation=cv2.INTER_AREA)
            ok, jpeg = cv2.imencode(".jpg", frame, self._encode_params)
            if not ok:
                logger.error("JPEG encode failed for a %sx%s frame", self.width, self.height)
                continue
            self._on_frame(jpeg.tobytes())
