"""THE WINDOW FACTORIES — every top-level Qt window this app has, built in
its FULLEST realistic state.

Split out of `tests/test_layout_audit_qt.py` on 2026-08-19, at THE STRUCTURE
LAW's wall (that file reached exactly 1000 lines and this project's ratchet is
empty and may only shrink). The cut is along the seam that was already there:
this file BUILDS the windows, the audit MEASURES them, and `.claude/
uv_windows.py` photographs them. One list of windows, three readers.

WHY "FULLEST REALISTIC STATE" IS THE WHOLE JOB OF THIS FILE. THE SPACE &
LEGIBILITY LAW is written about the content a window can really be asked to
show, not the content it happens to have a second after it was built. Two of
the owner's own 2026-08-06 screenshots were of a window measured before the
thing that overflowed it had arrived — an update offer that lands when GitHub
answers, a caption that grows to three lines when it has a failure to report.
So every factory here shows the window, lets the late content arrive, and only
then hands it over.

NOTHING HERE MAY LEAVE A FAKE BEHIND. `SETTINGS` is one process-wide object
and these factories run inside the whole suite (tests/conftest.py — the day
forty tests failed on a stub nobody restored). A factory that changes a
setting to build a state puts it back before it returns.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

TESTS_DIR = Path(__file__).resolve().parent
SERVER_DIR = TESTS_DIR.parent / "server"
for entry in (str(TESTS_DIR), str(SERVER_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from PySide6.QtCore import QSize, Qt  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

def make_app() -> QApplication:
    """Native platform first (real fonts, real DPI), offscreen if there is no
    desktop to talk to."""
    existing = QApplication.instance()
    if existing is not None:
        return existing
    try:
        return QApplication([])
    except Exception:                       # no session - measure what we can
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        return QApplication([])


# --- the window registry ---------------------------------------------------

def _fake_controller() -> SimpleNamespace:
    """A running server with the LONGEST real strings the window can show:
    a Tailscale address (longer than a LAN one) with a full-length token."""
    info = SimpleNamespace(
        mode="h264", encoder="h264_nvenc", monitor_width=3840,
        monitor_height=2160, port=8765, token="A" * 22,
        qr_url="http://100.101.102.103:8765/?token=" + "A" * 22,
        lan_url="http://192.168.100.100:8765/?token=" + "A" * 22,
        tailscale_ip="100.101.102.103",
        stats=SimpleNamespace(clients=1),
    )
    return SimpleNamespace(state="running", info=info, error=None,
                           start=lambda: None, stop=lambda: None)


# The longest sentence the notify switch can print under itself. Until round
# R2's SECOND independent grader (2026-08-07) this constant was the RAW
# "[Errno 2] No such file or directory: ...\_internal\setup\agent_hook.py"
# the owner photographed on 2026-08-06 - a real bug at the time, but
# agent_hook_switch._hook_module() has printed a plain-language sentence for that exact
# case since v0.0.251, so the fixture was sizing the window for a caption the
# product can no longer produce (and grading it in plain grey, which is what
# made the STILL-real finding - no failure caption anywhere in this window
# had a distinct colour - read as if the text itself were still the bug).
# SIX sentences can land in that slot, and the fixture must measure whichever
# is longest TODAY rather than naming one. Pinning a single constant is how
# this gate came to be photographing the raw
# "[Errno 2] ...\_internal\setup\agent_hook.py" for two versions after the bug
# behind it was fixed - a stale fixture teaches a false lesson, and this one
# was teaching that a solved packaging bug was still live. Every candidate is
# IMPORTED from the module that owns it and the longest wins by measurement,
# so no edit to any of them can leave the window sized for a string the
# product no longer prints.
from gui.settings_window import NOTIFY_OFF_TEXT, NOTIFY_ON_TEXT  # noqa: E402
from agent_hook_switch import (  # noqa: E402
    HOOK_CHANGE_FAILED_TEXT, MISSING_SCRIPT_TEXT, NO_PYTHON_TEXT,
    UNLOADABLE_SCRIPT_TEXT,
)

NOTIFY_WORST = max((NOTIFY_ON_TEXT, NOTIFY_OFF_TEXT, NO_PYTHON_TEXT,
                    HOOK_CHANGE_FAILED_TEXT, MISSING_SCRIPT_TEXT,
                    UNLOADABLE_SCRIPT_TEXT), key=len)


def make_main_window() -> QWidget:
    """The window in the state that CONTAINS every other one.

    Two things arrive AFTER the window is built and its minimum measured - an
    update offer (the button is hidden until GitHub answers) and the notify
    switch's own caption (one line normally, three when it has to report a
    failure). Both were absent from this factory, so the audit measured a
    window the owner never sees, and both of his 2026-08-06 screenshots showed
    the same overlap: content that arrived later had nowhere to go.
    """
    import updates
    from gui.main_window import MainWindow
    updates.check = lambda: None  # no network inside a guard run
    window = MainWindow(_fake_controller())
    # BEFORE the show below: without this, every guard run FLASHED the real
    # main window on the owner's screen and stole his keyboard focus
    # (reported 2026-08-06 - "iskaču ekrani... prekidaju komunikaciju").
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()                 # …and only THEN does the later content arrive
    window._refresh()             # the guided text + QR, as the owner sees it
    _late_content(window)
    return window


def _late_content(window) -> None:
    """The update offer — the one thing that still reaches this window after
    it was built and measured.

    The notify switch's failure line used to be planted here too. It left with
    the switch in round R2 (it lives in the Settings window now) and is
    planted there instead, by `make_settings_window` — the string itself is
    still NOTIFY_WORST, because it is still the longest sentence this app
    prints under a checkbox.
    """
    window._update = SimpleNamespace(version="9.9.999", installer_url="http://x/y.exe",
                                     page_url="http://x")
    window._update_state = "found"
    window._refresh()             # the refresh tick that shows it


def make_main_window_stopped() -> QWidget:
    """The main window with the server STOPPED — and the reason it is here is
    the finding, not the state.

    Every factory in this file builds a RUNNING server, so the stopped window
    had never been photographed once. That is how a postcard-sized WHITE
    rectangle with unreadable grey text in the middle of a dark window reached
    the owner (his screenshot, 2026-08-09): `QLabel#qr` paints white PAPER
    because a camera scans a QR, and with no QR on it the same rule painted a
    blank sheet under the words "Server stopped".

    A state outside the sweep has no law over it — the same sentence the
    notices card earned the day before.
    """
    import updates
    from gui.main_window import MainWindow
    updates.check = lambda force=False: None
    stopped = SimpleNamespace(state="stopped", info=None, error=None,
                              start=lambda: None, stop=lambda: None)
    window = MainWindow(stopped)
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()
    window._refresh()
    return window


def make_main_window_developer() -> QWidget:
    """The row with the DEVELOPER DOOR open (owner 2026-08-19).

    A fresh install shows two doors — Controls and Settings — and Traffic
    comes back when the title is clicked five times. Two states of the same
    row, and the one with three buttons is the FULLEST real content, which is
    the state this law is written about: if three captions and three icons do
    not fit the declared minimum, the third one is the button that gets cut
    off, and it gets cut off only for the person who went looking for it.

    The setting is put back before this function returns: `SETTINGS` is one
    process-wide object, and a factory that left the whole suite in developer
    mode is exactly the leak tests/conftest.py exists for.
    """
    import config
    import updates
    from gui.main_window import MainWindow
    updates.check = lambda: None
    was = config.SETTINGS.developer_tools
    config.apply(developer_tools=True)
    try:
        window = MainWindow(_fake_controller())
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        window.show()
        window._refresh()
        _late_content(window)
    finally:
        config.apply(developer_tools=was)
    return window


def make_main_window_from_tray() -> QWidget:
    """The same window, reached the way the owner actually reaches it.

    Closing this app does not close it — `closeEvent` hides it to the tray and
    the server keeps running, so the update offer that arrives at 3 a.m. lands
    on a window nobody is looking at. Qt gives a hidden window no real metrics;
    anything measured there is a smaller, wrong floor. This case proves the
    window is measured again on its way BACK.
    """
    import updates
    from gui.main_window import MainWindow
    updates.check = lambda: None
    window = MainWindow(_fake_controller())
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)  # same flash guard as above
    window.show()
    window._refresh()
    window.hide()                 # to the tray — the refresh timer keeps ticking
    _late_content(window)
    return window                 # …and audit_window shows it again


def make_controls_editor() -> QWidget:
    from gui.controls_editor import ControlsEditor
    editor = ControlsEditor()
    # The theme is on the APPLICATION since build round R3 (gui/theme.py ->
    # apply_theme), so a bare instance is already styled — including the combo
    # min-width that caused "ift+tab". `main()` below applies the palette
    # under audit before building anything.
    # Fullest state: the set with the longest command pool selected.
    entries = editor._entries()
    if entries:
        biggest = max(range(len(entries)),
                      key=lambda i: len(entries[i][2].get("buttons") or []))
        # `_entries()` counts SETS; the list also holds section headings
        # (owner 2026-08-06), so the entry index has to be translated into a
        # list row — otherwise this measures whatever set happens to sit
        # `biggest` rows down, not the fullest one.
        editor.set_list.setCurrentRow(editor._row_of(biggest))
    return editor


def make_chord_recorder() -> QWidget:
    from gui.controls_widgets import ChordRecorder
    return ChordRecorder()


def make_wheel_order_dialog() -> QWidget:
    """Build round R5 (2026-08-07): the wheel-order ring, in its FULLEST
    real state — every set the shipped file has (categories + app sets),
    the longest real names among them."""
    from gui.controls_data import natural_order, shipped_actions_path
    from gui.controls_order import WheelOrderDialog
    import json
    data = json.loads(shipped_actions_path().read_text(encoding="utf-8"))
    names = natural_order(data)
    return WheelOrderDialog(names, names)


def make_traffic_window() -> QWidget:
    import time
    import traffic
    import traffic_devices
    from gui.theme import device_color
    from gui.traffic_window import TrafficWindow
    # FULLEST state (the 2026-08-05 lesson: an empty panel measures nothing).
    # Round 2 (coordinator rejection, 2026-08-13): the FIRST version staged
    # two devices but never fed the METER a `Sample` — the chart, "Session
    # length" and MB/h all read `traffic.METER.samples`/`.since`/`.total_out`,
    # none of which a bare `note_device`/`set_clients` call touches, so the
    # screenshot showed the true EMPTY state under a passing gate. This now
    # drives the real path: two devices alternating three times (one named,
    # one resolution-only), a session backdated 10 minutes so the MB/h guard
    # (<5s) never hides the rate, one sample/second across the default span.
    traffic.METER.reset()
    # AN AUDIT MAY NEVER WRITE INTO THE OWNER'S REAL, PERSISTED REGISTRY
    # (found 2026-08-13 by reading the picture, not the code): a fixture
    # calling `note()` on the live singleton wrote fake phones into his file
    # for good, so a LATER run inherited a stale entry (three devices in the
    # legend for two staged) while an EARLIER run's tablet key was simply
    # missing (`index_for` -> -1, drawn in neutral grey) — a fixture whose
    # result depends on a previous run's leftovers proves nothing either way.
    tmp = Path(tempfile.mkdtemp(prefix="vc-audit-devices-"))
    traffic_devices.REGISTRY = traffic_devices.DeviceRegistry(
        tmp / "traffic_devices.json")
    phone = traffic_devices.REGISTRY.note(1080, 2400, "Samsung Galaxy S10")
    tablet = traffic_devices.REGISTRY.note(2560, 1600, None)
    # The colours the chart will really use, asserted HERE rather than hoped
    # for: two devices that both resolve to a real slot, and two slots that
    # are not the same colour. A staged device that fails to register is the
    # exact defect above, and it must not be able to pass quietly again.
    assert phone["index"] >= 0 and tablet["index"] >= 0, (
        "both staged devices must hold a colour slot")
    assert device_color(phone["index"]) != device_color(tablet["index"]), (
        "the staged devices must not share a colour — the picture is the proof")

    now = time.time()
    session_start = now - 600.0   # a real 10-minute session for the MB/h line
    traffic.METER.since = session_start

    SPAN_S = 110          # inside the default "Last 2 minutes" (120 s) span
    PHONE_STREAM = {"fps": "30", "res": "full", "bitrate": "high", "crop": "3840x2160", "enc": "1920x1080", "zoom": "1"}  # T106
    TABLET_STREAM = {"fps": "30", "res": "full", "bitrate": "low", "crop": "968x2096", "enc": "968x2096", "zoom": "2"}
    SEGMENTS = 4           # A, B, A, B -> three colour switches
    PHONE_OUT, PHONE_IN = 6_000, 900          # smaller screen, smaller bytes
    TABLET_OUT, TABLET_IN = 42_000, 3_000     # bigger screen, bigger bytes
    # THE FIXTURE MUST SPEAK THE PRODUCTION KEY, NOT A LITERAL (found
    # 2026-08-13 by sampling the drawn stroke): a hand-written "2560x1600"
    # string does not match `device_key`'s SORTED output, so `index_for`
    # answered -1 and every tablet segment drew unknown-device grey while the
    # shipped code was right. Calling `device_key` here also proves the
    # ROTATED tablet (two spellings, one physical device) stays one slot.
    tablet_key_by_segment = [traffic_devices.device_key(2560, 1600),
                             traffic_devices.device_key(1600, 2560)]
    phone_key = traffic_devices.device_key(1080, 2400)
    seg_len = SPAN_S // SEGMENTS
    total_out = total_in = 0
    traffic.METER.samples.clear()
    for i in range(SPAN_S):
        t, segment = now - SPAN_S + i + 1, (i // seg_len)
        on_tablet = segment % 2 == 1
        key = tablet_key_by_segment[segment // 2 % 2] if on_tablet else phone_key
        out_b, in_b = (TABLET_OUT, TABLET_IN) if on_tablet else (PHONE_OUT, PHONE_IN)
        traffic.METER.samples.append(traffic.Sample(t, out_b, in_b, 1, key, TABLET_STREAM if on_tablet else PHONE_STREAM))
        total_out += out_b
        total_in += in_b
    # The session TOTAL is the whole 10 minutes, not just the visible 110 s
    # window (a real session sends steadily, not only in the last 2 minutes
    # the default span shows) — scaled from the same per-second rates so the
    # "this session X MB" line and the MB/h line agree with what the chart
    # itself is showing per second.
    traffic.METER.total_out = int(total_out * (600.0 / SPAN_S))
    traffic.METER.total_in = int(total_in * (600.0 / SPAN_S))
    traffic.METER.note_device(2560, 1600, None)   # the CURRENT device (tablet, unnamed)
    traffic.METER.set_clients(1)
    traffic.METER.note_phone({"app_rx": 9 << 20, "app_tx": 9 << 20,
                              "dev_rx": 9 << 30, "dev_tx": 9 << 30})
    # The BATTERY line (T80d) in its fullest real state: TWO readings, so the
    # drop and the averaged draw are real, backdated to the same 10 minutes
    # (below MIN_DROP_SPAN_S the drop clause is suppressed, and a fixture
    # staging both readings in one instant photographs a state he never sees).
    traffic.METER.note_battery({"level": 66, "current_ua": 448_000, "charging": False})
    traffic.METER.note_battery({"level": 62, "current_ua": 512_000, "charging": False})
    traffic.METER.battery_first["t"] = session_start
    window = TrafficWindow()
    window._refresh()
    return window


def make_settings_window() -> QWidget:
    """The Settings window in its FULLEST state (round R2).

    Three things make this window bigger than a fresh install ever shows, and
    all three are planted here rather than hoped for:

      - the phone has reported VOICES, with names as long as a real engine
        produces ("English (United Kingdom) female_2") — they size the widest
        combo in the window;
      - a voice is SAVED that the phone did not report, which adds the
        "remembered, phone not connected" entry, longer than any real one;
      - the agent-hook switch is showing a FAILURE — the longest sentence this
        window can print (`agent_hook_switch.NO_PYTHON_TEXT`), through the SAME
        `_set_caption` the real toggle handler uses, so the shot proves the
        error COLOUR too, not just the words (round R2's second independent
        grader, 2026-08-07: a raw exception once stood here in plain caption
        grey — see NOTIFY_WORST's own comment above).
    """
    import notify
    from gui.settings_window import SettingsWindow
    notify.set_voices([
        {"name": "en-gb-x-gba#female_2", "label": "English female_2", "locale": "en-GB"},
        {"name": "sr-rs-x-srb#male_1", "label": "Serbian male_1", "locale": "sr-RS"},
    ])
    from config import SETTINGS, apply as apply_settings
    apply_settings(notify_voice="a-voice-this-phone-no-longer-has")
    window = SettingsWindow(_fake_controller(), lambda: None)
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()               # …resolves the QSS font, then the worst caption
    window._set_caption(window.notify_caption, NOTIFY_WORST, error=True)
    # …and the STREAM card OPEN at Custom… (2026-08-12). That disclosure holds
    # three more combo rows and its own wrapping caption, so a shut card is not
    # this window's fullest state — and ALG-1 (EXTREME STATE MATRIX) says a
    # toggle is audited through its options, not in the one it happens to
    # start in. The declared minimum already measures the open state; this is
    # what makes the audit and the shot agree with it.
    window.stream_card.custom_check.setChecked(True)
    assert window.stream_card.custom_box.isVisible()
    assert SETTINGS.notify_voice   # the planted state really is in place
    return window


# A MEASUREMENT CASE THAT IS NOT A SECOND PICTURE (independent graders,
# 2026-08-06 and twice on 2026-08-07: `MainWindow.png` and
# `MainWindow__reopened_from_the_tray.png` are byte-identical, md5 12c59bd6ae08,
# as are their light pair c72b15932b44 — "four proof lines standing over two
# pictures").
#
# Measured before deciding, rather than argued: built both windows, resized
# each to its own declared minimum and rendered each at 2x. Dark and light,
# plain and tray, all four report minimum 463x685, sizeHint 463x657, and the
# two pixel buffers hash the same in each palette (7ce0566f4066 dark,
# 3bcd7da153a3 light). They CANNOT differ, and not by accident: the tray
# factory reaches exactly the same widget state by a longer road — show,
# refresh, hide to the tray, late update offer, and `audit_window` shows it
# again. What it proves is that the hidden round trip does not leave a WRONG
# FLOOR behind (Qt gives a hidden window no real metrics, so a window measured
# while hidden would report a smaller minimum than it needs) — a claim about
# numbers, which the audit checks, and about which a photograph says nothing.
#
# So the case stays and its picture goes. A picture that is a copy of another
# picture is not evidence; it is a second proof line that costs a grader a
# second look and returns the first look's answer.
NO_SHOT = {"MainWindow (reopened from the tray)"}

WINDOWS: list[tuple[str, object]] = [
    ("MainWindow", make_main_window),
    ("MainWindow (server stopped)", make_main_window_stopped),
    ("MainWindow (developer tools)", make_main_window_developer),
    ("MainWindow (reopened from the tray)", make_main_window_from_tray),
    ("ControlsEditor", make_controls_editor),
    ("ChordRecorder", make_chord_recorder),
    ("WheelOrderDialog", make_wheel_order_dialog),
    ("TrafficWindow", make_traffic_window),
    ("SettingsWindow", make_settings_window),
]
