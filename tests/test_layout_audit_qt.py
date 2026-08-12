"""Guard test - THE SPACE & LEGIBILITY LAW, runtime half, Qt (rules/GUI.md).

Installed from rules/templates/test_layout_audit_qt.py (MIGRATE-LAYOUT.md
step 2, owner go 2026-08-05). The template's pytest harness is replaced by
plain functions, because this project's guards run through
tests/run_guards.py and the venv carries no pytest; the CHECKS are the
template's, plus one this project needed (item views).

It opens every Qt window OFFSCREEN at its declared minimum size and at a
larger size, walks the whole widget tree, and fails on exactly the things the
owner keeps reporting by hand:

  A. CLIPPED      - a widget got less room than it minimally needs
  B. ELIDED       - text does not fit its own element ("shift+tab" -> "ift+tab")
  C. SCROLL+SLACK - something scrolls while the same window holds unused
                    space: a SPACER on the way up (the 300-px-empty-dialog
                    screenshot) or a stretched ITEM VIEW anywhere in the
                    window (the Controls editor's set list, 242 px idle beside
                    a table hiding three rows - see `idle_view_slack`)
  D. ITEM CUT     - a row of a list/table is wider than the column it sits in
                    (Qt's item views truncate silently; the widget checks
                    above never see item text)

plus the precondition the law puts on every window: a DECLARED MINIMUM SIZE,
computed from real content.

Windows registered (all three the project has): MainWindow, ControlsEditor,
ChordRecorder. Every factory builds its window in the FULLEST state it can
show - the running server with the longest guidance text, and the set with
the longest command pool.

Run:  .venv\\Scripts\\python tests/test_layout_audit_qt.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

# THE PLATFORM IS THE MEASUREMENT (owner 2026-08-06, after this guard passed
# over a window whose link was drawn across its QR). "offscreen" has none of
# the machine's fonts and falls back to substitutes with different metrics: it
# reported the main window needing 869x880 where the REAL Segoe UI at his 125%
# scaling needs 524x857 - different enough that the defect lived on the other
# side of the difference. So the native platform is used whenever there is a
# desktop, and each window is shown with WA_DontShowOnScreen: the full layout
# machinery runs with the real fonts and DPI, and nothing appears on screen.
# offscreen stays the fallback so the guard still runs where there is no
# session at all.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from PySide6.QtCore import QSize, Qt  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView, QAbstractScrollArea, QApplication, QCheckBox,
    QHeaderView, QLabel, QLayout, QLineEdit, QListWidget, QPushButton,
    QSpacerItem, QTableWidget, QWidget,
)

# px of slack tolerated before a spacer counts as "unused space"
SLACK_TOLERANCE = 24

# px of padding assumed between an element's frame and its text
TEXT_PADDING = 8

# Where the screenshots the layout gate demands are written (one per window,
# taken at its DECLARED minimum - the size the grade has to hold at).
# WHERE THE PICTURES GO (rules/GUI.md -> Zubi v2, GATE of 2026-08-08).
# Every screenshot lives in a TOPIC subfolder named after what was being worked
# on, so the owner opens ONE folder and sees ONE story instead of a dump of a
# hundred and eighty cryptic names in a single directory. The topic is the
# ROUND's subject and it is set on this one line; `RU_SHOT_TOPIC` overrides it
# for a one-off sweep that is not the round's own proof (the colour VARIANTS of
# 2026-08-08 were rendered into their own folder that way, because alternatives
# offered for a decision are not candidate designs of ours to pass or fail).
SHOT_TOPIC = os.environ.get("RU_SHOT_TOPIC", "round17-caret-claude-set-colours")
SHOT_DIR = Path(__file__).resolve().parent.parent / ".claude" / "shots" / SHOT_TOPIC

# ONE FOLDER, ONE SUBJECT (owner 2026-08-08, his second word on this): a topic
# folder per ROUND was still a dump — "necu da folderi budu ovako siroki, da
# otvorim folder koji ima 161 sliku; hocu da ih grupises u sub-foldere". So the
# round's folder now holds SUBJECT folders, and a subject is what the picture
# is OF, read from its own name. Anything unrecognised lands in `other`, which
# is a signal rather than a hiding place: an `other` that grows means a new
# screen exists and nobody named it.
SHOT_SUBJECTS = (
    ("Controls_and_wheel", "controls-and-wheel"),
    ("Controls", "controls"),
    ("ControlsEditor", "desktop-controls-editor"),
    ("Sets_picker", "sets-picker"),
    ("Quality_panel", "quality-panel"),
    ("Dictation_card", "dictation-card"),
    ("Region_grab", "region-grab"),
    ("Command_chooser", "command-chooser"),
    ("Layout_list", "layouts"),
    ("Rename_card", "layouts"),
    ("Aspect_panel", "layouts"),
    ("Creation_panel", "layouts"),
    ("Grid_arrangement", "layouts"),
    ("MainWindow", "desktop-windows"),
    ("SettingsWindow", "desktop-windows"),
    ("TrafficWindow", "desktop-traffic"),
    ("WheelOrderDialog", "desktop-windows"),
)


def shot_path(name: str):
    """`<round topic>/<subject>/<name>.png`, with the subject folder made on
    demand. The longest matching prefix wins, so `Controls_and_wheel` never
    falls into `controls`."""
    subject = "other"
    best = 0
    for prefix, folder in SHOT_SUBJECTS:
        if name.startswith(prefix) and len(prefix) > best:
            subject, best = folder, len(prefix)
    out = SHOT_DIR / subject
    out.mkdir(parents=True, exist_ok=True)
    return out / f"{name}.png"



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
# notify._hook_module() has printed a plain-language sentence for that exact
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
from notify import (  # noqa: E402
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
    import traffic
    from gui.traffic_window import TrafficWindow
    # FULLEST state (the 2026-08-05 lesson: an empty panel measures nothing):
    # a phone connected and reporting its own counters, and an absence long
    # enough for the away-gap line to carry its longest sentence.
    traffic.METER.reset()
    traffic.METER.set_clients(1)
    traffic.METER.note_phone({"app_rx": 1, "app_tx": 1, "dev_rx": 1, "dev_tx": 1})
    traffic.METER.set_clients(0)
    traffic.METER.set_clients(1)
    traffic.METER.note_phone({"app_rx": 9 << 20, "app_tx": 9 << 20,
                              "dev_rx": 9 << 30, "dev_tx": 9 << 30})
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
        window can print (`notify.NO_PYTHON_TEXT`), through the SAME
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
    ("MainWindow (reopened from the tray)", make_main_window_from_tray),
    ("ControlsEditor", make_controls_editor),
    ("ChordRecorder", make_chord_recorder),
    ("WheelOrderDialog", make_wheel_order_dialog),
    ("TrafficWindow", make_traffic_window),
    ("SettingsWindow", make_settings_window),
]


# --- the checks ------------------------------------------------------------

def walk(widget: QWidget):
    yield widget
    for child in widget.findChildren(QWidget):
        if child.isVisible():
            yield child


def check_declared_minimum(window: QWidget) -> list[str]:
    minimum = window.minimumSize()
    if minimum.width() > 0 and minimum.height() > 0:
        return []
    return ["no declared minimum size - the law requires one, COMPUTED from "
            "the longest real content (setMinimumSize / setMinimumWidth)"]


def layout_cells(layout: QLayout, path: str = ""):
    """Every cell a layout hands out, with the name of what sits in it —
    recursing into nested layouts, because a row inside a column is where the
    siblings that can collide actually live."""
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        child = item.layout()
        if child is not None:
            yield from layout_cells(child, f"{path}/layout{i}")
            continue
        widget = item.widget()
        if widget is None or widget.isHidden():
            continue                        # spacers own no pixels to collide
        name = widget.objectName() or widget.__class__.__name__
        yield f"{path}/{name}", item.geometry()


def check_overlap(window: QWidget) -> list[str]:
    """E. OVERLAP - two elements of the same layout drawn ON TOP of each other.

    THE CHECK THIS FILE WAS MISSING, and the reason it could report PASS over
    the window the owner photographed twice (2026-08-06). Every other check
    here asks whether an element got its own SIZE; none asked where it was
    PUT. Qt does not clip a layout that is short of space - it overlaps it, so
    every widget can report its full size while the pairing link is painted
    across the QR code. Sizes were green; the window was broken.

    Layout cells are compared, not arbitrary siblings: a layout's own cells
    may never intersect, while unmanaged children (a scrollbar over a
    viewport, a combo's popup) legitimately do.
    """
    problems = []
    for widget in walk(window):
        layout = widget.layout()
        if layout is None:
            continue
        cells = list(layout_cells(layout))
        for i, (name_a, rect_a) in enumerate(cells):
            for name_b, rect_b in cells[i + 1:]:
                if rect_a.intersects(rect_b):
                    hit = rect_a.intersected(rect_b)
                    problems.append(
                        f"OVERLAP in {widget.objectName() or widget.__class__.__name__}: "
                        f"'{name_a}' {rect_a.x()},{rect_a.y()} {rect_a.width()}x{rect_a.height()} "
                        f"is drawn over '{name_b}' {rect_b.x()},{rect_b.y()} "
                        f"{rect_b.width()}x{rect_b.height()} "
                        f"({hit.width()}x{hit.height()} px of the two on the same pixels)")
    return problems


def check_clipping(window: QWidget) -> list[str]:
    problems = []
    for widget in walk(window):
        if isinstance(widget, QHeaderView):
            # Qt returns an orientation-blind SQUARE for a header's
            # minimumSizeHint (QSize(68, 68) whatever its sections hold), so
            # the generic comparison below flags every header. Only the
            # header's own axis is meaningful — measured against Qt's own
            # size hint AND against the font, so a header too short for its
            # text is still caught.
            hint = widget.sizeHint()
            if widget.orientation() == Qt.Orientation.Horizontal:
                need = QSize(widget.width(),
                             max(hint.height(), widget.fontMetrics().height()))
            else:
                need = QSize(max(hint.width(), 8), widget.height())
        else:
            need = widget.minimumSizeHint()
            layout = widget.layout()
            if layout is not None and layout.hasHeightForWidth():
                # A container of WRAPPING children has no single minimum
                # height - minimumSizeHint quotes a wrapping label at ONE
                # line. This branch used to zero the height out and check only
                # the width, and that blind spot is half of the 2026-08-06
                # bug: the QR card was handed 332 px against a minimum of 348
                # and nothing said a word. heightForWidth at the width the
                # container ACTUALLY has is the honest question - how tall
                # must this be, here, now - so it is asked instead of skipped.
                need = QSize(need.width(),
                             max(need.height(), layout.heightForWidth(widget.width())))
        if need.width() > widget.width() or need.height() > widget.height():
            problems.append(
                f"CLIPPED {widget.__class__.__name__} "
                f"'{widget.objectName() or '-'}': has "
                f"{widget.width()}x{widget.height()}, needs at least "
                f"{need.width()}x{need.height()}")
    return problems


def visible_text(widget: QWidget) -> str:
    if isinstance(widget, (QLabel, QPushButton, QCheckBox)):
        return widget.text()
    if isinstance(widget, QLineEdit):
        return widget.text() or widget.placeholderText()
    return ""


def check_elision(window: QWidget) -> list[str]:
    problems = []
    for widget in walk(window):
        text = visible_text(widget)
        if not text:
            continue
        metrics = widget.fontMetrics()
        # A QLabel paints straight into its contentsRect — no frame, no QSS
        # padding — so charging it a control's padding would flag every
        # caption that fits exactly. Framed controls really do lose their
        # frame plus padding.
        padding = 0 if isinstance(widget, QLabel) else TEXT_PADDING
        available = widget.contentsRect().width() - padding
        if isinstance(widget, QLabel) and widget.wordWrap():
            wanted = metrics.boundingRect(
                0, 0, max(available, 1), 10_000, 0x1000, text).height()
            if wanted > widget.contentsRect().height():
                problems.append(
                    f"ELIDED (wrapped text taller than its element) "
                    f"{widget.__class__.__name__} '{text[:40]}': needs "
                    f"{wanted}px height, has {widget.contentsRect().height()}")
            continue
        wanted = metrics.horizontalAdvance(text)
        if wanted > available:
            problems.append(
                f"ELIDED {widget.__class__.__name__} '{text[:40]}': text needs "
                f"{wanted}px, element offers {available}px")
    return problems


def check_item_views(window: QWidget) -> list[str]:
    """Qt's item views truncate row text silently - the widget checks above
    never see it, because an item is not a QWidget. This is the same failure
    class as ELIDED, one layer down.

    The needed width is Qt's OWN `sizeHintForColumn` (text + decoration +
    the delegate's margins), never a hand-rolled estimate — a column sized
    to contents then matches exactly, and only a genuinely squeezed column
    (a stretched one, a list too narrow for its rows) is reported.
    """
    problems = []
    for widget in walk(window):
        if isinstance(widget, QTableWidget):
            for col in range(widget.columnCount()):
                wanted = widget.sizeHintForColumn(col)
                if wanted > widget.columnWidth(col):
                    texts = [widget.item(r, col).text() for r in range(widget.rowCount())
                             if widget.item(r, col) is not None]
                    longest = max(texts, key=len, default="")
                    problems.append(
                        f"ITEM CUT {widget.__class__.__name__} column {col} "
                        f"(longest '{longest[:40]}'): needs {wanted}px, "
                        f"column offers {widget.columnWidth(col)}px")
        elif isinstance(widget, QListWidget) and widget.count():
            wanted = widget.sizeHintForColumn(0)
            if wanted > widget.viewport().width():
                longest = max((widget.item(r).text() for r in range(widget.count())),
                              key=len, default="")
                problems.append(
                    f"ITEM CUT {widget.__class__.__name__} "
                    f"'{widget.objectName() or '-'}' (longest '{longest[:40]}'): "
                    f"needs {wanted}px, list offers {widget.viewport().width()}px")
    return problems


def ancestor_spacer_slack(widget: QWidget, window: QWidget,
                          vertical: bool) -> list[str]:
    """Spacers between `widget` and `window` handed real space IN THE
    SCROLLING AXIS - a 328x0 stretch holds no vertical space and must
    not convict a legitimately scrolling list (Aviator, 2026-08-06)."""
    slack = []
    node = widget.parentWidget()
    while node is not None:
        layout = node.layout()
        if layout is not None:
            for index in range(layout.count()):
                item = layout.itemAt(index)
                if isinstance(item, QSpacerItem):
                    geometry = item.geometry()
                    extent = (geometry.height() if vertical
                              else geometry.width())
                    if extent > SLACK_TOLERANCE:
                        slack.append(
                            f"{node.__class__.__name__}"
                            f"'{node.objectName() or '-'}' holds a spacer of "
                            f"{geometry.width()}x{geometry.height()}px")
        if node is window:
            break
        node = node.parentWidget()
    return slack


def view_content(view: QAbstractItemView, vertical: bool) -> int:
    """How much of the view's own axis its ROWS (or columns) actually use."""
    model = view.model()
    if model is None:
        return 0
    if vertical:
        return sum(view.sizeHintForRow(r) for r in range(model.rowCount()))
    return sum(view.sizeHintForColumn(c) for c in range(model.columnCount()))


def idle_view_slack(scroller: QWidget, window: QWidget,
                    vertical: bool) -> list[str]:
    """THE BLIND SPOT THIS CHECK HAD (2026-08-07).

    `ancestor_spacer_slack` above counts only `QSpacerItem`s, and only on the
    path from the scrolling widget up to the window. The Controls editor's
    failure was neither: its set list — a SIBLING, in the other column — was
    handed 822 px for 580 px of rows and simply STRETCHED, holding 242 px of
    nothing while the commands table beside it hid three of thirteen rows
    behind a scrollbar. An independent grader measured that hole off the
    screenshot twice; this file reported PASS both times, because a stretched
    widget owns its slack instead of parking it in a spacer.

    So idle space is measured where it can be measured HONESTLY: an item view
    knows exactly how much of itself its rows use. Views that contain, or are
    contained by, the scrolling widget are skipped — a scroll area's own idle
    tail is not slack somewhere else.

    Honest limit: this sees item views, not every stretched widget. A generic
    "size minus sizeHint" sweep convicts every legitimately stretched
    container in the tree (a group box whose child wants the room), and a check
    that cries wolf gets deleted. Item views are where this project's holes
    have actually appeared, twice.
    """
    slack = []
    for widget in walk(window):
        if widget is scroller or not isinstance(widget, QAbstractItemView):
            continue
        if widget.isAncestorOf(scroller) or scroller.isAncestorOf(widget):
            continue
        viewport = widget.viewport()
        extent = viewport.height() if vertical else viewport.width()
        idle = extent - view_content(widget, vertical)
        if idle > SLACK_TOLERANCE:
            slack.append(
                f"{widget.__class__.__name__}"
                f"'{widget.objectName() or '-'}' is stretched to {extent}px "
                f"for {extent - idle}px of rows — {idle}px standing idle")
    return slack


def check_scroll_with_free_space(window: QWidget) -> list[str]:
    problems = []
    for widget in walk(window):
        if not isinstance(widget, QAbstractScrollArea):
            continue
        for name, bar in (("vertically", widget.verticalScrollBar()),
                          ("horizontally", widget.horizontalScrollBar())):
            if bar is None or bar.maximum() <= 0:
                continue
            vertical = name == "vertically"
            slack = (ancestor_spacer_slack(widget, window, vertical)
                     + idle_view_slack(widget, window, vertical))
            if slack:
                problems.append(
                    f"SCROLL+SLACK {widget.__class__.__name__} "
                    f"'{widget.objectName() or '-'}' scrolls {name} while the "
                    f"same window holds unused space: " + "; ".join(slack)
                    + " - ladder step 1: the starving element takes the free "
                      "space before any scrollbar appears")
    return problems


def audit(window: QWidget, label: str) -> list[str]:
    return [f"[{label}] {problem}" for problem in (
        check_overlap(window)
        + check_clipping(window)
        + check_elision(window)
        + check_item_views(window)
        + check_scroll_with_free_space(window))]


# BOTH PALETTES, every window (build round R3, 2026-08-07). A light theme is
# not a repaint of a dark one: a translucent white border vanishes on white, a
# 16 %-alpha wash reads as nothing on a card, and an icon whose ink was baked
# in at build time turns invisible. None of that is caught by looking at the
# dark run twice, so the whole registry is audited under each palette and each
# window is SHOT under each — the light shots carry a `__light` suffix so the
# dark ones keep the names the existing proof lines already use.
PALETTES = ("dark", "light")


# THE DESKTOP HAD NO CONTRAST CHECK AT ALL until 2026-08-08, and that absence
# is the whole reason the Settings window's error line shipped at 3.89:1
# through three rounds of being named by a grader. The phone has had one since
# 2026-08-07; this is its twin, and the split is deliberate: the phone's runs
# in the live DOM because the page composites overlays and inherited opacity,
# while a Qt palette is a flat table, so here the honest form is arithmetic on
# the tokens themselves.
#
# Each entry is (ink token, background it is really painted on, what it is).
# The backgrounds are not guesses — they are read out of the QSS in theme.py:
# `QLabel#caption[tone=...]` and `#card` sit on `surface1`, and the pill and
# danger button paint their own wash OVER that same card.
SEMANTIC_INK = [
    ("error", "surface1", "errorDim", "the error caption / failed pill"),
    ("warning", "surface1", "warningDim", "the warning caption"),
    ("success", "surface1", "successDim", "the running pill"),
    ("accent", "surface1", "accentDim", "an accent caption"),
    ("text2", "surface1", None, "secondary text on a card"),
]
SEMANTIC_FLOOR = 4.5   # DESIGN.md, for text this size — no large-text case here


def _rgb(value: str) -> tuple[int, int, int] | None:
    value = value.strip()
    if value.startswith("#") and len(value) == 7:
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    if value.startswith("rgba"):
        parts = [float(p) for p in value[value.index("(") + 1:value.index(")")].split(",")]
        return tuple(round(p) for p in parts[:3]) + (parts[3],) if len(parts) == 4 else None
    return None


def _luminance(rgb) -> float:
    out = []
    for channel in rgb[:3]:
        c = channel / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def _ratio(a, b) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _live_tokens() -> dict:
    """The palette that is IN FORCE right now. Read from theme.TOKENS — the
    dict `qss()` itself builds the stylesheet from — so this check can never
    be measuring a table the app no longer paints with."""
    from gui import theme
    return dict(theme.TOKENS)


def check_semantic_contrast(tokens: dict) -> list[str]:
    """Every semantic ink against the surface it is really painted on — and
    against its own wash, which is DARKER work than the bare card and is where
    the failed pill and the danger button actually live."""
    problems = []
    for ink_key, surface_key, wash_key, what in SEMANTIC_INK:
        ink = _rgb(tokens.get(ink_key, ""))
        card = _rgb(tokens.get(surface_key, ""))
        if not ink or not card:
            problems.append(f"{ink_key}/{surface_key} is not a colour this check can read")
            continue
        surfaces = [(surface_key, card)]
        wash = _rgb(tokens.get(wash_key, "")) if wash_key else None
        if wash and len(wash) == 4:
            alpha = wash[3]
            surfaces.append((wash_key, tuple(
                round(w * alpha + c * (1 - alpha)) for w, c in zip(wash[:3], card))))
        for name, background in surfaces:
            ratio = _ratio(ink, background)
            if ratio < SEMANTIC_FLOOR:
                problems.append(
                    f"{what}: {ink_key} on {name} = {ratio:.2f}:1 "
                    f"(needs {SEMANTIC_FLOOR}:1)")
    return problems


def use_palette(app: QApplication, palette: str) -> None:
    """Make `palette` the one every window built after this call is born in.

    The SETTING is changed too, not just the live palette: MainWindow applies
    `SETTINGS.ui_theme` in its own constructor, so a guard that only called
    apply_theme would have the main window flip the whole app back.
    """
    import config
    from gui import theme
    config.apply(ui_theme=palette)
    theme.apply_theme(palette)
    app.processEvents()


def shot_name(name: str, palette: str = "dark") -> str:
    stem = "".join(c if c.isalnum() else "_" for c in name).strip("_")
    return stem + ("" if palette == "dark" else f"__{palette}") + ".png"


def audit_window(app: QApplication, name: str, factory,
                 palette: str = "dark") -> list[str]:
    window: QWidget = factory()
    # The layout runs for real - real fonts, real DPI - but nothing appears on
    # the owner's screen while a guard runs.
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()
    app.processEvents()

    problems = [f"[{name}] {p}" for p in check_declared_minimum(window)]
    minimum = window.minimumSize()
    sizes = [("minimum", minimum.width(), minimum.height()),
             ("minimum+50%", int(minimum.width() * 1.5),
              int(minimum.height() * 1.5))]
    for label, width, height in sizes:
        if width <= 0 or height <= 0:
            continue
        window.resize(width, height)
        app.processEvents()
        problems += audit(window, f"{name} @ {label} {width}x{height}")
        if label == "minimum" and width * height >= 40_000 and name not in NO_SHOT:
            # The gate's SHOT: the window at the size the grade has to hold
            # at. Written by the audit itself so the picture can never be of
            # a different build than the one just measured. A window too small
            # to be a designed surface (the chord recorder is 219x66 of "press
            # a key now") gets no shot rather than a strip nobody can grade.
            SHOT_DIR.mkdir(parents=True, exist_ok=True)
            # Rendered at 2x device pixels. The grade is given BY EYE against
            # DESIGN.md, and THE VISUAL PROOF (rules/GUI.md) refuses an image
            # under 700 px on its short side — rightly: a 629 px thumbnail of
            # a full app window cannot show whether a label is crowded or a
            # tick is the wrong grey. This is real resolution, not an upscale:
            # QWidget.render draws the widget again into the larger pixmap.
            shot = QPixmap(window.size() * 2)
            shot.setDevicePixelRatio(2)
            shot.fill(Qt.transparent)
            window.render(shot)
            shot.save(str(shot_path(shot_name(name, palette)[:-4])))

    window.close()
    return problems


def test_layout_audit() -> None:
    app = make_app()
    problems: list[str] = []
    for palette in PALETTES:
        use_palette(app, palette)
        problems += [f"[{palette} contrast] {p}"
                     for p in check_semantic_contrast(_live_tokens())]
        for name, factory in WINDOWS:
            problems += [f"[{palette}] {p}"
                         for p in audit_window(app, name, factory, palette)]
    assert not problems, (
        "THE SPACE & LEGIBILITY LAW (rules/GUI.md) - runtime audit failed:\n  "
        + "\n  ".join(problems)
        + "\nLadder: (1) the starving element takes the free space, "
          "(2) reflow into more rows, (3) raise the window minimum, "
          "(4) scroll only when the window is genuinely full."
    )


def main() -> int:
    app = make_app()
    failed = False
    for palette in PALETTES:
        use_palette(app, palette)
        print(f"--- {palette} palette ---")
        bad = check_semantic_contrast(_live_tokens())
        if bad:
            failed = True
            print(f"{palette}/semantic contrast: FAIL", file=sys.stderr)
            for p in bad:
                print("  " + p, file=sys.stderr)
        else:
            print(f"{palette}/semantic contrast: PASS "
                  f"({len(SEMANTIC_INK)} inks, card + own wash)")
        for name, factory in WINDOWS:
            problems = audit_window(app, name, factory, palette)
            if problems:
                failed = True
                print(f"{palette}/{name}: FAIL", file=sys.stderr)
                for p in problems:
                    print("  " + p, file=sys.stderr)
            else:
                print(f"{palette}/{name}: PASS (declared minimum "
                      f"{factory.__name__} audited at minimum and +50%)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
