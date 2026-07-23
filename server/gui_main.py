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

    controller.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
