"""Vibe Coder CLI entry point — headless server with console pairing (QR in
the terminal + image viewer). The desktop app entry point is gui_main.py; both
share the same bootstrap and server core.

Order matters: bootstrap.init_process() declares DPI awareness before any
screen/GPU-touching import runs (root CLAUDE constraint), which is why
server_core is imported inside main() and never at module level.
"""


def main() -> None:
    from bootstrap import init_process
    init_process()

    from server_core import ServerController
    controller = ServerController(console_pairing=True)

    # A console run ends in ways Python never hears about: closing the console
    # window, a logoff, a shutdown — all of them CTRL_* console events, none of
    # them SIGINT. Any window this run raised would simply stay always-on-top
    # (owner decree 2026-08-05: nothing of ours outlives us up there). Ctrl+C
    # is already covered by uvicorn's own handler; this catches the rest, and
    # the handler stays tiny because Windows gives it only seconds.
    import atexit
    import ctypes

    import foreground_lock
    atexit.register(controller.release_windows)
    atexit.register(foreground_lock.release)   # round R2 — same discipline
    handler_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

    def _console_event(_event: int) -> bool:
        controller.release_windows()
        foreground_lock.release()
        return False  # let the default handler end the process

    _keep_alive = handler_type(_console_event)   # must outlive the call
    ctypes.windll.kernel32.SetConsoleCtrlHandler(_keep_alive, True)

    controller.run_blocking()


if __name__ == "__main__":
    main()
