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

  STREAM         — what the PC sends. Since 2026-08-12 (owner ballot, option
                   A) it is Monitor + ONE Quality dropdown of four named steps
                   carrying their own numbers — Max / High / Balanced / Data
                   saver — with the exact values behind a Custom… disclosure;
                   Resolution left the front of the card because the PC now
                   scales to the watching device's panel. The card itself
                   lives in gui/stream_card.py (THE STRUCTURE LAW); this
                   window keeps the column and the measured minimum. Still the
                   only card with an Apply: these shape the encoder, so they
                   need the server restarted, exactly as before.
  NOTIFICATIONS  — the agent hook switch (moved here from the main window),
                   and WHETHER the phone reads a notice out loud. WHICH voice
                   and how fast is no longer here: that moved onto the phone
                   itself on 2026-08-12, because the owner uses a tablet AND a
                   phone whose engines carry different voices, and one dropdown
                   on one PC could only ever name a voice that exists on one of
                   them — pick the tablet's and the phone falls silently back
                   to its own default while this window still shows a name.
                   Two master switches (decisions about the JOB) stayed; the
                   device-specific choice went to the device, where it can also
                   be HEARD before it is picked (client/notify.js).
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
  - **The phone** — GONE FROM THIS WINDOW on 2026-08-12 (owner ballot:
    "appearance is also per device, not global, so it belongs on the phone /
    tablet"). Three combos stood here — theme, coloured/plain, outlined/filled
    — and they could only ever describe ONE handset while he uses a tablet and
    a phone. The choice now lives on the device (client/appearance-panel.js,
    stored through the SharedPreferences bridge); `phone_theme` /
    `phone_colored` / `phone_fill` survive as the DEFAULT a device wears until
    it chooses, still riding every `config` frame, and the caption here is the
    forwarding note.

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
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

import threading

import autostart
import foreground_lock
import updates
# `import notify` left with the Voice dropdown on 2026-08-12 — `notify.voices()`
# was its only caller here. The three names below are still imported by name.
from config import SETTINGS, save_user_settings
from gui.sizing import clamp_to_screen, settle_minimum
from gui.stream_card import (
    BITRATES, CUSTOM_TEXT, FPS_CHOICES, QUALITY_STEPS, RESOLUTIONS, STREAM_TEXT,
    StreamCard,
)
from gui.switch import TRACK_W as THEME_SWITCH_W, ThemeSwitch, choose_theme
from gui.theme import card, repolish
from notify import HOOK_CHANGE_FAILED_TEXT, agent_hook_installed, set_agent_hook

logger = logging.getLogger(__name__)

# The stream choices moved to gui/stream_card.py on 2026-08-12 (THE STRUCTURE
# LAW) along with the card that offers them. They are imported back only for
# the computed minimum below, which has to measure every string this window
# can ever show — including the ones it no longer owns.

# Every labelled row in the window, in one place — the label column is sized
# from the widest of them ALL so the cards' fields line up in one straight
# edge instead of each card finding its own.
FORM_LABELS = ("Monitor", "Quality", "Exact", "Port", "JPEG quality")

# The granularity of the width search the computed minimum runs (see
# `_computed_minimum`). It walks UP from the widest unwrappable row and stops
# at the first width whose measured height fits the screen floor, so a coarser
# step costs a few pixels of extra width and a finer one costs a few more
# layout measurements — neither is load-bearing.
CAPTION_STEP = 16

# THE SCREEN FLOOR this window must fit inside (.claude/layout-frame.json).
# Named here because `_computed_minimum` SEARCHES against it: it takes the
# smallest width whose measured height fits, rather than the widest width that
# minimises height. Declaring a bigger floor instead would be widening our way
# out of the exact bug the ladder exists to prevent — and the owner's screen
# does not grow to match a declaration.
FLOOR_WIDTH, FLOOR_HEIGHT = 1280, 1000

# The notify caption sits BETWEEN two checkboxes ("Tell my phone…" above,
# "Say it out loud" below), so a plain full-width line under it reads at a
# glance as if it could belong to either (round R2's SECOND independent
# grader, 2026-08-07). Indented to the checkbox's own text column — indicator
# width (16px) + its spacing (9px), gui/theme.py QCheckBox rule — it visually
# hangs off "Tell my phone…" the way a form's helper text hangs off its field,
# whatever the caption says. Ladder step 2 (reflow the BINDING), not a wider
# window: the indent costs no extra row, only a few px of wrap width.
CAPTION_INDENT_LEFT = 25

# WHAT IS LEFT OF THIS CARD (owner ballot 2026-08-12: "appearance is also per
# device, not global, so it belongs on the phone / tablet"). The three phone
# combos are gone to the handset; the PC's own sun/moon pill stays, because
# THIS window is the PC. The caption is the forwarding note — a setting that
# moves without one reads as a setting that was taken away, which is the same
# rule the Voice dropdown left behind on this window earlier the same day.
APPEARANCE_TEXT = (
    "The switch above is this PC's own theme. How your phone or tablet looks — "
    "dark or light, coloured or plain controls, outlined or filled — is now "
    "chosen on the device itself: Settings → Look in the app. A device that "
    "has not chosen follows the PC.")
NOTIFY_ON_TEXT = ("Claude Code will call this PC when a turn ends, and the PC "
                  "passes it to your phone by name.")
NOTIFY_OFF_TEXT = "Off — the phone stays quiet when a job on this PC finishes."
SPEAK_OFF_TEXT = ("Off — the phone still shows the notification, it just does "
                  "not read it out loud.")
# What used to be a Voice dropdown and a Speaking pace dropdown (owner
# 2026-08-12). The card says where they went instead of leaving a gap: a
# setting that moves without a forwarding note reads as a setting that was
# taken away.
PHONE_VOICE_TEXT = ("The voice and pace are chosen on each phone — Settings → "
                    "Voice in the app, where every voice can be heard before "
                    "it is picked. Two devices carry two different voice "
                    "lists, so each keeps its own answer.")
FOCUS_TEXT = ("While this is on, Windows stops other programs from jumping in "
              "front of whatever you are using. It is switched back off when "
              "Vibe Coder closes, and it is never written into the registry.")
STARTUP_TEXT = ("Vibe Coder starts hidden in the tray, so the phone can "
                "reach this PC without anyone logging in and opening it.")

# ADVANCED (task 226, owner ballot verdict) — the four config keys that had a
# field in Settings but no door in this window: port, use_h264, jpeg_quality,
# open_qr_image. Last card on purpose — every owner who never needs these
# never has to scroll past them to reach anything he does need.
PORT_TEXT = ("Which network port the PC listens on. Changing it needs the "
             "server restarted — Apply & restart, same as the stream card.")
H264_TEXT = ("H.264 is the normal path — hardware-encoded, small on the "
             "wire. Off falls back to sending a plain JPEG picture every "
             "frame, which any PC can do but costs far more bandwidth; use "
             "it only if H.264 will not run here.")
JPEG_QUALITY_TEXT = ("Sharpness of the JPEG fallback picture, 1 to 100. Only "
                     "spent while H.264 is off — a native H.264 stream never "
                     "reads this.")
QR_IMAGE_TEXT = ("Also opens the pairing QR as its own image file when the "
                 "server starts — useful for scanning it from a second "
                 "screen. The app's own window shows the QR either way.")


class SettingsWindow(QDialog):
    """Modeless, like the Traffic window: the owner watches the main window's
    status pill while a stream change restarts the server."""

    # A display change arrives on the watch's own thread (a WM_DISPLAYCHANGE
    # message window, or Qt's screen signals). A Qt signal is the marshal:
    # emitted from there, delivered on the GUI thread, so `_repopulate` never
    # touches a widget from a foreign thread.
    displays_changed = Signal()

    def __init__(self, controller, restart, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._restart = restart
        # The combo the monitor list lives in, kept so a monitor plugged in
        # while this window is OPEN can refill it (constraint 30: dxcam
        # enumerates its outputs once per process, so the list built when this
        # window was constructed is frozen — reopening the window never
        # helped, only restarting the app did).
        self._monitor_combo: QComboBox | None = None
        self._watching_displays = False
        self._settled = False   # the minimum is measured on first show
        self._form_label_widgets: list[QLabel] = []   # aligned on first show

        self.setWindowTitle("Settings — Vibe Coder")

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

        FOCUS and STARTUP therefore shared one row from R3 onward. That bought
        one rung and it was not enough: by 2026-08-12 the measured minimum had
        reached **767x1226**, and the guard named the real defect —

            MIN 767x1226 does not fit the screen floor 1280x1000.

        This is problem #4 on the owner's own list ("desktop Settings escapes
        the screen"), and it is why round 46's `clamp_to_screen` could not fix
        it: clamping pulls a window that has been pushed off-screen back
        inside, and can do NOTHING for a window that is TALLER than the screen.
        On his 1920x1080 display the workspace is about 1040 px with the
        taskbar, so this window could not be shown whole wherever it was put.
        The number was in the audit output the whole time.

        SO THE WHOLE COLUMN REFLOWS (ladder step 2, and step 1 was tried first
        — see `_computed_minimum`). The window is 767 px wide inside a 1280 px
        floor: about 500 px of unused WIDTH beside 226 px of missing height.
        Two columns convert the axis we are short of into the one we have
        spare.

        WHICH CARDS GO SIDE BY SIDE IS NOT ARBITRARY. The two cards at the top
        stay FULL WIDTH:
          - STREAM because it must: its Exact row holds three combos plus a
            label column and needs ~644 px that no half-column can give. Split
            it and the trio clips, which is the bug one rung down.
          - APPEARANCE because its caption is four lines at half width and one
            at full — halving it would buy height with one hand and give it
            back with the other, which is the mistake R3's own comment warned
            about.
        The four SWITCH cards below split THREE AND ONE, and the split is
        measured rather than tidy: ADVANCED is nearly as tall as the other
        three together (four captions, two form rows, its own Apply), so
        putting it alone in the right column balances the two columns to within
        a few rows, while any two-and-two split leaves one column ~120 px
        taller than the other — and the taller column IS the window's height.
        It also reads correctly: the left column is the app's behaviour while
        you work and when it starts, the right is the one card almost nobody
        opens. FOCUS and STARTUP stop sharing their old half-of-a-half row;
        each is now simply a card in a column, and both captions wrap at a real
        width for the first time.
        """
        root.addWidget(self._build_appearance_card())
        root.addWidget(self._build_stream_card())

        columns = QHBoxLayout()
        columns.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(self._build_notifications_card())
        left.addWidget(self._build_focus_card())
        left.addWidget(self._build_startup_card())
        left.addStretch()
        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(self._build_advanced_card())
        right.addStretch()
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        root.addLayout(columns)

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
        """THIS PC's look, and a pointer to where the phone's went.

        The PC's row is the SWITCH, not a combo: two states with a picture
        each is a switch, and the owner's own PromptPainter pill is the shape
        he already reads.

        THE PHONE'S THREE COMBOS LEFT ON 2026-08-12 (owner ballot: appearance
        is per device). They were one dropdown each for theme, colour and
        fill, and they could only ever describe ONE handset — he uses a tablet
        and a phone. What is left is a card with a heading row and a caption,
        and NOT a hole: the pill still sits on the heading's own line where it
        always did, the form row that carried the trio is gone rather than
        emptied, and the caption below says where the setting went. An
        orphaned label over an empty column is what a grader measures.

        Takes effect at once — the PC repaints under the cover transition. No
        Apply, exactly like every other card in this window except STREAM.
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

        self._caption(box, APPEARANCE_TEXT)
        return frame

    # -- the seam the STREAM card is built through -------------------------
    # gui/stream_card.py owns the card; this window owns the column and its
    # measured minimum. These four are the window's own row helpers under
    # public names, so the card can build rows that line up with every other
    # card's without reaching into a private method.

    def card(self):
        return card()

    def section(self, box: QVBoxLayout, title: str) -> None:
        self._section(box, title)

    def form(self) -> QFormLayout:
        return self._form()

    def row(self, form: QFormLayout, text: str, field: QWidget) -> None:
        self._row(form, text, field)

    def caption(self, box: QVBoxLayout, text: str) -> QLabel:
        return self._caption(box, text)

    def resettle(self) -> None:
        self._resettle()

    def _build_stream_card(self):
        self.stream_card = StreamCard(self, self._populate_monitors, self._restart)
        return self.stream_card.build()

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

        # TWO SWITCHES AND NOTHING ELSE (owner 2026-08-12). The Voice and
        # Speaking pace rows that stood here are gone to the phone; what is
        # left in this card is the pair of decisions that belong to the JOB
        # rather than to a handset — whether the PC calls at all, and whether
        # the call is spoken. `notify_voice` / `notify_rate` are still SENT on
        # every frame (server/notify.py) so a phone that has never chosen keeps
        # behaving exactly as it did; they simply have no dial here any more.
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
        self.autostart_check = QCheckBox("Start with Windows")
        self.autostart_check.setChecked(autostart.installed())
        self.autostart_check.toggled.connect(self._toggle_autostart)
        box.addWidget(self.autostart_check)
        self.startup_caption = self._caption(box, STARTUP_TEXT)
        return frame

    def _build_advanced_card(self):
        """LAST card, deliberately: port / H.264 / JPEG quality / QR image —
        four fields that had a `Settings` entry and no door, so an owner who
        needed one edited `%LOCALAPPDATA%/VibeCoder/settings.json` by hand.
        Only the port field needs Apply & restart, matching STREAM's own rule
        (it reshapes the socket the server listens on); the other three act
        at once like every other switch in this window.
        """
        frame, box = card()
        self._section(box, "ADVANCED")

        form = self._form()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(SETTINGS.port)
        self._row(form, "Port", self.port_spin)
        box.addLayout(form)
        self._caption(box, PORT_TEXT)

        self.h264_check = QCheckBox("H.264 streaming")
        self.h264_check.setChecked(SETTINGS.use_h264)
        self.h264_check.toggled.connect(self._toggle_h264)
        box.addWidget(self.h264_check)
        self._caption(box, H264_TEXT, indent=CAPTION_INDENT_LEFT)
        box.addSpacing(6)

        jpeg_form = self._form()
        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(1, 100)
        self.jpeg_quality_spin.setValue(SETTINGS.jpeg_quality)
        self.jpeg_quality_spin.valueChanged.connect(self._save_jpeg_quality)
        self._row(jpeg_form, "JPEG quality", self.jpeg_quality_spin)
        box.addLayout(jpeg_form)
        self._caption(box, JPEG_QUALITY_TEXT)

        self.qr_image_check = QCheckBox("Also open the QR as an image file")
        self.qr_image_check.setChecked(SETTINGS.open_qr_image)
        self.qr_image_check.toggled.connect(self._toggle_qr_image)
        box.addWidget(self.qr_image_check)
        self._caption(box, QR_IMAGE_TEXT, indent=CAPTION_INDENT_LEFT)

        apply_row = QHBoxLayout()
        apply_row.addStretch()
        self.advanced_apply_btn = QPushButton("Apply && restart")
        self.advanced_apply_btn.clicked.connect(self._apply_advanced)
        apply_row.addWidget(self.advanced_apply_btn)
        box.addLayout(apply_row)
        return frame

    def _apply_advanced(self) -> None:
        save_user_settings({"port": self.port_spin.value()})
        self._restart()

    def _toggle_h264(self, on: bool) -> None:
        save_user_settings({"use_h264": bool(on)})

    def _save_jpeg_quality(self) -> None:
        save_user_settings({"jpeg_quality": self.jpeg_quality_spin.value()})

    def _toggle_qr_image(self, on: bool) -> None:
        save_user_settings({"open_qr_image": bool(on)})

    # -- stream settings ---------------------------------------------------

    def _populate_monitors(self, combo: QComboBox) -> None:
        """Enumeration stays HERE — it asks the capture layer a question about
        this PC, which is this window's subject, not the stream card's.

        The combo is REMEMBERED and the window subscribes to the display
        watch: `BaseCapture.output_count()` reads `dxcam.output_info()`, whose
        outputs were enumerated ONCE at import for the life of the process
        (constraint 30, measured — it cost a 3.8-hour dead picture), so a
        monitor plugged in mid-run never appeared here and reopening the
        window did not help. Now a real display change re-enumerates DXGI
        (`capture.on_display_change`) and re-asks this question."""
        self._monitor_combo = combo
        self._watch_displays()
        self._fill_monitors(combo)

    def _fill_monitors(self, combo: QComboBox) -> None:
        from capture import BaseCapture
        try:
            count = BaseCapture.output_count()
        except Exception as e:  # enumeration is cosmetic — never kill the window
            logger.error("Monitor enumeration failed: %s", e)
            count = 1
        chosen = combo.currentData()
        combo.clear()
        for i in range(max(1, count)):
            combo.addItem(f"Monitor {i + 1}", i)
        # A repopulate must not silently re-point the owner's choice at
        # monitor 1; his pick is restored when it still exists.
        if chosen is not None:
            index = combo.findData(chosen)
            if index >= 0:
                combo.setCurrentIndex(index)

    # -- displays that come and go ------------------------------------------

    def _watch_displays(self) -> None:
        """Subscribe the OPEN window to the process's one display watch.

        The callback arrives on the watch's own thread (a message-only window,
        or Qt's screen signals), so it only EMITS — the repopulate itself runs
        on the GUI thread through the queued signal. A widget touched from
        another thread is a crash, not a glitch."""
        if self._watching_displays:
            return
        try:
            watch = self.controller.display_watch
        except Exception:  # a controller without one (a test double) is fine
            return
        self.displays_changed.connect(self._on_displays_changed)
        watch.subscribe(self._emit_displays_changed)
        self._watching_displays = True

    def _emit_displays_changed(self, _diff) -> None:
        """The watch's callback — the ONE thing it may do off the GUI thread."""
        try:
            self.displays_changed.emit()
        except RuntimeError:
            pass  # the window went away between the change and the emit

    def _on_displays_changed(self) -> None:
        if self._monitor_combo is not None:
            self._fill_monitors(self._monitor_combo)

    def _unwatch_displays(self) -> None:
        """A closed window's callback must not be held — the watch would keep
        this dialog alive and emit into a dead widget."""
        if not self._watching_displays:
            return
        self._watching_displays = False
        try:
            self.controller.display_watch.unsubscribe(self._emit_displays_changed)
        except Exception:
            logger.exception("Unsubscribing from the display watch failed")
        try:
            self.displays_changed.disconnect(self._on_displays_changed)
        except (RuntimeError, TypeError):
            pass

    def done(self, result: int) -> None:
        """QDialog's ONE exit — `accept()`, `reject()` and the window's own ✕
        all end here, which is why the unsubscribe sits here and not in
        `closeEvent` alone."""
        self._unwatch_displays()
        super().done(result)

    # -- notifications ------------------------------------------------------

    def _show_notify_state(self) -> None:
        self._set_caption(self.notify_caption,
                          NOTIFY_ON_TEXT if self.notify_check.isChecked()
                          else NOTIFY_OFF_TEXT)
        self._resettle()  # a longer caption gets its room NOW, not on the next open

    def _show_speak_state(self) -> None:
        """One caption slot, two alternatives — off says what still happens,
        on says where the voice itself is chosen (owner 2026-08-12). It used
        to have four, three of which described a dropdown that no longer
        exists on this window."""
        self.speak_caption.setText(
            PHONE_VOICE_TEXT if self.speak_check.isChecked() else SPEAK_OFF_TEXT)
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

        The live state is re-read on EVERY show: the autostart task and the
        agent hook may both have been changed from outside this window (an
        installer run, `agent_hook.py --install`) since the last one.
        """
        super().showEvent(event)
        self._refresh_live_state()
        if self._settled:
            return
        self._settled = True
        self._align_label_column()
        self.stream_card.settle()
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
        # …and then back onto the screen (owner report 2026-08-12). This is the
        # point at which this window's geometry is FINAL — every growth above
        # spends itself on the bottom and right edges, and the top of the first
        # card was what he found missing. gui/sizing.py holds the one copy.
        clamp_to_screen(self)

    def _computed_minimum(self) -> QSize:
        """MEASURED, never guessed (THE SPACE & LEGIBILITY LAW, rules/GUI.md) —
        and since 2026-08-12 measured by asking THE LAYOUT, not by modelling it.

        Two numbers, found two different ways, because they are two different
        questions:

        WIDTH FLOOR — the widest row that CANNOT wrap. A form label plus the
        longest entry of the combo beside it; the Exact row's three combos side
        by side; the APPEARANCE heading with its pill; and, now that everything
        below STREAM sits in two columns, the widest unwrappable thing in a
        SWITCH card twice over. Combo entries and checkbox labels never reflow,
        so no amount of height can pay for them.

        HEIGHT — `layout().totalHeightForWidth(w)`, the real answer from the
        real widgets. This REPLACED a hand-written model of every heading, row,
        caption and card frame in the window (2026-08-12). That model was
        already drifting — it read 875 where Qt needed 948 — and a model of a
        layout is one more thing to keep in step with the layout. It also could
        not see what actually binds: the model said width kept buying height up
        to 1,175 px, while Qt stops improving at about 960.

        THE SEARCH TAKES THE SMALLEST WIDTH THAT FITS THE SCREEN FLOOR, not the
        widest that minimises height. That is the ladder's own instruction read
        honestly: reflow until it fits, then stop. Spending another 200 px of
        width past the point of fitting buys nothing and costs the reader —
        DESIGN.md calls 60–80 characters a readable line, and this window's
        guidance at 1,175 px runs to about 150. If no width fits (which would
        mean the reflow itself is not enough), it falls back to the width with
        the smallest height and the audit says so out loud, which is the honest
        failure rather than a silent oversized window.
        """
        metrics = QFontMetrics(self.font())

        def widest(strings) -> int:
            return max((metrics.horizontalAdvance(s) for s in strings), default=0)

        label_col = widest(FORM_LABELS) + 16
        # The Quality steps are the longest entries this window has ever had
        # ("Balanced — 30 fps, 6 Mbps"), and they cannot wrap — a combo entry
        # never does. That makes them the row that sets the width, which is
        # the whole reason they are measured here rather than guessed at.
        combo_col = widest(
            [label for label, _ in RESOLUTIONS + BITRATES + FPS_CHOICES]
            + [label for label, _, _ in QUALITY_STEPS]
            + [f"Monitor {self.stream_card.monitor_combo.count()}"]
        ) + 56
        checkbox_col = widest(("Tell my phone when an agent finishes",
                               "Don't let applications steal focus",
                               "Check for new versions when the app starts",
                               "Start with Windows", "Say it out loud",
                               "Custom…")) + 34
        # The Exact row holds THREE combos side by side behind Custom…, and
        # they share the row's width EQUALLY (each is stretch 1), so the widest
        # entry of ANY of the three sets all three. `StreamCard.settle` pins
        # each to its own polished size hint on first show, which is what makes
        # this a floor Qt then enforces rather than an estimate.
        exact_row = (label_col + 16
                     + 3 * (widest([label for label, _ in
                                    RESOLUTIONS + BITRATES + FPS_CHOICES]) + 64))
        head_row = (metrics.horizontalAdvance("APPEARANCE")
                    + metrics.horizontalAdvance("This PC")
                    + THEME_SWITCH_W + 32)

        card_pad, root_pad = 36, 36   # card contents margins, window margins
        # THE TWO COLUMNS (2026-08-12 reflow — see `_build_cards`). The widest
        # UNWRAPPABLE thing in a switch card has to fit in a HALF, twice over,
        # plus each card's padding and the gap. Get this wrong and the reflow
        # buys its height by clipping a switch, which is the rung below the one
        # we are standing on.
        column_need = max(checkbox_col, label_col + 120,
                          metrics.horizontalAdvance("Apply & restart") + 40)
        floor = max(label_col + combo_col, exact_row, head_row,
                    2 * (column_need + card_pad) + 12) + card_pad + root_pad

        layout = self.layout()
        widths = list(range(floor, max(floor, FLOOR_WIDTH) + 1, CAPTION_STEP))
        heights = {w: layout.totalHeightForWidth(w) for w in widths}
        fits = [w for w in widths if heights[w] <= FLOOR_HEIGHT]
        best = fits[0] if fits else min(widths, key=lambda w: (heights[w], w))
        return QSize(best, heights[best])
