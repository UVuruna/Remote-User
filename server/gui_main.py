"""Remote User desktop app entry point — window + tray around the server core.

This is what the installed EXE runs. Order matters exactly as in main.py:
bootstrap first (DPI awareness before any screen-touching import), then Qt,
then the server. `--minimized` starts hidden in the tray (used by the
installer's autostart entry); the server itself always starts on launch.
"""

import sys


def main() -> None:
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
