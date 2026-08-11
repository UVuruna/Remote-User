"""The desktop Controls editor (ROADMAP Phase G1, owner spec 2026-08-05).

Edits the USER copy of actions.json — end users never hand-edit files. What
it can do:
- pick WHICH four commands of a set ride on the phone's D-pad. Every set
  carries a POOL (`buttons`) that may hold more than four commands — the
  reserves (VSCode's Markdown preview, Explorer's tab hops, Edit's Save…) —
  and `active` names the chosen four by ID (owner 2026-08-05);
- create/delete/rename any number of CUSTOM sets, whose commands are fully
  editable — a built-in action, a recorded chord/special key, or TYPED TEXT
  (the `paste_text` mechanism the Claude set is built from: a string pasted
  into the focused PC box, with an optional "press Enter afterwards" and an
  icon from the shipped set). Built-in and app sets are read-only in their
  commands — the owner picks from their pool, he does not rewrite them
  (owner decision 2026-08-05);
- choose which sets are shown in the phone's wheel by default
  (Mouse/Input/Settings are `required` and always shown; every other shipped
  or custom set toggles, at most WHEEL_MAX in the wheel);
- rearrange the four active buttons per orientation — landscape (top·left·
  right·bottom cross) and portrait (top→bottom column) — with a one-click
  reset to the shipped default order.
- choose the ORDER the sets ride the phone's category wheel in — a separate
  small dialog (`gui.controls_order.WheelOrderDialog`, build round R5,
  2026-08-07), opened from the "Wheel order…" button: position 1 sits at
  12 o'clock, the rest follow clockwise, stored as `wheel_order` (a list of
  set names) in actions.json.

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

This module owns only the WINDOW — load/assemble/save actions.json. The data
plumbing (paths, client-table parsing, the shipped-pool merge) lives in
[controls_data.py](controls_data.py); the command-editing widgets (chord
recorder, pool table, command form) live in
[controls_widgets.py](controls_widgets.py); the arrangement/order-editing
widgets (the per-set ladder, the new wheel-order ring) live in
[controls_order.py](controls_order.py) — THE STRUCTURE LAW, split again in
build round R5 (2026-08-07) along the same lines the 2026-08-05 split drew.
"""

import json
import logging

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from gui.controls_data import (
    DPAD_SLOTS, WHEEL_MAX, WHEEL_MAX_DROPOUT, active_buttons, button_id,
    effective_wheel_order, load_client_builtins, load_client_icons,
    merge_shipped_pools, natural_order, shipped_actions_path, user_actions_path,
)
from gui.controls_order import LAND_SLOTS, PORT_SLOTS, OrderList, WheelOrderDialog
from gui.controls_widgets import (
    CommandDetail, CommandTable, RowDelegate, icon_for, paint_check,
)
from gui.sizing import settle_minimum

logger = logging.getLogger(__name__)

# The set list's three sections, in the order they are shown (owner
# 2026-08-06: "hoću da srodne celine budu odvojene linijom"). One flat list of
# twelve names said nothing about WHEN a set appears — and that is the only
# thing that separates them. The names match the vocabulary of CLAUDE.md and
# ACTIONS.md ("app-aware sets"), so the editor and the docs speak one language.
SECTIONS = (
    ("categories", "Standard"),    # always available in the wheel
    ("app_sets", "App-aware"),     # appear only while a matching layout is focused
    ("custom_sets", "Custom"),     # made here by the owner
)

# Sections that simply DO NOT EXIST while they hold nothing (owner 2026-08-06:
# "CUSTOM SAM REKAO DA NE SME DA SE VIDI ako je PRAZAN"). A heading over an
# apologetic "(none yet)" line is a placeholder, not information — the "New
# set" button is what invites; the section appears with its first set.
HIDE_WHEN_EMPTY = {"custom_sets"}

HEADER_ROLE = Qt.ItemDataRole.UserRole + 1  # marks a section-heading row
CHECK_ROLE = Qt.ItemDataRole.UserRole + 2   # "" | LOCKED | ON — see _rides()
LOCKED = "locked"   # on the wheel and NOT the owner's to switch (`required`)
ON = "on"           # on the wheel by his choice, and switchable


class SectionDelegate(RowDelegate):
    """Paints the set list's section headings — and each set's own TICK.

    A heading is not a small bold set name — it is a TITLE: centered, a size
    larger than the rows it governs, and separated from the section above by a
    real horizontal LINE (owner 2026-08-06). Qt's own item painting gives none
    of that, so both the metrics (`sizeHint`) and the rule (`paint`) live here
    rather than in per-item font fiddling that only made the text bold.

    The tick answers the question the list could not (owner 2026-08-06,
    shouted — it had been asked for once already and not delivered): WHICH of
    these twelve sets are actually on the phone's wheel? The state was
    readable only by clicking every set in turn and watching one checkbox on
    the other side of the dialog. Now the list says it at a glance, in a strip
    of its own on the LEFT — and it is DRAWN, not a font glyph (this project
    has already paid for a glyph that came out a blunt cross on the owner's
    device).

    The MARK ITSELF is `controls_widgets.paint_check`, shared with the
    commands table (2026-08-07). It used to be a bare checkmark with nothing
    at all drawn for a set that is switched OFF — so "off" and "not
    switchable" looked identical, and a screen with three different tick
    affordances on it had no way to say which of them was a control. One box,
    three states, everywhere: see that function.
    """

    GAP = 16   # breathing room above a heading, where the rule is drawn
    TOP = 6    # …and above the very first one, which has nothing to divide
    MARK = 22  # the tick's own column on the LEFT — reserved, never shared,
               # so a set's icon and name are indented past it and nothing is
               # ever drawn underneath the mark

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        if not index.data(HEADER_ROLE):
            return
        option.displayAlignment = Qt.AlignmentFlag.AlignCenter
        font = option.font
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 1.25)
        option.font = font
        option.fontMetrics = QFontMetrics(font)

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        if index.data(HEADER_ROLE):
            size.setHeight(size.height() + (self.GAP if index.row() else self.TOP))
        else:
            size.setWidth(size.width() + self.MARK)
        return size

    def paint(self, painter, option, index) -> None:
        if not index.data(HEADER_ROLE):
            # The tick sits in its own strip on the LEFT, and the set's icon
            # and name are indented past it (owner 2026-08-06: "ispred Mouse
            # levo da bude štiklirano"). The row's background is drawn across
            # the FULL width first, so the strip is part of the selected row
            # rather than a gap beside it; the content is then painted into
            # what is left.
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            # The row's fill is drawn across the FULL width first, so the tick
            # strip is part of the selected row rather than a gap beside it —
            # and it is drawn by `RowDelegate.take_selection`, in this app's
            # accent, because the native panel paints the WINDOWS one (gold on
            # the owner's PC, see that method).
            self.take_selection(painter, opt)
            opt.rect = option.rect.adjusted(self.MARK, 0, 0, 0)
            super().paint(painter, opt, index)
            self._paint_tick(painter, option.rect, index.data(CHECK_ROLE))
            return
        super().paint(painter, option, index)
        if not index.row():
            return  # the first heading divides nothing — no rule above it
        painter.save()
        # Derived from the TEXT colour, not `palette.mid()`: on the dark theme
        # this dialog actually runs in, mid() is a hair off the background and
        # the rule was invisible — a line nobody can see is no line at all.
        rule = QColor(option.palette.text().color())
        rule.setAlpha(110)
        painter.setPen(QPen(rule))
        y = option.rect.top() + self.GAP // 2
        painter.drawLine(option.rect.left() + 6, y, option.rect.right() - 6, y)
        painter.restore()

    def _paint_tick(self, painter, rect, state) -> None:
        """The box, in its own MARK-wide strip on the left.

        The drawing is `paint_check` — the one tick this dialog owns. The
        owner's 2026-08-06 rule survives it, now carried by the FILL rather
        than by the ink: a `required` set shows the accent WASH (riding, and
        not his to switch), a set he switched on shows the solid accent, and a
        set he switched off shows the empty box that used to be nothing at
        all.
        """
        strip = QRect(rect.left(), rect.top(), self.MARK, rect.height())
        paint_check(painter, strip, on=bool(state), locked=state == LOCKED)


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
        self._detail_set: dict | None = None
        self._settled = False  # the minimum is measured on first show
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.error("actions.json unreadable (%s) — starting empty", e)
            self.data = {"categories": [], "custom_sets": [], "app_sets": []}
        for key in ("categories", "custom_sets", "app_sets"):
            self.data.setdefault(key, [])
        self._shipped: dict = {}  # the Wheel order dialog's "Default" reset
        try:
            self._shipped = json.loads(shipped_actions_path().read_text(encoding="utf-8"))
            merge_shipped_pools(self.data, self._shipped)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Shipped actions.json unavailable (%s) — pools as saved", e)
        self._current: int | None = None  # index into _entries()

        root = QHBoxLayout(self)

        # left: the set list
        left = QVBoxLayout()
        # The caption is where the tick is explained ONCE — a mark nobody can
        # name is decoration, and the list has no other room to say it.
        left.addWidget(QLabel("Sets — ticked = on the phone's wheel"))
        self.set_list = QListWidget()
        self._section_delegate = SectionDelegate(self.set_list)
        self.set_list.setItemDelegate(self._section_delegate)
        self.set_list.currentRowChanged.connect(self._row_selected)
        left.addWidget(self.set_list, 1)
        row = QHBoxLayout()
        add = QPushButton("New set")
        add.clicked.connect(self._add_set)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._delete_set)
        row.addWidget(add)
        row.addWidget(self.del_btn)
        # Global, not per-set (build round R5, 2026-08-07: "the owner chooses
        # the ORDER of the sets around the phone's category wheel") — a
        # SEPARATE dialog, not a fourth box in the right column. It rides the
        # same row as New set / Delete (2026-08-07): a full-width button of
        # its own cost the left column 44 px of HEIGHT, and height is the axis
        # this window is short of — width it has to spare.
        wheel_btn = QPushButton("Wheel order")
        wheel_btn.clicked.connect(self._open_wheel_order)
        row.addWidget(wheel_btn)
        left.addLayout(row)
        # Drop-out vs fixed (task 181, owner decree 2026-08-11, "the
        # fixed-wheel variant still exists, tucked away in settings"): same
        # domain as "Wheel order…", set-once, so it rides the same corner
        # instead of a new box competing for the window's short axis. Default
        # drop-out — a placed set sheds off the wheel and the cap rises to 10;
        # fixed keeps a placed set on the wheel too, capped at 8.
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Wheel mode"))
        self.wheel_mode_combo = QComboBox()
        self.wheel_mode_combo.addItem(
            f"Drop-out — placed sets leave the wheel (up to {WHEEL_MAX_DROPOUT})",
            "dropout")
        self.wheel_mode_combo.addItem(
            f"Fixed — every ticked set always shows (up to {WHEEL_MAX})",
            "fixed")
        mode = self.data.get("wheel_mode", "dropout")
        self.wheel_mode_combo.setCurrentIndex(1 if mode == "fixed" else 0)
        mode_row.addWidget(self.wheel_mode_combo, 1)
        left.addLayout(mode_row)

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
        self.enabled_check.toggled.connect(self._mark_current)
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

        # The caption says only what the box IS (owner 2026-08-06): every
        # position is spelled out in the rows below it, so repeating
        # "top · left · right · bottom" in the titles was the same text twice.
        arr = QGroupBox("Arrangement")
        acol = QVBoxLayout(arr)
        arow = QHBoxLayout()
        # The slot ladder differs per orientation: landscape is a cross with
        # real directions, portrait is a plain column — 1st…4th from the top
        # (owner 2026-08-05: "left/right/bottom" said nothing about a column).
        # The names are the owner's own (2026-08-06): D-pad is what the cross
        # is called everywhere else in this project, Stack is the column.
        self.order_land = OrderList("D-pad (landscape)", LAND_SLOTS)
        self.order_port = OrderList("Stack (portrait)", PORT_SLOTS)
        arow.addWidget(self.order_land, 1)
        arow.addWidget(self.order_port, 1)
        acol.addLayout(arow)
        # A lone button belongs UNDER the two lists, not beside them (owner
        # 2026-08-06): sitting in the third column it charged the whole box its
        # own width, and the two lists — the content — paid for it.
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset = QPushButton("Default")
        reset.clicked.connect(self._reset_arrangement)
        reset_row.addWidget(reset)
        acol.addLayout(reset_row)
        # THE REFLOW, done properly this time (2026-08-07, second independent
        # grader). Arrangement is a LEFT-column box: everything on the left
        # answers "which set, and how does it ride" (pick it, make it, order
        # the wheel, arrange its four buttons) and everything on the right
        # answers "which commands" (the pool, the selected one).
        #
        # The first attempt at this move failed and the failure is worth
        # keeping: the box went left, all thirteen commands became visible and
        # the minimum FELL to 799 — and the set list then SCROLLED AND CLIPPED
        # "Explorer" mid-row, because nothing in this window ever declared how
        # tall the set list needs to be. Qt quotes a QListWidget's
        # `minimumSizeHint` at a couple of rows whatever it holds, so the
        # settle loop never grew the window for it and the reflow simply moved
        # the starvation from one column to the other.
        #
        # `_fit_set_list` now declares the list's real content height (capped,
        # exactly like `CommandTable.ROWS_SHOWN`), so the window's minimum is
        # the honest max of the two columns and BOTH fit: fifteen list rows on
        # the left, all thirteen pool rows on the right, nothing scrolling,
        # no hole. The 253 px of idle set-list space the grader measured is
        # what pays for the three pool rows that used to hide behind a
        # scrollbar — which is what ladder step 2 means.
        left.addWidget(arr)
        root.addLayout(left, 0)

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
        # gui/sizing.py — one settle for every window. The loop that used to
        # live here trusted `minimumSizeHint`, and this dialog's wrapping
        # captions made it quote 59 px less than the dialog needs.
        settle_minimum(self, self._computed_minimum(), QSize(0, 0))

    def _computed_minimum(self) -> QSize:
        """MEASURED, never guessed (THE SPACE & LEGIBILITY LAW).

        A FLOOR, not the answer: `settle_minimum` grows it until every real
        widget fits, and since 2026-08-07 both columns actually state their
        need (`_fit_set_list` for the list, `CommandTable._fit_rows` for the
        pool), so the settle has the truth to work from. What this estimate
        still owes is the WIDTH, which no widget declares by itself.

        Width = the widest real row this dialog can show: the set list's
        longest entry, plus the detail form (caption + the longest command
        name / chord / TYPED TEXT / "Built-in: …" entry + the Record button).
        The "Press Enter afterwards" checkbox does NOT compete for this width
        — it rides its own row spanning the field+button columns (build round
        R6, 2026-08-07), specifically so it cannot starve the `kind` combo the
        way it did when it shared the Record button's narrow column: the
        runtime audit caught the combo clipped to 162 px against a 218 px
        need the moment a TYPED command (Claude's Usage, the first button in
        its pool) became the default selection. Height = the taller column:
        LEFT is the set list's rows plus its button row and the arrangement
        box (caption + four slots + the ↑↓ row + the Default row); RIGHT is
        the pool rows, the detail form's VISIBLE rows in its FULLEST state
        (Does, Text, Enter — its own row, Name, Icon = 5; the chord state is
        one row SHORTER, Shortcut+Record sharing a row Text+Enter does not)
        and the actions row. Both carry the fixed furniture — headers, group
        titles, margins.
        """
        metrics = QFontMetrics(self.font())

        def widest(strings) -> int:
            return max((metrics.horizontalAdvance(s) for s in strings), default=0)

        names, shortcuts, kinds = [""], [""], ["Shortcut (chord)", "Types (paste text)"]
        for _, _, s in self._entries():
            for b in s.get("buttons") or []:
                action = b.get("action")
                if action:
                    shown = self.builtins.get(action, (action, ""))[0]
                    names.append(shown)
                    kinds.append(f"Built-in: {shown}  ({action})")
                names.append(str(b.get("label", "")))
                # A typed command's value lives in "text" (paste_text), never
                # in "chord"/"key" — it rides the SAME field column as those,
                # so it has to be measured the same way (build round R6).
                shortcuts.append(str(b.get("chord") or b.get("key")
                                     or b.get("text") or ""))

        # The set list measures itself (icons, suffixes and all) in
        # _reload_list — reuse that number instead of re-guessing it here.
        # "Wheel mode" (task 181, 2026-08-11) rides the SAME left column as
        # the list — its combo carries the longest string in the whole
        # window ("Drop-out — placed sets leave the wheel (up to 10)"), and
        # the audit caught it clipped (needs 329, had 221) the first time
        # this ran: the row's real need must compete for `side` too, or the
        # window settles a width its own combo cannot fit in.
        mode_texts = [self.wheel_mode_combo.itemText(i)
                      for i in range(self.wheel_mode_combo.count())]
        mode_w = (metrics.horizontalAdvance("Wheel mode")
                  + widest(mode_texts) + 90)
        side = max(self.set_list.minimumWidth() or (widest(names) + 90), mode_w)
        field = max(widest(shortcuts), widest(names), widest(kinds)) + 60
        caption = widest(("Shortcut", "Text", "Name", "Icon", "Does")) + 16
        # Column 2 holds ONLY the Record button now — "Press Enter afterwards"
        # moved to its own row (build round R6) precisely so it never has to
        # be weighed here against the field column's own, much bigger, need.
        record = metrics.horizontalAdvance("Record") + 44
        checkbox = metrics.horizontalAdvance(self.enabled_check.text()) + 60
        width = max(side + caption + field + record, side + checkbox) + 72

        rows = metrics.height() + 12
        left = (rows * 8                      # eight set rows before the
                                              # settle takes over from
                                              # _fit_set_list's real count
                + rows * 7                    # arrangement: caption + 4 slots
                                              # + the ↑↓ row + the Default row
                + rows * 2)                   # the caption and the button row
        right = (rows * 6                     # six pool rows before the settle
                 + rows * 5                   # the detail form's FULLEST state
                                              # (Text kind: Does, Text, Enter,
                                              # Name, Icon — one row more than
                                              # the chord state, build round R6)
                 + rows * 4)                  # header, group titles, actions
        return QSize(width, max(left, right) + 190)  # frames, margins, buttons

    # -- data helpers --------------------------------------------------------

    def _entries(self) -> list[tuple[str, int, dict]]:
        """(kind, index in its own list, set) for every set the editor shows —
        the shipped categories, the owner's custom sets, and the app-aware
        sets (editable for the first time, owner 2026-08-05)."""
        out: list[tuple[str, int, dict]] = []
        for key, _ in SECTIONS:
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

    def _set_suffix(self, kind: str, s: dict) -> str:
        """What a row adds after the set's name. The section heading already
        says WHAT the set is, so only the app sets still owe an explanation —
        and there the interesting part is not the process (two sets share
        `code`) but the CONDITION: which window brings this set out."""
        if kind != "app_sets":
            return ""
        title = s.get("title")
        if title:
            names = title if isinstance(title, list) else [title]
            return f"   ({s.get('process', '?')} · “{names[0]}”)"
        return f"   ({s.get('process', '?')})"

    def _rides(self, kind: str, s: dict) -> str:
        """What the tick claims: LOCKED (on the wheel and not his to switch),
        ON (allowed on the wheel, switchable) or nothing.

        App sets are ticked exactly like the rest (owner 2026-08-06: "zašto ne
        stoji štiklirano pored ovih APP AWARE"). They were left blank on the
        reasoning that they ride only in layout focus — but the phone reads
        the SAME `enabled` flag for them (`appSetOn` in client/sets.js), so a
        blank row was hiding a switch that exists and works. What the tick
        claims here is the honest thing: this set is ALLOWED on the wheel.
        When it actually appears is the layout's business."""
        if s.get("required"):
            return LOCKED
        return ON if s.get("enabled", True) else ""

    def _mark_current(self, on: bool) -> None:
        """Keeps the list's tick and the form's checkbox saying the same thing
        the instant one of them changes — the form writes into `self.data`
        only on the way out, so the row cannot be re-read from there."""
        item = self.set_list.currentItem()
        entry = self._current_entry()
        if item is None or entry is None:
            return
        # `required` stays LOCKED whatever the checkbox says — its box is
        # disabled precisely because that set cannot leave the wheel.
        item.setData(CHECK_ROLE,
                     LOCKED if entry[2].get("required") else (ON if on else ""))
        self.set_list.viewport().update()

    def _header_item(self, text: str) -> QListWidgetItem:
        """A section heading: a title, and NOT a set — Qt must never let the
        selection land on it, or `_select` would be handed a row that has no
        entry behind it. How it LOOKS is `SectionDelegate`'s job; the role is
        what tells the delegate this row is a heading."""
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setData(HEADER_ROLE, True)
        return item

    def _reload_list(self, select: int = 0) -> None:
        """Rebuilds the left list as three separated sections.

        `select` is an index into `_entries()` — NOT a list row, because the
        headings occupy rows of their own. `self._rows` is the bridge: row →
        entry index, or None for a heading/hint row.
        """
        self.set_list.blockSignals(True)
        self.set_list.clear()
        self._rows: list[int | None] = []
        entry = 0
        for key, heading in SECTIONS:
            sets = self.data.get(key) or []
            if not sets and key in HIDE_WHEN_EMPTY:
                continue  # the section is born with its first set
            self.set_list.addItem(self._header_item(heading))
            self._rows.append(None)
            for s in sets:
                item = QListWidgetItem(f"{s.get('name', '?')}{self._set_suffix(key, s)}")
                body = self.icons.get(s.get("icon", ""))
                if body:
                    item.setIcon(icon_for(body))
                item.setData(CHECK_ROLE, self._rides(key, s))
                self.set_list.addItem(item)
                self._rows.append(entry)
                entry += 1
        self.set_list.blockSignals(False)
        self.set_list.setIconSize(QSize(22, 22))
        self._fit_set_list()
        self.set_list.setCurrentRow(self._row_of(select))

    def _row_of(self, entry: int) -> int:
        """Entry index → list row (the first real row when it is out of range,
        so a deletion can never leave the list on a heading)."""
        rows = getattr(self, "_rows", [])
        if entry in rows:
            return rows.index(entry)
        real = [r for r, e in enumerate(rows) if e is not None]
        return real[0] if real else -1

    # How many set rows the window's minimum makes room for. The cap plays
    # exactly the part `CommandTable.ROWS_SHOWN` plays for the pool: the ladder
    # says RAISE THE MINIMUM before you scroll, and it also says the minimum
    # must fit the declared 1280x1000 frame — so the raise has to stop
    # somewhere. It is the shipped file's own fullest list — FOURTEEN sets
    # plus two section headings since 2026-08-11, when `Claude Tools` joined
    # (task 219). That one extra row is why this number is not a constant to
    # leave alone: at fifteen the list scrolled while the pool table beside it
    # held 145 px of idle space, and the runtime Qt audit convicted the window
    # of BUG A the same run the set was added. A set added to actions.json
    # RAISES this number in the same commit, or the ladder's step 1 is skipped
    # by arithmetic. An owner with a dozen custom sets still scrolls, which is
    # the ladder's legitimate last step rather than a shortcut past its first.
    ROWS_SHOWN = 16

    def _fit_set_list(self) -> None:
        """Ladder step 1, BOTH axes.

        Width: the column is not stretched, so it must ASK for the width its
        longest real entry needs ("Explorer   (app · explorer)") — otherwise Qt
        hands it a default and the names are cut.

        Height: and it must ask for that too, which is the half that was
        missing until 2026-08-07. Qt answers `minimumSizeHint` for a
        QListWidget with a couple of rows however many it holds, so the settle
        loop had nothing to grow the window for; the list simply took whatever
        the OTHER column's height left over. That is why it held 253 px of idle
        space while the pool table scrolled — and why the first attempt to
        reflow the Arrangement box in here made the list scroll instead. A
        column that does not state its need cannot be given its share.
        """
        rows = min(self.set_list.count(), self.ROWS_SHOWN)
        frame = 2 * self.set_list.frameWidth()
        self.set_list.setMinimumWidth(self.set_list.sizeHintForColumn(0) + frame + 12)
        if rows:
            self.set_list.setMinimumHeight(
                sum(self.set_list.sizeHintForRow(i) for i in range(rows)) + frame + 2)

    def _row_selected(self, row: int) -> None:
        """The list's own signal speaks in ROWS; everything else in this
        dialog speaks in ENTRY indices (the headings sit between them). This
        is the one place that translates — a heading row selects nothing."""
        rows = getattr(self, "_rows", [])
        self._select(rows[row] if 0 <= row < len(rows) else None)

    def _select(self, index: int | None) -> None:
        self._store_current()
        self._current = index if index is not None and index >= 0 else None
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
        # Mouse/Input/Settings are always in the wheel and cannot be switched.
        # Everything else can — INCLUDING the app sets: the phone reads the
        # same `enabled` flag for them (client/sets.js appSetOn), so leaving
        # this box dead for them hid a switch that was already working.
        self.enabled_check.setEnabled(not required)
        self.enabled_check.setChecked(required or s.get("enabled", True))
        self.add_cmd.setEnabled(custom)
        self.del_cmd.setEnabled(custom)
        self.table.fill(s.get("buttons") or [],
                        [button_id(b) for b in active_buttons(s)],
                        self.builtins, self.icons)
        self._refresh_count()
        # setCurrentCell stays silent when the cell index does not change
        # (set A row 0 → set B row 0), which left the detail form showing the
        # PREVIOUS set's command. Load it explicitly — and invalidate the form
        # BEFORE setCurrentCell, not after: that call fires currentCellChanged
        # synchronously, and the handler would otherwise write the OLD set's
        # command into the NEW set's pool at the old row index. That is the
        # owner's "zašto je WIN u MOUSE i nema RIGHT CLICK" of 2026-08-05.
        self._detail_row = -1
        self._detail_set = None
        self.table.setCurrentCell(0, 1)
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
        self._detail_set = s
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
        if entry is None or entry[2] is not self._detail_set:
            # The form belongs to a DIFFERENT set than the one selected now —
            # a set switch in flight. Writing here put one set's command into
            # another's pool at the same row number (owner report 2026-08-05:
            # Win landed in Mouse, on top of Right). Identity, not index: a
            # row number means nothing across two pools.
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
        if not s.get("required"):
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
        # The entry index of the set just appended — Custom is the LAST
        # section, so it is simply the end of the flat entry list.
        self._reload_list(len(self._entries()) - 1)

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
        self._detail_set = None
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

    def _open_wheel_order(self) -> None:
        """Opens the wheel-order ring (build round R5, 2026-08-07). A
        SEPARATE dialog on purpose — see the module docstring and `arr`'s
        comment below for why the right column takes no more boxes.

        `effective_wheel_order` already extends a saved order with any set it
        does not mention (a future version's addition), so the dialog always
        lists every set the file has, riding or not — a set not currently on
        the wheel is simply skipped by the CLIENT at render time, never left
        out of this list (the owner arranges the whole roster once)."""
        self._store_current()
        current = effective_wheel_order(self.data)
        default = natural_order(self._shipped) or current
        dlg = WheelOrderDialog(current, default, self)
        if dlg.exec():
            self.data["wheel_order"] = dlg.order_names()

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
        self.data["wheel_mode"] = self.wheel_mode_combo.currentData() or "dropout"
        wheel_max = (WHEEL_MAX_DROPOUT if self.data["wheel_mode"] == "dropout"
                     else WHEEL_MAX)
        incomplete = [s.get("name", "?") for s in self.data["custom_sets"]
                      if not active_buttons(s)]
        if incomplete:
            QMessageBox.warning(
                self, "Empty sets",
                "These sets have no finished buttons yet and will show empty "
                "on the phone:\n  " + ", ".join(incomplete))
        # App sets DO charge the wheel count (owner 2026-08-06, reversing the
        # 2026-08-05 line that used to stand here). Saying they were free is
        # the desktop half of what he found on his phone: NINE sets ticked by
        # default under a cap of eight. The charge is the largest group that
        # can appear TOGETHER — grouped by process, because Chrome, Explorer
        # and VSCode can never match at once while VSCode and Claude always
        # do. Same rule, same arithmetic as sets.js on the phone.
        per_process: dict[str, int] = {}
        for kind, _, s in self._entries():
            if kind == "app_sets" and s.get("enabled", True):
                key = str(s.get("process", "")).lower()
                per_process[key] = per_process.get(key, 0) + 1
        reserve = max(per_process.values(), default=0)
        shown = [s for kind, _, s in self._entries()
                 if kind != "app_sets" and (s.get("required") or s.get("enabled", True))]
        if len(shown) + reserve > wheel_max:
            room = wheel_max - reserve
            extras = [s for s in shown if not s.get("required")][room - len(shown):]
            for s in extras:
                s["enabled"] = False
            QMessageBox.information(
                self, "Wheel limit",
                f"The wheel holds up to {wheel_max} sets, and {reserve} of "
                f"them are held for app shortcuts that can appear together "
                f"(VSCode and Claude share a window). That leaves {room} — "
                f"the last {len(extras)} were left OFF by default (the "
                "phone's Sets picker can swap them in).")
        self._write()
        self.accept()
