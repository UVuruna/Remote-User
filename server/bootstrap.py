"""Process bootstrap shared by both entry points (CLI main.py, desktop GUI).

Everything here must run BEFORE any module that touches the screen, the GPU or
injection is imported — that is the whole reason this file exists and stays
free of heavy imports (ctypes + stdlib only).
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import sys
from logging.handlers import RotatingFileHandler

from config import SETTINGS, load_user_settings

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
    SETTINGS.log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [RotatingFileHandler(
        SETTINGS.log_dir / SETTINGS.log_file,
        maxBytes=SETTINGS.log_max_bytes,
        backupCount=SETTINGS.log_backups,
        encoding="utf-8",
    )]
    if sys.stderr is not None:  # windowed (no-console) EXE has no stderr — file only
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def init_process() -> None:
    """DPI awareness → logging → user settings, in that order. Call FIRST,
    before importing server_core / capture / gui modules."""
    declare_dpi_awareness()
    setup_logging()
    load_user_settings()
