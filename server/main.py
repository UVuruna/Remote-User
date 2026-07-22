"""Remote User CLI entry point — headless server with console pairing (QR in
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
    ServerController(console_pairing=True).run_blocking()


if __name__ == "__main__":
    main()
