"""THE USE-LOG GATES — everything that proves the app can account for itself.

Split out of `setup/gates.py` by RESPONSIBILITY on 2026-08-17, the third time
that file crossed THE STRUCTURE LAW's wall and the third time the answer was a
module rather than a ratchet (`gates_picture.py` 2026-08-16 — the gates that
prove he SEES something; `gates_desktop.py` the same day — the gates that prove
the PC's own Qt windows). What is left in `gates.py` proves something about the
wire and the phone; these five prove something about the RECORD the app keeps
of its own run — that it is opened, written, rolled, closed, shipped and
summed, and that a monitor changing under it is reported rather than guessed at.

They are one family and they fail as one: a log that is never opened, a log
whose footer is never written and a log deleted before its transfer confirmed
are the same defect wearing three faces — the run cannot answer for itself
afterwards, which is exactly when anybody looks.

The suite is fail-closed: `run` raises on a non-zero exit, so a red gate stops
the build before anything ships.
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


def log_gates(step, run) -> None:
    """Run the five use-log gates in order, oldest wiring first."""
    # T113, 2026-08-17: the four modules of the use log — `session_log.py`,
    # `log_shipper.py`, `log_summary.py` and `display_watch.py` — are WIRED,
    # not merely written. Each has its own gate proving it works; this one
    # proves it is CALLED, which is the actions.json lesson of 2026-08-07
    # restated (a pure module nobody calls is a feature that does not exist —
    # every one of those four gates would stay green while the app never
    # wrote a line). It pins the load-bearing ORDER at start (repair and
    # sweep BEFORE the new file exists — a run that ended without us is
    # recognised ONLY by its missing footer, so opening first would ship a
    # log still being written), the close being idempotent across the four
    # exits that all reach `release_windows()`, a display change really
    # reaching BOTH the Settings window's monitor list and capture's DXGI
    # re-enumeration (constraint 30: dxcam enumerates its outputs once at
    # import, so a monitor plugged in mid-run was invisible for the life of
    # the process), the captured monitor vanishing really moving the picture
    # instead of waiting out the stall ladder, and the event call sites —
    # `session.connect` on auth with the link MEASURED off the Host header,
    # `session.leave` with its caller's reason, and ONE `notice.*` record at
    # `notify.deliver`'s single choke. No real dxcam and no real desktop
    # (`sys.modules["dxcam"]` replaced before `capture` imports it); each
    # check proven against its own planted defect.
    step("0b24/6  LOG WIRING GATE — the use log is opened after the previous "
         "run is repaired, closed exactly once however we exit, and a display "
         "change reaches capture and the GUI (tests/test_log_wiring.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_log_wiring.py")])

    # T113, 2026-08-17, the same use-log family as 0b24 above: that gate
    # proves the four modules are CALLED, these four prove each one WORKS on
    # its own. Wired the same night they were written — `test_phone_chrome.py`
    # sat in neither gates.py nor build.py and a real portrait-layout defect
    # shipped over four releases before anyone noticed (see the T89 entry in the
    # round's ledger); a gate not in the build is not enforcement.
    step("0b25/6  SESSION LOG GATE — the header carries only what cannot "
         "change while the process lives, a record is counted under both its "
         "kind and its group, the file rolls at the day boundary and the "
         "byte ceiling, close writes exactly one footer, an unclosed file is "
         "told apart from a closed one by its TAIL alone, repair invents no "
         "end time and skips the file we just opened, and the log is a "
         "silent no-op whether it is switched off or its disk stops "
         "answering (tests/test_session_log.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_session_log.py")])

    step("0b26/6  LOG SHIPPER GATE — a file is never deleted before its "
         "transfer is confirmed, and every non-happy path (bad destination, "
         "unreachable disk, debug mode, empty target, a URL target, a worker "
         "that cannot start) leaves the local file exactly where it was "
         "(tests/test_log_shipper.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_log_shipper.py")])

    step("0b27/6  LOG SUMMARY GATE — the span/total arithmetic over a "
         "session_log.py file, including the honest edge cases its own "
         "docstring names, and the dedupe proven at the WRITER's own "
         "boundary rather than only from hand-built JSONL (tests/test_log_summary.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_log_summary.py")])

    step("0b28/6  DISPLAY WATCH GATE — a monitor change is reported, never "
         "guessed at, without ever touching a real monitor or opening a real "
         "window (tests/test_display_watch.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_display_watch.py")])
