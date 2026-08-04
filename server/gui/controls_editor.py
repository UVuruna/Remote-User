"""The desktop Controls editor (ROADMAP Phase G1, owner spec 2026-08-05).

Edits the USER copy of actions.json — end users never hand-edit files. What
it can do:
- create/delete/rename any number of CUSTOM sets (4 buttons each: a built-in
  action or a recorded chord, with an optional icon from the shipped set);
- choose which custom sets are shown in the phone's wheel by default (the
  five built-in sets are ALWAYS shown; at most CUSTOM_MAX custom ones);
- rearrange any set's buttons per orientation — landscape (top·left·right·
  bottom cross) and portrait (top→bottom column) — with a one-click reset to
  the shipped default order.

The phone picks every change up on its next connection (actions.json is
re-read per connect); the phone's own Settings → Sets picker can further
override which custom sets ride in the wheel on that device.

Icons are the CLIENT's icon set: the editor parses `const ICONS = {...}` out
of client/controls.js at open time, so there is exactly one source of truth
for what an icon name draws.
"""

import json
import logging
import re
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from config import FROZEN, SETTINGS, USER_DIR, apply as apply_settings

logger = logging.getLogger(__name__)

CUSTOM_MAX = 3          # custom sets shown in the wheel at once (owner 2026-08-05)
BUILTIN_SET_COUNT = 5   # Mouse/Input/Attach/Edit/Settings — always shown, content fixed

# Built-in actions a custom button may trigger (mirrors client BUILTINS —
# calibrate is retired and left out on purpose).
BUILTIN_ACTIONS = [
    "click", "right", "middle", "scroll", "drag", "keyboard", "enter", "esc",
    "newrow", "mic", "gallery", "camera", "files", "pcshot", "upload",
    "monitor", "snap", "sets", "next_input", "quality", "anywhere",
]

ICON_STROKE = "#cbd5e1"  # icon preview stroke on the editor's dark-ish list


def user_actions_path() -> Path:
    """The writable actions.json. In the installed app the bundled default is
    read-only (Program Files), so the first use seeds the %LOCALAPPDATA% copy
    and repoints the RUNNING server at it (edits reach the phone on its next
    connection, no restart)."""
    path = Path(SETTINGS.actions_path)
    if not FROZEN:
        return path
    user_copy = USER_DIR / "actions.json"
    if not user_copy.exists():
        user_copy.parent.mkdir(parents=True, exist_ok=True)
        user_copy.write_bytes(path.read_bytes())
    apply_settings(actions_path=user_copy)
    return user_copy


def load_client_icons() -> dict[str, str]:
    """Parses the ICONS table out of client/controls.js — one entry per line,
    `name: '<svg fragment>'`. Returns {} on any surprise (the editor then
    shows plain names instead of previews — never a crash)."""
    try:
        text = (SETTINGS.client_dir / "controls.js").read_text(encoding="utf-8")
        block = re.search(r"const ICONS = \{(.*?)\n\};", text, re.S)
        if not block:
            return {}
        icons: dict[str, str] = {}
        for line in block.group(1).splitlines():
            m = re.match(r"\s*([A-Za-z0-9_]+):\s*'(.*)',?\s*$", line)
            if m:
                icons[m.group(1)] = m.group(2)
        return icons
    except OSError as e:
        logger.warning("Client icons unavailable for the editor: %s", e)
        return {}


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
}


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
        box.addWidget(label)
        self.setMinimumWidth(280)

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


class ButtonRow:
    """One of a custom set's four buttons: builtin OR chord + label + icon."""

    def __init__(self, icons: dict[str, str], grid: QGridLayout, row: int):
        self.kind = QComboBox()
        self.kind.addItem("Shortcut (chord)", "chord")
        for a in BUILTIN_ACTIONS:
            self.kind.addItem(f"Built-in: {a}", a)
        self.label = QLineEdit()
        self.label.setPlaceholderText("Name on the button")
        self.icon = QComboBox()
        self.icon.addItem("(no icon)", "")
        for name, body in icons.items():
            self.icon.addItem(icon_for(body), name, name)
        self.chord = QLineEdit()
        self.chord.setPlaceholderText("e.g. ctrl+shift+p")
        self.record = QPushButton("Record…")
        self.record.clicked.connect(self._record)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        grid.addWidget(QLabel(("Top", "Left", "Right", "Bottom")[row]), row, 0)
        grid.addWidget(self.kind, row, 1)
        grid.addWidget(self.label, row, 2)
        grid.addWidget(self.icon, row, 3)
        grid.addWidget(self.chord, row, 4)
        grid.addWidget(self.record, row, 5)
        self._kind_changed()

    def _record(self) -> None:
        rec = ChordRecorder(self.record.window())
        if rec.exec() and rec.chord:
            self.chord.setText(rec.chord)

    def _kind_changed(self) -> None:
        is_chord = self.kind.currentData() == "chord"
        for w in (self.chord, self.record, self.label, self.icon):
            w.setEnabled(is_chord)

    def load(self, btn: dict) -> None:
        action = btn.get("action")
        idx = self.kind.findData(action) if action else 0
        self.kind.setCurrentIndex(max(0, idx))
        self.label.setText(btn.get("label", ""))
        self.icon.setCurrentIndex(max(0, self.icon.findData(btn.get("icon", ""))))
        self.chord.setText(btn.get("chord", btn.get("key", "")))
        self._kind_changed()

    def dump(self) -> dict | None:
        """The button as an actions.json entry — None when incomplete."""
        kind = self.kind.currentData()
        if kind != "chord":
            return {"action": kind}
        chord = self.chord.text().strip()
        if not chord:
            return None
        out: dict = {"label": self.label.text().strip() or chord, "chord": chord}
        if self.icon.currentData():
            out["icon"] = self.icon.currentData()
        return out


class OrderList(QWidget):
    """Four buttons in slot order with Up/Down — one per orientation."""

    def __init__(self, title: str):
        super().__init__()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(QLabel(title))
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setFixedHeight(96)
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

    def set_order(self, labels: list[str], order: list[int]) -> None:
        self.list.clear()
        idxs = order if sorted(order) == list(range(len(labels))) else list(range(len(labels)))
        for i in idxs:
            item = QListWidgetItem(labels[i])
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(item)

    def order(self) -> list[int]:
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list.count())]


class ControlsEditor(QDialog):
    """The Controls window: set list on the left, the selected set's editor on
    the right. Save = write the user actions.json; the phone refreshes on its
    next connection."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Controls — sets on the phone")
        self.setMinimumSize(860, 560)
        self.icons = load_client_icons()
        self.path = user_actions_path()
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.error("actions.json unreadable (%s) — starting empty", e)
            self.data = {"categories": [], "custom_sets": []}
        self.data.setdefault("custom_sets", [])
        self._current: int | None = None  # index into _sets()

        root = QHBoxLayout(self)

        # left: the set list
        left = QVBoxLayout()
        left.addWidget(QLabel("Sets"))
        self.set_list = QListWidget()
        self.set_list.currentRowChanged.connect(self._select)
        left.addWidget(self.set_list, 1)
        row = QHBoxLayout()
        add = QPushButton("New set")
        add.clicked.connect(self._add_set)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._delete_set)
        row.addWidget(add)
        row.addWidget(self.del_btn)
        left.addLayout(row)
        root.addLayout(left, 0)

        # right: the selected set
        right = QVBoxLayout()
        form = QGridLayout()
        form.addWidget(QLabel("Name"), 0, 0)
        self.name_edit = QLineEdit()
        form.addWidget(self.name_edit, 0, 1)
        form.addWidget(QLabel("Icon"), 0, 2)
        self.icon_combo = QComboBox()
        for name, body in self.icons.items():
            self.icon_combo.addItem(icon_for(body), name, name)
        form.addWidget(self.icon_combo, 0, 3)
        self.enabled_check = QCheckBox(
            f"Shown in the wheel by default (up to {CUSTOM_MAX} of your sets)")
        form.addWidget(self.enabled_check, 1, 1, 1, 3)
        right.addLayout(form)

        self.buttons_group = QGroupBox("Buttons — a built-in action, or a recorded shortcut")
        bgrid = QGridLayout(self.buttons_group)
        self.button_rows = [ButtonRow(self.icons, bgrid, r) for r in range(4)]
        right.addWidget(self.buttons_group)

        arr = QGroupBox("Arrangement (the shipped order is the default)")
        arow = QHBoxLayout(arr)
        self.order_land = OrderList("Landscape — top · left · right · bottom")
        self.order_port = OrderList("Portrait — top → bottom")
        arow.addWidget(self.order_land)
        arow.addWidget(self.order_port)
        reset = QPushButton("Reset arrangement")
        reset.clicked.connect(self._reset_arrangement)
        arow.addWidget(reset, 0, Qt.AlignmentFlag.AlignBottom)
        right.addWidget(arr)

        right.addStretch()
        actions = QHBoxLayout()
        open_json = QPushButton("Open the file")
        open_json.clicked.connect(self._open_json)
        actions.addWidget(open_json)
        actions.addStretch()
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(save)
        actions.addWidget(cancel)
        right.addLayout(actions)
        root.addLayout(right, 1)

        self._reload_list()

    # -- data helpers --------------------------------------------------------

    def _sets(self) -> list[dict]:
        return list(self.data.get("categories", [])) + list(self.data["custom_sets"])

    def _is_custom(self, index: int) -> bool:
        return index >= len(self.data.get("categories", []))

    def _button_labels(self, s: dict) -> list[str]:
        out = []
        for b in (s.get("buttons") or [])[:4]:
            out.append(b.get("label") or b.get("action") or b.get("chord") or "?")
        return out

    # -- UI logic ------------------------------------------------------------

    def _reload_list(self, select: int = 0) -> None:
        self.set_list.blockSignals(True)
        self.set_list.clear()
        for i, s in enumerate(self._sets()):
            suffix = "" if self._is_custom(i) else "   (built-in)"
            item = QListWidgetItem(f"{s.get('name', '?')}{suffix}")
            body = self.icons.get(s.get("icon", ""))
            if body:
                item.setIcon(icon_for(body))
            self.set_list.addItem(item)
        self.set_list.blockSignals(False)
        self.set_list.setIconSize(QSize(22, 22))
        self.set_list.setCurrentRow(min(select, self.set_list.count() - 1))

    def _select(self, index: int) -> None:
        self._store_current()
        self._current = index if index >= 0 else None
        if self._current is None:
            return
        s = self._sets()[index]
        custom = self._is_custom(index)
        self.name_edit.setText(s.get("name", ""))
        self.name_edit.setEnabled(custom)
        self.icon_combo.setEnabled(custom)
        self.icon_combo.setCurrentIndex(max(0, self.icon_combo.findData(s.get("icon", ""))))
        self.enabled_check.setEnabled(custom)
        self.enabled_check.setChecked(custom and s.get("enabled", True))
        self.buttons_group.setEnabled(custom)
        buttons = (s.get("buttons") or [])[:4]
        for r, rowe in enumerate(self.button_rows):
            rowe.load(buttons[r] if r < len(buttons) else {})
        labels = self._button_labels(s)
        self.order_land.set_order(labels, s.get("order_land", list(range(len(labels)))))
        self.order_port.set_order(labels, s.get("order_port", list(range(len(labels)))))
        self.del_btn.setEnabled(custom)

    def _store_current(self) -> None:
        """Writes the on-screen state back into self.data (RAM only)."""
        if self._current is None:
            return
        index = self._current
        sets = self._sets()
        if index >= len(sets):
            return
        custom = self._is_custom(index)
        if custom:
            s = self.data["custom_sets"][index - len(self.data.get("categories", []))]
            s["name"] = self.name_edit.text().strip() or s.get("name", "Set")
            if self.icon_combo.currentData():
                s["icon"] = self.icon_combo.currentData()
            s["enabled"] = self.enabled_check.isChecked()
            buttons = [row.dump() for row in self.button_rows]
            s["buttons"] = [b for b in buttons if b is not None]
        else:
            s = self.data["categories"][index]
        n = len((s.get("buttons") or [])[:4])
        for key, widget in (("order_land", self.order_land), ("order_port", self.order_port)):
            order = widget.order()[:n]
            if sorted(order) == list(range(n)) and order != list(range(n)):
                s[key] = order
            else:
                s.pop(key, None)  # default order needs no entry

    def _add_set(self) -> None:
        self._store_current()
        self.data["custom_sets"].append({
            "name": f"Set {len(self.data['custom_sets']) + 1}",
            "icon": "grid",
            "enabled": True,
            "buttons": [],
        })
        self._reload_list(self.set_list.count())

    def _delete_set(self) -> None:
        if self._current is None or not self._is_custom(self._current):
            return
        i = self._current - len(self.data.get("categories", []))
        name = self.data["custom_sets"][i].get("name", "?")
        if QMessageBox.question(self, "Delete set", f"Delete “{name}”?") != \
                QMessageBox.StandardButton.Yes:
            return
        self._current = None  # the stored index no longer matches the list
        del self.data["custom_sets"][i]
        self._reload_list()

    def _reset_arrangement(self) -> None:
        if self._current is None:
            return
        s = self._sets()[self._current]
        labels = self._button_labels(s)
        self.order_land.set_order(labels, list(range(len(labels))))
        self.order_port.set_order(labels, list(range(len(labels))))

    def _open_json(self) -> None:
        import os
        self._store_current()
        self._write()
        try:
            os.startfile(self.path)  # noqa: S606 — the owner's own file
        except OSError as e:
            logger.error("Could not open %s: %s", self.path, e)

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        logger.info("actions.json saved (%d custom sets)", len(self.data["custom_sets"]))

    def _save(self) -> None:
        self._store_current()
        incomplete = [s.get("name", "?") for s in self.data["custom_sets"]
                      if not s.get("buttons")]
        if incomplete:
            QMessageBox.warning(
                self, "Empty sets",
                "These sets have no finished buttons yet and will show empty "
                "on the phone:\n  " + ", ".join(incomplete))
        enabled = [s for s in self.data["custom_sets"] if s.get("enabled", True)]
        if len(enabled) > CUSTOM_MAX:
            for s in enabled[CUSTOM_MAX:]:
                s["enabled"] = False
            QMessageBox.information(
                self, "Wheel limit",
                f"The wheel shows up to {CUSTOM_MAX} of your sets — the extras "
                "were left OFF by default (the phone's Sets picker can swap them in).")
        self._write()
        self.accept()
