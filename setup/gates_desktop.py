"""THE DESKTOP-WINDOW GATES — what the PC's OWN Qt windows must survive.

SPLIT OUT OF setup/gates.py on 2026-08-16 (THE STRUCTURE LAW). gates.py had
reached exactly 1,000 lines and the split was made by RESPONSIBILITY, not by
where the line count happened to fall: almost everything left there proves
something about the WIRE and the PHONE — a protocol message answers, the page
draws, the encoder crops, the shell reports. These four prove something about
the desktop application's own windows, which the owner reaches with a mouse
and which have their own toolkit (Qt), their own failure modes (a widget with
no parent is a WINDOW; a job that lands under the wrong label) and their own
rate of change.

`step` and `run` are PASSED IN, exactly as gates.py takes them from build.py
and for the same reason: build.py owns the console's voice and the subprocess
policy, and a module that imported them back would be a cycle for no gain.
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


def desktop_gates(step, run) -> None:
    # OWNER REQUEST 2026-08-13: the Traffic window's "this session X MB"
    # line gains session length, MB/h, and WHICH device(s) sent it — named
    # where a name was ever learned, else identified by resolution — with
    # the chart's line coloured differently per device. The identity must
    # be stable across a reconnect and across a server restart (persisted,
    # `layout_history.py`'s own precedent), and an older CSV row with no
    # `device` column must keep reading — the long-term record cannot break
    # on the day this shipped.
    step("0b2/6  TRAFFIC DEVICES GATE — a stable per-device identity, "
         "session length/rate, and the old-CSV-still-reads promise "
         "(tests/test_traffic_devices.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_traffic_devices.py")])

    # OWNER REPORT 2026-08-14: the Traffic window's two long spans "end up
    # either in an endless loop or in some very long loading loop", and both
    # drew the SAME four hours — his screenshots have "All (from file)" and
    # "Since start" reading 11:48 -> 15:42. Measured: his file holds 2.5 days
    # and reads whole in 0.23 s, so neither the file nor the reader was the
    # problem — the window's job bookkeeping was. A span switch made while a
    # read was in flight started no read of its own, and the older read's
    # data was then stamped with the span selected when it arrived. This gate
    # is fail-closed because the failure is invisible from the code: both
    # spans look right, and only the x-axis says otherwise.
    step("0b15/6  TRAFFIC SPANS GATE — one span's data may never appear under "
         "another span's label, and the loading overlay may never outlive the "
         "work (tests/test_traffic_spans.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_traffic_spans.py")])

    # OWNER ROUND 2026-08-15 (T103-T107): the graph gained min/max buttons, a
    # zoom axis, a drag rectangle that zooms to what he drew, and a hover card
    # that states the encoder's settings per second. Fail-closed and driven
    # end-to-end through the real widget's mouse handlers — the drag is the
    # feature, and a green pure-arithmetic check says nothing about what the
    # widget does with a mouse press.
    step("0b20/6  TRAFFIC ZOOM GATE — the graph zooms to what he drew, and "
         "every point says what the encoder was doing (tests/test_traffic_zoom.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_traffic_zoom.py")])

    # OWNER REPORT 2026-08-16, "FLASH sa otvaranjem nekog prozora u sredini": a
    # parentless QWidget is a real top-level window, so a teardown that
    # unparents a still-VISIBLE child hands Windows a native window at the
    # centre of his screen for the span until the event loop deletes it. A
    # SWEEP over every Qt module rather than a check on the one call site he
    # reported, for the reason constraint 28 names — a rule kept beside one
    # call is read only by somebody already standing there.
    step("0b21/6  WIDGET ORPHAN GATE — nothing we unparent is still visible "
         "when it becomes a window (tests/test_widget_orphan.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_widget_orphan.py")])
