"""Vibe Coder desktop app entry point — window + tray around the server core.

This is what the installed EXE runs. Order matters exactly as in main.py:
bootstrap first (DPI awareness before any screen-touching import), then Qt,
then the server. `--minimized` starts hidden in the tray (used by the
installer's autostart entry); the server itself always starts on launch.

ONE INSTANCE PER PC (owner 2026-08-09). The handover fork of that night —
"instalirao mi je preko 20 aplikacija" — multiplied  # lang-ok: owner quote
because every extra VibeCoder.exe the racing handover scripts started simply
LIVED: each one checked GitHub within seconds, each found one of that night's
six releases newer than itself, and each could arm an installer of its own.
A named Win32 mutex collapses the swarm to one: whoever claims the name runs,
everybody else writes one log line and leaves before touching the screen or
the port. Scoped to THIS entry point on purpose — the headless dev main.py
stays unguarded (a leftover dev server is its own, separate story).
"""

import logging
import sys

MUTEX_NAME = "VibeCoderGuiSingleton"

# The claimed mutex handle, held for the WHOLE process on purpose and never
# closed by us: the OS frees a named mutex the instant its holder dies,
# however it dies — which is exactly the lifetime a single-instance claim
# must have. No stale state is possible, so no repair path exists.
_singleton_handle = None


def _claim_gui_singleton() -> bool:
    """True = this process owns the name and may run; False = another packaged
    GUI instance already holds it.

    A named mutex, not a pid file or a port probe: it cannot go stale (the OS
    releases it on ANY death, Task Manager and power cuts included), and the
    claim is atomic — two instances racing CreateMutexW cannot both win.
    ERROR_ALREADY_EXISTS is the ordinary "someone is running"; a NULL handle
    with ERROR_ACCESS_DENIED reads the same way (an elevated instance's mutex
    refuses a non-elevated opener, but its existence IS the answer). Any other
    failure lets the app run — the guard must never be the thing that stops
    the one instance the owner double-clicked.
    """
    global _singleton_handle
    import ctypes
    ERROR_ALREADY_EXISTS, ERROR_ACCESS_DENIED = 183, 5
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                          ctypes.c_wchar_p]
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    except (AttributeError, OSError):  # not Windows — nothing to claim
        return True
    err = ctypes.get_last_error()
    if not handle:
        return err != ERROR_ACCESS_DENIED
    _singleton_handle = handle
    return err != ERROR_ALREADY_EXISTS


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

    # A second instance leaves NOW — after logging exists (so the one line is
    # written where the owner's update.log lives), before Qt draws anything
    # and before ServerController can fight the first instance for the port.
    # `--selfcheck` above deliberately skips this: the build's smoke test must
    # pass on a dev PC whose real app is running.
    if not _claim_gui_singleton():
        logging.getLogger(__name__).warning(
            "Vibe Coder is already running — this second instance exits "
            "(single-instance guard, owner 2026-08-09)")
        return

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Vibe Coder")
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
