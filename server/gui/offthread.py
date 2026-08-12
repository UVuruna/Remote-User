"""The desktop window's blocking work, off the window's thread.

Born 2026-08-12 out of one broken promise: [Main Window](main_window.py)'s own
header says "The window never blocks", and two calls made that false.

  * `pairing.pairing_urls()` — a UDP socket with a 1 s timeout plus the
    Tailscale CLI with a 3 s one, run from the 1 s refresh timer every fifth
    tick for as long as Tailscale is NOT signed in. Up to four frozen seconds,
    recurring, in exactly the state a first-time user sits in while he waits
    for that window to tell him his phone can reach the PC.
  * `ServerController.stop()` — joins the server thread for up to 10 s, and
    the tray's Quit called it inline.

Both are plain "do a slow thing, then let the UI notice" jobs, and the window
already had the pattern for that (the update workers): a daemon thread writes
a plain attribute, and the refresh timer — on the UI thread — reads it and
touches Qt. This module is that pattern given a home, because main_window.py
stands at the 1,000-line wall and the guard refuses to let it grow.

NOTHING HERE MAY TOUCH Qt. Every function in this file runs on a worker
thread; the widgets belong to the thread that made them, and the window's own
timer is what redraws.
"""

import logging
import threading
import time

import pairing

logger = logging.getLogger(__name__)

# How long a quit waits for the server to stop before going anyway. The stop
# itself is bounded (`ServerController.stop` joins for up to 10 s); this is the
# window's own patience on top of it, so a wedged worker can never leave the
# app on screen with no way out.
QUIT_WAIT_S = 12.0


def run(fn, *args, on_done=None) -> threading.Thread:
    """`fn(*args)` on a daemon thread, exceptions logged and never raised into
    a thread nobody joins. `on_done` runs on that same thread, always — it is
    how a caller clears its own busy flag."""
    def worker() -> None:
        try:
            fn(*args)
        except Exception:
            logger.exception("%s failed on a background thread",
                             getattr(fn, "__name__", fn))
        finally:
            if on_done is not None:
                on_done()
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


def refresh_pairing(info) -> None:
    """Re-read this PC's pairing addresses and write them into `info`.

    Blocking — call it through `run`. When the owner signs in to Tailscale
    mid-run the QR and the hints must switch to the works-anywhere URL with no
    restart (the server already listens on all interfaces); the window's
    refresh tick notices the changed URL by itself and redraws the QR.
    """
    urls = pairing.pairing_urls(info.token)
    if urls["qr"] != info.qr_url:
        info.qr_url = urls["qr"]
        info.lan_url = urls["lan"]
        info.tailscale_ip = urls["tailscale_ip"]


def stop_server(controller):
    """Begin `controller.stop()` on a worker; returns `finished()` — true once
    the stop has ended, however it ended, or once QUIT_WAIT_S has passed.

    The caller (the tray's Quit) POLLS that from a Qt timer instead of waiting
    on it, so the window keeps painting through a shutdown that can take ten
    seconds. The deadline lives here rather than at the call site because it is
    part of the same promise: the app must leave even if the stop wedges. The
    desk's windows are released BEFORE this is called — the owner's decree of
    2026-08-05, unchanged: nothing may be left nailed above his desk because a
    quit was slow.
    """
    done = threading.Event()
    give_up_at = time.monotonic() + QUIT_WAIT_S
    run(controller.stop, on_done=done.set)
    return lambda: done.is_set() or time.monotonic() >= give_up_at
