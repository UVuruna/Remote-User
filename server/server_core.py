"""The server as a component: build once, start/stop from any thread.

Shared by both entry points — `main.py` (CLI, blocking on the main thread) and
the desktop GUI (background thread, controlled by buttons). Owns everything
`main.py` used to wire inline: stream-mode decision (H.264 vs JPEG), injector,
pairing info, uvicorn lifecycle, teardown.

The process must already be per-monitor DPI aware BEFORE this module is
imported (both entry points declare it first) — capture and injection break
silently otherwise.
"""

import asyncio
import logging
import threading
from dataclasses import dataclass, field

import uvicorn

import encoders
import monitors
import pairing
from config import SETTINGS
from input_injector import InputInjector
from web import FrameHub, ServerStats, create_app

logger = logging.getLogger(__name__)


@dataclass
class ServerInfo:
    """Everything the GUI shows about a running server."""
    mode: str                 # "h264" | "jpeg"
    encoder: str | None       # e.g. "h264_nvenc"; None in JPEG mode
    monitor_width: int
    monitor_height: int
    port: int
    token: str
    qr_url: str               # preferred address (Tailscale when present)
    lan_url: str
    tailscale_ip: str | None
    stats: ServerStats = field(default_factory=ServerStats)


class ServerController:
    """start()/stop() the whole server stack. One instance per process.

    States: "stopped" → "starting" → "running" → "stopped", or "failed"
    (with .error set). The GUI polls state/info; the CLI uses run_blocking().
    """

    def __init__(self, console_pairing: bool = False):
        self._console_pairing = console_pairing
        self._thread: threading.Thread | None = None
        self._uvicorn: uvicorn.Server | None = None
        self.state = "stopped"
        self.error: str | None = None
        self.info: ServerInfo | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Non-blocking: spawns the server thread. No-op when already up."""
        if self._thread and self._thread.is_alive():
            return
        self.state = "starting"
        self.error = None
        self._thread = threading.Thread(target=self._run, name="server-core", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        """Signals uvicorn to exit and waits for the thread to unwind."""
        if self._uvicorn:
            self._uvicorn.should_exit = True
        if self._thread:
            self._thread.join(timeout)
            if self._thread.is_alive():
                logger.error("Server thread did not stop within %.0fs", timeout)
            self._thread = None
        if self.state != "failed":
            self.state = "stopped"

    def run_blocking(self) -> None:
        """CLI mode: run on the calling thread until Ctrl+C/exit."""
        try:
            asyncio.run(self._serve())
        finally:
            if self.state != "failed":
                self.state = "stopped"

    def _run(self) -> None:
        try:
            asyncio.run(self._serve())
            if self.state != "failed":
                self.state = "stopped"
        except Exception as e:  # visible in log AND in the GUI status
            logger.exception("Server crashed")
            self.state = "failed"
            self.error = str(e)

    # -- the stack ---------------------------------------------------------

    async def _serve(self) -> None:
        loop = asyncio.get_running_loop()

        # Stream mode is decided per start: H.264 when a verified encoder
        # exists (capture then runs on demand, per client), JPEG otherwise.
        encoder = encoders.detect_encoder() if SETTINGS.use_h264 else None
        hub = None
        if encoder:
            from h264_streamer import H264Manager
            stream = H264Manager(encoder)
        else:
            from capture import JpegStreamer
            if SETTINGS.use_h264:
                logger.warning("No working H.264 encoder/ffmpeg — falling back to JPEG streaming")
            hub = FrameHub(loop)
            stream = JpegStreamer(on_frame=hub.push_threadsafe)

        injector = InputInjector(
            monitor_rect=monitors.rect_for_size(stream.width, stream.height, stream.monitor_index)
        )

        token = pairing.generate_token()
        urls = pairing.pairing_urls(token)
        stats = ServerStats()
        self.info = ServerInfo(
            mode=stream.mode,
            encoder=encoder,
            monitor_width=stream.width,
            monitor_height=stream.height,
            port=SETTINGS.port,
            token=token,
            qr_url=urls["qr"],
            lan_url=urls["lan"],
            tailscale_ip=urls["tailscale_ip"],
            stats=stats,
        )
        app = create_app(stream, hub, injector, token, stats=stats)
        if self._console_pairing:
            pairing.show_pairing(token)

        if stream.mode == "jpeg":
            stream.start()  # H.264 capture starts when the first client connects
        try:
            # log_level info so every HTTP/WS access is visible — with "warning" a
            # failing client is invisible in the log, which already cost us a debug
            # session (the phone WAS reaching the server while the log showed nothing).
            # log_config=None: uvicorn's own dictConfig calls sys.stdout.isatty(),
            # which crashes in a windowed (no-console) PyInstaller app where stdout
            # is None; without it uvicorn's loggers propagate to our root handlers.
            self._uvicorn = uvicorn.Server(uvicorn.Config(
                app, host=SETTINGS.host, port=SETTINGS.port,
                log_level="info", log_config=None,
            ))
            self.state = "running"
            await self._uvicorn.serve()
        finally:
            self._uvicorn = None
            if stream.mode == "jpeg":
                stream.stop()
            else:
                stream.shutdown()
