"""The Controls editor's own widgets (split out of `controls_editor.py`).

THE STRUCTURE LAW: the dialog module had grown to the 1,000-line threshold
holding two different responsibilities — the WINDOW (load/assemble/save
actions.json) and the WIDGETS it is assembled from. The widgets live here:

- `ChordRecorder` — a shortcut is RECORDED from the PC keyboard, never typed;
- `SlotList` / `SlotDelegate` / `OrderList` — the per-orientation arrangement
  of the four active buttons;
- `CommandDetail` — the selected pool command, one field per full-width row;
- `CommandTable` — the set's whole pool with a tick on the four that ride.

Everything the widgets need to draw a command (the icon painter, the command
identity, the D-pad slot names) lives here too — the dialog imports them from
this module, so the dependency runs one way only.
"""

import html
import logging

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QAbstractTextDocumentLayout, QFontMetrics, QIcon, QPainter, QPalette,
    QPixmap, QTextDocument,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QStyle, QStyledItemDelegate,
    QStyleOptionViewItem, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

logger = logging.getLogger(__name__)

DPAD_SLOTS = 4  # a D-pad cross has exactly four positions — the pool may be
                # longer, the phone still shows four (owner 2026-08-05)

# The slot ladder each orientation shows. LANDSCAPE is a cross, so its slots
# have real directions; PORTRAIT is a plain column, where "Left"/"Right" were
# a lie — it is 1st, 2nd, 3rd, 4th from the top (owner 2026-08-05). The
# ordinals are HTML because the list draws rich text (see SlotDelegate).
LAND_SLOTS = ("Top", "Left", "Right", "Bottom")
PORT_SLOTS = ("1<sup>st</sup>", "2<sup>nd</sup>", "3<sup>rd</sup>", "4<sup>th</sup>")

# Built-in actions a custom button may trigger (mirrors client BUILTINS —
# calibrate is retired and left out on purpose). Used as the fallback when
# client/controls.js cannot be parsed.
BUILTIN_ACTIONS = [
    "click", "right", "middle", "x1", "x2", "scroll", "drag", "keyboard",
    "enter", "esc", "newrow", "mic", "gallery", "camera", "files", "pcshot",
    "upload", "monitor", "snap", "sets", "next_input", "quality", "anywhere",
    "dictation",
]

ICON_STROKE = "#cbd5e1"  # icon preview stroke on the editor's dark-ish list

KIND_CHORD = "__chord"
KIND_KEY = "__key"

# Qt key → our chord token for the recorder (letters/digits/F-keys are
# handled generically; this table covers the named keys the injector knows).
QT_NAMED_KEYS = {
    Qt.Key.Key_Return: "enter", Qt.Key.Key_Enter: "enter",
    Qt.Key.Key_Escape: "esc", Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_Backtab: "tab", Qt.Key.Key_Space: "space",
    Qt.Key.Key_Backspace: "backspace", Qt.Key.Key_Delete: "delete",
    Qt.Key.Key_Insert: "insert", Qt.Key.Key_Home: "home",
    Qt.Key.Key_End: "end", Qt.Key.Key_PageUp: "pageup",
    Qt.Key.Key_PageDown: "pagedown", Qt.Key.Key_Left: "left",
    Qt.Key.Key_Up: "up", Qt.Key.Key_Right: "right",
    Qt.Key.Key_Down: "down", Qt.Key.Key_QuoteLeft: "`",
    Qt.Key.Key_Slash: "/", Qt.Key.Key_Minus: "minus", Qt.Key.Key_Equal: "plus",
}


def icon_for(body: str) -> QIcon:
    """One client icon fragment → a QIcon (24×24 stroke drawing)."""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{ICON_STROKE}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        + body.replace("currentColor", ICON_STROKE) + "</svg>"
    )
    renderer = QSvgRenderer(svg.encode("utf-8"))
    pix = QPixmap(48, 48)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)


def button_id(btn: dict) -> str:
    """Stable identity of a pool command — what `active` stores. Explicit
    `id` wins; otherwise the action / chord / key / label, which are unique
    inside one set. IDs (not indices) survive a later version inserting or
    reordering pool commands."""
    return (btn.get("id") or btn.get("action") or btn.get("chord")
            or btn.get("key") or btn.get("label") or "")


class ChordRecorder(QDialog):
    """Press the combination on the PC keyboard — it is written, not typed
    (owner spec: chords are RECORDED)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Record a shortcut")
        self.chord: str | None = None
        box = QVBoxLayout(self)
        label = QLabel("Press the key combination now…\n(Esc alone cancels)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        box.addWidget(label)
        # Computed minimum (SPACE & LEGIBILITY LAW): the label is the whole
        # window, so its two real lines ARE the minimum — measured, not a
        # round number.
        metrics = QFontMetrics(label.font())
        text_w = max(metrics.horizontalAdvance(line) for line in label.text().split("\n"))
        margins = box.contentsMargins()
        self.setMinimumSize(
            text_w + margins.left() + margins.right() + 24,
            metrics.height() * 2 + margins.top() + margins.bottom() + 12,
        )

    def keyPressEvent(self, event) -> None:  # noqa: N802 — Qt override
        key = Qt.Key(event.key())
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
                   Qt.Key.Key_Meta, Qt.Key.Key_Super_L, Qt.Key.Key_Super_R):
            return  # wait for the main key
        mods = event.modifiers()
        if key == Qt.Key.Key_Escape and not mods:
            self.reject()
            return
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("win")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        main = None
        if key in QT_NAMED_KEYS:
            main = QT_NAMED_KEYS[key]
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            main = f"f{int(key) - int(Qt.Key.Key_F1) + 1}"
        elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            main = chr(int(key)).lower()
        if main is None:
            return  # a key the injector cannot press — keep listening
        parts.append(main)
        self.chord = "+".join(parts)
        self.accept()


class SlotDelegate(QStyledItemDelegate):
    """Draws an arrangement row as RICH text.

    The portrait ladder is ordinals with a REAL superscript (1ˢᵗ, 2ⁿᵈ …,
    owner 2026-08-05). Qt builds a `<sup>` out of the dialog's own font, so
    nothing depends on the machine carrying an exotic character — the ✥
    lesson of the same day: a glyph that renders here can be a blunt box on
    the owner's device. The row's own width is measured from the RENDERED
    text (`idealWidth`), so the item-view guard still sees the truth.
    """

    def _doc(self, option: QStyleOptionViewItem) -> QTextDocument:
        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setDocumentMargin(1)
        doc.setHtml(option.text)
        return doc

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        doc = self._doc(opt)
        style = opt.widget.style() if opt.widget is not None else QApplication.style()
        opt.text = ""  # background + selection stay Qt's, the text is ours
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        palette = QPalette(opt.palette)
        if opt.state & QStyle.StateFlag.State_Selected:
            palette.setColor(QPalette.ColorRole.Text,
                             opt.palette.color(QPalette.ColorRole.HighlightedText))
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette = palette
        rect = style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemText, opt, opt.widget)
        painter.save()
        painter.translate(rect.topLeft())
        doc.documentLayout().draw(painter, ctx)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: N802
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        doc = self._doc(opt)
        return QSize(int(doc.idealWidth()) + 10, int(doc.size().height()) + 6)


class SlotList(QListWidget):
    """A list that asks for exactly the height of its rows.

    THE SPACE & LEGIBILITY LAW, ladder step 1: a hard height on this widget
    made it scroll with four items while ~300 px of the same dialog stood
    empty (the owner's screenshot of 2026-08-05). A content-derived size hint
    takes what it needs and leaves the free space to the command table.
    """

    def _needed_height(self) -> int:
        rows = sum(self.sizeHintForRow(i) for i in range(self.count()))
        frame = 2 * self.frameWidth() + 2
        return max(rows + frame, self.fontMetrics().height() * 2 + frame)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        return QSize(super().sizeHint().width(), self._needed_height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt override
        return QSize(super().minimumSizeHint().width(), self._needed_height())


class OrderList(QWidget):
    """The active buttons in slot order with Up/Down — one per orientation.

    The slot name belongs to the POSITION, not to the command (owner fix
    2026-08-05). The first version wrote the name INTO the item's text, so
    moving a command carried its old name along and the ladder read
    Top · Left · Bottom · Right — the owner's screenshot. Here the item holds
    only the command (its label and its index into the active four); the
    ladder is re-drawn from the row numbers after every move, so the left
    column can never change order.
    """

    INDEX_ROLE = Qt.ItemDataRole.UserRole
    LABEL_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, title: str, slots: tuple[str, ...]):
        super().__init__()
        self.slots = slots
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        caption = QLabel(title)
        caption.setWordWrap(True)
        box.addWidget(caption)
        self.list = SlotList()
        self.list.setItemDelegate(SlotDelegate(self.list))
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        box.addWidget(self.list)
        row = QHBoxLayout()
        up = QPushButton("↑")
        down = QPushButton("↓")
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        row.addWidget(up)
        row.addWidget(down)
        row.addStretch()
        box.addLayout(row)

    def _move(self, delta: int) -> None:
        i = self.list.currentRow()
        j = i + delta
        if i < 0 or not (0 <= j < self.list.count()):
            return
        item = self.list.takeItem(i)
        self.list.insertItem(j, item)
        self.list.setCurrentRow(j)
        self._relabel()
        self.list.updateGeometry()

    def _relabel(self) -> None:
        """Re-draws the fixed slot ladder over the current command order."""
        for slot in range(self.list.count()):
            item = self.list.item(slot)
            label = html.escape(str(item.data(self.LABEL_ROLE) or ""))
            name = self.slots[slot] if slot < len(self.slots) else ""
            item.setText(f"{name} &nbsp;·&nbsp; {label}" if name else label)

    def set_order(self, labels: list[str], order: list[int]) -> None:
        self.list.clear()
        idxs = order if sorted(order) == list(range(len(labels))) else list(range(len(labels)))
        for i in idxs:
            item = QListWidgetItem()
            item.setData(self.INDEX_ROLE, i)
            item.setData(self.LABEL_ROLE, labels[i])
            self.list.addItem(item)
        self._relabel()
        self.list.updateGeometry()

    def order(self) -> list[int]:
        return [self.list.item(i).data(self.INDEX_ROLE)
                for i in range(self.list.count())]


class CommandDetail(QWidget):
    """The selected command, one field per full-width row.

    Six fields crammed into one row was BUG B on the owner's screenshot
    ("shift+tab" rendered "ift+tab"). A row per field cannot squeeze: the
    field column takes all the width the caption and the button do not need.
    """

    def __init__(self, icons: dict[str, str], builtins: dict[str, tuple[str, str]]):
        super().__init__()
        self.icons = icons
        self.builtins = builtins
        self._btn: dict | None = None
        self._editable = False

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)

        self.kind = QComboBox()
        self.kind.addItem("Shortcut (chord)", KIND_CHORD)
        self.kind.addItem("Special key", KIND_KEY)
        for action in sorted(builtins or {b: (b, "") for b in BUILTIN_ACTIONS}):
            label = builtins.get(action, (action, ""))[0]
            self.kind.addItem(f"Built-in: {label}  ({action})", action)
        self.kind.currentIndexChanged.connect(self._kind_changed)

        self.chord = QLineEdit()
        self.chord.setPlaceholderText("e.g. ctrl+shift+p")
        self.record = QPushButton("Record…")
        self.record.clicked.connect(self._record)

        self.label = QLineEdit()
        self.label.setPlaceholderText("Name on the button")

        self.icon = QComboBox()
        self.icon.addItem("(no icon)", "")
        for name, body in icons.items():
            self.icon.addItem(icon_for(body), name, name)

        for row, (caption, widget) in enumerate((
                ("Does", self.kind), ("Shortcut", self.chord),
                ("Name", self.label), ("Icon", self.icon))):
            grid.addWidget(QLabel(caption), row, 0)
            grid.addWidget(widget, row, 1)
        grid.addWidget(self.record, 1, 2)
        # The field column is the one that must never starve — ladder step 1.
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)

    # -- state ---------------------------------------------------------------

    def show_button(self, btn: dict | None, editable: bool) -> None:
        """Loads one pool command. `editable` is False for built-in and app
        sets — their commands are ours; the owner picks from the pool
        (owner decision 2026-08-05) — but every field still shows the REAL
        value, greyed, never an empty placeholder."""
        self._btn = btn
        self._editable = editable
        for w in (self.kind, self.chord, self.record, self.label, self.icon):
            w.blockSignals(True)
        if btn is None:
            self.kind.setCurrentIndex(0)
            self.chord.clear()
            self.label.clear()
            self.icon.setCurrentIndex(0)
        else:
            action = btn.get("action")
            if action:
                kind = action
                shortcut = ""
                # An own name wins over the phone's default — that override is
                # exactly what the owner renames (2026-08-05).
                _, icon = self.builtins.get(action, (action, ""))
                label = btn.get("label", "")
            elif btn.get("key"):
                kind, shortcut = KIND_KEY, btn.get("key", "")
                label, icon = btn.get("label", ""), btn.get("icon", "")
            else:
                kind, shortcut = KIND_CHORD, btn.get("chord", "")
                label, icon = btn.get("label", ""), btn.get("icon", "")
            self.kind.setCurrentIndex(max(0, self.kind.findData(kind)))
            self.chord.setText(shortcut)
            self.label.setText(label)
            self.icon.setCurrentIndex(max(0, self.icon.findData(icon)))
        for w in (self.kind, self.chord, self.record, self.label, self.icon):
            w.blockSignals(False)
        self._kind_changed()

    def _kind_changed(self) -> None:
        is_builtin = self.kind.currentData() not in (KIND_CHORD, KIND_KEY)
        self.kind.setEnabled(self._editable)
        # A built-in action's icon and shortcut come from the phone (BUILTINS)
        # — shown, not typed. Its NAME is the one thing anybody may change,
        # in EVERY set including the shipped ones (owner 2026-08-05): the side
        # buttons Btn 4 / Btn 5 do whatever the user's mouse driver assigned,
        # so the face has to be allowed to say "Back" or "Undo".
        self.label.setEnabled(True)
        for w in (self.chord, self.record, self.icon):
            w.setEnabled(self._editable and not is_builtin)
        if is_builtin:
            label, icon = self.builtins.get(self.kind.currentData(),
                                            (self.kind.currentData(), ""))
            self.label.setPlaceholderText(label)   # the phone's own name
            self.icon.setCurrentIndex(max(0, self.icon.findData(icon)))
            self.chord.clear()
        else:
            # Back on a chord/key row the placeholder must stop advertising
            # the built-in's name, or dump() would read a leftover as "this
            # equals the default" and drop a real name.
            self.label.setPlaceholderText("Name on the button")

    def _record(self) -> None:
        rec = ChordRecorder(self.window())
        if rec.exec() and rec.chord:
            self.chord.setText(rec.chord)

    def dump(self) -> dict | None:
        """The edited command as an actions.json entry — None when unusable."""
        if self._btn is None:
            return None
        name = self.label.text().strip()
        if not self._editable:
            # A built-in or app-set command: the command itself is ours, but
            # the NAME travels back (owner 2026-08-05). An empty field means
            # "use the phone's own name", so the override disappears rather
            # than freezing today's default into his file.
            out = dict(self._btn)
            if name and name != self.label.placeholderText():
                out["label"] = name
            else:
                out.pop("label", None)
            return out
        kind = self.kind.currentData()
        if kind not in (KIND_CHORD, KIND_KEY):
            out = {"action": kind}
            if name and name != self.label.placeholderText():
                out["label"] = name
            return out
        shortcut = self.chord.text().strip()
        if not shortcut:
            return None
        out: dict = {"label": self.label.text().strip() or shortcut}
        out["chord" if kind == KIND_CHORD else "key"] = shortcut
        if self.icon.currentData():
            out["icon"] = self.icon.currentData()
        return out


class CommandTable(QTableWidget):
    """The set's whole POOL, with a tick on the four that ride the D-pad."""

    HEADERS = ("On", "Name on the button", "Does", "Shortcut")

    def __init__(self):
        super().__init__(0, len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.verticalHeader().hide()
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)  # layout-law: exempt - turns Qt's default item truncation OFF, which is what the law demands
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def fill(self, pool: list[dict], active: list[str],
             builtins: dict[str, tuple[str, str]], icons: dict[str, str]) -> None:
        self.blockSignals(True)
        self.setRowCount(len(pool))
        for row, btn in enumerate(pool):
            action = btn.get("action")
            if action:
                name, icon_name = builtins.get(action, (action, ""))
                does, shortcut = "built-in", action
            elif btn.get("key"):
                name, icon_name = btn.get("label", ""), btn.get("icon", "")
                does, shortcut = "key", btn.get("key", "")
            else:
                name, icon_name = btn.get("label", ""), btn.get("icon", "")
                does, shortcut = "chord", btn.get("chord", "")
            tick = QTableWidgetItem()
            tick.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                          | Qt.ItemFlag.ItemIsSelectable)
            tick.setCheckState(Qt.CheckState.Checked
                               if button_id(btn) in active else Qt.CheckState.Unchecked)
            self.setItem(row, 0, tick)
            name_item = QTableWidgetItem(name or shortcut)
            body = icons.get(icon_name)
            if body:
                name_item.setIcon(icon_for(body))
            self.setItem(row, 1, name_item)
            self.setItem(row, 2, QTableWidgetItem(does))
            self.setItem(row, 3, QTableWidgetItem(shortcut))
        self.resizeRowsToContents()
        self.blockSignals(False)

    def checked_rows(self) -> list[int]:
        return [r for r in range(self.rowCount())
                if self.item(r, 0).checkState() == Qt.CheckState.Checked]
