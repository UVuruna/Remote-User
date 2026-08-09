"""The Settings window — everything the owner can change about this PC.

The third window beside Controls and Traffic (round R2, owner 2026-08-07). It
exists because the main window had become two things at once: the thing you
open to PAIR a phone, and the thing you open to CONFIGURE a PC. Pairing is a
first-day task with a QR the size of a postcard; configuring is a rare, dense
one. Keeping both in one column meant the settings form sat under the QR
forever, and every new switch made the pairing window taller.

So the settings LEFT (his answer to the round's one open question was "yes,
move the stream controls in") and the main window kept the QR, the state and
the buttons. Nothing about the stream settings themselves changed: same four
combos, same Apply & restart, same save path.

Five cards, in the order the owner reads them:

  STREAM         — what the PC sends (monitor / resolution / bitrate / fps).
                   The only card with an Apply: these shape the encoder, so
                   they need the server restarted, exactly as before.
  NOTIFICATIONS  — the agent hook switch (moved here from the main window),
                   and HOW the phone says a notice: aloud or not, in which of
                   the PHONE's voices, at which pace.
  FOCUS          — the desktop half of the focus work: Windows' own
                   foreground lock, raised for this session only.
  STARTUP        — the update check (which existed in code with no UI at all)
                   and "Start with Windows", which reads and writes the REAL
                   Task Scheduler task rather than a preference of its own.

APPEARANCE arrived in round R3 (owner-approved 2026-08-07) exactly where R2
left the seam for it — first in `_build_cards`, nothing else moved. Its PHONE
half was CORRECTED to three independent axes 2026-08-08 (owner: "teme
postoje samo dve, svetla i tamna … a ove komande … on može da bude obojen,
neobojen, i može da bude transparentan ili pun") — the card holds the whole
look of the product, both halves of it:

  - **This PC** — the sun/moon pill, the same widget the main window's top bar
    carries. Neither switch owns the setting; both call `switch.choose_theme`.
  - **The phone** — THREE combos, not two: theme (dark / light), whether the
    D-pad + wheel are coloured (coloured / plain) and their fill (outlined /
    filled), chosen HERE and only here. A coloured look wears the SAME palette
    whichever theme is picked (config.SET_COLORS — owner decision 2026-08-08,
    replacing the two tables of 2026-08-07: a set's colour is its IDENTITY and
    does not follow the page). Never a fourth theme name either — the
    2026-08-07
    shape folded colour into `phone_theme` itself ("colored" / "colored-light")
    and produced the same eight looks by accident, but said the page has four
    themes when the owner's own model is two themes plus two switches that
    belong to the CONTROLS. The owner's answer to this round's P4 was one
    source of truth and no menu on the phone, so the page never asks the
    device anything: it applies what `config.ui` tells it.

Everything except the STREAM card takes effect the moment it is switched;
that is the rule the notify switch already set on the main window, and a
window where some switches act and others wait for a button is a window
nobody can trust.
"""

import logging

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

import threading

import autostart
import foreground_lock
import notify
import updates
from config import SETTINGS, save_user_settings
from gui.sizing import settle_minimum
from gui.switch import TRACK_W as THEME_SWITCH_W, ThemeSwitch, choose_theme
from gui.theme import card, repolish
from notify import HOOK_CHANGE_FAILED_TEXT, agent_hook_installed, set_agent_hook

logger = logging.getLogger(__name__)

# The stream choices. They moved here WITH the combos they fill (round R2) —
# a list of resolutions belongs to the window that offers them, and the main
# window no longer has a settings form to measure them against.
RESOLUTIONS = [("Native (up to 4K)", 3840), ("2560 — QHD", 2560),
               ("1920 — Full HD", 1920), ("1600 — light", 1600)]
BITRATES = [("6 Mbps — slow links", "6M"), ("12 Mbps — default", "12M"),
            ("20 Mbps — max quality", "20M")]
FPS_CHOICES = [("10 fps — light", 10), ("30 fps", 30), ("60 fps", 60)]

# How fast the phone speaks a notice. Android's TextToSpeech rate, where 1.0
# is the engine's own normal pace; the labels are what the owner reads.
SPEECH_RATES = [("0.8× — slower", 0.8), ("1× — normal", 1.0),
                ("1.25× — faster", 1.25), ("1.5× — fastest", 1.5)]

# The phone's look (round R3, corrected to three axes 2026-08-08). SHORT
# labels on purpose: a combo is sized by its longest entry, and one
# explanatory entry would set the width of the whole window (the lesson the
# Voice row already taught this file on 2026-08-05). What the choices MEAN
# belongs in the caption, which wraps.
#
# THREE COMBOS, NOT TWO (owner correction 2026-08-08, replacing the
# 2026-08-07 shape that folded colour into a fourth `phone_theme` value:
# "colored" / "colored-light"). His own model has exactly two themes and two
# SEPARATE switches that belong to the controls, not the page: "teme postoje
# samo dve, svetla i tamna … a ove komande … on može da bude obojen,
# neobojen, i može da bude transparentan ili pun." PHONE_THEMES therefore
# drops back to two entries — and the palette a coloured look wears is the
# SAME under both (config.SET_COLORS, owner 2026-08-08: "oni ce uvijek imati
# ove jake upecatljive boje"). This combo therefore moves everything AROUND
# the controls and never the controls' own colours. PHONE_COLORED is new.
PHONE_THEMES = [("Dark", "dark"), ("Light", "light")]
PHONE_COLORED = [("Coloured", True), ("Plain", False)]
PHONE_FILLS = [("Outlined", "transparent"), ("Filled", "full")]

# Every labelled row in the window, in one place — the label column is sized
# from the widest of them ALL so the cards' fields line up in one straight
# edge instead of each card finding its own.
FORM_LABELS = ("The phone", "Monitor", "Resolution", "Bitrate", "Frame rate",
               "Voice", "Speaking pace")

# The Voice dropdown's first entry: no choice at all, which is the honest
# default — the phone then uses whatever its own engine considers best for
# its locale.
DEFAULT_VOICE_LABEL = "The phone's own default"

# The search the computed minimum runs over its own width (see
# `_computed_minimum`): width is spent only while it buys height, in steps of
# CAPTION_STEP, and never past CAPTION_MAX_INNER — beyond which the guidance
# lines run past the 60–80 characters DESIGN.md's typography calls readable.
CAPTION_STEP = 16
CAPTION_MAX_INNER = 620

# The notify caption sits BETWEEN two checkboxes ("Tell my phone…" above,
# "Say it out loud" below), so a plain full-width line under it reads at a
# glance as if it could belong to either (round R2's SECOND independent
# grader, 2026-08-07). Indented to the checkbox's own text column — indicator
# width (16px) + its spacing (9px), gui/theme.py QCheckBox rule — it visually
# hangs off "Tell my phone…" the way a form's helper text hangs off its field,
# whatever the caption says. Ladder step 2 (reflow the BINDING), not a wider
# window: the indent costs no extra row, only a few px of wrap width.
CAPTION_INDENT_LEFT = 25

APPEARANCE_TEXT = (
    "Dark or Light picks the whole page. Coloured gives every set its own "
    "colour on top of it — dark shades on a dark page, strong ones on a "
    "light page; Filled paints the buttons in, Outlined leaves them "
    "see-through. The phone has no menu of its own — it reads this on its "
    "next connection.")

STREAM_TEXT = ("These are the PC's own limits. The phone's quality panel may "
               "go below them, never above.")
NOTIFY_ON_TEXT = ("Claude Code will call this PC when a turn ends, and the PC "
                  "passes it to your phone by name.")
NOTIFY_OFF_TEXT = "Off — the phone stays quiet when a job on this PC finishes."
SPEAK_OFF_TEXT = ("Off — the phone still shows the notification, it just does "
                  "not read it out loud.")
NO_VOICES_TEXT = ("The list of voices comes from the phone itself — connect it "
                  "once and reopen this window to choose one.")
VOICES_TEXT = "The voices are the phone's own — this PC cannot install one for it."
VOICE_ABSENT_TEXT = ("The voice chosen here is not on the phone that is "
                     "connected now, so it will speak in that phone's own "
                     "default. The choice is kept — it works again on the "
                     "phone that has it.")
FOCUS_TEXT = ("While this is on, Windows stops other programs from jumping in "
              "front of whatever you are using. It is switched back off when "
              "Remote User closes, and it is never written into the registry.")
STARTUP_TEXT = ("Remote User starts hidden in the tray, so the phone can "
                "reach this PC without anyone logging in and opening it.")


class SettingsWindow(QDialog):
    # The manual update check answers from a worker thread; Qt widgets
    # may only be touched on the GUI thread, so the answer comes back as
    # a signal rather than as a direct call.
    _update_answer = Signal(str, str)

    """Modeless, like the Traffic window: the owner watches the main window's
    status pill while a stream change restarts the server."""

    def __init__(self, controller, restart, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._restart = restart
        self._settled = False   # the minimum is measured on first show
        self._form_label_widgets: list[QLabel] = []   # aligned on first show
        self._update_answer.connect(self._say_update)

        self.setWindowTitle("Settings — Remote User")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        self._build_cards(root)
        root.addStretch()

    # -- the cards ---------------------------------------------------------

    def _build_cards(self, root: QVBoxLayout) -> None:
        """The window's column, in reading order.

        Round R3 inserted APPEARANCE at the top — and paid for it with a
        REFLOW at the bottom, not with a taller window. A fifth card put the
        measured minimum at 614x1048, past the 1000 px height this project
        declares in `.claude/layout-frame.json`; raising that frame is the
        owner's decision, and the ladder says reflow first anyway
        (rules/GUI.md — free space → reflow → minimum → scroll).

        FOCUS and STARTUP therefore share one row. They are the two shortest
        cards AND the two that belong together — both answer "how does Remote
        User behave on this PC" rather than "what does it send". The window
        has 666 px of unused WIDTH inside its own frame and 0 px of spare
        height, so spending one to save the other is the whole point of the
        ladder's first two rungs. The three cards above keep their full width:
        their captions are long, and halving their width would have bought
        height back with one hand while giving it away with the other.
        """
        root.addWidget(self._build_appearance_card())
        root.addWidget(self._build_stream_card())
        root.addWidget(self._build_notifications_card())
        pair = QHBoxLayout()
        pair.setSpacing(12)
        pair.addWidget(self._build_focus_card(), 1)
        pair.addWidget(self._build_startup_card(), 1)
        root.addLayout(pair)

    def _section(self, box: QVBoxLayout, title: str) -> None:
        label = QLabel(title)
        label.setObjectName("section")
        box.addWidget(label)

    def _form(self) -> QFormLayout:
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        return form

    def _row(self, form: QFormLayout, text: str, field: QWidget) -> None:
        """One labelled row whose LABEL COLUMN is the same in every card.

        Two QFormLayouts in two cards each size their own label column, so
        STREAM's combos started at one x and NOTIFICATIONS' at another — a
        visible step down the window for no reason anyone could name (caught
        by opening the screenshot, which is what that gate is for). A minimum,
        not a fixed width: the label may still grow if a longer one ever
        arrives, so ladder step 1 stays possible.
        """
        label = QLabel(text)
        self._form_label_widgets.append(label)
        form.addRow(label, field)

    def _align_label_column(self) -> None:
        """Give every form label the same width — ON SHOW, never in the
        constructor. The theme reaches this dialog through its parent's
        stylesheet and Qt resolves a QSS font only when a widget is polished,
        so a width measured at construction is measured in the WRONG font: it
        came out ~15 px short, each card fell back to its own natural column,
        and the two columns stepped apart again (the same lesson the Traffic
        window's span combo learned on 2026-08-05)."""
        metrics = QFontMetrics(self.font())
        width = max(metrics.horizontalAdvance(text) for text in FORM_LABELS)
        for label in self._form_label_widgets:
            label.setMinimumWidth(width)

    def _caption(self, box: QVBoxLayout, text: str, indent: int = 0) -> QLabel:
        label = QLabel(text)
        label.setObjectName("caption")
        label.setWordWrap(True)   # ladder step 2: reflow, never a wider window
        if indent:
            label.setContentsMargins(indent, 0, 0, 0)
        box.addWidget(label)
        return label

    def _set_caption(self, label: QLabel, text: str, error: bool = False) -> None:
        """Set a caption's TEXT and, when it is reporting a FAILURE, its
        COLOUR — the semantic Error hue DESIGN.md carries for exactly this,
        never a hardcoded hex. A raw exception string once stood in this slot
        wearing plain caption grey (round R2's second independent grader,
        2026-08-07): the colour alone would not have saved it — the words had
        to become a sentence too — but a real failure must still be
        unmistakable from routine guidance at a glance, which grey cannot do.

        A DYNAMIC PROPERTY, never `setStyleSheet` on the label. That was the
        first shape of this method and it reintroduced the exact defect round
        R3 removed from every window in this app (gui/theme.py docstring): a
        per-widget stylesheet WINS over its parent's and freezes the hex it was
        given, so a label painted red in dark stayed the dark palette's red
        after a live flip to light — `apply_theme` rebuilds the APPLICATION's
        sheet and can never reach a colour baked into one widget. The property
        + `repolish` reads `QLabel#caption[tone="error"]` out of that sheet, so
        the hue follows the palette for free.
        """
        label.setText(text)
        label.setProperty("tone", "error" if error else "")
        repolish(label)

    def _build_appearance_card(self):
        """Both surfaces' looks, in one card (round R3).

        The PC's row is the SWITCH, not a combo: two states with a picture
        each is a switch, and the owner's own PromptPainter pill is the shape
        he already reads. The phone's two rows are combos because one of them
        has three states and the other has to sit beside it in the same
        column.

        Everything here takes effect at once — the PC repaints under the
        cover transition, the phone reads `config.ui` on its next connect.
        No Apply, exactly like every other card in this window except STREAM.
        """
        frame, box = card()

        # The PC's switch rides the SECTION HEADING's own row rather than
        # taking a row of its own. Not decoration: this window's minimum
        # height is the axis that binds (see `_computed_minimum`), the
        # declared frame allows 1000 px and the four earlier cards already
        # spend 890 of it. A card that adds three labelled rows and a
        # four-line caption would have pushed the floor past the screen —
        # ladder step 2, reflow, before ladder step 3.
        head = QHBoxLayout()
        title = QLabel("APPEARANCE")
        title.setObjectName("section")
        self.pc_theme_label = QLabel("This PC")
        self.pc_theme_label.setObjectName("caption")
        self.theme_switch = ThemeSwitch()
        self.theme_switch.set_theme_name(SETTINGS.ui_theme)
        self.theme_switch.picked.connect(choose_theme)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(self.pc_theme_label)
        head.addSpacing(8)
        head.addWidget(self.theme_switch)
        box.addLayout(head)

        # …and the phone's three choices share ONE row for the same reason
        # (three combos since the owner's 2026-08-08 correction split what
        # used to be a single four-value theme combo into theme + coloured).
        # Each is one or two words; giving any of them a labelled row of its
        # own would have bought nothing but height.
        form = self._form()
        self.phone_theme_combo = QComboBox()
        for label, value in PHONE_THEMES:
            self.phone_theme_combo.addItem(label, value)
        index = self.phone_theme_combo.findData(SETTINGS.phone_theme)
        self.phone_theme_combo.setCurrentIndex(index if index >= 0 else 0)
        self.phone_theme_combo.currentIndexChanged.connect(self._save_phone_theme)

        self.phone_colored_combo = QComboBox()
        for label, value in PHONE_COLORED:
            self.phone_colored_combo.addItem(label, value)
        index = self.phone_colored_combo.findData(SETTINGS.phone_colored)
        self.phone_colored_combo.setCurrentIndex(index if index >= 0 else 0)
        self.phone_colored_combo.currentIndexChanged.connect(self._save_phone_colored)

        self.phone_fill_combo = QComboBox()
        for label, value in PHONE_FILLS:
            self.phone_fill_combo.addItem(label, value)
        index = self.phone_fill_combo.findData(SETTINGS.phone_fill)
        self.phone_fill_combo.setCurrentIndex(index if index >= 0 else 0)
        self.phone_fill_combo.currentIndexChanged.connect(self._save_phone_fill)

        trio = QWidget()
        trio_row = QHBoxLayout(trio)
        trio_row.setContentsMargins(0, 0, 0, 0)
        trio_row.setSpacing(8)
        trio_row.addWidget(self.phone_theme_combo, 1)
        trio_row.addWidget(self.phone_colored_combo, 1)
        trio_row.addWidget(self.phone_fill_combo, 1)
        self._row(form, "The phone", trio)
        box.addLayout(form)
        self._caption(box, APPEARANCE_TEXT)
        return frame

    def _save_phone_theme(self) -> None:
        save_user_settings({"phone_theme": str(self.phone_theme_combo.currentData())})

    def _save_phone_colored(self) -> None:
        save_user_settings({"phone_colored": bool(self.phone_colored_combo.currentData())})

    def _save_phone_fill(self) -> None:
        save_user_settings({"phone_fill": str(self.phone_fill_combo.currentData())})

    def _build_stream_card(self):
        frame, box = card()
        self._section(box, "STREAM")

        form = self._form()
        self.monitor_combo = QComboBox()
        self._populate_monitors()
        self.resolution_combo = QComboBox()
        for label, value in RESOLUTIONS:
            self.resolution_combo.addItem(label, value)
        self.bitrate_combo = QComboBox()
        for label, value in BITRATES:
            self.bitrate_combo.addItem(label, value)
        self.fps_combo = QComboBox()
        for label, value in FPS_CHOICES:
            self.fps_combo.addItem(label, value)
        self._select_current_settings()

        self._row(form, "Monitor", self.monitor_combo)
        self._row(form, "Resolution", self.resolution_combo)
        self._row(form, "Bitrate", self.bitrate_combo)
        self._row(form, "Frame rate", self.fps_combo)
        box.addLayout(form)

        self._caption(box, STREAM_TEXT)

        apply_row = QHBoxLayout()
        apply_row.addStretch()
        self.apply_btn = QPushButton("Apply && restart")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self._apply_settings)
        apply_row.addWidget(self.apply_btn)
        box.addLayout(apply_row)
        return frame

    def _build_notifications_card(self):
        frame, box = card()
        self._section(box, "NOTIFICATIONS")

        # ROADMAP H2 — the switch that installs the agent hook (owner
        # 2026-08-06). The feature shipped in v0.0.081 and then sat silent on
        # his own PC for a day because nobody had run `agent_hook.py
        # --install`: an end user must never type a command, so the app does
        # it. Takes effect at once — no Apply, nothing restarts.
        self.notify_check = QCheckBox("Tell my phone when an agent finishes")
        self.notify_check.setChecked(agent_hook_installed())
        self.notify_check.toggled.connect(self._toggle_agent_hook)
        box.addWidget(self.notify_check)
        self.notify_caption = self._caption(box, "", indent=CAPTION_INDENT_LEFT)
        # …and a gap UNDER it, so the caption is nearer the checkbox it
        # explains than the one it precedes. The indent says whose it is; the
        # gap says it at a glance, which is the half the grader was reading
        # when a failure line between two switches looked like it belonged to
        # the lower one. Six pixels — the card's own spacing is 10.
        box.addSpacing(6)

        self.speak_check = QCheckBox("Say it out loud")
        self.speak_check.setChecked(SETTINGS.notify_speak)
        self.speak_check.toggled.connect(self._toggle_speak)
        box.addWidget(self.speak_check)

        form = self._form()
        self.voice_combo = QComboBox()
        self._populate_voices()
        self.voice_combo.currentIndexChanged.connect(self._save_voice)
        self.rate_combo = QComboBox()
        for label, value in SPEECH_RATES:
            self.rate_combo.addItem(label, value)
        index = self.rate_combo.findData(SETTINGS.notify_rate)
        self.rate_combo.setCurrentIndex(index if index >= 0 else 1)
        self.rate_combo.currentIndexChanged.connect(self._save_rate)
        self._row(form, "Voice", self.voice_combo)
        self._row(form, "Speaking pace", self.rate_combo)
        box.addLayout(form)

        self.speak_caption = self._caption(box, "")
        self._show_notify_state()
        self._show_speak_state()
        return frame

    def _build_focus_card(self):
        frame, box = card()
        self._section(box, "FOCUS")
        self.focus_check = QCheckBox("Don't let applications steal focus")
        self.focus_check.setChecked(SETTINGS.foreground_lock)
        self.focus_check.toggled.connect(self._toggle_focus_lock)
        box.addWidget(self.focus_check)
        self.focus_caption = self._caption(box, FOCUS_TEXT)
        return frame

    def _build_startup_card(self):
        frame, box = card()
        self._section(box, "STARTUP")
        self.update_check = QCheckBox("Check for new versions when the app starts")
        self.update_check.setChecked(SETTINGS.update_check)
        self.update_check.toggled.connect(self._toggle_update_check)
        box.addWidget(self.update_check)
        # READ FROM WINDOWS, every time this window is built — the installer
        # may have created the task, a previous session may have deleted it,
        # and a tick that remembered an intention instead of asking would be
        # wrong in both directions (autostart.py).
        # ASK NOW, without restarting the app (owner 2026-08-09: "trebao bi da
        # imam opciju i tu na licu mesta da proverim novu verziju, neki button,
        # a ne da moram restart aplikacije"). The switch above governs the
        # AUTOMATIC check at start; this is him asking, so it runs even with
        # that switch off — a setting must not swallow a deliberate action.
        self.update_now = QPushButton("Check now")
        self.update_now.setObjectName("secondary")
        self.update_now.clicked.connect(self._check_updates_now)
        box.addWidget(self.update_now, alignment=Qt.AlignmentFlag.AlignLeft)
        self.update_now_caption = self._caption(box, "")
        self.update_now_caption.hide()
        self.autostart_check = QCheckBox("Start with Windows")
        self.autostart_check.setChecked(autostart.installed())
        self.autostart_check.toggled.connect(self._toggle_autostart)
        box.addWidget(self.autostart_check)
        self.startup_caption = self._caption(box, STARTUP_TEXT)
        return frame

    def _check_updates_now(self) -> None:
        """One press, one answer, off the GUI thread — the check is a network
        call and a frozen window is not a status report."""
        self.update_now.setEnabled(False)
        self._say_update("Asking GitHub…", "")

        def ask():
            try:
                found = updates.check(force=True)
                text = (f"Version {found.version} is available — the main "
                        f"window carries the button that installs it."
                        if found else "This is the newest version.")
                tone = "accent" if found else ""
            except Exception as e:  # noqa: BLE001 — a failed check is a state
                logger.warning("Manual update check failed: %s", e)
                text, tone = "Could not reach GitHub just now.", "error"
            self._update_answer.emit(text, tone)

        threading.Thread(target=ask, daemon=True).start()

    def _say_update(self, text: str, tone: str) -> None:
        self.update_now_caption.setText(text)
        self.update_now_caption.setProperty("tone", tone or None)
        repolish(self.update_now_caption)
        self.update_now_caption.show()
        self.update_now.setEnabled(text != "Asking GitHub…")

    # -- stream settings ---------------------------------------------------

    def _populate_monitors(self) -> None:
        from capture import BaseCapture
        try:
            count = BaseCapture.output_count()
        except Exception as e:  # enumeration is cosmetic — never kill the window
            logger.error("Monitor enumeration failed: %s", e)
            count = 1
        self.monitor_combo.clear()
        for i in range(max(1, count)):
            self.monitor_combo.addItem(f"Monitor {i + 1}", i)

    def _select_current_settings(self) -> None:
        def select(combo: QComboBox, value) -> None:
            index = combo.findData(value)
            combo.setCurrentIndex(index if index >= 0 else 0)
        select(self.monitor_combo, SETTINGS.monitor_index)
        select(self.resolution_combo, SETTINGS.h264_max_width)
        select(self.bitrate_combo, SETTINGS.h264_bitrate)
        select(self.fps_combo, SETTINGS.target_fps)

    def _apply_settings(self) -> None:
        save_user_settings({
            "monitor_index": self.monitor_combo.currentData(),
            "h264_max_width": self.resolution_combo.currentData(),
            "h264_bitrate": self.bitrate_combo.currentData(),
            "target_fps": self.fps_combo.currentData(),
        })
        self._restart()

    # -- notifications ------------------------------------------------------

    def _populate_voices(self) -> None:
        """The phone's voices, plus a saved one the phone did not report.

        That last part is the whole care in this method: opening Settings with
        no phone connected must never quietly drop the owner's choice, so a
        stored voice that is not in the live list is offered anyway, marked as
        remembered. Nothing here writes to the settings file.
        """
        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        self.voice_combo.addItem(DEFAULT_VOICE_LABEL, "")
        names = set()
        for voice in notify.voices():
            names.add(voice["name"])
            locale = voice.get("locale") or ""
            label = voice.get("label") or voice["name"]
            self.voice_combo.addItem(f"{label} ({locale})" if locale else label,
                                     voice["name"])
        saved = SETTINGS.notify_voice
        self._voice_absent = bool(saved) and saved not in names
        if self._voice_absent:
            # SHORT on purpose (ladder step 2 — reflow before width). The
            # marker used to spell the whole situation out inside the item
            # ("— remembered, phone not connected"), and a combo is sized by
            # its longest entry, so one worst-case row was setting the width
            # of the entire window. The sentence belongs in the caption, which
            # WRAPS; the row only has to be recognisable.
            self.voice_combo.addItem(f"{saved} (not on this phone)", saved)
        index = self.voice_combo.findData(saved)
        self.voice_combo.setCurrentIndex(index if index >= 0 else 0)
        self.voice_combo.blockSignals(False)

    def _show_notify_state(self) -> None:
        self._set_caption(self.notify_caption,
                          NOTIFY_ON_TEXT if self.notify_check.isChecked()
                          else NOTIFY_OFF_TEXT)
        self._resettle()  # a longer caption gets its room NOW, not on the next open

    def _show_speak_state(self) -> None:
        speaking = self.speak_check.isChecked()
        self.voice_combo.setEnabled(speaking)
        self.rate_combo.setEnabled(speaking)
        if not speaking:
            text = SPEAK_OFF_TEXT
        elif not notify.voices():
            text = NO_VOICES_TEXT
        elif self._voice_absent:
            text = VOICE_ABSENT_TEXT
        else:
            text = VOICES_TEXT
        self.speak_caption.setText(text)
        self._resettle()

    def _toggle_agent_hook(self, on: bool) -> None:
        """Install or remove the Claude Code Stop hook. The packaged EXE has no
        interpreter inside it, so the script is copied somewhere permanent
        (it must outlive an app update) and a real python is named — and when
        this PC has none, the switch SAYS so instead of failing quietly.

        THAT GUARANTEE DOES NOT EXIST, and believing it is what put an
        `OSError` repr on the owner's own screen. `set_agent_hook` does far
        more than call `notify._hook_module()` (which does raise authored
        sentences): it runs `USER_DIR.mkdir`, `shutil.copyfile`, and
        `agent_hook.install()` — and that last one ends in an UNGUARDED
        `SETTINGS.parent.mkdir(...)` + `SETTINGS.write_text(...)` on
        `~/.claude/settings.json` (setup/agent_hook.py). A read-only or
        locked settings file therefore reaches this handler as
        `[Errno 13] Permission denied: 'C:\\Users\\…\\.claude\\settings.json'`
        — a path, in the slot where this window explains things in plain
        language.

        The two cannot be told apart by their text, but they CAN be told apart
        by `errno`: an OSError raised BY HAND carries a message and no errno,
        one raised by the operating system carries both. Only the first was
        ever written for a person to read, so only the first is shown; the
        other becomes `notify.HOOK_CHANGE_FAILED_TEXT`, with the technical
        text going where technical text belongs — the log.

        `notify.set_agent_hook` has since grown its own try/except and phrases
        that case itself, which makes this the SECOND net rather than the
        first — and it stays, because `_hook_module()` is still called outside
        that guard and any future path added inside it would otherwise reach a
        person as a repr. The sentence is notify.py's, not a second copy of
        it: one failure, one wording, wherever it is caught.
        """
        try:
            ok, detail = set_agent_hook(on)
        except OSError as e:  # noqa: BLE001 — a switch may never crash the app
            logger.error("agent hook switch failed: %s", e)
            ok = False
            detail = "" if e.errno is not None else str(e)
        if not ok:
            self.notify_check.blockSignals(True)
            self.notify_check.setChecked(agent_hook_installed())
            self.notify_check.blockSignals(False)
            self._set_caption(self.notify_caption,
                              detail or HOOK_CHANGE_FAILED_TEXT, error=True)
            self._resettle()  # a reported failure is the caption's longest state
            return
        self._show_notify_state()

    def _toggle_speak(self, on: bool) -> None:
        save_user_settings({"notify_speak": bool(on)})
        self._show_speak_state()

    def _save_voice(self) -> None:
        save_user_settings({"notify_voice": str(self.voice_combo.currentData() or "")})

    def _save_rate(self) -> None:
        save_user_settings({"notify_rate": float(self.rate_combo.currentData() or 1.0)})

    # -- focus + startup ----------------------------------------------------

    def _toggle_focus_lock(self, on: bool) -> None:
        """Raise or restore Windows' foreground lock, NOW — and report a
        machine that refuses instead of leaving a tick that lies."""
        if not foreground_lock.apply(bool(on)):
            self.focus_check.blockSignals(True)
            self.focus_check.setChecked(foreground_lock.is_raised())
            self.focus_check.blockSignals(False)
            self._set_caption(self.focus_caption,
                              "Windows refused to change the focus rule on "
                              "this PC — the log has the exact error.",
                              error=True)
            self._resettle()
            return
        save_user_settings({"foreground_lock": bool(on)})
        self._set_caption(self.focus_caption, FOCUS_TEXT)
        self._resettle()

    def _toggle_update_check(self, on: bool) -> None:
        save_user_settings({"update_check": bool(on)})

    def _toggle_autostart(self, on: bool) -> None:
        ok, detail = autostart.set_autostart(bool(on))
        if not ok:
            self.autostart_check.blockSignals(True)
            self.autostart_check.setChecked(autostart.installed())
            self.autostart_check.blockSignals(False)
            self._set_caption(self.startup_caption, detail, error=True)
            self._resettle()
            return
        self._set_caption(self.startup_caption, STARTUP_TEXT)
        self._resettle()

    # -- the law's computed minimum ----------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802 — Qt override
        """Measured on first SHOW, never in __init__ — the theme's font only
        resolves when Qt polishes the widget, and measuring before that
        under-shoots every string by roughly a tenth (the 2026-08-05 lesson
        that cost the Controls editor a second release).

        The live state is re-read on EVERY show: a phone may have connected
        since the last one (new voices) and the autostart task may have been
        changed by an installer run.
        """
        super().showEvent(event)
        self._refresh_live_state()
        if self._settled:
            return
        self._settled = True
        self._align_label_column()
        settle_minimum(self, self._computed_minimum(), QSize(0, 0))
        # …AND AGAIN once the show has actually happened. Inside `showEvent`
        # the window still reports the geometry it had BEFORE the show, so
        # every `heightForWidth` the settle loop asked was answered for a
        # width this window no longer has — and this window is almost entirely
        # WRAPPING captions, whose height is nothing but a function of width.
        # The audit caught the gap exactly: 819 declared where Qt then said
        # 833 was needed at that very width. A single-shot timer runs the same
        # settle with the real geometry in place, and a settle can only ever
        # GROW the floor, so running it twice is safe by construction.
        QTimer.singleShot(0, self._resettle)

    def _refresh_live_state(self) -> None:
        self._populate_voices()
        self.autostart_check.blockSignals(True)
        self.autostart_check.setChecked(autostart.installed())
        self.autostart_check.blockSignals(False)
        self.notify_check.blockSignals(True)
        self.notify_check.setChecked(agent_hook_installed())
        self.notify_check.blockSignals(False)
        self._show_notify_state()
        self._show_speak_state()

    def _resettle(self) -> None:
        """A caption that grew must get its room now, not on the next open.
        Never below the owner's current window size (`settle_minimum`'s
        `keep` defaults to exactly that)."""
        if not self._settled or not self.isVisible():
            return
        settle_minimum(self, self._computed_minimum())

    def _computed_minimum(self) -> QSize:
        """MEASURED, never guessed (THE SPACE & LEGIBILITY LAW, rules/GUI.md).

        Width = the widest row that CANNOT wrap: a form label plus the longest
        entry of the combo beside it (the voice names come from the phone, so
        the real ones are measured, not a guess at their length) — then WIDENED
        until the guidance under the switches stops becoming a paragraph.
        Height = every row, plus what those captions need once wrapped at that
        width.

        The widening is not decoration, it is which axis is scarce. A desktop
        has 1280 px of width to spare and 720 px of height to obey, so a window
        that saves 100 px of width by turning a two-line explanation into a
        five-line one has made itself WORSE by the only measure that binds.
        Both numbers are still measured — the loop stops at the first width
        where the longest caption fits `CAPTION_LINES`, and never goes past
        `CAPTION_MAX_INNER`.
        """
        metrics = QFontMetrics(self.font())

        def widest(strings) -> int:
            return max((metrics.horizontalAdvance(s) for s in strings), default=0)

        def tallest(width: int, *texts) -> int:
            return max(metrics.boundingRect(0, 0, width, 10_000,
                                            int(Qt.TextFlag.TextWordWrap), t).height()
                       for t in texts)

        label_col = widest(FORM_LABELS) + 16
        combo_col = widest(
            [label for label, _ in RESOLUTIONS + BITRATES + FPS_CHOICES
             + SPEECH_RATES + PHONE_THEMES + PHONE_COLORED + PHONE_FILLS]
            + [f"Monitor {self.monitor_combo.count()}", DEFAULT_VOICE_LABEL]
            + [self.voice_combo.itemText(i) for i in range(self.voice_combo.count())]
        ) + 56
        checkbox_col = widest(("Tell my phone when an agent finishes",
                               "Don't let applications steal focus",
                               "Check for new versions when the app starts",
                               "Start with Windows", "Say it out loud")) + 34
        # FOCUS and STARTUP share a row (see `_build_cards`), so the window
        # must be wide enough for the longer of THEIR checkboxes twice over,
        # plus both cards' own padding and the gap between them — otherwise
        # ladder step 2 would have bought height by clipping a switch.
        paired_row = 2 * (widest(("Don't let applications steal focus",
                                  "Check for new versions when the app starts",
                                  "Start with Windows")) + 34 + 36) + 12

        # The phone's row holds THREE combos side by side (owner correction
        # 2026-08-08 split one theme combo into theme + coloured), so it can
        # be wider than the widest single one — and a heading row that also
        # carries the theme pill has its own floor. Both measured, neither
        # guessed. +8 per gap between combos (trio_row's own spacing), twice.
        phone_row = (label_col
                     + widest([label for label, _ in PHONE_THEMES]) + 56
                     + widest([label for label, _ in PHONE_COLORED]) + 56
                     + widest([label for label, _ in PHONE_FILLS]) + 56 + 16)
        head_row = (metrics.horizontalAdvance("APPEARANCE")
                    + metrics.horizontalAdvance("This PC")
                    + THEME_SWITCH_W + 32)

        card_pad, root_pad = 36, 36   # card contents margins, window margins
        inner = max(label_col + combo_col, checkbox_col, phone_row, head_row,
                    paired_row,
                    metrics.horizontalAdvance("Apply & restart") + 40)
        # The wrapping captions, at the width they will actually have. FIVE
        # slots, and each slot contributes only its OWN tallest alternative —
        # a caption that swaps between three sentences occupies one of them at
        # a time, and summing all three would declare a floor with empty space
        # under it, which is the same law read from the other side.
        rows = metrics.height() + 12

        def height_at(width: int) -> int:
            # FOCUS and STARTUP sit SIDE BY SIDE, so their captions wrap at
            # roughly half the width and only the TALLER of the two costs the
            # window anything — the same "one slot contributes its own tallest
            # alternative" rule, applied to a row instead of to a label.
            half = max(1, (width - 12) // 2 - 36)
            wrapped = (tallest(width, APPEARANCE_TEXT)
                       + tallest(width, STREAM_TEXT)
                       # indented (see CAPTION_INDENT_LEFT) — less width to
                       # wrap in than every other caption in this window
                       + tallest(width - CAPTION_INDENT_LEFT,
                                 NOTIFY_ON_TEXT, NOTIFY_OFF_TEXT)
                       + tallest(width, SPEAK_OFF_TEXT, NO_VOICES_TEXT,
                                 VOICES_TEXT, VOICE_ABSENT_TEXT)
                       + max(tallest(half, FOCUS_TEXT) + rows,      # + 1 tick
                             tallest(half, STARTUP_TEXT) + rows * 2))
            return (rows * 5      # the five section headings (one row shared)
                    + rows * 7    # seven form rows (the phone's trio + four
                                  #                  stream + voice + pace)
                    + rows * 2    # the two checkboxes above the paired row
                    + rows * 1    # the Apply row
                    + wrapped
                    + 5 * 32      # card frames + paddings (the pair is one)
                    + 40)         # window margins and spacings

        # Spend width ONLY while it buys height. Every extra pixel of width
        # lets the guidance wrap into fewer rows, until it stops helping — and
        # the first width that reaches the smallest height is the floor. Any
        # wider is empty space; any narrower turns a two-line explanation into
        # a five-line paragraph and pushes the window past the screen floor,
        # which is the axis that actually binds on a desktop.
        # `max(...)` on the stop: content alone can already be wider than the
        # readable-line ceiling (a long voice name, or a machine whose font
        # metrics run large), and there is nothing to search then — the widest
        # unwrappable row IS the width.
        best = min(range(inner, max(inner, CAPTION_MAX_INNER) + 1, CAPTION_STEP),
                   key=lambda w: (height_at(w), w))
        return QSize(best + card_pad + root_pad, height_at(best))
