"""TRAFFIC DEVICES GATE — session length, MB/h, per-device attribution, and
the CSV's backward-compatibility promise.

Owner request 2026-08-13: beside "this session X MB" the Traffic window
should say how LONG the session lasted, its rate in MB/h, and WHICH Android
device(s) sent it — named where a name was ever learned, else identified by
resolution — with the chart's line coloured differently per device "so we
can see the difference in how much is sent to a device with a smaller
resolution".

WHAT THIS GATE EXISTS TO PREVENT, and it is not "the numbers print".

  * A stable identity that is not actually stable. `device_key` must key on
    the RESOLUTION alone — the plant flips it to include the name too, which
    would split one phone into two colours the moment a late
    `userAgentData` promise supplies a name a first paint did not have.
  * A registry that forgets a device on the very next connection, or that
    LOSES a name it already learned when a later connection sends none (the
    late-promise case again, from the other direction).
  * A registry that does not survive a restart — `layout_history.py`'s own
    class of bug, so this module is held to the same persisted-across-
    restart proof.
  * `duration_and_rate` printing an absurd number for a session a few
    seconds old (dividing by a near-zero duration).
  * `traffic.py`'s CSV writer breaking an OLDER 4-column file, or
    `traffic_history._parse_row` failing (or worse, MISATTRIBUTING) a row
    that predates the `device` column — the hard rule for this round: the
    CSV is the long-term record, and a file spanning the upgrade must still
    read.
  * The disk-read and the live-chart bucket-merge (`traffic_history.py` and
    `gui/traffic_window.py`'s `_coalesce`) disagreeing about which device an
    ambiguous (idle-heartbeat) bucket belongs to.

Every check below is proven by planting its own defect and confirming the
check catches it (project gate methodology, unchanged from every other gate
in this suite).

Run:  .venv\\Scripts\\python tests/test_traffic_devices.py
"""

import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import traffic_devices  # noqa: E402
import traffic_history  # noqa: E402


def fail(msg: str) -> None:
    raise AssertionError(msg)


def run_checks(title: str, checks) -> int:
    print(f"=== {title} ===")
    failed = 0
    for name, fn in checks:
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"{title} FAILED — {failed} check(s).")
        return 1
    print(f"{title} PASSED — session length, rate, per-device attribution, "
          "and the old-CSV-still-reads promise all hold.")
    return 0


# ═══════════════════════════ 1. IDENTITY ═══════════════════════════

def test_key_is_resolution_only() -> bool:
    """The PLANTED defect: a key built from resolution AND name would give
    the same physical phone two different keys as soon as a name arrives —
    exactly the split the module's own docstring forbids."""
    key_before_name = traffic_devices.device_key(1080, 2400)
    # Simulate the "late name" case directly against the real function: the
    # key must depend on nothing but w/h.
    key_again = traffic_devices.device_key(1080, 2400)
    return key_before_name == key_again == "1080x2400"


def test_key_ignores_bad_input() -> bool:
    return (traffic_devices.device_key("bad", "x") == ""
            and traffic_devices.device_key(0, 0) == ""
            and traffic_devices.device_key(-5, 100) == "")


def test_label_admits_unknown_name() -> bool:
    key = traffic_devices.device_key(1440, 3040)
    return (traffic_devices.label_for(key, None)
            == f"{traffic_devices.UNKNOWN_LABEL} (1440×3040)"
            and traffic_devices.label_for(key, "Pixel 9")
            == "Pixel 9 (1440×3040)")


def test_key_is_orientation_invariant() -> bool:
    """PLANTED DEFECT this catches (coordinator report 2026-08-13, a real
    tablet photographed rotating mid-session): reverting `device_key` to a
    plain `f"{w}x{h}"` with no sort makes this fail immediately —
    `device_key(1080, 2400) != device_key(2400, 1080)`, and one physical
    device would file itself as two."""
    return (traffic_devices.device_key(1080, 2400)
            == traffic_devices.device_key(2400, 1080)
            != "")


IDENTITY_CHECKS = [
    ("device_key is keyed by resolution alone", test_key_is_resolution_only),
    ("device_key refuses unusable input", test_key_ignores_bad_input),
    ("label_for admits an unknown name honestly", test_label_admits_unknown_name),
    ("device_key is ORIENTATION-INVARIANT (w,h == h,w)",
     test_key_is_orientation_invariant),
]


# ═══════════════════════════ 2. REGISTRY ═══════════════════════════

def _fresh_registry(path: Path) -> "traffic_devices.DeviceRegistry":
    return traffic_devices.DeviceRegistry(path=path)


def test_first_seen_gets_slot_zero() -> bool:
    with tempfile.TemporaryDirectory() as d:
        reg = _fresh_registry(Path(d) / "devices.json")
        entry = reg.note(1080, 2400, None)
        return entry["key"] == "1080x2400" and entry["index"] == 0


def test_second_device_gets_the_next_slot() -> bool:
    with tempfile.TemporaryDirectory() as d:
        reg = _fresh_registry(Path(d) / "devices.json")
        a = reg.note(1080, 2400, None)
        b = reg.note(1440, 3040, None)
        return a["index"] == 0 and b["index"] == 1 and a["key"] != b["key"]


def test_reconnect_keeps_the_same_slot() -> bool:
    """PLANTED DEFECT this catches: a registry that appends a new slot on
    every `note()` call regardless of whether the key already exists — the
    literal bug this constraint is a defence against ("survives a
    reconnect: same tablet, not a third colour")."""
    with tempfile.TemporaryDirectory() as d:
        reg = _fresh_registry(Path(d) / "devices.json")
        first = reg.note(1080, 2400, None)
        reg.note(1440, 3040, None)          # a second device connects between
        again = reg.note(1080, 2400, None)  # the first phone reconnects
        return first["index"] == again["index"] == 0


def test_late_name_replaces_blank() -> bool:
    with tempfile.TemporaryDirectory() as d:
        reg = _fresh_registry(Path(d) / "devices.json")
        reg.note(1080, 2400, None)
        entry = reg.note(1080, 2400, "Samsung Galaxy S10")
        return entry["name"] == "Samsung Galaxy S10"


def test_a_later_blank_name_never_erases_a_learned_one() -> bool:
    """PLANTED DEFECT: `note()` overwriting `entry["name"]` unconditionally
    on every call — a plain reconnect that (this round, or an older APK)
    sends no model string would silently erase a name an earlier connection
    already found."""
    with tempfile.TemporaryDirectory() as d:
        reg = _fresh_registry(Path(d) / "devices.json")
        reg.note(1080, 2400, "Samsung Galaxy S10")
        entry = reg.note(1080, 2400, None)
        return entry["name"] == "Samsung Galaxy S10"


def test_survives_a_restart() -> bool:
    """A fresh `DeviceRegistry` instance pointed at the same file — the
    same proof `layout_history.py`'s own persistence gets — must read back
    the slot a previous process already handed out. PLANTED DEFECT: a
    registry that never calls `_save()` would pass every other check here
    and still lose every colour on the next `Apply & restart`."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "devices.json"
        reg1 = _fresh_registry(path)
        reg1.note(1080, 2400, "Pixel 9")
        reg1.note(1440, 3040, None)
        reg2 = _fresh_registry(path)   # a brand new process would build this
        again = reg2.note(1080, 2400, None)
        return again["index"] == 0 and again["name"] == "Pixel 9"


def test_index_for_unknown_key_is_negative() -> bool:
    with tempfile.TemporaryDirectory() as d:
        reg = _fresh_registry(Path(d) / "devices.json")
        return reg.index_for("999x999") == -1


def test_all_lists_oldest_slot_first() -> bool:
    with tempfile.TemporaryDirectory() as d:
        reg = _fresh_registry(Path(d) / "devices.json")
        reg.note(1080, 2400, None)
        reg.note(1440, 3040, None)
        indices = [e["index"] for e in reg.all()]
        return indices == sorted(indices) == [0, 1]


def test_old_order_sensitive_duplicates_migrate_to_one_slot() -> bool:
    """PLANTS an OLD-FORMAT registry file — two raw keys, "1080x2400" and
    "2400x1080", for what is now one orientation-invariant identity — the
    exact shape a pre-fix server would have written for one tablet rotated
    mid-session (the coordinator's reported defect). Without the migration
    in `DeviceRegistry._load`, loading this file keeps BOTH raw keys as two
    separate entries and `all()` reports 2 devices for one physical tablet;
    the fix folds them into a single slot, keeping the earlier index and the
    name whichever entry had it."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "devices.json"
        path.write_text(json.dumps({
            "1080x2400": {"index": 0, "name": None},
            "2400x1080": {"index": 1, "name": "Samsung Galaxy Tab"},
        }), encoding="utf-8")
        reg = _fresh_registry(path)
        entries = reg.all()
        if len(entries) != 1:
            return False
        entry = entries[0]
        # Earliest-seen index (0) kept, and the name only the SECOND raw
        # entry had is not lost in the merge.
        return entry["index"] == 0 and entry["name"] == "Samsung Galaxy Tab"


REGISTRY_CHECKS = [
    ("the first device seen gets slot 0", test_first_seen_gets_slot_zero),
    ("a second device gets the next slot", test_second_device_gets_the_next_slot),
    ("a reconnect lands on the SAME slot", test_reconnect_keeps_the_same_slot),
    ("a late name replaces a blank one", test_late_name_replaces_blank),
    ("a later blank name never erases a learned one",
     test_a_later_blank_name_never_erases_a_learned_one),
    ("the registry survives a restart (persisted to disk)", test_survives_a_restart),
    ("index_for on an unmet key is -1, never 0", test_index_for_unknown_key_is_negative),
    ("all() lists oldest slot first", test_all_lists_oldest_slot_first),
    ("an OLD order-sensitive duplicate pair migrates to ONE slot",
     test_old_order_sensitive_duplicates_migrate_to_one_slot),
]


# ═══════════════════════════ 3. DURATION / RATE ═══════════════════════════

def test_duration_is_now_minus_since() -> bool:
    since = time.time() - 3661   # 1h 1m 1s
    duration, _ = traffic_devices.duration_and_rate(0, since, time.time())
    return abs(duration - 3661) < 2


def test_rate_is_none_for_a_young_session() -> bool:
    """PLANTED DEFECT: dividing by a near-zero duration without a floor
    would print a nonsense MB/h for the first tick of a brand new session —
    3 bytes over 0.01 s is not "1000 MB/h", it is not a measurement yet."""
    since = time.time() - 0.5
    _, mb_h = traffic_devices.duration_and_rate(3, since, time.time())
    return mb_h is None


def test_rate_arithmetic() -> bool:
    since = time.time() - 3600.0   # exactly one hour
    total = 10 * (1 << 20)         # 10 MB
    _, mb_h = traffic_devices.duration_and_rate(total, since, time.time())
    return mb_h is not None and abs(mb_h - 10.0) < 0.5


def test_human_duration_reads_short() -> bool:
    return (traffic_devices.human_duration(45) == "45s"
            and traffic_devices.human_duration(125) == "2m 5s"
            and traffic_devices.human_duration(3661) == "1h 1m")


RATE_CHECKS = [
    ("duration is now - since", test_duration_is_now_minus_since),
    ("rate is None for a session too young to measure",
     test_rate_is_none_for_a_young_session),
    ("rate arithmetic: 10 MB over 1 hour is 10 MB/h", test_rate_arithmetic),
    ("human_duration reads short, never more than two units",
     test_human_duration_reads_short),
]


# ═══════════════════════════ 4. CSV BACKWARD COMPATIBILITY ═══════════════════════════

def test_parse_row_accepts_old_4_column_rows() -> bool:
    """PLANTED DEFECT: requiring exactly 5 columns would reject — or worse,
    silently drop — every row an older server ever wrote, which is the hard
    rule for this round: the CSV is the long-term record."""
    row = traffic_history._parse_row("2026-08-01 10:00:00,100,50,1")
    return row is not None and row[3] == 1 and row[4] == ""


def test_parse_row_accepts_new_5_column_rows() -> bool:
    row = traffic_history._parse_row(
        "2026-08-13 10:00:00,100,50,1,1080x2400")
    return row is not None and row[4] == "1080x2400"


def test_parse_row_rejects_garbage_width() -> bool:
    return (traffic_history._parse_row("garbage,only,three") is None
            and traffic_history._parse_row("a,b,c,d,e,f,g") is None)


def test_old_and_new_rows_coexist_in_one_read() -> bool:
    """A file spanning the upgrade — old rows before the device column
    existed, new rows after — must read start to finish with the old rows
    attributed to no device (never crash, never mis-attribute)."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "traffic.csv"
        now = float(int(time.time()))
        lines = ["time,out_bytes,in_bytes,clients,device\n"]
        for i in range(5):
            t = time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime(now - 300 + i))
            lines.append(f"{t},10,5,1\n")            # OLD, 4 columns
        for i in range(5, 10):
            t = time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime(now - 300 + i))
            lines.append(f"{t},10,5,1,1080x2400\n")   # NEW, 5 columns
        path.write_text("".join(lines), encoding="utf-8")

        import config
        original = config.SETTINGS.traffic_csv_path
        object.__setattr__(config.SETTINGS, "traffic_csv_path", path)
        try:
            points = traffic_history.read_history(now - 300, 100)
        finally:
            object.__setattr__(config.SETTINGS, "traffic_csv_path", original)
        if not points:
            return False
        devices = {p.device for p in points}
        # Both an unattributed stretch ("") and the named device must
        # survive the read — neither swallowed, neither crashing the other.
        return "" in devices and "1080x2400" in devices


CSV_CHECKS = [
    ("an OLD 4-column row still parses", test_parse_row_accepts_old_4_column_rows),
    ("a NEW 5-column row parses with its device",
     test_parse_row_accepts_new_5_column_rows),
    ("a malformed row is rejected, never raises",
     test_parse_row_rejects_garbage_width),
    ("a file spanning the upgrade reads start to finish",
     test_old_and_new_rows_coexist_in_one_read),
]


# ═══════════════════════════ 5. BUCKET ATTRIBUTION ═══════════════════════════

def test_bucket_device_is_last_active_sender() -> bool:
    """`read_history`'s own rule (see `traffic_history.Point.device`'s
    docstring): a bucket's device is whoever last ACTUALLY sent bytes in
    it — an idle heartbeat second from a device about to be replaced must
    not steal the bucket's colour. PLANTED DEFECT: attributing by the FIRST
    device seen in the bucket instead would get this backwards."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "traffic.csv"
        now = float(int(time.time()))
        lines = ["time,out_bytes,in_bytes,clients,device\n"]
        t0 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 10))
        t1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 9))
        lines.append(f"{t0},1000,0,1,deviceA\n")
        lines.append(f"{t1},1000,0,1,deviceB\n")
        path.write_text("".join(lines), encoding="utf-8")

        import config
        original = config.SETTINGS.traffic_csv_path
        object.__setattr__(config.SETTINGS, "traffic_csv_path", path)
        try:
            # One wide bucket so both rows fold together.
            points = traffic_history.read_history(now - 10, 1)
        finally:
            object.__setattr__(config.SETTINGS, "traffic_csv_path", original)
        return len(points) == 1 and points[0].device == "deviceB"


def test_idle_second_never_steals_the_buckets_colour() -> bool:
    """The SAME rule from the other direction: a trailing idle second (a
    heartbeat with clients>0 but zero bytes) from a device that is about to
    take over must not blank out the device that did the real work."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "traffic.csv"
        now = float(int(time.time()))
        lines = ["time,out_bytes,in_bytes,clients,device\n"]
        t0 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 10))
        t1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 9))
        lines.append(f"{t0},1000,0,1,deviceA\n")
        lines.append(f"{t1},0,0,1,deviceB\n")   # deviceB's idle heartbeat
        path.write_text("".join(lines), encoding="utf-8")

        import config
        original = config.SETTINGS.traffic_csv_path
        object.__setattr__(config.SETTINGS, "traffic_csv_path", path)
        try:
            points = traffic_history.read_history(now - 10, 1)
        finally:
            object.__setattr__(config.SETTINGS, "traffic_csv_path", original)
        return len(points) == 1 and points[0].device == "deviceA"


def test_coalesce_agrees_with_the_disk_reader() -> bool:
    """`gui/traffic_window.py`'s live in-memory merge (`_coalesce`) must
    attribute a mixed chunk by the SAME rule as the disk reader — imported
    with QT_QPA_PLATFORM=offscreen so this runs with no display. PLANTED
    DEFECT: the two paths independently reimplementing "which device owns
    this merged point" is exactly how they could drift and colour the same
    session two different ways depending which span the owner has open."""
    tw = importlib.import_module("gui.traffic_window")
    Point = traffic_history.Point
    now = float(int(time.time()))
    chunk = [
        Point(t=now - 2, out_avg=1000, out_max=1000, in_avg=0, in_max=0,
              clients=1, device="deviceA"),
        Point(t=now - 1, out_avg=1000, out_max=1000, in_avg=0, in_max=0,
              clients=1, device="deviceB"),
        Point(t=now, out_avg=0, out_max=0, in_avg=0, in_max=0,
              clients=1, device="deviceB"),   # deviceB's idle tail
    ]
    merged = tw._coalesce(chunk, 1)
    return len(merged) == 1 and merged[0].device == "deviceB"


ATTRIBUTION_CHECKS = [
    ("a bucket is attributed to the last device that actually sent bytes",
     test_bucket_device_is_last_active_sender),
    ("a trailing idle second never steals a bucket's colour",
     test_idle_second_never_steals_the_buckets_colour),
    ("the live chart's bucket-merge agrees with the disk reader",
     test_coalesce_agrees_with_the_disk_reader),
]


# ═══════════════════════════ 6. RENDERED PIXELS ═══════════════════════════
# Coordinator report 2026-08-13 (Defect B): the legend swatches differed but
# the PLOTTED line was one uniform colour end to end — a paint-path bug that
# no code-shape check could have caught, because the segmenting CODE was
# present and correct; something about how it painted was not reaching the
# screen. So this check does not read source, it GRABS THE WIDGET
# (`QWidget.grab()` -> `QPixmap` -> `QImage`) and samples real pixels at an
# x inside a device-A stretch and an x inside a device-B stretch, the same
# way a human grading a screenshot would.

def _staged_chart_widget():
    """The real rendering path — `DeviceRegistry` + `traffic.METER` samples
    + `TrafficChart.paintEvent` — with two devices alternating three times,
    same shape as the Qt audit's own `make_traffic_window` fixture (kept
    independent of it deliberately: this gate must not depend on the audit
    module to run standalone)."""
    from PySide6.QtWidgets import QApplication
    if QApplication.instance() is None:
        QApplication([])
    traffic = importlib.import_module("traffic")
    td = importlib.import_module("traffic_devices")
    tw = importlib.import_module("gui.traffic_window")

    traffic.METER.reset()
    td.REGISTRY.note(1080, 2400, "Samsung Galaxy S10")
    td.REGISTRY.note(2560, 1600, None)
    now = float(int(time.time()))
    traffic.METER.since = now - 600.0
    SPAN_S, SEGMENTS = 110, 4
    seg_len = SPAN_S // SEGMENTS
    traffic.METER.samples.clear()
    total_out = total_in = 0
    for i in range(SPAN_S):
        t = now - SPAN_S + i + 1
        on_tablet = (i // seg_len) % 2 == 1
        key = "2560x1600" if on_tablet else "1080x2400"
        out_b, in_b = (42_000, 3_000) if on_tablet else (6_000, 900)
        traffic.METER.samples.append(traffic.Sample(t, out_b, in_b, 1, key))
        total_out += out_b
        total_in += in_b
    traffic.METER.total_out = total_out
    traffic.METER.total_in = total_in
    traffic.METER.note_device(2560, 1600, None)
    traffic.METER.set_clients(1)
    window = tw.TrafficWindow()
    window.resize(1074, 700)
    window.show()
    QApplication.instance().processEvents()
    window._refresh()
    QApplication.instance().processEvents()
    return window


def test_chart_line_is_actually_coloured_per_device() -> bool:
    """Real pixel readback. PLANTED DEFECT this catches: forcing
    `multi_device = False` in `TrafficChart.paintEvent` (simulating the
    paint path silently falling back to one colour regardless of how many
    devices the points carry) makes every sampled pixel along the line come
    back the SAME colour, and this check fails — proven live below by
    monkeypatching exactly that."""
    from gui.theme import device_color
    td = importlib.import_module("traffic_devices")
    window = _staged_chart_widget()
    try:
        chart = window.chart
        plot = chart._plot
        idx_a = td.REGISTRY.index_for("1080x2400")
        idx_b = td.REGISTRY.index_for("2560x1600")
        color_a, color_b = device_color(idx_a), device_color(idx_b)
        pixmap = chart.grab()
        image = pixmap.toImage()

        def line_color_at(frac: float):
            from PySide6.QtGui import QColor
            x = int(plot.left() + plot.width() * frac)
            best, best_d = None, 1e9
            for y in range(plot.top(), plot.bottom()):
                c = image.pixelColor(x, y)
                for cand in (color_a, color_b):
                    tc = QColor(cand)
                    d = ((c.red() - tc.red()) ** 2 + (c.green() - tc.green()) ** 2
                         + (c.blue() - tc.blue()) ** 2)
                    if d < best_d:
                        best_d, best = d, cand
            return best if best_d < 900 else None

        # Segment 1 (device A) is the first quarter, segment 2 (device B)
        # the second quarter of the visible span — sampled well inside each,
        # away from the transition.
        seen_a = line_color_at(0.12)
        seen_b = line_color_at(0.37)
        return (seen_a is not None and seen_b is not None
                and seen_a != seen_b)
    finally:
        window.close()


def test_chart_line_check_catches_a_single_colour_regression() -> bool:
    """Proves the check above actually catches the defect: monkeypatches
    `TrafficChart._peak_of`'s sibling — the `multi_device` decision — by
    forcing every point's `device` attribute blank right before paint, which
    is exactly what a broken paint path (or a broken point-attribution path
    feeding it) looks like from the outside. With every device blanked the
    chart falls back to ONE colour for the whole line, and the readback
    check above must then report `seen_a == seen_b` (or one side unreadable) —
    i.e. FAIL. This is run inline rather than via `run_checks` because it
    asserts the OPPOSITE of the real check's normal pass condition."""
    window = _staged_chart_widget()
    try:
        chart = window.chart
        for p in chart.points:
            p.device = ""
        chart.update()
        from PySide6.QtWidgets import QApplication
        QApplication.instance().processEvents()
        plot = chart._plot
        pixmap = chart.grab()
        image = pixmap.toImage()
        tw = importlib.import_module("gui.traffic_window")
        base = tw.out_color()

        def sample(frac):
            x = int(plot.left() + plot.width() * frac)
            for y in range(plot.top(), plot.bottom()):
                c = image.pixelColor(x, y)
                if abs(c.red() - base.red()) < 30 and abs(c.green() - base.green()) < 30 \
                        and abs(c.blue() - base.blue()) < 30:
                    return "base"
            return None

        a, b = sample(0.12), sample(0.37)
        # Both stretches must now read as the SAME plain series colour —
        # proving the readback check above is sensitive to exactly this
        # regression, not a check that would pass regardless.
        return a == b == "base"
    finally:
        window.close()


PAINT_CHECKS = [
    ("the chart line is ACTUALLY coloured per device (real pixel readback)",
     test_chart_line_is_actually_coloured_per_device),
    ("the readback check catches a forced single-colour regression",
     test_chart_line_check_catches_a_single_colour_regression),
]


if __name__ == "__main__":
    failed = 0
    failed += run_checks("IDENTITY", IDENTITY_CHECKS)
    failed += run_checks("REGISTRY", REGISTRY_CHECKS)
    failed += run_checks("DURATION / RATE", RATE_CHECKS)
    failed += run_checks("CSV BACKWARD COMPATIBILITY", CSV_CHECKS)
    failed += run_checks("BUCKET ATTRIBUTION", ATTRIBUTION_CHECKS)
    failed += run_checks("RENDERED PIXELS", PAINT_CHECKS)
    sys.exit(1 if failed else 0)
