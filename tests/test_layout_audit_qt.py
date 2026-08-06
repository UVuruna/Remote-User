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
  C. SCROLL+SLACK - something scrolls while a spacer in the same window holds
                    unused space (the 300-px-empty-dialog screenshot)
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
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractScrollArea, QApplication, QCheckBox, QHeaderView, QLabel, QLayout,
    QLineEdit, QListWidget, QPushButton, QSpacerItem, QTableWidget, QWidget,
)

# px of slack tolerated before a spacer counts as "unused space"
SLACK_TOLERANCE = 24

# px of padding assumed between an element's frame and its text
TEXT_PADDING = 8

# Where the screenshots the layout gate demands are written (one per window,
# taken at its DECLARED minimum - the size the grade has to hold at).
SHOT_DIR = Path(__file__).resolve().parent.parent / ".claude" / "shots"


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


# The longest sentence the notify switch can print under itself: the switch
# reports its own failures there, and a failure names a PATH. Measured, not
# guessed - this exact string is what the owner photographed on 2026-08-06
# with the QR and its link overlapping each other above it.
NOTIFY_WORST = ("[Errno 2] No such file or directory: 'C:\\\\Program Files\\\\"
                "Remote User\\\\_internal\\\\setup\\\\agent_hook.py'")


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
    window.show()                 # …and only THEN does the later content arrive
    window._refresh()             # the guided text + QR, as the owner sees it
    _late_content(window)
    return window


def _late_content(window) -> None:
    """The update offer and the notify switch's failure line — the two things
    that reach this window after it was built and measured."""
    window._update = SimpleNamespace(version="9.9.999", installer_url="http://x/y.exe",
                                     page_url="http://x")
    window._update_state = "found"
    window.notify_caption.setText(NOTIFY_WORST)
    window._refresh()             # the refresh tick that shows both of them


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
    window.show()
    window._refresh()
    window.hide()                 # to the tray — the refresh timer keeps ticking
    _late_content(window)
    return window                 # …and audit_window shows it again


def make_controls_editor() -> QWidget:
    from gui.controls_editor import ControlsEditor
    from gui.theme import QSS
    editor = ControlsEditor()
    # In the app this dialog is a child of MainWindow and inherits the theme;
    # a bare instance would be measured WITHOUT it — and the QSS is where the
    # combo min-width that caused "ift+tab" lives. Measure what ships.
    editor.setStyleSheet(QSS)
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


def make_traffic_window() -> QWidget:
    import traffic
    from gui.theme import QSS
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
    window.setStyleSheet(QSS)   # in the app it inherits MainWindow's theme
    window._refresh()
    return window


WINDOWS: list[tuple[str, object]] = [
    ("MainWindow", make_main_window),
    ("MainWindow (reopened from the tray)", make_main_window_from_tray),
    ("ControlsEditor", make_controls_editor),
    ("ChordRecorder", make_chord_recorder),
    ("TrafficWindow", make_traffic_window),
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


def ancestor_spacer_slack(widget: QWidget, window: QWidget) -> list[str]:
    """Spacers between `widget` and `window` that were handed real space."""
    slack = []
    node = widget.parentWidget()
    while node is not None:
        layout = node.layout()
        if layout is not None:
            for index in range(layout.count()):
                item = layout.itemAt(index)
                if isinstance(item, QSpacerItem):
                    geometry = item.geometry()
                    if max(geometry.width(), geometry.height()) > SLACK_TOLERANCE:
                        slack.append(
                            f"{node.__class__.__name__}"
                            f"'{node.objectName() or '-'}' holds a spacer of "
                            f"{geometry.width()}x{geometry.height()}px")
        if node is window:
            break
        node = node.parentWidget()
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
            slack = ancestor_spacer_slack(widget, window)
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


def shot_name(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_") + ".png"


def audit_window(app: QApplication, name: str, factory) -> list[str]:
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
        if label == "minimum":
            # The gate's SHOT: the window at the size the grade has to hold
            # at. Written by the audit itself so the picture can never be of
            # a different build than the one just measured.
            SHOT_DIR.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(SHOT_DIR / shot_name(name)))

    window.close()
    return problems


def test_layout_audit() -> None:
    app = make_app()
    problems: list[str] = []
    for name, factory in WINDOWS:
        problems += audit_window(app, name, factory)
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
    for name, factory in WINDOWS:
        problems = audit_window(app, name, factory)
        if problems:
            failed = True
            print(f"{name}: FAIL", file=sys.stderr)
            for p in problems:
                print("  " + p, file=sys.stderr)
        else:
            print(f"{name}: PASS (declared minimum "
                  f"{factory.__name__} audited at minimum and +50%)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
