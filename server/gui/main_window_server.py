"""SERVER CONTROL: the desktop window's power over the server it wraps.

Split out of `gui/main_window.py` on 2026-08-18 (THE STRUCTURE LAW, VC-R3) as
a MIXIN and not a helper object, deliberately: every method here reaches the
window's own widgets and its `controller`, and handing them a `self` they do
not own would be a second, quieter way to write the same coupling down.

One responsibility: starting, stopping, restarting and QUITTING — including
the rule that outranks every other line in this project when the app goes
down. Nothing we forced on a window may outlive us (project CLAUDE.md), so the
quit path is a funnel every documented exit runs through, and the worker that
does the blocking work never touches a widget.
"""

import logging

from PySide6.QtCore import QTimer

from gui import offthread

logger = logging.getLogger(__name__)


class ServerControl:
    """Start / stop / restart / quit, mixed into `MainWindow`.

    Reads and writes the window's own attributes (`controller`, the status
    labels, the buttons, the tray) — it IS the window, split by subject."""

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
        until the worker finishes (the refresh timer clears it). The thread,
        its exception logging and the always-runs `on_done` are
        [Off-thread](offthread.py)'s — one definition for every background job
        this window has."""
        self._busy = True
        self._refresh_buttons()
        offthread.run(target, on_done=lambda: setattr(self, "_busy", False))

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
        if self._quitting:
            return
        self._quitting = True
        self._timer.stop()
        self.tray.hide()
        # The desk gets its windows back FIRST — before anything that can
        # block. controller.stop() joins the server thread for up to 10 s, and
        # a 2x2 placement in flight can burn every one of them; the owner must
        # not be left with windows nailed above his desk because a quit was
        # slow (owner decree 2026-08-05).
        self.controller.release_windows()
        # …and the stop itself goes to a worker (2026-08-12): those ten seconds
        # used to be ten seconds of a frozen, un-redrawing window sitting on
        # his screen after he had already chosen Quit. Polled from a Qt timer
        # rather than waited on, so the event loop keeps painting; the app
        # leaves the moment the server is really down, or when
        # offthread.QUIT_WAIT_S says a wedged stop has had long enough.
        finished = offthread.stop_server(self.controller)
        self._quit_timer = QTimer(self)
        def poll() -> None:
            if not finished():
                return
            self._quit_timer.stop()
            QGuiApplication.instance().quit()

        self._quit_timer.timeout.connect(poll)
        self._quit_timer.start(100)
