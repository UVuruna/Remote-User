"""The desktop Controls editor (ROADMAP Phase G1, owner spec 2026-08-05).

Edits the USER copy of actions.json — end users never hand-edit files. What
it can do:
- pick WHICH four commands of a set ride on the phone's D-pad. Every set
  carries a POOL (`buttons`) that may hold more than four commands — the
  reserves (VSCode's Markdown preview, Explorer's tab hops, Edit's Save…) —
  and `active` names the chosen four by ID (owner 2026-08-05);
- create/delete/rename any number of CUSTOM sets, whose commands are fully
  editable (a built-in action or a recorded chord, with an optional icon from
  the shipped set). Built-in and app sets are read-only in their commands —
  the owner picks from their pool, he does not rewrite them (owner decision
  2026-08-05);
- choose which sets are shown in the phone's wheel by default
  (Mouse/Input/Settings are `required` and always shown; every other shipped
  or custom set toggles, at most WHEEL_MAX in the wheel);
- rearrange the four active buttons per orientation — landscape (top·left·
  right·bottom cross) and portrait (top→bottom column) — with a one-click
  reset to the shipped default order.

The phone picks every change up on its next connection (actions.json is
re-read per connect); the phone's own Settings → Sets picker can further
override which sets ride in the wheel on that device.

Icons AND built-in labels are the CLIENT's (`const ICONS` / `const BUILTINS`
in client/controls.js are parsed at open time), so a built-in row shows the
real text and icon the phone will draw instead of an empty placeholder —
the owner's 2026-08-05 report: "kako NO ICON kad svi imaju ikonu?".

Layout: THE SPACE & LEGIBILITY LAW (rules/GUI.md) — the command table takes
the window's free height, every editor field owns a full-width row, and the
window's minimum size is COMPUTED from the longest real string this dialog
can show (see `_computed_minimum`), never guessed.

The widgets this dialog is assembled from (the chord recorder, the pool
table, the command form, the arrangement lists) live in
[controls_widgets.py](controls_widgets.py) — THE STRUCTURE LAW.
"""

import json
import logging
import re
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT, SETTINGS, USER_DIR, apply as apply_settings
from gui.controls_widgets import (
    DPAD_SLOTS, LAND_SLOTS, PORT_SLOTS, CommandDetail, CommandTable, OrderList,
    button_id, icon_for,
)

logger = logging.getLogger(__name__)

WHEEL_MAX = 8  # sets in the phone's wheel at once; Mouse/Input/Settings are
               # `required` (never hidden), everything else toggles
               # (owner 2026-08-05)


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


def shipped_actions_path() -> Path:
    """The actions.json we SHIP — the source of every built-in set's command
    pool. It stays reachable after `user_actions_path()` repoints SETTINGS,
    which is what lets a new version's reserve commands reach an owner who
    already has his own copy."""
    return (BUNDLE_DIR if FROZEN else PROJECT_ROOT) / "actions.json"


def load_client_table(name: str, line_re: str,
                      source: str = "controls.js") -> dict[str, tuple[str, ...]]:
    """Parses a `const <name> = {...}` table out of a client script — one
    entry per line. Returns {} on any surprise (the editor then falls back to
    plain names — never a crash)."""
    try:
        text = (SETTINGS.client_dir / source).read_text(encoding="utf-8")
        block = re.search(r"const " + name + r" = \{(.*?)\n\};", text, re.S)
        if not block:
            return {}
        out: dict[str, tuple[str, ...]] = {}
        for line in block.group(1).splitlines():
            m = re.match(line_re, line)
            if m:
                out[m.group(1)] = tuple(m.groups()[1:])
        return out
    except OSError as e:
        logger.warning("Client table %s unavailable for the editor: %s", name, e)
        return {}


def load_client_icons() -> dict[str, str]:
    """{icon name: svg fragment} — the phone's own icon set. It lives in
    client/icons.js since the 2026-08-05 icon round (before that, in
    controls.js beside the actions)."""
    table = load_client_table("ICONS", r"\s*([A-Za-z0-9_]+):\s*'(.*)',?\s*$",
                              source="icons.js")
    return {name: body[0] for name, body in table.items()}


def load_client_builtins() -> dict[str, tuple[str, str]]:
    """{action: (label, icon)} — what the PHONE draws for a built-in action.
    The editor shows these instead of an empty field, so a built-in row tells
    the truth about the button it configures."""
    return load_client_table(
        "BUILTINS",
        r'\s*([A-Za-z0-9_]+):\s*\{[^}]*label:\s*"([^"]*)"[^}]*icon:\s*"([^"]*)"')


def active_buttons(s: dict) -> list[dict]:
    """The ≤4 commands of `s` that sit on the D-pad — mirrors the client's
    activeButtons(): `active` by ID, or the first four (pre-pool behaviour)."""
    pool = s.get("buttons") or []
    ids = s.get("active")
    if not isinstance(ids, list):
        return pool[:DPAD_SLOTS]
    picked: list[dict] = []
    by_id = {button_id(b): b for b in pool}
    for i in ids:
        b = by_id.get(i)
        if b is not None and b not in picked:
            picked.append(b)
        if len(picked) == DPAD_SLOTS:
            break
    return picked or pool[:DPAD_SLOTS]


def merge_shipped_pools(data: dict, shipped: dict) -> None:
    """Refreshes every built-in set's POOL from the shipped file while keeping
    the owner's choices (`active`, `order_*`, `enabled`) — and his RENAMES.

    Without this, an owner who already has a %LOCALAPPDATA% copy would never
    see the reserve commands a new version adds — his copy is seeded once and
    then never touched by an update.

    The renames are the second half of that promise (owner 2026-08-05): he may
    rename any button of a built-in set — Btn 4 / Btn 5 carry whatever his
    mouse driver puts on them — and a pool refresh that overwrote those names
    would quietly undo the only thing he is allowed to change here. Names are
    carried over BY COMMAND ID, so a reordered or extended pool keeps them
    pointing at the right button.
    """
    for key, ident in (("categories", "name"), ("app_sets", "process")):
        mine = data.get(key) or []
        by_ident = {s.get(ident): s for s in mine}
        for ship in shipped.get(key) or []:
            s = by_ident.get(ship.get(ident))
            if s is None:
                mine.append(json.loads(json.dumps(ship)))  # a set we newly ship
                continue
            renamed = {button_id(b): b["label"] for b in (s.get("buttons") or [])
                       if b.get("action") and b.get("label")}
            fresh = json.loads(json.dumps(ship.get("buttons") or []))
            for b in fresh:
                name = renamed.get(button_id(b))
                if name:
                    b["label"] = name
            s["buttons"] = fresh
            for field in ("name", "icon", "required", "process", "title"):
                if field in ship:
                    s[field] = ship[field]
        data[key] = mine


class ControlsEditor(QDialog):
    """The Controls window: set list on the left, the selected set's editor on
    the right. Save = write the user actions.json; the phone refreshes on its
    next connection."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Controls — sets on the phone")
        self.icons = load_client_icons()
        self.builtins = load_client_builtins()
        self.path = user_actions_path()
        self._detail_row = -1
        self._settled = False  # the minimum is measured on first show
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.error("actions.json unreadable (%s) — starting empty", e)
            self.data = {"categories": [], "custom_sets": [], "app_sets": []}
        for key in ("categories", "custom_sets", "app_sets"):
            self.data.setdefault(key, [])
        try:
            shipped = json.loads(shipped_actions_path().read_text(encoding="utf-8"))
            merge_shipped_pools(self.data, shipped)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Shipped actions.json unavailable (%s) — pools as saved", e)
        self._current: int | None = None  # index into _entries()

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
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 0)
        self.enabled_check = QCheckBox(
            f"Shown in the wheel by default (the wheel holds up to {WHEEL_MAX} sets)")
        form.addWidget(self.enabled_check, 1, 1, 1, 3)
        right.addLayout(form)

        self.buttons_group = QGroupBox(
            f"Commands in this set — tick the {DPAD_SLOTS} that sit on the D-pad")
        bbox = QVBoxLayout(self.buttons_group)
        self.table = CommandTable()
        self.table.itemChanged.connect(self._tick_changed)
        self.table.currentCellChanged.connect(self._row_changed)
        bbox.addWidget(self.table, 1)
        table_row = QHBoxLayout()
        self.add_cmd = QPushButton("Add command")
        self.add_cmd.clicked.connect(self._add_command)
        self.del_cmd = QPushButton("Remove")
        self.del_cmd.clicked.connect(self._remove_command)
        # No wrapping here on purpose: the label sits behind a stretch, so
        # ladder step 1 already gives it every pixel it asks for — wrapping
        # would only make a one-line status two lines tall.
        self.count_label = QLabel("")
        table_row.addWidget(self.add_cmd)
        table_row.addWidget(self.del_cmd)
        table_row.addStretch()
        table_row.addWidget(self.count_label)
        bbox.addLayout(table_row)
        right.addWidget(self.buttons_group, 1)  # takes the free height

        self.detail_group = QGroupBox("The selected command")
        dbox = QVBoxLayout(self.detail_group)
        self.detail = CommandDetail(self.icons, self.builtins)
        dbox.addWidget(self.detail)
        right.addWidget(self.detail_group)

        arr = QGroupBox("Arrangement (the shipped order is the default)")
        arow = QHBoxLayout(arr)
        # The slot ladder differs per orientation: landscape is a cross with
        # real directions, portrait is a plain column — 1st…4th from the top
        # (owner 2026-08-05: "left/right/bottom" said nothing about a column).
        self.order_land = OrderList("Landscape — top · left · right · bottom", LAND_SLOTS)
        self.order_port = OrderList("Portrait — top → bottom", PORT_SLOTS)
        arow.addWidget(self.order_land, 1)
        arow.addWidget(self.order_port, 1)
        reset = QPushButton("Reset arrangement")
        reset.clicked.connect(self._reset_arrangement)
        arow.addWidget(reset, 0, Qt.AlignmentFlag.AlignBottom)
        right.addWidget(arr)

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

        self._reload_list()          # fills the widest real content first…
        self.setMinimumSize(self._computed_minimum())   # …then measure it

    # -- the law's computed minimum -----------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802 — Qt override
        """The minimum is SETTLED on first show, not in `__init__`.

        The theme reaches this dialog through its parent's stylesheet, and Qt
        resolves the QSS font and padding only when the widget is polished —
        which happens on show. Measuring in the constructor therefore measured
        every string in the DEFAULT font (~8% narrower than the theme's 13 px)
        and produced a minimum in which the wheel checkbox and the set list
        were cut. Here the metrics are real, so the measurement is real.
        """
        super().showEvent(event)
        if self._settled:
            return
        self._settled = True
        self._fit_set_list()
        size = self._computed_minimum()
        for _ in range(4):
            self.setMinimumSize(size)
            self.layout().activate()
            needs = self.minimumSizeHint()
            grown = QSize(max(size.width(), needs.width()),
                          max(size.height(), needs.height()))
            if grown == size:
                break
            size = grown
        self.setMinimumSize(size)

    def _computed_minimum(self) -> QSize:
        """MEASURED, never guessed (THE SPACE & LEGIBILITY LAW).

        Width = the widest real row this dialog can show: the set list's
        longest entry, plus the detail form (caption + the longest command
        name / chord / "Built-in: …" entry + the Record button). Height = six
        pool rows, the detail form's four rows, the arrangement's caption plus
        four slots, and the fixed furniture (headers, group titles, buttons) —
        the smallest window in which a shipped set still reads whole.
        """
        metrics = QFontMetrics(self.font())

        def widest(strings) -> int:
            return max((metrics.horizontalAdvance(s) for s in strings), default=0)

        names, shortcuts, kinds = [""], [""], ["Shortcut (chord)"]
        for _, _, s in self._entries():
            for b in s.get("buttons") or []:
                action = b.get("action")
                if action:
                    shown = self.builtins.get(action, (action, ""))[0]
                    names.append(shown)
                    kinds.append(f"Built-in: {shown}  ({action})")
                names.append(str(b.get("label", "")))
                shortcuts.append(str(b.get("chord") or b.get("key") or ""))

        # The set list measures itself (icons, suffixes and all) in
        # _reload_list — reuse that number instead of re-guessing it here.
        side = self.set_list.minimumWidth() or (widest(names) + 90)
        field = max(widest(shortcuts), widest(names), widest(kinds)) + 60
        caption = widest(("Shortcut", "Name", "Icon", "Does")) + 16
        record = metrics.horizontalAdvance("Record…") + 44
        checkbox = metrics.horizontalAdvance(self.enabled_check.text()) + 60
        width = max(side + caption + field + record, side + checkbox) + 72

        rows = metrics.height() + 12
        height = (rows * 6                    # six pool rows, no scrollbar
                  + rows * 4                  # the detail form's four rows
                  + rows * 5                  # arrangement: caption + 4 slots
                  + rows * 4                  # header, group titles, actions
                  + 190)                      # group frames, margins, buttons
        return QSize(width, height)

    # -- data helpers --------------------------------------------------------

    def _entries(self) -> list[tuple[str, int, dict]]:
        """(kind, index in its own list, set) for every set the editor shows —
        the shipped categories, the owner's custom sets, and the app-aware
        sets (editable for the first time, owner 2026-08-05)."""
        out: list[tuple[str, int, dict]] = []
        for key in ("categories", "custom_sets", "app_sets"):
            for i, s in enumerate(self.data.get(key) or []):
                out.append((key, i, s))
        return out

    def _current_entry(self) -> tuple[str, int, dict] | None:
        entries = self._entries()
        if self._current is None or self._current >= len(entries):
            return None
        return entries[self._current]

    def _button_labels(self, s: dict) -> list[str]:
        out = []
        for b in active_buttons(s):
            action = b.get("action")
            if action:
                out.append(self.builtins.get(action, (action, ""))[0])
            else:
                out.append(b.get("label") or b.get("chord") or b.get("key") or "?")
        return out

    # -- UI logic ------------------------------------------------------------

    def _reload_list(self, select: int = 0) -> None:
        self.set_list.blockSignals(True)
        self.set_list.clear()
        for kind, _, s in self._entries():
            suffix = {"categories": "   (built-in)", "custom_sets": "",
                      "app_sets": f"   (app · {s.get('process', '?')})"}[kind]
            item = QListWidgetItem(f"{s.get('name', '?')}{suffix}")
            body = self.icons.get(s.get("icon", ""))
            if body:
                item.setIcon(icon_for(body))
            self.set_list.addItem(item)
        self.set_list.blockSignals(False)
        self.set_list.setIconSize(QSize(22, 22))
        self._fit_set_list()
        self.set_list.setCurrentRow(min(select, self.set_list.count() - 1))

    def _fit_set_list(self) -> None:
        """Ladder step 1: the list column is not stretched, so it must ASK for
        the width its longest real entry needs ("Explorer   (app · explorer)")
        — otherwise Qt hands it a default and the names are cut."""
        self.set_list.setMinimumWidth(
            self.set_list.sizeHintForColumn(0) + 2 * self.set_list.frameWidth() + 12)

    def _select(self, index: int) -> None:
        self._store_current()
        self._current = index if index >= 0 else None
        entry = self._current_entry()
        if entry is None:
            return
        kind, _, s = entry
        custom = kind == "custom_sets"
        required = bool(s.get("required"))
        self.name_edit.setText(s.get("name", ""))
        self.name_edit.setEnabled(custom)
        self.icon_combo.setEnabled(custom)
        self.icon_combo.setCurrentIndex(max(0, self.icon_combo.findData(s.get("icon", ""))))
        # Mouse/Input/Settings are always in the wheel; app sets ride with the
        # focused layout and have no wheel toggle at all.
        self.enabled_check.setEnabled(not required and kind != "app_sets")
        self.enabled_check.setChecked(required or s.get("enabled", True))
        self.add_cmd.setEnabled(custom)
        self.del_cmd.setEnabled(custom)
        self.table.fill(s.get("buttons") or [],
                        [button_id(b) for b in active_buttons(s)],
                        self.builtins, self.icons)
        self._refresh_count()
        # setCurrentCell stays silent when the cell index does not change
        # (set A row 0 → set B row 0), which left the detail form showing the
        # PREVIOUS set's command. Load it explicitly; _detail_row = -1 first
        # so the reload cannot write a stale form back into the new pool.
        self.table.setCurrentCell(0, 1)
        self._detail_row = -1
        self._row_changed(self.table.currentRow())
        self._refresh_orders(s)
        self.del_btn.setEnabled(custom)

    def _refresh_orders(self, s: dict) -> None:
        labels = self._button_labels(s)
        self.order_land.set_order(labels, s.get("order_land", list(range(len(labels)))))
        self.order_port.set_order(labels, s.get("order_port", list(range(len(labels)))))

    def _refresh_count(self) -> None:
        n = len(self.table.checked_rows())
        self.count_label.setText(f"{n} of {DPAD_SLOTS} on the D-pad")

    def _row_changed(self, row: int, _col: int = 0, *_args) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        kind, _, s = entry
        self._store_command()
        pool = s.get("buttons") or []
        self._detail_row = row
        self.detail.show_button(pool[row] if 0 <= row < len(pool) else None,
                                kind == "custom_sets")

    def _tick_changed(self, item: QTableWidgetItem) -> None:
        """Keeps the D-pad at four: a fifth tick is refused, with the reason
        on screen (never a silent revert)."""
        if item.column() != 0:
            return
        checked = self.table.checked_rows()
        if len(checked) > DPAD_SLOTS:
            self.table.blockSignals(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.table.blockSignals(False)
            self.count_label.setText(
                f"A D-pad holds {DPAD_SLOTS} — untick one first")
            return
        self._refresh_count()
        entry = self._current_entry()
        if entry is not None:
            self._store_active(entry[2])
            entry[2].pop("order_land", None)  # the four changed — the shipped
            entry[2].pop("order_port", None)  # order is the honest default
            self._refresh_orders(entry[2])

    def _store_active(self, s: dict) -> None:
        pool = s.get("buttons") or []
        if self.table.rowCount() != len(pool):
            return  # the pool just changed under a stale table — the ticks
                    # are re-read from `active` when fill() runs, and reading
                    # them now would map row numbers onto the wrong commands
        rows = self.table.checked_rows()
        ids = [button_id(pool[r]) for r in rows if r < len(pool)]
        if ids == [button_id(b) for b in pool[:DPAD_SLOTS]]:
            # The first four ARE the default — writing them would freeze
            # today's pool order into the file and stop a later version's
            # reshuffle from reaching the phone. A set of four or fewer
            # therefore never carries `active` at all.
            s.pop("active", None)
        else:
            s["active"] = ids

    def _store_command(self) -> None:
        """Writes the detail form back into the pool.

        Custom sets write everything; a built-in or app set writes exactly one
        field — the button's NAME (owner 2026-08-05). `CommandDetail.dump()`
        is what enforces that split, so this method only has to let the write
        through for every kind of set.
        """
        entry = self._current_entry()
        if entry is None:
            return
        pool = entry[2].get("buttons") or []
        if not (0 <= self._detail_row < len(pool)):
            return
        edited = self.detail.dump()
        if edited is not None:
            pool[self._detail_row] = edited

    def _store_current(self) -> None:
        """Writes the on-screen state back into self.data (RAM only)."""
        entry = self._current_entry()
        if entry is None:
            return
        kind, _, s = entry
        self._store_command()
        if kind == "custom_sets":
            s["name"] = self.name_edit.text().strip() or s.get("name", "Set")
            if self.icon_combo.currentData():
                s["icon"] = self.icon_combo.currentData()
        if kind != "app_sets" and not s.get("required"):
            if self.enabled_check.isChecked():
                s.pop("enabled", None)  # shown by default needs no entry
            else:
                s["enabled"] = False
        self._store_active(s)
        n = len(active_buttons(s))
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
        self._current = None  # the list is about to be rebuilt
        self._reload_list(len(self.data.get("categories") or [])
                          + len(self.data["custom_sets"]) - 1)

    def _delete_set(self) -> None:
        entry = self._current_entry()
        if entry is None or entry[0] != "custom_sets":
            return
        _, i, s = entry
        name = s.get("name", "?")
        if QMessageBox.question(self, "Delete set", f"Delete “{name}”?") != \
                QMessageBox.StandardButton.Yes:
            return
        self._current = None  # the stored index no longer matches the list
        del self.data["custom_sets"][i]
        self._reload_list()

    def _add_command(self) -> None:
        entry = self._current_entry()
        if entry is None or entry[0] != "custom_sets":
            return
        self._store_current()
        pool = entry[2].setdefault("buttons", [])
        pool.append({"label": f"Command {len(pool) + 1}", "chord": ""})
        current = self._current
        self._select(current)
        self.table.setCurrentCell(len(pool) - 1, 1)

    def _remove_command(self) -> None:
        entry = self._current_entry()
        if entry is None or entry[0] != "custom_sets":
            return
        row = self.table.currentRow()
        pool = entry[2].get("buttons") or []
        if not (0 <= row < len(pool)):
            return
        self._detail_row = -1  # the row is going away — do not write it back
        del pool[row]
        self._store_active(entry[2])
        self._select(self._current)

    def _reset_arrangement(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        labels = self._button_labels(entry[2])
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
                      if not active_buttons(s)]
        if incomplete:
            QMessageBox.warning(
                self, "Empty sets",
                "These sets have no finished buttons yet and will show empty "
                "on the phone:\n  " + ", ".join(incomplete))
        # App sets never charge the wheel count — they appear only while a
        # matching layout is focused (owner 2026-08-05).
        shown = [s for kind, _, s in self._entries()
                 if kind != "app_sets" and (s.get("required") or s.get("enabled", True))]
        if len(shown) > WHEEL_MAX:
            extras = [s for s in shown if not s.get("required")][WHEEL_MAX - len(shown):]
            for s in extras:
                s["enabled"] = False
            QMessageBox.information(
                self, "Wheel limit",
                f"The wheel holds up to {WHEEL_MAX} sets — the last "
                f"{len(extras)} were left OFF by default (the phone's Sets "
                "picker can swap them in).")
        self._write()
        self.accept()
