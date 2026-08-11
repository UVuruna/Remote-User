"""The desktop window: status, pairing QR, start/stop, tray.

One column of soft-shadowed cards (DESIGN.md bento style, single column at
this size). The window never blocks: server start/stop/restart run on worker
threads and a 1 s timer pulls state from the ServerController. Closing the
window hides to the tray — the server keeps running until Quit.

WHAT THIS WINDOW IS *NOT*, since round R2 (owner 2026-08-07). It had become
two things at once: the thing you open to PAIR a phone, and the thing you open
to CONFIGURE a PC. The stream form and the notify switch moved out to
[gui/settings_window.py]; what is left is one job — get a phone connected to
this PC and say whether it worked — plus one row of doors to the three windows
that do the rest (Controls, Traffic, Settings). Those three are ICON buttons
with real SVG icons and no trailing "…": drawn assets, never a font glyph, for
the same reason the phone's Move handle is drawn (owner 2026-08-05 — a glyph
came out a blunt cross on his device).
"""

import logging
import os
import subprocess
import tempfile
import threading
import webbrowser
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFontMetrics, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QProgressBar,
    QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget,
)

import pairing
import update_handover
import updates
from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT, SETTINGS, app_version, save_user_settings
from gui.controls_editor import ControlsEditor
from gui.freeze_offer import build_freeze_offer_banner
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

# The Update button's failure caption when nothing more specific is known —
# i.e. the download itself never finished. Named because the window's computed
# minimum has to MEASURE it (THE SPACE & LEGIBILITY LAW), alongside the three
# the handover can hand back.
UPDATE_FAILED_TEXT = "Update download failed — retry"

# What the button says in the moments between "downloaded" and the process
# actually going down (owner decree 2026-08-10, task 207): a window that
# vanishes with no explanation reads as a crash to whoever is watching it —
# plain and complete: what is happening, that we are closing, and that we
# come back. Module-level (not a class attribute) so `_computed_minimum`
# can measure it like every other caption this button can wear.
UPDATE_HANDOVER_TEXT = "Vibe Coder will close to finish updating — it comes back on its own"

PILL_TEXT = {"running": "RUNNING", "starting": "STARTING…",
             "stopped": "STOPPED", "failed": "FAILED"}

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


class MainWindow(QMainWindow):
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

        freeze_offer = build_freeze_offer_banner(self)
        if freeze_offer is not None:
            root.addWidget(freeze_offer)
        root.addLayout(self._build_header())
        root.addWidget(self._build_qr_card())
        root.addLayout(self._build_power_row())
        root.addLayout(self._build_window_row())
        root.addWidget(self._build_update_button())
        root.addWidget(self._build_footer())

        self._build_tray(icon)

        self._manual_answer.connect(self._apply_manual_check)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(REFRESH_MS)
        self._refresh()  # fills the guided text — the fullest state to measure

        self._settle_minimum(keep=QSize(0, 0))

        threading.Thread(target=self._check_updates, daemon=True).start()
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

        row.addWidget(logo)
        row.addSpacing(10)
        row.addLayout(titles)
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

    def _build_window_row(self) -> QHBoxLayout:
        """The three doors, as one row of equals (round R2).

        They used to sit between the power button and the Tailscale button,
        which put five unrelated buttons in one line and made that line the
        thing that decided how wide this window has to be. Given a row of
        their own they share it equally, they carry their SVG icon, and they
        lost the trailing "…" — a dialog is what a button does, not something
        its label has to apologise for.
        """
        row = QHBoxLayout()
        for label, name, handler in (
                ("Controls", "icon-controls", self._edit_controls),
                ("Traffic", "icon-traffic", self._show_traffic),
                ("Settings", "icon-settings", self._show_settings)):
            button = QPushButton(themed_icon(name), f"  {label}")
            # The palette is BAKED into the SVG source (Qt's renderer ignores
            # `currentColor`), so an icon built once is a picture in the old
            # ink after a theme flip. Naming the asset on the widget is what
            # lets `theme.apply_theme` rebuild it — round R3.
            button.setProperty("iconName", name)
            button.setIconSize(QSize(ICON_PX, ICON_PX))
            button.clicked.connect(handler)
            row.addWidget(button, 1)
        return row

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

        threading.Thread(target=ask, daemon=True).start()

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
        self.tray_toggle = QAction("Stop server", menu)
        self.tray_toggle.triggered.connect(self._toggle_server)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(open_action)
        menu.addAction(self.tray_toggle)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self._show_window()
            if reason == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self.tray.show()

    # -- server control ----------------------------------------------------

    def restart_server(self) -> None:
        """The Settings window's "Apply & restart", run the way every other
        server action in this app runs: on a worker thread, with this window's
        buttons gated until it finishes. The Settings window saved the values;
        picking them up is a restart, and a restart belongs to whoever owns
        the controller — this window. A no-op while a worker is already in
        flight, and while the server is stopped there is nothing to restart:
        the new values are read by the next start."""
        if self._busy or self.controller.state not in ("running", "starting"):
            return
        self._run_worker(self._restart_worker)

    def _run_worker(self, target) -> None:
        """Start/stop must never block the UI thread; _busy gates the buttons
        until the worker finishes (the refresh timer clears it)."""
        self._busy = True
        self._refresh_buttons()
        threading.Thread(target=self._guarded(target), daemon=True).start()

    def _guarded(self, target):
        def run() -> None:
            try:
                target()
            finally:
                self._busy = False
        return run

    def _restart_worker(self) -> None:
        self.controller.stop()
        self.controller.start()

    def _toggle_server(self) -> None:
        if self._busy:
            return
        if self.controller.state in ("running", "starting"):
            self._run_worker(self.controller.stop)
        else:
            self._run_worker(self.controller.start)

    def _show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit(self) -> None:
        self._timer.stop()
        self.tray.hide()
        # The desk gets its windows back FIRST — before anything that can
        # block. controller.stop() joins the server thread for up to 10 s, and
        # a 2x2 placement in flight can burn every one of them; the owner must
        # not be left with windows nailed above his desk because a quit was
        # slow (owner decree 2026-08-05).
        self.controller.release_windows()
        self.controller.stop()
        QGuiApplication.instance().quit()

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

    # -- updates -----------------------------------------------------------

    def _check_updates(self) -> None:
        """Worker: ask GitHub whether a newer release exists. Only sets the
        attribute — the refresh timer shows the button on the UI thread.

        THIS RAN ONCE PER START UNTIL 2026-08-07, and that one word cost the
        owner more than any bug in this repo. Proven from his own machine the
        morning he lost his temper:

            installed exe 0.0.089, running since 2026-08-06 19:49:58
            v0.0.090 published                   2026-08-06 20:06

        He had been testing — and reporting as broken — a build published
        BEFORE the fix he was testing for, for a full day, because the app he
        leaves running for days had asked GitHub exactly once, seventeen
        minutes too early. Every round after that re-diagnosed a bug that was
        already fixed and released. A desktop app that only looks for its own
        update at startup is, for this owner, an app that never updates.
        """
        self._update = updates.check()
        if self._update:
            self._update_state = "found"

    def _recheck_updates(self) -> None:
        """The periodic re-check. Never disturbs an update already in flight
        (found / downloading / ready / launched) — only a state of None can
        still learn something new, and re-arming a button he is mid-way
        through installing would be its own bug."""
        if self._update_state is not None:
            return
        threading.Thread(target=self._check_updates, daemon=True).start()

    def _install_update(self) -> None:
        upd = self._update
        if not upd or self._update_state not in ("found", "failed"):
            return
        if not upd.installer_url:
            webbrowser.open(upd.page_url)  # release without an exe asset
            return
        self._update_state = "downloading"
        self._update_error = None    # a retry re-downloads; last time's reason goes
        self._update_progress = None  # a retry starts its bar from empty, not the last try's %
        self._refresh_update_button()
        threading.Thread(target=self._download_update, args=(upd,), daemon=True).start()

    def _download_update(self, upd) -> None:
        """Worker: fetch the installer to %TEMP%; the refresh timer launches
        it (Qt work stays on the UI thread). `updates.download` does the
        actual streaming (chunked, with a socket timeout — urlretrieve has
        none, and a mid-transfer stall would leave the button on
        "Downloading…" forever with no retry) and reports (received, total)
        bytes after every chunk — `total` is None whenever the response gave
        no Content-Length, which `_show_progress` reads as "show the
        indeterminate bar, never a frozen number" (owner decree 2026-08-10,
        task 207)."""
        def report(received: int, total: int | None) -> None:
            self._update_progress = (received, total)

        try:
            path = Path(tempfile.gettempdir()) / f"VibeCoder_Setup_v{upd.version}.exe"
            updates.download(upd.installer_url, path, on_progress=report)
        except Exception as e:
            logger.error("Update download failed: %s", e)
            self._update_state = "failed"
            self._update_progress = None
            return
        self._update_path = path
        self._update_state = "ready"
        self._update_progress = None

    def _begin_handover(self) -> None:
        """The downloaded installer is on disk — hand this PC over to it.

        THE WHOLE POINT (owner report 2026-08-07): he installs from the PHONE,
        through the very session the install is about to end. *"čim uđem u
        instalaciju on će meni ugasiti Vibe Coder i više neću moći da
        komandujem odavde."* So from the tap on this button there is nothing
        left for anyone to click — [update_handover] verifies the file, tells
        the phone, arms the script that will install and restart us, and only
        then do we go. This window keeps its manual path exactly as it was
        for the case the handover cannot run unattended (a dev checkout with
        no elevation): the installer is launched visibly instead.
        """
        action, text = update_handover.begin(
            self.controller, self._update_path, self._update.version,
            self._update.size)
        if action == "stop":
            # The REASON goes on the button, and it survives the next refresh
            # tick — `_update_error`, not a setText the 1 s timer overwrites
            # one second later with "Update download failed" (which would be a
            # lie: the download finished, it was the FILE that was wrong).
            self._update_error = text
            self._update_state = "failed"
            self._refresh_update_button()
            return
        if action == "manual":
            # os.startfile = ShellExecute, which raises the UAC prompt the
            # installer's admin manifest requires — Popen/CreateProcess from
            # an unelevated app fails with WinError 740 and would wedge the
            # whole flow. "launched" only after the call succeeds.
            try:
                os.startfile(str(self._update_path))
            except OSError as e:
                logger.error("Installer launch failed: %s", e)
                self._update_error = "Update launch failed — retry"
                self._update_state = "failed"
                self._refresh_update_button()
                return
        # THE LATCH CLOSES FIRST (owner 2026-08-09, the handover fork): this
        # line used to sit BELOW processEvents(), so a pending 1 s refresh
        # tick re-entered _refresh_update_button while the state still said
        # "ready" and armed ANOTHER handover — the arming lock now refuses
        # that second arm, but the late latch was the re-entrancy ROOT, and
        # a root left standing invites the next variant.
        self._update_state = "launched"
        # SAY IT BEFORE WE GO (owner 2026-08-09: "aplikacija je pukla kad sam
        # stisnuo download — krenuo je da radi downloading a onda je izašao i
        # podigao ponovo aplikaciju; je l' to zamisao?"). It IS the intention,
        # and that is exactly why it must be announced: from his side a window
        # that vanishes mid-action is a crash, and being right about the design
        # does not make the experience honest.
        #
        # Painted with processEvents BEFORE the quit — a setText alone would
        # never reach the screen, because the very next line ends the app.
        self.update_btn.setText(UPDATE_HANDOVER_TEXT)
        self.update_btn.setEnabled(False)
        # THE BAR (owner decree 2026-08-10, task 207 — replacing the
        # 2026-08-09 placeholder marker): the actual install runs in the
        # handover SCRIPT, after this process is gone (update_handover.py) —
        # there is nothing left here to measure, so `_show_progress(None)`
        # is the honest indeterminate animation, never a frozen ellipsis
        # claiming to know a progress this window cannot see.
        self._show_progress(None)
        QApplication.processEvents()
        self._quit()  # free our files; the handover takes over from here

    def _show_progress(self, progress: tuple[int, int | None] | None) -> None:
        """Drive the bar under the update button (owner decree 2026-08-10,
        task 207 — "ne znam da li je blokirao ili radi"). `progress` is
        (received, total) with `total` possibly None, or None outright (the
        install hand-over step, which has no bytes to count at all).

        DETERMINATE — a real, advancing % — whenever a total is known;
        INDETERMINATE (Qt's own scrolling-chunk animation, engaged by
        `setRange(0, 0)`) whenever it is not. Never a value frozen mid-way
        and never a percent text pretending to know a number it does not
        have — that is exactly the "three static dots" bug this replaces.
        """
        received, total = progress if progress else (0, None)
        if total:
            self.update_progress.setRange(0, 100)
            self.update_progress.setValue(min(100, int(received * 100 / total)))
            self.update_progress.setTextVisible(True)
        else:
            self.update_progress.setRange(0, 0)
            self.update_progress.setTextVisible(False)
        self.update_progress.show()

    def _refresh_update_button(self) -> None:
        state = self._update_state
        if state in (None, "launched") or self._update is None:
            return
        if state == "ready":
            self._begin_handover()
            return
        if state == "found":
            self.update_btn.setText(f"Update to v{self._update.version} — download && install")
            self.update_btn.setEnabled(True)
            self.update_progress.hide()
        elif state == "downloading":
            self.update_btn.setText("Downloading update…")
            self.update_btn.setEnabled(False)
            self._show_progress(self._update_progress)
        elif state == "failed":
            self.update_btn.setText(self._update_error or UPDATE_FAILED_TEXT)
            self.update_btn.setEnabled(True)
            self.update_progress.hide()
        self.update_btn.show()

    def _refresh_pairing(self) -> None:
        """Re-checks the addresses while running — when the owner signs in to
        Tailscale mid-run, the QR and hints switch to the works-anywhere URL
        WITHOUT a restart (the server listens on all interfaces already)."""
        info = self.controller.info
        if not info:
            return
        urls = pairing.pairing_urls(info.token)
        if urls["qr"] != info.qr_url:
            info.qr_url = urls["qr"]
            info.lan_url = urls["lan"]
            info.tailscale_ip = urls["tailscale_ip"]  # _refresh redraws the QR

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
