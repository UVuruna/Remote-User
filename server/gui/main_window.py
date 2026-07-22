"""The desktop window: status, pairing QR, settings, start/stop, tray.

One column of soft-shadowed cards (DESIGN.md bento style, single column at
this size). The window never blocks: server start/stop/restart run on worker
threads and a 1 s timer pulls state from the ServerController. Closing the
window hides to the tray — the server keeps running until Quit.
"""

import logging
import os
import subprocess
import tempfile
import threading
import urllib.request
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget,
)

import pairing
import updates
from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT, SETTINGS, app_version, save_user_settings
from gui.theme import QSS, card_shadow, repolish
from server_core import ServerController

logger = logging.getLogger(__name__)

ASSET_DIR = (BUNDLE_DIR if FROZEN else PROJECT_ROOT) / "assets"

QR_SIZE = 216
REFRESH_MS = 1000
PAIRING_RECHECK_TICKS = 5  # re-check addresses/Tailscale every N refresh ticks

RESOLUTIONS = [("Native (up to 4K)", 3840), ("2560 — QHD", 2560),
               ("1920 — Full HD", 1920), ("1600 — light", 1600)]
BITRATES = [("6 Mbps — slow links", "6M"), ("12 Mbps — default", "12M"),
            ("20 Mbps — max quality", "20M")]
FPS_CHOICES = [("30 fps", 30), ("60 fps", 60)]

PILL_TEXT = {"running": "RUNNING", "starting": "STARTING…",
             "stopped": "STOPPED", "failed": "FAILED"}


class MainWindow(QMainWindow):
    def __init__(self, controller: ServerController):
        super().__init__()
        self.controller = controller
        self._busy = False           # a start/stop/restart worker is running
        self._shown_qr_url = None    # avoid re-rendering the same QR every tick
        self._tray_notice_shown = False
        self._tick = 0               # refresh counter (pairing re-checks are throttled)
        # Update flow — workers only SET these; the refresh timer (UI thread)
        # reads them and touches Qt. States: None → found → downloading →
        # ready (launch installer + quit) / failed (retry).
        self._update = None
        self._update_state = None
        self._update_path = None

        self.setWindowTitle("Remote User")
        self.setStyleSheet(QSS)
        icon = QIcon(str(ASSET_DIR / "logo.svg"))
        self.setWindowIcon(icon)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)

        root.addLayout(self._build_header())
        root.addWidget(self._build_qr_card())
        root.addWidget(self._build_settings_card())
        root.addLayout(self._build_bottom_row())
        root.addWidget(self._build_update_button())
        root.addWidget(self._build_footer())

        self._build_tray(icon)
        self.setFixedWidth(400)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(REFRESH_MS)
        self._refresh()

        threading.Thread(target=self._check_updates, daemon=True).start()

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
        title = QLabel("Remote User")
        title.setObjectName("h1")
        sub = QLabel("Control this PC from your phone")
        sub.setObjectName("caption")
        titles.addWidget(title)
        titles.addWidget(sub)

        self.pill = QLabel(PILL_TEXT["stopped"])
        self.pill.setObjectName("pill")
        self.pill.setProperty("state", "stopped")

        row.addWidget(logo)
        row.addSpacing(10)
        row.addLayout(titles)
        row.addStretch()
        row.addWidget(self.pill)
        return row

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        card_shadow(card)
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(10)
        return card, box

    def _build_qr_card(self) -> QFrame:
        card, box = self._card()

        self.qr_label = QLabel("Server stopped")
        self.qr_label.setObjectName("qr")
        self.qr_label.setFixedSize(QR_SIZE, QR_SIZE)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.qr_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.url_label = QLabel("—")
        self.url_label.setObjectName("url")
        self.url_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.url_label.setWordWrap(True)
        box.addWidget(self.url_label)

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
        return card

    def _build_settings_card(self) -> QFrame:
        card, box = self._card()
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

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

        form.addRow("Monitor", self.monitor_combo)
        form.addRow("Resolution", self.resolution_combo)
        form.addRow("Bitrate", self.bitrate_combo)
        form.addRow("Frame rate", self.fps_combo)
        box.addLayout(form)

        apply_row = QHBoxLayout()
        apply_row.addStretch()
        self.apply_btn = QPushButton("Apply && restart")
        self.apply_btn.clicked.connect(self._apply_settings)
        apply_row.addWidget(self.apply_btn)
        box.addLayout(apply_row)
        return card

    def _build_bottom_row(self) -> QHBoxLayout:
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

    def _build_update_button(self) -> QPushButton:
        """Hidden until the startup check finds a newer release; one click
        downloads the installer, launches it and quits this app (files must
        not be in use while the installer replaces them)."""
        self.update_btn = QPushButton("")
        self.update_btn.setObjectName("primary")
        self.update_btn.clicked.connect(self._install_update)
        self.update_btn.hide()
        return self.update_btn

    def _build_footer(self) -> QLabel:
        footer = QLabel(f"v{app_version()}  ·  closing hides to tray — server keeps running")
        footer.setObjectName("caption")
        footer.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        return footer

    def _build_tray(self, icon: QIcon) -> None:
        self.tray = QSystemTrayIcon(icon, self)
        menu = QMenu()
        open_action = QAction("Open Remote User", menu)
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

    # -- settings ----------------------------------------------------------

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
        changes = {
            "monitor_index": self.monitor_combo.currentData(),
            "h264_max_width": self.resolution_combo.currentData(),
            "h264_bitrate": self.bitrate_combo.currentData(),
            "target_fps": self.fps_combo.currentData(),
        }
        save_user_settings(changes)
        if self.controller.state in ("running", "starting"):
            self._run_worker(self._restart_worker)

    # -- server control ----------------------------------------------------

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
        self.controller.stop()
        QGuiApplication.instance().quit()

    # -- actions -----------------------------------------------------------

    def _copy_link(self) -> None:
        info = self.controller.info
        if info:
            QGuiApplication.clipboard().setText(info.qr_url)
            self.tray.showMessage("Remote User", "Pairing link copied.",
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
        """Worker: one GitHub check per start. Only sets the attribute — the
        refresh timer shows the button on the UI thread."""
        self._update = updates.check()
        if self._update:
            self._update_state = "found"

    def _install_update(self) -> None:
        upd = self._update
        if not upd or self._update_state not in ("found", "failed"):
            return
        if not upd.installer_url:
            webbrowser.open(upd.page_url)  # release without an exe asset
            return
        self._update_state = "downloading"
        self._refresh_update_button()
        threading.Thread(target=self._download_update, args=(upd,), daemon=True).start()

    def _download_update(self, upd) -> None:
        """Worker: fetch the installer to %TEMP%; the refresh timer launches
        it (Qt work stays on the UI thread). Chunked with a socket timeout —
        urlretrieve has none, and a mid-transfer stall (Wi-Fi drop, CDN hang)
        would leave the button on "Downloading…" forever with no retry."""
        try:
            path = Path(tempfile.gettempdir()) / f"RemoteUser_Setup_v{upd.version}.exe"
            with urllib.request.urlopen(upd.installer_url, timeout=30) as response, \
                    open(path, "wb") as out:
                while chunk := response.read(256 * 1024):
                    out.write(chunk)
        except Exception as e:
            logger.error("Update download failed: %s", e)
            self._update_state = "failed"
            return
        self._update_path = path
        self._update_state = "ready"

    def _refresh_update_button(self) -> None:
        state = self._update_state
        if state in (None, "launched") or self._update is None:
            return
        if state == "ready":
            # os.startfile = ShellExecute, which raises the UAC prompt the
            # installer's admin manifest requires — Popen/CreateProcess from
            # this unelevated app fails with WinError 740 and would wedge
            # the whole flow. "launched" only after the call succeeds.
            try:
                os.startfile(str(self._update_path))
            except OSError as e:
                logger.error("Installer launch failed: %s", e)
                self._update_state = "failed"
                self.update_btn.setText("Update launch failed — retry")
                self.update_btn.setEnabled(True)
                self.update_btn.show()
                return
            self._update_state = "launched"
            self._quit()  # free our files; the installer takes over
            return
        if state == "found":
            self.update_btn.setText(f"Update to v{self._update.version} — download && install")
            self.update_btn.setEnabled(True)
        elif state == "downloading":
            self.update_btn.setText("Downloading update…")
            self.update_btn.setEnabled(False)
        elif state == "failed":
            self.update_btn.setText("Update download failed — retry")
            self.update_btn.setEnabled(True)
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
                self.qr_label.setPixmap(pix.scaled(
                    QR_SIZE - 16, QR_SIZE - 16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                self.url_label.setText(info.qr_url)
            # Three guided states — the user follows THIS window, never
            # Tailscale's site (owner principle: no confusing third-party
            # screens; we say exactly what happens next).
            if info.tailscale_ip:
                self.reach_label.setText(
                    "Anywhere-access is ON. First pairing: the phone must be on "
                    "THIS Wi-Fi, then scan the QR once — install, tap Open the "
                    "app, done. After that the app works from anywhere, no QR.")
                self.tailscale_btn.hide()
            elif pairing.tailscale_exe():
                self.reach_label.setText(
                    "One step left for away-from-home use: sign in to Tailscale. "
                    "A browser will open — pick your account and press Connect, "
                    "then come back here; this window continues by itself. "
                    "(Tailscale may ask a few one-time questions — any answers are fine.)")
                self.tailscale_btn.setText("Sign in to Tailscale")
                self.tailscale_btn.show()
            else:
                self.reach_label.setText(
                    "Works on home Wi-Fi now (the phone must be on THIS Wi-Fi "
                    "to scan the QR). For access from anywhere, add Tailscale "
                    "(free, one-time, guided).")
                self.tailscale_btn.setText("Install Tailscale")
                self.tailscale_btn.show()
            mode = "H.264 · " + (info.encoder or "?") if info.mode == "h264" else "JPEG fallback"
            clients = info.stats.clients
            self.tray.setToolTip(f"Remote User — running ({mode}, "
                                 f"{clients} client{'s' if clients != 1 else ''})")
        else:
            self._shown_qr_url = None
            self.qr_label.setPixmap(QPixmap())
            self.qr_label.setText("Server stopped" if state != "failed" else "Server failed")
            self.url_label.setText(self.controller.error or "—")
            self.tray.setToolTip("Remote User — stopped")

        self._refresh_buttons()
        if state == "failed":
            self.reach_label.setText("See the log for details.")

    def _refresh_buttons(self) -> None:
        state = self.controller.state
        running = state in ("running", "starting")
        self.power_btn.setText("Stop server" if running else "Start server")
        self.power_btn.setObjectName("danger" if running else "primary")
        repolish(self.power_btn)
        self.power_btn.setEnabled(not self._busy)
        self.apply_btn.setEnabled(not self._busy)
        self.copy_btn.setEnabled(state == "running")
        self.browser_btn.setEnabled(state == "running")
        self.tray_toggle.setText("Stop server" if running else "Start server")

    # -- window behavior ---------------------------------------------------

    def closeEvent(self, event) -> None:
        """Close = hide to tray (the server keeps running). Quit lives in the
        tray menu."""
        event.ignore()
        self.hide()
        if not self._tray_notice_shown:
            self._tray_notice_shown = True
            self.tray.showMessage(
                "Remote User is still running",
                "The server keeps working in the tray. Right-click the icon to quit.",
                QSystemTrayIcon.MessageIcon.Information, 3000,
            )
