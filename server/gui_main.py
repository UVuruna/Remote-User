"""Remote User desktop app entry point — window + tray around the server core.

This is what the installed EXE runs. Order matters exactly as in main.py:
bootstrap first (DPI awareness before any screen-touching import), then Qt,
then the server. `--minimized` starts hidden in the tray (used by the
installer's autostart entry); the server itself always starts on launch.
"""

import sys


def _selfcheck() -> None:
    """Import the whole app graph and exit — the build's smoke test runs the
    FROZEN exe with `--selfcheck` so a packaging gap (a module that did not get
    bundled, e.g. qrcode) fails the BUILD instead of the user's first launch.
    Exceptions are caught here so PyInstaller's windowed crash dialog can never
    block the automated check; the build reads only the exit code."""
    import traceback
    try:
        from bootstrap import init_process
        init_process()  # same order as main(): DPI/logging before screen imports
        from PySide6.QtWidgets import QApplication
        QApplication(sys.argv)
        from gui.main_window import MainWindow  # noqa: F401  — pulls pairing → qrcode
        from server_core import ServerController  # noqa: F401  — pulls the server stack
    except BaseException:
        try:
            traceback.print_exc()
        except Exception:
            pass
        sys.exit(1)
    print("selfcheck OK")
    sys.exit(0)


def main() -> None:
    if "--selfcheck" in sys.argv:
        _selfcheck()
        return

    from bootstrap import init_process
    init_process()

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Remote User")
    app.setQuitOnLastWindowClosed(False)  # closing the window hides to tray

    from gui.main_window import MainWindow
    from server_core import ServerController

    controller = ServerController(console_pairing=False)
    window = MainWindow(controller)
    if "--minimized" not in sys.argv:
        window.show()

    # NOTHING of ours may outlive this process in the always-on-top band
    # (owner decree 2026-08-05, after finding his Chrome and VSCode nailed
    # above everything twice). Three nets, deliberately overlapping, because
    # each one alone has a hole:
    #   - aboutToQuit  — the ordinary Qt exit (tray Quit, the self-update
    #     relaunch, Windows logging the session off).
    #   - atexit       — anything that ends the interpreter without Qt, an
    #     unhandled exception included.
    #   - the ledger on disk — the paths that run NO code at all (Task
    #     Manager, the installer's taskkill, a power cut) are repaired by the
    #     next start (ServerController.__init__ -> repair_stranded).
    # release_windows() is idempotent, so running all three is the design.
    #
    # Windows' FOREGROUND LOCK (round R2) rides the same three nets and has a
    # fourth of its own: the raised value never reaches the registry, so a
    # reboot already restores it. Released separately from release_windows()
    # because that one also runs on every server stop, and this lock belongs
    # to the process, not to a server run.
    import atexit
    import foreground_lock
    app.aboutToQuit.connect(controller.release_windows)
    app.aboutToQuit.connect(foreground_lock.release)
    atexit.register(controller.release_windows)
    atexit.register(foreground_lock.release)

    controller.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
