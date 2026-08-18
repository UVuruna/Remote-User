"""Window registry for `uv shot` (root rules/tools/uv.py, rules/howto/runner.md).

The factories are NOT written twice: `tests/test_layout_audit_qt.py` already
builds every top-level Qt window in its fullest realistic state - a running
server with the longest guidance text, the set with the longest command pool,
the update offer that only arrives after the window was measured - for the
runtime half of THE SPACE & LEGIBILITY LAW. This file points the runner at
those same builders. One window built two ways is two windows in practice, and
the audit's one is the one the law is written about.

Registered here: the four windows the owner opens. The audit's three extra
MainWindow STATES (server stopped, reopened from the tray) stay in the pytest
audit - they are the same window, and `uv shot` photographs windows.

The phone client is the other half of this product and is not in here: it is a
web page, and its profiles (phone-portrait, phone-landscape, tablet-landscape)
are shot with `uv device <profile> <url>`, not by building a Qt widget.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = PROJECT_ROOT / "server"            # the Python root: gui/, web.py
TESTS_ROOT = PROJECT_ROOT / "tests"

for entry in (SERVER_ROOT, TESTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

TOOLKIT = "qt"                                   # PySide6

# rules/devices.json. The desktop app is judged on the two PC profiles; the
# phone/tablet ones belong to `uv device` and are listed in CLAUDE.md.
# Neither of these is the owner's own machine - we build for others.
MANDATORY_PROFILES = ["laptop-avg", "pc-low"]


def prepare() -> None:
    """Give the offscreen platform real fonts.

    Qt's offscreen QPA plugin on Windows starts with an EMPTY platform font
    database, so every label falls back to QFontEngineBox and the PNG comes
    out as rows of tofu boxes - a picture nobody can grade, measured at
    metrics the owner never sees. The cure is to register the machine's own
    font files as APPLICATION fonts: the offscreen plugin loads those through
    FreeType even though its platform database is empty. A no-op on a native
    platform, where families already exist.
    """
    import os

    from PySide6.QtGui import QFontDatabase, QGuiApplication

    if QGuiApplication.instance() is None or QFontDatabase.families():
        return
    directories = (
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows"
        / "Fonts",
    )
    for directory in directories:
        if not directory.is_dir():
            continue
        for font in directory.iterdir():
            if font.suffix.lower() in (".ttf", ".ttc", ".otf"):
                QFontDatabase.addApplicationFont(str(font))


def _audit_factory(name: str):
    """The builder of `name` from the pytest layout audit's own registry."""
    import test_layout_audit_qt

    for window_name, factory in test_layout_audit_qt.WINDOWS:
        if window_name == name:
            return factory
    raise KeyError(f"{name} is not in tests/test_layout_audit_qt.py WINDOWS")


def make_main_window():
    return _audit_factory("MainWindow")()


def make_settings_window():
    return _audit_factory("SettingsWindow")()


def make_controls_editor():
    return _audit_factory("ControlsEditor")()


def make_traffic_window():
    return _audit_factory("TrafficWindow")()


WINDOWS = {
    "MainWindow": make_main_window,
    "SettingsWindow": make_settings_window,
    "ControlsEditor": make_controls_editor,
    "TrafficWindow": make_traffic_window,
}
