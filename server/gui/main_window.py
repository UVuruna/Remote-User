"""The desktop window: status, pairing QR, start/stop, tray.

One column of soft-shadowed cards (DESIGN.md bento style, single column at
this size). THE WINDOW NEVER BLOCKS, and since 2026-08-12 that is true: every
slow thing — start/stop/restart, the pairing probe, the quit's own shutdown —
runs on a worker thread ([Off-thread](offthread.py)) while a 1 s timer pulls
state from the ServerController. The last two used to run inline and freeze it
for seconds. Closing the window hides to the tray — the server runs until Quit.

WHAT THIS WINDOW IS *NOT*, since round R2 (owner 2026-08-07). It had become
two things at once: the thing you open to PAIR a phone, and the thing you open
to CONFIGURE a PC. The stream form and the notify switch moved out to
[gui/settings_window.py]; what is left is one job — get a phone connected to
this PC and say whether it worked — plus one row of doors to the windows that
do the rest. Those are ICON buttons with real SVG icons and no trailing "…":
drawn assets, never a font glyph, for the same reason the phone's Move handle
is drawn (owner 2026-08-05 — a glyph came out a blunt cross on his device).

WHICH DOORS, since 2026-08-19 (owner request). Controls and Settings are every
user's; Traffic is the owner's own instrument and is the first of a class he
named — "i jos neke naknadne opcije" — so it is behind DEVELOPER TOOLS, opened
by clicking this window's title five times (gui/developer_mode.py). A fresh
install therefore shows two doors, and the row is still measured against all
three, because the law measures the fullest real content and not the state
that happens to be on screen.
"""

import logging
import subprocess
import webbrowser

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFontMetrics, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QProgressBar,
    QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget,
)

import pairing
import update_handover
import updates
from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT, SETTINGS, app_version, save_user_settings
from gui import offthread
from gui.main_window_server import ServerControl
from gui.main_window_updates import (
    UPDATE_FAILED_TEXT, UPDATE_HANDOVER_TEXT, UpdateFlow,
)
from gui.controls_editor import ControlsEditor
from gui.developer_mode import OFF_TEXT, ON_TEXT, TitleTap, is_on as dev_tools_on
from gui.settings_window import SettingsWindow
from gui.sizing import settle_minimum
from gui.switch import TRACK_W as THEME_SWITCH_W, ThemeSwitch, choose_theme
from gui.theme import apply_theme, card, icon as themed_icon, repolish
from gui.traffic_window import TrafficWindow
from server_core import ServerController

logger = logging.getLogger(__name__)

ASSET_DIR = (BUNDLE_DIR if FROZEN else PROJECT_ROOT) / "assets"

QR_SIZE = 216
REFRESH_MS = 1000
PAIRING_RECHECK_TICKS = 5  # re-check addresses/Tailscale every N refresh ticks
# How often a RUNNING app asks GitHub again (owner 2026-08-07). Fifteen
# minutes: a release he is waiting for reaches him inside one coffee, and 96
# unauthenticated calls a day sit far under any rate limit. See
# `_check_updates` for the day this number was worth.
UPDATE_CHECK_MS = 15 * 60 * 1000

# The stream choices moved to gui/settings_window.py with the combos they
# fill (round R2). "Phone hand" is GONE (owner 2026-08-02): the cursor-offset
# system it fed was removed — the pointer sits exactly under the finger.
ICON_PX = 17   # icon height on the three window buttons, next to 13px text
# THEME_SWITCH_W is imported from the widget that DRAWS the pill, so the
# measured minimum below can never drift from what is actually on the row.

PILL_TEXT = {"running": "RUNNING", "starting": "STARTING…",
             "stopped": "STOPPED", "failed": "FAILED"}

# THE ROW OF DOORS, and which of them are the developer's (owner 2026-08-19).
# `dev` is the whole difference between "a thing every user needs" and "a thing
# the owner needs", and it is a COLUMN in this table rather than an `if` in the
# builder because he asked for more of them: "i jos neke naknadne opcije".
# A new developer door is a row here with `dev=True` and nothing else.
DOORS = (
    ("Controls", "icon-controls", "_edit_controls", False),
    ("Traffic", "icon-traffic", "_show_traffic", True),
    ("Settings", "icon-settings", "_show_settings", False),
)

# Shown under the row while the developer doors are open, and the ONLY place
# in the product the gesture is written down. A tray balloon is not a promise —
# Focus assist, Do-not-disturb or notifications turned off for this app all
# swallow it — and without this line an accidental ON is a mystery button with
# no way back.
DEV_NOTE_TEXT = ("Developer tools are on. Click the title above five times to "
                 "hide them again.")

# The three guided states under the QR, in one place: the refresh loop shows
# them, and the window's COMPUTED minimum size measures them (THE SPACE &
# LEGIBILITY LAW — the minimum comes from the fullest real content, and that
# content is the longest of these).
REACH_TEXT = {
    "ready": ("On the phone, first time only:\n"
              "1.  Join THIS same Wi-Fi\n"
              "2.  Scan this QR with the camera\n"
              "3.  Tap Install, then Open the app\n"
              "Done — after that it works from anywhere, no QR."),
    "signin": ("One step left for away-from-home use: sign in to Tailscale. "
               "A browser will open — pick your account and press Connect, "
               "then come back here; this window continues by itself. "
               "(Tailscale may ask a few one-time questions — any answers are fine.)"),
    "lan": ("On the phone, first time only:\n"
            "1.  Join THIS same Wi-Fi\n"
            "2.  Scan this QR with the camera\n"
            "3.  Tap Install, then Open the app\n"
            "For use away from home too, add Tailscale (free, guided)."),
}


class MainWindow(ServerControl, UpdateFlow, QMainWindow):
    # The manual update check answers from a worker thread; Qt widgets
    # may only be touched on the GUI thread.
    _manual_answer = Signal(object)

    def __init__(self, controller: ServerController):
        super().__init__()
        self.controller = controller
        self._busy = False           # a start/stop/restart worker is running
        self._shown_qr_url = None    # avoid re-rendering the same QR every tick
        self._tray_notice_shown = False
        self._tick = 0               # refresh counter (pairing re-checks are throttled)
        self._pairing_busy = False   # a pairing-address worker is running
        self._quitting = False       # the quit worker owns the shutdown now
        # Update flow — workers only SET these; the refresh timer (UI thread)
        # reads them and touches Qt. States: None → found → downloading →
        # ready (hand over to the installer + quit) / failed (retry).
        self._update = None
        self._update_state = None
        self._update_path = None
        self._update_error = None    # the SPECIFIC reason a failed state shows
        # (received, total) bytes for the download bar — total is None when
        # the response gave no Content-Length, which is what tells
        # `_show_progress` to fall back to the indeterminate animation
        # instead of a frozen 0%. Worker-thread writes, UI-thread reads —
        # same pattern as `_update_state` above.
        self._update_progress = None
        self._traffic = None         # the Traffic window, built on first open
        self._settings = None        # the Settings window, built on first open
        self._settled_for = None     # content the declared minimum was measured against

        self.setWindowTitle("Vibe Coder")
        # ON THE APPLICATION, not on this window (build round R3): a
        # per-widget stylesheet WINS over its parent's, so styling this window
        # alone would have left Controls, Traffic, Settings and the
        # wheel-order dialog in whichever palette they were born with. One
        # call themes every window the app has and every window it opens
        # later (gui/theme.py → apply_theme).
        apply_theme(SETTINGS.ui_theme)
        icon = QIcon(str(ASSET_DIR / "logo.svg"))
        self.setWindowIcon(icon)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)

        root.addLayout(self._build_header())
        root.addWidget(self._build_qr_card())
        root.addLayout(self._build_power_row())
        root.addWidget(self._build_window_row())
        root.addWidget(self._build_dev_note())
        root.addWidget(self._build_update_button())
        root.addWidget(self._build_footer())

        self._build_tray(icon)

        self._manual_answer.connect(self._apply_manual_check)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(REFRESH_MS)
        self._refresh()  # fills the guided text — the fullest state to measure

        self._settle_minimum(keep=QSize(0, 0))

        offthread.run(self._check_updates)
        # …and again while the app RUNS (owner 2026-08-07, and this is the
        # single most expensive defect this project has had). See
        # `_check_updates` for what one-check-per-start actually cost him.
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._recheck_updates)
        self._update_timer.start(UPDATE_CHECK_MS)

    # -- the law's computed minimum ----------------------------------------

    def _settle_minimum(self, keep: QSize | None = None) -> None:
        """Declare the minimum this window's CURRENT content needs (ladder
        step 3, rules/GUI.md) — and re-declare it whenever that content grows.

        The wrapped guidance text makes height depend on width, so the minimum
        is SETTLED: measure at the candidate size, grow, measure again — until
        Qt stops asking for more. (One pass would under-shoot by exactly the
        row a narrower window adds.)

        Measuring ONCE, at construction, was the owner's 2026-08-06 bug in both
        screenshots: two things arrive later — the update button (hidden until
        GitHub answers) and the notify switch's caption (three lines when it
        reports a failure instead of one) — and an explicit `setMinimumSize`
        makes Qt stop enforcing the layout's own minimum, so the extra rows had
        nowhere to go and were drawn ON TOP of the QR and its link. Every
        content change now re-settles: the floor rises, and the window rises
        with it. `keep` is the size never to shrink below — the owner's own
        window size at runtime, nothing at construction.
        """
        settle_minimum(self, self._computed_minimum(), keep)
        self._settled_for = self._content_signature()

    def _content_signature(self) -> tuple:
        """Everything on this window whose LENGTH can change after it was
        built. When one of these differs from what the minimum was measured
        against, the minimum is measured again — and only then, so the refresh
        timer does not re-lay-out the window once a second.

        `isHidden()`, never `isVisible()`: a child of a hidden window is not
        visible either, so a signature built on visibility would change the
        moment the owner closes the window to the tray — and the re-measure
        that followed would hand back a minimum with no update button in it,
        putting the overlap back on the next open. `isHidden()` asks the only
        question this window actually decides: was the button shown or not.
        """
        return (self.update_btn.isHidden(), self.update_btn.text(),
                self.update_progress.isHidden(),
                self.dev_note.isHidden(),
                self.reach_label.text(), self.qr_label.text())

    def _resettle(self) -> None:
        if self._settled_for is None:
            return  # still being built — the first settle has not run yet
        if not self.isVisible():
            return  # in the tray: Qt gives no real metrics, so any measurement
                    # taken here would be a smaller, wrong floor. `showEvent`
                    # settles whatever changed while the window was away.
        if self._content_signature() != self._settled_for:
            self._settle_minimum()

    def _computed_minimum(self) -> QSize:
        """MEASURED, never guessed (THE SPACE & LEGIBILITY LAW, rules/GUI.md).

        The window used to be pinned at a hard 400 px, which is exactly the
        "element can no longer take the free space" the law forbids. The floor
        below is the widest real row it can show — the two button rows at
        their longest captions, the update button's full sentence, and the QR
        — plus the height its longest guidance text needs once wrapped at that
        width. The caller takes the LARGER of this and Qt's own layout
        minimum, so neither measurement can undercut the other.

        The settings form left this window in round R2, and with it the row
        that used to drive the width. Two shorter rows replaced one long one
        on purpose: five heterogeneous buttons side by side is what made the
        old row wide, and a wide window spends its extra pixels on empty space
        beside a fixed-size QR.
        """
        metrics = QFontMetrics(self.font())

        def widest(strings) -> int:
            return max(metrics.horizontalAdvance(s) for s in strings)

        button_pad, spacing = 40, 8   # QSS padding 8/16 + border, layout spacing
        power_row = (widest(("Start server", "Stop server"))
                     + widest(("Set up Tailscale", "Sign in to Tailscale",
                               "Install Tailscale"))
                     + 2 * button_pad + spacing)
        # ALL THREE, even though a fresh install shows two: Traffic is behind
        # the developer switch (DOORS, 2026-08-19) and the law measures the
        # FULLEST real content, not the state that happens to be on screen. A
        # floor taken from two buttons would be a floor the row outgrows the
        # moment he clicks the title five times.
        window_row = (widest(("Controls",)) + widest(("Traffic",))
                      + widest(("Settings",))
                      + 3 * (button_pad + ICON_PX + 6)   # icon + its 6px gap
                      + 2 * spacing)
        # EVERY caption this one button can wear, not just the happy one (THE
        # SPACE & LEGIBILITY LAW — the minimum comes from the fullest real
        # content). The handover's refusals are longer than the offer, and a
        # sentence that says WHY an update did not install is exactly the
        # sentence that must not be cut off.
        update_row = widest((f"Update to v{app_version()} — download && install",
                             UPDATE_FAILED_TEXT,
                             UPDATE_HANDOVER_TEXT,
                             update_handover.DAMAGED_TEXT,
                             update_handover.NOT_ELEVATED_TEXT,
                             update_handover.HANDOVER_FAILED_TEXT)) + button_pad
        # The header row grew a theme pill in round R3, and it sits OUTSIDE
        # the card — so it competes with the card's own width and has to be
        # measured, or the widest state (logo + subtitle + STARTING… pill +
        # switch) would simply overlap. Logo 34 + its 10 gap, the longest of
        # the two title lines, the longest pill with its QSS padding, the
        # switch and its gap.
        header_row = (34 + 10 + widest(("Vibe Coder",
                                        "Control this PC from your phone"))
                      + widest(tuple(PILL_TEXT.values())) + 28
                      + 10 + THEME_SWITCH_W)

        card_pad, root_pad = 36, 48   # card contents margins, window margins
        inner = max(QR_SIZE, power_row - card_pad, window_row - card_pad,
                    update_row - card_pad, header_row - card_pad)
        width = inner + card_pad + root_pad

        guidance = max(
            metrics.boundingRect(0, 0, inner, 10_000,
                                 int(Qt.TextFlag.TextWordWrap), text).height()
            for text in REACH_TEXT.values())
        rows = metrics.height() + 20
        # +18 for the update/install progress bar (task 207) — a slim row of
        # its own under the update button, only ever shown alongside it, but
        # THE SPACE & LEGIBILITY LAW measures the fullest real content and
        # this is content the window can genuinely need to show.
        height = (QR_SIZE + guidance          # the QR card's two tall parts
                  + rows * 2                  # url label (wraps) + its buttons
                  + rows * 5                  # header, 2 button rows, update, footer
                  + 18                        # update/install progress bar
                  + 120)                      # card frames, spacings, margins
        return QSize(width, height)

    # -- layout builders ---------------------------------------------------

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        logo = QLabel()
        pix = QPixmap(str(ASSET_DIR / "logo.svg"))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("Vibe Coder")
        title.setObjectName("h1")
        sub = QLabel("Control this PC from your phone")
        sub.setObjectName("caption")
        titles.addWidget(title)
        titles.addWidget(sub)

        # FIVE CLICKS ON THE TITLE open the developer doors (his request of
        # 2026-08-19, and Android's own build-number gesture). The logo and
        # both lines count as one target, because that is what he circled in
        # his picture. Nothing about the header changes: it is not a button, it
        # does not look pressable, and a user who never taps it five times in
        # three seconds never learns there is anything here — which is the
        # whole point of hiding the row rather than removing it.
        self.title_area = QWidget()
        area = QHBoxLayout(self.title_area)
        area.setContentsMargins(0, 0, 0, 0)
        area.setSpacing(10)
        area.addWidget(logo)
        area.addLayout(titles)
        # ONE INSTALL, ON THE CONTAINER. A QLabel ignores a mouse press, so Qt
        # propagates it up to this widget by itself — which is why the filter
        # reaches every click on the logo and both lines without being
        # installed on any of them, and why installing it on them as well made
        # each click count TWICE (a grader measured three clicks opening the
        # door; see gui/developer_mode.py).
        self._title_tap = TitleTap(self._developer_tools_changed)
        self.title_area.installEventFilter(self._title_tap)

        self.pill = QLabel(PILL_TEXT["stopped"])
        self.pill.setObjectName("pill")
        self.pill.setProperty("state", "stopped")

        # The theme pill, top-right AFTER the RUNNING pill (owner's placement,
        # build round R3). The same switch also sits in Settings → Appearance;
        # neither remembers a state of its own — both are told the current
        # theme, so clicking one moves the other.
        self.theme_switch = ThemeSwitch()
        self.theme_switch.set_theme_name(SETTINGS.ui_theme)
        self.theme_switch.picked.connect(choose_theme)

        row.addWidget(self.title_area)
        row.addStretch()
        row.addWidget(self.pill)
        row.addSpacing(10)
        row.addWidget(self.theme_switch)
        return row

    def _build_qr_card(self) -> QFrame:
        frame, box = card()   # the shared card factory — gui/theme.py

        self.qr_label = QLabel("Server stopped")
        self.qr_label.setObjectName("qr")
        # White paper only while a QR is really on it (theme.py QLabel#qr).
        self.qr_label.setProperty("empty", "true")
        self.qr_label.setFixedSize(QR_SIZE, QR_SIZE)  # layout-law: exempt - a QR is an IMAGE that must stay square at its scan size; it carries no text to reflow
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.qr_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # The pairing URL is NOT printed here. It was a 60-character line of
        # random token that nobody reads and nobody can type — the QR already
        # carries it and "Copy link" already copies it — and it was the one
        # element that landed on the QR when the column ran short (owner
        # 2026-08-06: "ja ne znam zašto stoji taj link tu"). What the card
        # owes the user is the STATE, and that is `reach_label`'s job below.
        buttons = QHBoxLayout()
        self.copy_btn = QPushButton("Copy link")
        self.copy_btn.clicked.connect(self._copy_link)
        self.browser_btn = QPushButton("Open in browser")
        self.browser_btn.clicked.connect(self._open_browser)
        buttons.addWidget(self.copy_btn)
        buttons.addWidget(self.browser_btn)
        box.addLayout(buttons)

        self.reach_label = QLabel("")
        self.reach_label.setObjectName("caption")
        self.reach_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.reach_label.setWordWrap(True)
        box.addWidget(self.reach_label)
        return frame

    def _build_power_row(self) -> QHBoxLayout:
        """What this window is FOR: run the server, and reach the phone from
        anywhere. Nothing else lives on this row."""
        row = QHBoxLayout()
        self.power_btn = QPushButton("Start server")
        self.power_btn.setObjectName("primary")
        self.power_btn.clicked.connect(self._toggle_server)
        row.addWidget(self.power_btn)
        row.addStretch()
        self.tailscale_btn = QPushButton("Set up Tailscale")
        self.tailscale_btn.clicked.connect(self._setup_tailscale)
        row.addWidget(self.tailscale_btn)
        return row

    def _build_window_row(self) -> QWidget:
        """The doors, as one row of equals (round R2).

        They used to sit between the power button and the Tailscale button,
        which put five unrelated buttons in one line and made that line the
        thing that decided how wide this window has to be. Given a row of
        their own they share it equally, they carry their SVG icon, and they
        lost the trailing "…" — a dialog is what a button does, not something
        its label has to apologise for.

        A WIDGET and not a bare layout since 2026-08-19: the row is rebuilt
        when the developer doors are opened or closed, and a layout with no
        widget of its own has nothing to empty.
        """
        self.window_row = QWidget()
        box = QHBoxLayout(self.window_row)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        self._fill_window_row()
        return self.window_row

    def _build_dev_note(self) -> QWidget:
        """THE ROUTE BACK, in the window itself.

        The tray balloon that announces the switch is the only thing that says
        how to turn it off, and a tray balloon is not a promise: Focus assist,
        Do-not-disturb, or notifications turned off for this app all swallow
        it. A grader put it plainly — an accidental ON would then be a mystery
        button with no way back, since nothing else in the product reports
        `developer_tools` or clears it.

        So the row itself carries the sentence, for as long as the state
        lasts. It costs one line, only in the state that needs it, and it is
        also the only place the gesture is written down anywhere in the app.
        """
        self.dev_note = QLabel(DEV_NOTE_TEXT)
        self.dev_note.setObjectName("caption")
        self.dev_note.setWordWrap(True)
        self.dev_note.setVisible(dev_tools_on())
        return self.dev_note

    def _fill_window_row(self) -> None:
        """Whichever doors are currently the user's. Traffic is the developer's
        (DOORS), so a fresh install shows Controls and Settings and nothing
        else — his request of 2026-08-19."""
        box = self.window_row.layout()
        while box.count():
            old = box.takeAt(0).widget()
            if old is not None:
                # HIDE, then unparent, then queue the delete — in that order.
                # `deleteLater` alone leaves the widget a visible child at its
                # old geometry until the event loop runs (a rebuilt row drawn
                # over the old one for one paint), and `setParent(None)` alone
                # makes it a top-level WINDOW: a button briefly floating in the
                # middle of his screen. tests/test_widget_orphan.py is the gate
                # that caught exactly that here.
                old.hide()
                old.setParent(None)
                old.deleteLater()
        show_dev = dev_tools_on()
        for label, name, handler, dev in DOORS:
            if dev and not show_dev:
                continue
            button = QPushButton(themed_icon(name), f"  {label}")
            # The palette is BAKED into the SVG source (Qt's renderer ignores
            # `currentColor`), so an icon built once is a picture in the old
            # ink after a theme flip. Naming the asset on the widget is what
            # lets `theme.apply_theme` rebuild it — round R3.
            button.setProperty("iconName", name)
            button.setIconSize(QSize(ICON_PX, ICON_PX))
            button.clicked.connect(getattr(self, handler))
            box.addWidget(button, 1)

    def _developer_tools_changed(self, on: bool) -> None:
        """Five clicks landed on the title. Rebuild the row, say so twice —
        once in the tray and once in the window, because the tray balloon may
        never be shown — and close the room whose door has just gone.

        A window that silently grew a button would read as a glitch, and a
        user who turned it on by accident has to be told how to turn it off.
        """
        self._fill_window_row()
        self.dev_note.setVisible(on)
        # HIDE THE ROOM WITH THE DOOR. Turning the tools off is what he does
        # before handing the machine to somebody else; leaving the Traffic
        # chart standing on the desktop with no door to it is the same defect
        # as a chip about a window that has closed.
        if not on and self._traffic is not None and self._traffic.isVisible():
            self._traffic.hide()
        # The row's WIDTH floor is not re-measured — it is already taken from
        # the fullest real row (all three captions, `_computed_minimum`). The
        # HEIGHT is, because the note is a line the window did not have a
        # moment ago and `_content_signature` now carries it.
        self._resettle()
        self.tray.showMessage("Vibe Coder", ON_TEXT if on else OFF_TEXT,
                              QSystemTrayIcon.MessageIcon.Information, 4000)

    def _edit_controls(self) -> None:
        """The Controls editor (ROADMAP Phase G1): create custom sets, choose
        which ride in the phone's wheel, rearrange any set per orientation —
        end users never hand-edit files. The phone picks changes up on its
        next connection, no restart."""
        try:
            ControlsEditor(self).exec()
        except OSError as e:
            logger.error("Controls editor failed: %s", e)

    def _show_traffic(self) -> None:
        """The owner's own instrument (2026-08-05): every byte to and from the
        phone, over time, with a grey band wherever nobody was connected. He
        asked for it to settle a question no amount of assurance could —
        whether the app keeps talking to a locked phone. Modeless on purpose:
        he watches this window WHILE he locks the phone in his other hand."""
        if self._traffic is None:
            self._traffic = TrafficWindow(self)
        self._show_child(self._traffic)

    def _show_settings(self) -> None:
        """Everything about this PC that is not "get a phone connected"
        (round R2): the stream form that used to sit under the QR, the notify
        switch that used to sit under that, and the three switches that had no
        UI at all — focus, update check, start with Windows. Modeless like
        Traffic: an Apply restarts the server, and the owner watches the main
        window's status pill do it."""
        if self._settings is None:
            self._settings = SettingsWindow(self.controller, self.restart_server, self)
        self._show_child(self._settings)

    def _show_child(self, window) -> None:
        """Show a modeless child window without letting it be destroyed on
        close — these windows keep live state (a chart's history, a phone's
        reported voices) and are built once."""
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        window.show()
        window.raise_()
        window.activateWindow()

    def _build_update_button(self) -> QWidget:
        """Hidden until the check finds a newer release. ONE tap is the whole
        update — download, verify, tell the phone, install silently, restart —
        and nothing else is ever asked of anybody, because the person tapping
        it is usually a hundred kilometres away looking at this window through
        the app that is about to be replaced (`_begin_handover`).

        Carries a progress bar under the button (owner decree 2026-08-10,
        task 207 — a frozen "Downloading…"/"Installing" ellipsis told him
        nothing about whether the app had hung). `_show_progress` drives it:
        determinate with a real % while the download reports a length,
        indeterminate (Qt's own animation) when it does not, or during the
        install hand-over this app cannot see the progress of at all.
        """
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)

        self.update_btn = QPushButton("")
        self.update_btn.setObjectName("primary")
        self.update_btn.clicked.connect(self._install_update)
        self.update_btn.hide()
        box.addWidget(self.update_btn)

        self.update_progress = QProgressBar()
        self.update_progress.setObjectName("updateProgress")
        self.update_progress.setRange(0, 100)
        self.update_progress.setTextVisible(True)
        self.update_progress.hide()
        box.addWidget(self.update_progress)
        return container

    def _build_footer(self) -> QWidget:
        """The version line — and, beside it, the button that asks whether
        there is a newer one.

        IT BELONGS HERE (owner 2026-08-09): "mesto mu ne pripada tamo nego u
        početnom ekranu na dnu gde piše koja je verzija trenutna." He is right
        and the reason is plain — the question is "am I on the latest", and
        the line that says which version he is on is where that question is
        asked. It spent one round in the Settings window, two cards away from
        its own answer.
        """
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(10)
        self.footer = QLabel(
            f"v{app_version()}  ·  closing hides to tray — server keeps running")
        self.footer.setObjectName("caption")
        self.footer.setWordWrap(True)  # ladder step 2: reflow, never widen
        self.check_btn = QPushButton("Check now")
        self.check_btn.setObjectName("secondary")
        self.check_btn.clicked.connect(self._check_updates_now)
        box.addStretch(1)
        box.addWidget(self.footer)
        box.addWidget(self.check_btn)
        box.addStretch(1)
        return row

    def _check_updates_now(self) -> None:
        """One press, one answer — and if there IS a newer version, the button
        that installs it APPEARS.

        The first version of this only wrote a caption (0.0.367, in the wrong
        window): it found the update and then did nothing with it, which is the
        same defect he reported about the Model button a day earlier — a
        control that reports instead of acting. It arms the real update state
        now, so the offer above it lights up exactly as the automatic check
        would have made it."""
        self.check_btn.setEnabled(False)
        self.check_btn.setText("Checking…")

        def ask():
            try:
                found = updates.check(force=True)
            except Exception as e:  # noqa: BLE001 — a failed check is a state
                logger.warning("Manual update check failed: %s", e)
                found = None
            self._manual_answer.emit(found)

        offthread.run(ask)

    def _apply_manual_check(self, found) -> None:
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check now")
        if found and self._update_state in (None, "failed"):
            # ARM it — this is the half the first version was missing.
            self._update = found
            self._update_state = "found"
            self._refresh_update_button()
            return
        if not found:
            self.footer.setText(
                f"v{app_version()}  ·  this is the newest version")
            QTimer.singleShot(6000, self._restore_footer)

    def _restore_footer(self) -> None:
        self.footer.setText(
            f"v{app_version()}  ·  closing hides to tray — server keeps running")

    def _build_tray(self, icon: QIcon) -> None:
        self.tray = QSystemTrayIcon(icon, self)
        menu = QMenu()
        open_action = QAction("Open Vibe Coder", menu)
        open_action.triggered.connect(self._show_window)
        history_action = QAction("Work history", menu)
        history_action.triggered.connect(self._open_history)
        self.tray_toggle = QAction("Stop server", menu)
        self.tray_toggle.triggered.connect(self._toggle_server)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(open_action)
        menu.addAction(history_action)
        menu.addAction(self.tray_toggle)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self._show_window()
            if reason == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self.tray.show()

    # -- actions -----------------------------------------------------------

    def _copy_link(self) -> None:
        info = self.controller.info
        if info:
            QGuiApplication.clipboard().setText(info.qr_url)
            self.tray.showMessage("Vibe Coder", "Pairing link copied.",
                                  QSystemTrayIcon.MessageIcon.Information, 2000)

    def _open_browser(self) -> None:
        info = self.controller.info
        if info:
            webbrowser.open(f"http://127.0.0.1:{info.port}/?token={info.token}")

    def _open_history(self) -> None:
        """The desktop Work history page (`server/work_history.py`) — loopback
        only, no token, exactly like `_open_browser` above but for the page
        the phone never sees."""
        info = self.controller.info
        if info:
            webbrowser.open(f"http://127.0.0.1:{info.port}/history")

    def _setup_tailscale(self) -> None:
        """One button, whatever the state needs next: sign in when installed,
        download otherwise. (The installer chain-installs Tailscale; this
        covers dev runs and signed-out states. The refresh loop notices the
        login by itself and switches the QR to the Tailscale address.)"""
        exe = pairing.tailscale_exe()
        if exe:
            subprocess.Popen([exe, "login"])  # opens the browser sign-in
        else:
            webbrowser.open("https://tailscale.com/download/windows")

    def _refresh_pairing(self) -> None:
        """Signing in to Tailscale mid-run must switch the QR to the
        works-anywhere URL with no restart. ON A WORKER THREAD since
        2026-08-12 — it reaches the network for up to 4 s; the call and the
        reasoning live in [Off-thread](offthread.py), and `_refresh` redraws
        the QR on its next tick."""
        info = self.controller.info
        if self._pairing_busy or not info:
            return
        self._pairing_busy = True
        offthread.run(offthread.refresh_pairing, info,
                      on_done=lambda: setattr(self, "_pairing_busy", False))

    # -- refresh loop ------------------------------------------------------

    def _refresh(self) -> None:
        """Guarded as a whole: this runs every second and reaches the network
        (pairing re-checks). An OSError from a cosmetic refresh used to be
        able to abort the process — and take the daemon server thread, and
        every always-on-top window it was holding, down with it."""
        try:
            self._refresh_inner()
        except Exception:
            logger.exception("Window refresh failed")

    def _refresh_inner(self) -> None:
        state = self.controller.state
        info = self.controller.info

        self.pill.setText(PILL_TEXT.get(state, state))
        self.pill.setProperty("state", state)
        repolish(self.pill)
        self._refresh_update_button()

        if state == "running" and info:
            self._tick += 1
            if not info.tailscale_ip and self._tick % PAIRING_RECHECK_TICKS == 0:
                self._refresh_pairing()
            if info.qr_url != self._shown_qr_url:
                self._shown_qr_url = info.qr_url
                pix = QPixmap()
                pix.loadFromData(pairing.qr_png(info.qr_url))
                self.qr_label.setProperty("empty", None)
                repolish(self.qr_label)
                self.qr_label.setPixmap(pix.scaled(
                    QR_SIZE - 16, QR_SIZE - 16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
            # Three guided states — the user follows THIS window, never
            # Tailscale's site (owner principle: no confusing third-party
            # screens; we say exactly what happens next).
            if info.tailscale_ip:
                self.reach_label.setText(REACH_TEXT["ready"])
                self.tailscale_btn.hide()
            elif pairing.tailscale_exe():
                self.reach_label.setText(REACH_TEXT["signin"])
                self.tailscale_btn.setText("Sign in to Tailscale")
                self.tailscale_btn.show()
            else:
                self.reach_label.setText(REACH_TEXT["lan"])
                self.tailscale_btn.setText("Install Tailscale")
                self.tailscale_btn.show()
            mode = "H.264 · " + (info.encoder or "?") if info.mode == "h264" else "JPEG fallback"
            clients = info.stats.clients
            self.tray.setToolTip(f"Vibe Coder — running ({mode}, "
                                 f"{clients} client{'s' if clients != 1 else ''})")
        else:
            self._shown_qr_url = None
            self.qr_label.setPixmap(QPixmap())
            self.qr_label.setProperty("empty", "true")
            repolish(self.qr_label)
            self.qr_label.setText("Server stopped" if state != "failed" else "Server failed")
            # The reason a stopped server gives goes where the guidance goes —
            # one place under the QR that speaks, instead of two.
            self.reach_label.setText(self.controller.error or "")
            self.tray.setToolTip("Vibe Coder — stopped")

        self._refresh_buttons()
        if state == "failed":
            self.reach_label.setText(
                (self.controller.error + "\n" if self.controller.error else "")
                + "See the log for details.")
        self._resettle()  # content that grew since the last tick raises the floor

    def _refresh_buttons(self) -> None:
        state = self.controller.state
        running = state in ("running", "starting")
        self.power_btn.setText("Stop server" if running else "Start server")
        self.power_btn.setObjectName("danger" if running else "primary")
        repolish(self.power_btn)
        self.power_btn.setEnabled(not self._busy)
        self.copy_btn.setEnabled(state == "running")
        self.browser_btn.setEnabled(state == "running")
        self.tray_toggle.setText("Stop server" if running else "Start server")

    # -- window behavior ---------------------------------------------------

    def showEvent(self, event) -> None:
        """Re-measure the minimum every time the window is shown.

        A window measured while still hidden can under-report by whole rows —
        Qt hands a widget its real metrics when it is shown, and a button that
        was `show()`n on a hidden parent counts for nothing until then. That is
        43 px of update button in this window, which is exactly the strip that
        was drawn over the QR's link.

        EVERY show, not just the first: closing to the tray is this app's
        normal close, `_resettle` deliberately does nothing while the window is
        away, and an update found during those hours must not be handed a
        window that was measured without it.
        """
        super().showEvent(event)
        self._settle_minimum()

    def closeEvent(self, event) -> None:
        """Close = hide to tray (the server keeps running). Quit lives in the
        tray menu."""
        event.ignore()
        self.hide()
        if self._tray_notice_shown or self._tray_notice_seen():
            return
        self._tray_notice_shown = True
        self._mark_tray_notice_seen()
        self.tray.showMessage(
            "Vibe Coder is still running",
            "The server keeps working in the tray. Right-click the icon to quit.",
            QSystemTrayIcon.MessageIcon.Information, 3000,
        )

    # -- the one-time tray notice (owner 2026-08-06) -------------------------
    # "Closing hides me, I keep running" is something a user needs told ONCE.
    # The flag used to live only in this object, so it reset with every start
    # — and a day of starting and stopping the app turned one-time guidance
    # into a toast that "constantly opens and closes". A marker file next to
    # the rest of the user data is what makes once mean once.
    def _tray_notice_seen(self) -> bool:
        return SETTINGS.tray_notice_path.exists()

    def _mark_tray_notice_seen(self) -> None:
        try:
            path = SETTINGS.tray_notice_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("shown", encoding="utf-8")
        except OSError as e:  # a notice we cannot remember is not a failure
            logger.warning("Could not record the tray notice: %s", e)
