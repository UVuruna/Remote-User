"""H.264 screen streamer: dxcam capture -> ffmpeg (hardware/software) -> fMP4.

Replaces the JPEG-per-frame path with an inter-frame-compressed H.264 stream —
a static screen costs almost nothing, and a hardware encoder keeps latency low.
The output is fragmented MP4 (fMP4) so the browser/WebView can decode it live via
Media Source Extensions.

Pipeline: dxcam grabs BGR frames -> (optional downscale) -> ffmpeg stdin (rawvideo)
-> ffmpeg encodes with the auto-detected encoder -> fMP4 bytes on stdout -> callback.
Three threads: feed stdin, drain stdout (the stream), drain stderr (logging).
"""

import logging
import subprocess
import threading

import cv2
import dxcam

import encoders
from config import SETTINGS

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000
READ_CHUNK = 32768


def _even(n: int) -> int:
    return n - (n % 2)  # yuv420 needs even dimensions


class H264Streamer:
    def __init__(self, on_data, encoder: str):
        """on_data(bytes): called from the read thread with fMP4 chunks.
        encoder: an ffmpeg encoder verified by encoders.detect_encoder()."""
        self._on_data = on_data
        self.encoder = encoder
        self._camera = dxcam.create(output_idx=SETTINGS.monitor_index, output_color="BGR")
        if self._camera is None:
            raise RuntimeError(f"dxcam could not open monitor {SETTINGS.monitor_index}")
        self.monitor_index = SETTINGS.monitor_index
        self.width, self.height = self._camera.width, self._camera.height
        self.stream_w, self.stream_h = self._stream_size()
        self._proc: subprocess.Popen | None = None
        self._running = False
        self._threads: list[threading.Thread] = []
        logger.info(
            "H264Streamer ready — monitor %d %dx%d, stream %dx%d, encoder %s",
            self.monitor_index, self.width, self.height, self.stream_w, self.stream_h, self.encoder,
        )

    def _stream_size(self) -> tuple[int, int]:
        w, h = self.width, self.height
        if w > SETTINGS.max_stream_width:
            scale = SETTINGS.max_stream_width / w
            w, h = SETTINGS.max_stream_width, round(h * scale)
        return _even(w), _even(h)

    def _ffmpeg_cmd(self) -> list[str]:
        return [
            SETTINGS.ffmpeg_path, "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{self.stream_w}x{self.stream_h}", "-r", str(SETTINGS.target_fps),
            "-i", "pipe:0", "-an",
            "-c:v", self.encoder, *encoders.encoder_args(self.encoder),
            "-g", str(SETTINGS.h264_gop), "-pix_fmt", "yuv420p",
            "-b:v", SETTINGS.h264_bitrate, "-maxrate", SETTINGS.h264_bitrate,
            "-f", "mp4",
            "-movflags", "+frag_keyframe+empty_moov+default_base_moof",
            "-frag_duration", "16000", "-flush_packets", "1",  # small fragments, flush promptly
            "pipe:1",
        ]

    def start(self) -> None:
        self._proc = subprocess.Popen(
            self._ffmpeg_cmd(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW, bufsize=0,
        )
        self._camera.start(target_fps=SETTINGS.target_fps, video_mode=True)
        self._running = True
        for target in (self._feed_loop, self._read_loop, self._stderr_loop):
            t = threading.Thread(target=target, name=target.__name__, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._running = False
        if self._proc:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            self._proc.terminate()
        try:
            self._camera.stop()
        except Exception as e:  # dxcam raises bare on double-stop; log, don't crash shutdown
            logger.warning("Camera stop: %s", e)
        for t in self._threads:
            t.join(timeout=2)

    def _feed_loop(self) -> None:
        target = (self.stream_w, self.stream_h)
        while self._running:
            frame = self._camera.get_latest_frame()
            if frame is None:
                continue
            if (frame.shape[1], frame.shape[0]) != target:
                frame = cv2.resize(frame, target, interpolation=cv2.INTER_AREA)
            try:
                self._proc.stdin.write(frame.tobytes())
            except (BrokenPipeError, OSError, ValueError):
                break  # pipe closed by stop() mid-write — normal shutdown

    def _read_loop(self) -> None:
        while self._running:
            chunk = self._proc.stdout.read(READ_CHUNK)
            if not chunk:
                break
            self._on_data(chunk)

    def _stderr_loop(self) -> None:
        for line in self._proc.stderr:
            text = line.decode(errors="replace").strip()
            if text:
                logger.error("ffmpeg: %s", text)
