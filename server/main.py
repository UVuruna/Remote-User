"""Remote User server entry point — wires DPI awareness, logging, capture, web, pairing."""

import asyncio
import ctypes
import ctypes.wintypes as wintypes
import logging
from logging.handlers import RotatingFileHandler

import uvicorn

from config import SETTINGS

logger = logging.getLogger(__name__)

# Must run before any capture or injection (root CLAUDE constraint):
# without PER_MONITOR_AWARE_V2, Windows silently rescales coordinates.
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4


def declare_dpi_awareness() -> None:
    """The context handle is pointer-sized — passing a bare int truncates on
    64-bit and the call fails SILENTLY (found by a monitor-enumeration test
    returning DPI-scaled sizes). c_void_p + checked return, or we refuse to run."""
    user32 = ctypes.windll.user32
    user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    if not user32.SetProcessDpiAwarenessContext(
        ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    ):
        raise RuntimeError("Failed to declare per-monitor DPI awareness — refusing to run, "
                           "clicks would land at wrong coordinates")


def setup_logging() -> None:
    SETTINGS.log_dir.mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        SETTINGS.log_dir / SETTINGS.log_file,
        maxBytes=SETTINGS.log_max_bytes,
        backupCount=SETTINGS.log_backups,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[handler, logging.StreamHandler()],
    )


async def main() -> None:
    declare_dpi_awareness()
    setup_logging()

    # Imports that touch the GPU/screen come after DPI awareness is declared.
    import encoders
    import monitors
    from input_injector import InputInjector
    from pairing import generate_token, show_pairing
    from web import FrameHub, create_app

    loop = asyncio.get_running_loop()

    # Stream mode is decided once, at startup: H.264 when a verified encoder
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

    token = generate_token()
    app = create_app(stream, hub, injector, token)
    show_pairing(token)

    if stream.mode == "jpeg":
        stream.start()  # H.264 capture starts when the first client connects
    try:
        # log_level info so every HTTP/WS access is visible — with "warning" a
        # failing client is invisible in the log, which already cost us a debug
        # session (the phone WAS reaching the server while the log showed nothing).
        server = uvicorn.Server(
            uvicorn.Config(app, host=SETTINGS.host, port=SETTINGS.port, log_level="info")
        )
        await server.serve()
    finally:
        if stream.mode == "jpeg":
            stream.stop()
        else:
            stream.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
