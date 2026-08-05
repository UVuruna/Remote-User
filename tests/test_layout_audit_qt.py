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

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from PySide6.QtCore import QSize, Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractScrollArea, QApplication, QCheckBox, QHeaderView, QLabel,
    QLineEdit, QListWidget, QPushButton, QSpacerItem, QTableWidget, QWidget,
)

# px of slack tolerated before a spacer counts as "unused space"
SLACK_TOLERANCE = 24

# px of padding assumed between an element's frame and its text
TEXT_PADDING = 8


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


def make_main_window() -> QWidget:
    import updates
    from gui.main_window import MainWindow
    updates.check = lambda: None  # no network inside a guard run
    window = MainWindow(_fake_controller())
    window._refresh()  # the guided text + QR, exactly as the owner sees it
    return window


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
        editor.set_list.setCurrentRow(biggest)
    return editor


def make_chord_recorder() -> QWidget:
    from gui.controls_editor import ChordRecorder
    return ChordRecorder()


WINDOWS: list[tuple[str, object]] = [
    ("MainWindow", make_main_window),
    ("ControlsEditor", make_controls_editor),
    ("ChordRecorder", make_chord_recorder),
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
                # height: minimumSizeHint quotes the height needed at its
                # NARROWEST width, and heightForWidth quotes the PREFERRED
                # height — comparing either with the height it got at its
                # actual width invents a shortfall. Its width is still
                # checked here; its vertical truth is measured element by
                # element, at the real width, by the wrapped-text branch of
                # check_elision below.
                need = QSize(need.width(), 0)
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
        check_clipping(window)
        + check_elision(window)
        + check_item_views(window)
        + check_scroll_with_free_space(window))]


def audit_window(app: QApplication, name: str, factory) -> list[str]:
    window: QWidget = factory()
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

    window.close()
    return problems


def test_layout_audit() -> None:
    app = QApplication.instance() or QApplication([])
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
    app = QApplication.instance() or QApplication([])
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
