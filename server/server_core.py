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
import time
from dataclasses import dataclass, field

import uvicorn

import encoders
import focus_hook
import foreground_lock
import monitors
import pairing
import traffic
import window_manager
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
        # One registry for the PROCESS, not per server run: "Apply & restart"
        # used to build a fresh empty one, which threw away the owner's
        # layouts and the only list of windows still standing always-on-top.
        self.layouts = window_manager.LayoutRegistry()
        # Whatever a previous run was killed holding, put right before we can
        # possibly raise anything of our own — the always-on-top band, and
        # (round R2) Windows' foreground lock, which is the same discipline
        # applied to a machine-wide setting.
        window_manager.repair_stranded()
        foreground_lock.repair_stranded()
        # …and only THEN take it, if the owner's switch says so. Applied here
        # rather than in the window, because both entry points build a
        # controller and the headless CLI is entitled to the same setting.
        # Releasing it is NOT part of release_windows(): that runs on every
        # server stop (Apply & restart), and this lock belongs to the PROCESS
        # — the entry points release it on the way out (gui_main.py, main.py).
        if SETTINGS.foreground_lock:
            foreground_lock.apply(True)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Non-blocking: spawns the server thread. No-op when already up."""
        if self._thread and self._thread.is_alive():
            return
        self.state = "starting"
        self.error = None
        self._thread = threading.Thread(target=self._run, name="server-core", daemon=True)
        self._thread.start()

    def release_windows(self) -> None:
        """THE exit call: hand every window we raised back to the normal
        z-band and stop the foreground-hook thread, NOW, on the calling
        thread. Deliberately not part of the async teardown: dropping the
        topmost band is a handful of SetWindowPos calls that need no event
        loop, and the event loop is exactly what may be busy placing a 2x2
        layout when the owner hits Quit. Called before every stop, and again
        from the process-exit hooks — it is idempotent.

        Every documented way out of this process funnels here: tray Quit,
        server stop, Apply & restart, Ctrl+C, a console close, Qt's
        aboutToQuit, `atexit`. Which is why the Win32 resources that must not
        outlive us are released HERE and nowhere else."""
        try:
            window_manager.release_all()
        except Exception:  # nothing on the way out may raise
            logger.exception("Releasing the always-on-top windows failed")
        try:
            focus_hook.stop()
        except Exception:
            logger.exception("Stopping the foreground-hook listener failed")

    def stop(self, timeout: float = 10.0) -> None:
        """Stops uvicorn and waits for the thread to unwind.

        force_exit, not just should_exit: graceful shutdown DRAINS open
        connections, and a phone watching the stream keeps its WebSocket
        open — the drain then waits forever, the old thread got abandoned
        still bound to the port, and the next start() failed with
        port-in-use. That was the live "Apply & restart does nothing"
        failure; a client must never be able to hold the server hostage."""
        # BEFORE anything can block: the join below may wait out its full
        # timeout while the server thread is mid-placement, and the owner must
        # never be left with windows nailed above his desk because a stop took
        # too long (audit 2026-08-05).
        self.release_windows()
        thread = self._thread
        if thread and thread.is_alive() and self._uvicorn is None:
            # stop() during startup — wait for the uvicorn instance to exist
            # so the exit flags have something to land on.
            deadline = time.monotonic() + timeout
            while self._uvicorn is None and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
        if self._uvicorn:
            self._uvicorn.force_exit = True
            self._uvicorn.should_exit = True
        if thread:
            thread.join(timeout)
            if thread.is_alive():
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
        app = create_app(stream, hub, injector, token, stats=stats,
                         layouts=self.layouts)
        # The traffic meter samples for the life of the PROCESS once started:
        # a stopped server has to read as a line of zeros on the owner's
        # graph, never as a hole where anything could have happened.
        traffic.METER.start()
        if self._console_pairing:
            pairing.show_pairing(token)

        # Capture is ON DEMAND in both modes now: H.264 starts it with the
        # first session, and the JPEG fallback starts it with the first
        # subscriber (web.FrameHub.subscribers). Nothing is captured, encoded
        # or sent while no phone is watching — which is the flat line the
        # owner's traffic graph has to be able to show.
        try:
            # log_level info so every HTTP/WS access is visible — with "warning" a
            # failing client is invisible in the log, which already cost us a debug
            # session (the phone WAS reaching the server while the log showed nothing).
            # log_config=None: uvicorn's own dictConfig calls sys.stdout.isatty(),
            # which crashes in a windowed (no-console) PyInstaller app where stdout
            # is None; without it uvicorn's loggers propagate to our root handlers.
            # lifespan="off": we use no startup/shutdown hooks, and force_exit
            # cancels the lifespan task mid-wait — every stop would log a
            # scary (but harmless) CancelledError traceback.
            self._uvicorn = uvicorn.Server(uvicorn.Config(
                app, host=SETTINGS.host, port=SETTINGS.port,
                log_level="info", log_config=None, lifespan="off",
            ))
            self.state = "running"
            await self._uvicorn.serve()
        finally:
            self._uvicorn = None
            # FIRST, ahead of the encoder teardown: a hanging ffmpeg terminate
            # must not be able to eat the one thing the owner notices.
            self.release_windows()
            if stream.mode == "jpeg":
                stream.stop()
            else:
                stream.shutdown()
