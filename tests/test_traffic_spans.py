"""TRAFFIC SPANS GATE — which span's data is on the screen, and whether the
loading overlay can outlive the work that raised it.

Owner report 2026-08-14: "For these two options [All (from file) and Since
start] I don't know exactly what they do, but they end up either in an
endless loop or in some very long loading loop that I eventually exit ...
first, I do not understand why that list is now so small, i.e. why it shows
only the previous few hours". His screenshots settled it: with "All (from
file)" selected the x-axis read 11:48 -> 15:42 — this server process's own
four hours — while "Since start" read 11:48 -> 15:43. The two spans drew the
SAME data, and it was the short one.

MEASURED, not reasoned (driving the real `TrafficWindow` offscreen against
his real 3.7 MB `traffic.csv`): the file was never the problem — it holds
2.5 days and reads whole in 0.23 s — and the reader was never the problem
either. `gui/traffic_window.py`'s JOB BOOKKEEPING was: a span switch made
while a read was in flight started no read of its own (`_maybe_start_history`
returned early on `running`), and the older read's result then landed and was
stamped with whatever span was selected when it arrived.

WHAT THIS GATE EXISTS TO PREVENT, and it is not "the combo has more items".

  * One span's data displayed under another span's label — the owner's own
    report. Held at the METHOD boundary (a result carries its own key and is
    refused under any other) AND end-to-end through the real widget, because
    the end-to-end check alone cannot say WHY it passed.
  * A span switch that starts no read of its own, i.e. the early return
    coming back in any form.
  * A loading overlay that outlives the work — held to the job's own
    `pending_key` rather than to a flag the window sets, since a flag that
    only a successful poll clears is stuck forever the first time a result
    is dropped.
  * A superseded background thread clearing the `running`/`pending_key`
    state that belongs to a NEWER read (which is what would let two full
    file reads run against each other, each discarding the other's answer).
  * "Today" quietly meaning "the last 24 hours" — his day starts at local
    midnight, and a rolling window is a different question than the one he
    asked. And the two new spans being anything other than file-backed.
  * T110 (owner report 2026-08-16, his THIRD on this window): a read keyed
    on a view that MOVES WITH THE CLOCK. A file-backed span may slide
    ("Last 10 hours" is `now - 10h .. now`), and `ViewRange._clamp` then
    pushes a zoomed view forward one second per second — so a key built from
    the raw bounds is a new key every tick, every tick supersedes the read
    before it, no read ever finishes and the "Reading traffic.csv…" overlay
    never comes down. His own log, one line per second, both bounds +1 and
    the span staying exactly 36000 s — which is the give-away that the view
    was zoomed on the RATE axis and never narrowed in time at all. Two
    defences, one check each: a rate zoom does not key a file read (the key
    stays the bare span name), and a real time zoom is keyed to a PLOT
    COLUMN, so a shift that cannot move a pixel is not a different read.
  * The picker growing past the width the window's own computed minimum
    reserves for it (THE SPACE & LEGIBILITY LAW: nothing the user must read
    is ever cut off).

Every check below is proven by planting its own defect and confirming the
check catches it (project gate methodology).

PERSISTED STATE: this file writes nothing outside a temp directory — the
device registry and the CSV path are both redirected (the 2026-08-13 lesson
from `test_traffic_devices.py`, whose fixtures once wrote into the owner's
real registry).

Run:  .venv\\Scripts\\python tests/test_traffic_spans.py
"""

import contextlib
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

import traffic  # noqa: E402
import traffic_devices  # noqa: E402
import traffic_history  # noqa: E402
from config import SETTINGS  # noqa: E402

APP = QApplication.instance() or QApplication([])

from gui import traffic_spans as spans, traffic_window as tw  # noqa: E402


# ═══════════════════════════ FIXTURES ═══════════════════════════
@contextlib.contextmanager
def _isolated():
    """A throwaway device registry AND a throwaway CSV path — no check here
    may touch the owner's own `%LOCALAPPDATA%` files."""
    original = traffic_devices.REGISTRY
    original_csv = SETTINGS.traffic_csv_path
    with tempfile.TemporaryDirectory() as d:
        traffic_devices.REGISTRY = traffic_devices.DeviceRegistry(
            path=Path(d) / "traffic_devices.json")
        object.__setattr__(SETTINGS, "traffic_csv_path", Path(d) / "traffic.csv")
        try:
            yield Path(d)
        finally:
            traffic_devices.REGISTRY = original
            object.__setattr__(SETTINGS, "traffic_csv_path", original_csv)


def _pt(t: float) -> traffic_history.Point:
    return traffic_history.Point(t=t, out_avg=1.0, out_max=1.0, in_avg=1.0,
                                 in_max=1.0, clients=1)


class _StagedReader:
    """Stands in for `traffic_history.read_history`, holding each read open
    until the check releases it — the only way to stage the owner's race
    (a span switch made WHILE a read is in flight) deterministically."""

    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.gate = threading.Event()
        self.started: list[float | None] = []
        self.entered = threading.Event()
        if delay:
            self.gate.set()

    def __call__(self, since, max_buckets, until=None):
        # `until` is optional because a ZOOMED read passes it (the window
        # narrows the read to the view) while a whole-span read does not.
        # Without it here the stub raised inside the worker thread, the job
        # surfaced nothing, and a check about the overlay would have been
        # blaming the window for the fixture's own signature.
        self.started.append(since)
        self.entered.set()
        if self.delay:
            time.sleep(self.delay)
        else:
            self.gate.wait(10)
        # Data STAMPED with its own span so a check can tell whose it is:
        # a read with a `since` returns points at that `since`, "All" returns
        # points a long way before it.
        base = since if since is not None else time.time() - 400000
        return [_pt(base + i) for i in range(4)]


def _index_of(kind: str) -> int:
    for i, (_, k, _) in enumerate(spans.SPANS):
        if k == kind:
            return i
    raise AssertionError(f"no span of kind {kind}")


def _pump(window, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        APP.processEvents()
        window._refresh()
        time.sleep(0.02)


# ═══════════════════════════ CHECKS ═══════════════════════════
def check_result_carries_its_key() -> bool:
    """METHOD BOUNDARY: `poll()` hands back the key the read was STARTED
    with, so a caller can never adopt one span's points as another's.

    PLANTED: `HistoryJob.poll` returning bare points (the pre-fix shape) —
    this check fails at the unpack, which is the point: bare points cannot
    even be checked.
    """
    job = traffic_history.HistoryJob()
    reader = _StagedReader(delay=0.01)
    original, traffic_history.read_history = traffic_history.read_history, reader
    try:
        job.start("all", None, 50)
        for _ in range(400):
            got = job.poll()
            if got is not None:
                break
            time.sleep(0.01)
    finally:
        traffic_history.read_history = original
    if got is None:
        print("  FAIL: no result ever arrived")
        return False
    key, points = got
    if key != "all":
        print(f"  FAIL: result came back under key {key!r}, not 'all'")
        return False
    if not points:
        print("  FAIL: no points")
        return False
    print("  ok: the result carries its own key ('all')")
    return True


def check_superseded_read_keeps_its_hands_off() -> bool:
    """A read whose token was bumped by a newer `start` must clear NOTHING:
    not `running`, not `pending_key`, not the newer read's result.

    PLANTED: `_run` clearing `self.running = False` / `pending_key = None`
    unconditionally (the pre-fix code) — the check then sees `running`
    False and `pending_key` None while the newer read is still working.

    Staged so the superseded read A finishes FIRST while the newer read B is
    still working — the only arrangement in which the defect is observable,
    and the first draft of this check missed it by letting both finish
    together (planting is what said so).
    """
    job = traffic_history.HistoryJob()
    a_gate, b_gate = threading.Event(), threading.Event()
    entered_b = threading.Event()
    original = traffic_history.read_history

    def reader(since, max_buckets):
        if since is None:               # read B ("all")
            entered_b.set()
            b_gate.wait(10)
        else:                           # read A ("since_start")
            a_gate.wait(10)
        base = since if since is not None else time.time() - 400000
        return [_pt(base + i) for i in range(4)]

    traffic_history.read_history = reader
    try:
        job.start("since_start", 1.0, 50)   # A
        job.start("all", None, 50)          # B supersedes A
        entered_b.wait(5)
        a_gate.set()                        # A finishes while B still runs
        time.sleep(0.3)
        mid_running, mid_pending = job.running, job.pending_key
        mid_result = job.poll()
        b_gate.set()
        time.sleep(0.4)
        got = job.poll()
    finally:
        a_gate.set()
        b_gate.set()
        traffic_history.read_history = original
    if not mid_running or mid_pending != "all":
        print(f"  FAIL: the superseded read cleared the NEWER read's state "
              f"(running={mid_running}, pending={mid_pending!r})")
        return False
    if mid_result is not None:
        print(f"  FAIL: the superseded read's result surfaced "
              f"(key {mid_result[0]!r})")
        return False
    if got is None or got[0] != "all":
        print(f"  FAIL: the newer read's own result never arrived ({got!r})")
        return False
    if job.pending_key is not None or job.running:
        print(f"  FAIL: job still claims work: running={job.running} "
              f"pending={job.pending_key!r}")
        return False
    print("  ok: the superseded read surfaced nothing and cleared nothing")
    return True


def check_a_foreign_result_is_dropped() -> bool:
    """METHOD BOUNDARY for the adoption rule itself: hand `_refresh` a ready
    result belonging to ANOTHER span and it must be DROPPED, never re-
    labelled. This is not reachable end-to-end any more (a span switch now
    supersedes the in-flight read, so its result never surfaces), which is
    exactly why it needs its own check — planting proved the end-to-end one
    could not see it.

    PLANTED: `_refresh` adopting `points` without comparing `got_kind` to
    `kind` — the foreign "Since start" points are then drawn under the
    "All (from file)" label, the owner's own screenshot.
    """
    with _isolated():
        reader = _StagedReader(delay=0.0)
        reader.gate.clear()             # nothing may complete on its own
        original, traffic_history.read_history = traffic_history.read_history, reader
        try:
            window = tw.TrafficWindow()
            window.show()
            traffic.PROCESS_START = time.time() - 4 * 3600
            window.span_combo.setCurrentIndex(_index_of("all"))
            APP.processEvents()
            # A ready result from the span he clicked AWAY from.
            foreign = [_pt(traffic.PROCESS_START + i) for i in range(4)]
            with window._history._lock:
                window._history._result = ("since_start", foreign)
            window._refresh()
            adopted = list(window._history_points)
            label = window.chart.span_label
        finally:
            reader.gate.set()
            traffic_history.read_history = original
            window.close()
    if adopted:
        print(f"  FAIL: a 'since_start' result was adopted under {label!r}")
        return False
    print("  ok: a foreign span's ready result is dropped, not re-labelled")
    return True


def check_switch_never_shows_the_other_spans_data() -> bool:
    """THE OWNER'S BUG, end-to-end through the real widget: switch span while
    a read is in flight, and the older span's data must never be drawn under
    the new span's label.

    PLANTED (both halves, separately):
      * `_maybe_start_history` early-returning on an in-flight read;
      * `_refresh` adopting `points` without comparing `got_kind` to `kind`.
    With either one back, `chart.start` under the "All (from file)" label
    lands on the "Since start" data — his 11:48, exactly.
    """
    with _isolated():
        slow = _StagedReader()
        original, traffic_history.read_history = traffic_history.read_history, slow
        try:
            window = tw.TrafficWindow()
            window.show()
            traffic.PROCESS_START = time.time() - 4 * 3600
            window.span_combo.setCurrentIndex(_index_of("since_start"))
            slow.entered.wait(5)
            # ... and now, MID-READ, the owner picks "All (from file)".
            window.span_combo.setCurrentIndex(_index_of("all"))
            slow.gate.set()                 # the old read lands NOW
            bad = 0
            end = time.time() + 2.0
            while time.time() < end:
                APP.processEvents()
                window._refresh()
                if (window.chart.span_label.startswith("All")
                        and window.chart.points
                        and abs(window.chart.start - traffic.PROCESS_START) < 120):
                    bad += 1
                time.sleep(0.02)
            drawn_all = (window.chart.points
                         and window.chart.start < traffic.PROCESS_START - 1000)
        finally:
            traffic_history.read_history = original
            window.close()
    if bad:
        print(f"  FAIL: {bad} ticks drew the 'Since start' data under the "
              f"'All (from file)' label")
        return False
    if not drawn_all:
        print("  FAIL: 'All' never got its own data")
        return False
    print("  ok: the switch drew only 'All' data under the 'All' label")
    return True


def check_switch_starts_its_own_read() -> bool:
    """A span switch made while a read is in flight must SUPERSEDE it, not
    wait for it: the new span has to issue a read of its own.

    PLANTED: the `if self._history.running: return` early return — the
    reader then records only the first span's `since` and this check fails
    with one read where it demands two.
    """
    with _isolated():
        slow = _StagedReader()
        original, traffic_history.read_history = traffic_history.read_history, slow
        try:
            window = tw.TrafficWindow()
            window.show()
            traffic.PROCESS_START = time.time() - 4 * 3600
            window.span_combo.setCurrentIndex(_index_of("since_start"))
            slow.entered.wait(5)
            window.span_combo.setCurrentIndex(_index_of("all"))
            APP.processEvents()
            window._refresh()
            slow.gate.set()
            time.sleep(0.3)
            starts = list(slow.started)
        finally:
            traffic_history.read_history = original
            window.close()
    if None not in starts:
        print(f"  FAIL: the switch to 'All' started no read of its own "
              f"(reads: {starts})")
        return False
    print(f"  ok: the switch issued its own read ({len(starts)} reads, "
          f"one of them 'All')")
    return True


def check_overlay_cannot_outlive_the_work() -> bool:
    """The "Reading traffic.csv…" overlay is up while the SELECTED span is
    being read and is down the moment that span has data — and it can never
    be left up by a DROPPED result.

    PLANTED: deriving `loading` from a window-owned flag cleared only on a
    successful poll (the pre-fix `_history_loading`) — with a result dropped
    by the key check, the overlay then stays up forever and this check
    fails on the second half.
    """
    with _isolated():
        slow = _StagedReader()
        original, traffic_history.read_history = traffic_history.read_history, slow
        try:
            window = tw.TrafficWindow()
            window.show()
            traffic.PROCESS_START = time.time() - 4 * 3600
            window.span_combo.setCurrentIndex(_index_of("since_start"))
            slow.entered.wait(5)
            APP.processEvents()
            window._refresh()
            up_while_reading = window.chart.loading
            # Switch mid-read, so the FIRST read's result is dropped by the
            # key check — the exact state that used to strand the flag.
            window.span_combo.setCurrentIndex(_index_of("all"))
            slow.gate.set()
            _pump(window, 1.5)
            down_after = window.chart.loading
            pending = window._history.pending_key
        finally:
            traffic_history.read_history = original
            window.close()
    if not up_while_reading:
        print("  FAIL: no overlay while the selected span was being read")
        return False
    if down_after or pending is not None:
        print(f"  FAIL: overlay outlived the work (loading={down_after}, "
              f"pending={pending!r})")
        return False
    print("  ok: overlay up during the read, down once the span had data")
    return True


def check_today_is_local_midnight() -> bool:
    """"Today" is HIS day — local midnight — never a rolling 24 hours, and
    "Last 10 hours" is exactly 10 hours back. "All" stays None (the
    recording's own beginning) and "Since start" is the process's start.

    PLANTED: `history_since("today")` returning `now - 86400` — the check
    catches it because a rolling day is not midnight (staged at a fixed
    now whose local time-of-day is not 00:00:00).
    """
    now = time.mktime((2026, 8, 14, 15, 42, 7, 0, 0, -1))
    today = spans.history_since("today", now)
    lt = time.localtime(today)
    if (lt.tm_hour, lt.tm_min, lt.tm_sec) != (0, 0, 0):
        print(f"  FAIL: 'Today' starts at {time.strftime('%H:%M:%S', lt)}, "
              f"not local midnight")
        return False
    if time.localtime(now).tm_mday != lt.tm_mday:
        print("  FAIL: 'Today' starts on another day")
        return False
    if spans.history_since("last10h", now) != now - 10 * 3600:
        print("  FAIL: 'Last 10 hours' is not 10 hours")
        return False
    if spans.history_since("all", now) is not None:
        print("  FAIL: 'All' must be None (the recording's own beginning)")
        return False
    if spans.history_since("since_start", now) != traffic.PROCESS_START:
        print("  FAIL: 'Since start' is not the process start")
        return False
    print("  ok: Today = local midnight, Last 10 hours = now-10h, All = None")
    return True


def check_new_spans_are_file_backed_and_offered() -> bool:
    """The owner asked for shorter FILE-BACKED spans: the live ring buffer
    stops at one hour, so "Today"/"Last 10 hours" must read the CSV (kind
    != "recent", no fixed `seconds`) and both must be in the picker.

    PLANTED: declaring "Last 10 hours" as `("recent", 36000)` — the check
    catches it, and it matters: the ring buffer only holds
    `traffic_history_samples` (3600) seconds, so a "recent" 10-hour span
    would silently draw one hour under a ten-hour axis.
    """
    kinds = {k for _, k, _ in spans.SPANS}
    for kind in ("today", "last10h"):
        if kind not in kinds:
            print(f"  FAIL: span kind {kind!r} is not offered")
            return False
    for name, kind, seconds in spans.SPANS:
        if kind in ("today", "last10h"):
            if seconds is not None:
                print(f"  FAIL: {name} carries a fixed seconds={seconds}")
                return False
    for kind in ("recent", "since_start", "all"):
        if kind not in kinds:
            print(f"  FAIL: the pre-existing span kind {kind!r} was dropped")
            return False
    if len(spans.SPANS) != 7:
        print(f"  FAIL: expected the five old spans plus two, got {len(spans.SPANS)}")
        return False
    print("  ok: Today + Last 10 hours are file-backed, the five old spans stand")
    return True


def check_picker_fits_its_widest_name() -> bool:
    """THE SPACE & LEGIBILITY LAW: the combo must be able to show its widest
    entry inside the window's own computed minimum width — a span the owner
    must read may not be cut off.

    Two properties, because the first alone is what a hardcoded number would
    still satisfy: (a) the combo's own floor is at least what its content
    needs, and (b) `_computed_minimum` READS the widest span name — staging
    a 40-character name must widen the reserved minimum by roughly that
    text, so a future round adding a long name gets a wider window instead
    of a cut-off one.

    PLANTED: `_computed_minimum` measuring a fixed string instead of
    `max((n for n, _, _ in SPANS), key=len)` — the reserved width then does
    not move when the staged long name is added, and (b) fails.
    """
    long_name = "Everything the recording has ever held!!"   # 39 chars
    with _isolated():
        window = tw.TrafficWindow()
        window.show()
        APP.processEvents()
        combo_w = window.span_combo.sizeHint().width()
        combo_floor = window.span_combo.minimumWidth()
        min_w = window._computed_minimum().width()
        widest = max((n for n, _, _ in spans.SPANS), key=len)
        original_spans = list(spans.SPANS)
        try:
            spans.SPANS.append((long_name, "all", None))
            staged_w = window._computed_minimum().width()
        finally:
            spans.SPANS[:] = original_spans
        window.close()
    if combo_floor < combo_w:
        print(f"  FAIL: the combo's floor {combo_floor} is under what its "
              f"content needs ({combo_w})")
        return False
    if combo_w >= min_w:
        print(f"  FAIL: the picker alone ({combo_w}px, widest {widest!r}) does "
              f"not fit the window's computed minimum ({min_w}px)")
        return False
    grew = staged_w - min_w
    if grew < 100:
        print(f"  FAIL: the computed minimum does not read the widest span "
              f"name — a 39-character name widened it by only {grew}px")
        return False
    print(f"  ok: picker {combo_w}px (widest {widest!r}) inside the window's "
          f"{min_w}px minimum; a longer name widens it by {grew}px")
    return True


def check_a_sliding_zoomed_span_keeps_one_key() -> bool:
    """T110, METHOD BOUNDARY (owner report 2026-08-16, his THIRD on this
    window). A file-backed span whose end tracks the clock ("Last 10 hours"
    is `now - 10h .. now`) slides one second per second, and `ViewRange`
    correctly clamps a ZOOMED view forward inside it. Keyed on the raw view
    bounds, that invented a new key every tick — his own server log, one
    line per second, both bounds incrementing by exactly 1:

        dropped 'last10h|1786797517-1786833517' while showing
                'last10h|1786797518-1786833518'

    Nothing in flight could ever match the key by the time it landed, so
    every result was dropped and the overlay could never come down.

    WHAT IS STAGED IS A RATE-AXIS (Y) ZOOM, and getting that right is the
    whole check. The give-away in his own log is the arithmetic: 1786833517
    - 1786797517 is exactly 36000 — the whole ten hours — so the view was
    never narrowed in TIME at all. A Y zoom still made `is_zoomed()` true,
    which sent `set_full` down its clamping path, and the clamp drags a view
    sitting on the full span forward one second per second.

    The first draft of this check staged a TIME zoom instead and the plant
    below did not fail it — a view genuinely narrowed in time sits INSIDE the
    span and the clamp never touches it, so there was no drift to measure.
    That correction is the check.

    PLANTED: `traffic_spans.history_key` asking `is_zoomed()` instead of `is_time_zoomed()`
    — three distinct keys, one per second, exactly his log.

    Why the earlier round's harness could not see any of it: it drove
    FIXED-start spans, where the end does not track the clock and nothing
    moves however it is zoomed.
    """
    with _isolated():
        window = tw.TrafficWindow()
        try:
            now = time.time()
            view = window.chart.view
            view.set_full(now - 10 * 3600, now)
            view.y_lo, view.y_hi = 0.0, 1000.0     # HIS zoom: the rate axis
            keys = []
            for tick in range(60):
                t = now + tick
                view.set_full(t - 10 * 3600, t)    # the span slides, as it does
                keys.append(spans.history_key("last10h", window.chart.view))
            zoomed = view.is_zoomed() and not view.is_time_zoomed()
        finally:
            window.close()
    if not zoomed:
        print("  FAIL: the staged view was not Y-only-zoomed — the check "
              "would be measuring the wrong thing")
        return False
    # The key must be the BARE span name — no bounds in it at all. Asserting
    # merely "one key" would be satisfied by a coarse quantum swallowing the
    # drift, which is a different defence and is checked separately below;
    # this one is about a rate zoom not narrowing a file read in the first
    # place. Planting `is_zoomed()` was green against "one key" and is red
    # against this, which is why the check is written this way.
    if set(keys) != {"last10h"}:
        print(f"  FAIL: a Y-only zoom keyed the read on the view: "
              f"{sorted(set(keys))[:3]} … ({len(set(keys))} distinct)")
        return False
    print("  ok: 60 s of slide under a rate zoom, the key stays 'last10h'")
    return True


def check_the_overlay_comes_down_on_a_sliding_zoomed_span() -> bool:
    """T110 END-TO-END, which is the state he actually sat in front of:
    "Reading traffic.csv…" forever. The method-boundary check above says the
    key is stable; only this one says the WINDOW recovers — the overlay is
    derived from the job's `pending_key` against the selected key, so a key
    that drifts leaves it up whatever the reader does.

    PLANTED (both halves, separately):
      * `traffic_spans.history_key` asking `is_zoomed()` — the overlay never comes down
        and the reads pile up, which is the state he sat in front of;
      * `_refresh` recomputing `key = traffic_spans.history_key(kind, view)` after the read
        started instead of reading `self._requested_key` — same symptom the
        moment the view moves mid-read.
    """
    with _isolated():
        # A read SLOWER THAN A TICK, which is the whole point: his
        # `traffic.csv` is 3.7 MB and reads in ~0.23 s while the key drifted
        # once a second, so the read could never land under a key still
        # valid. A fast stub finishes inside one second, no drift ever
        # happens, and this check silently measures nothing — the first draft
        # used 0.02 s and stayed green under the true pre-fix code.
        reader = _StagedReader(delay=1.2)
        original, traffic_history.read_history = traffic_history.read_history, reader
        try:
            window = tw.TrafficWindow()
            window.show()
            window.span_combo.setCurrentIndex(_index_of("last10h"))
            APP.processEvents()
            now = time.time()
            view = window.chart.view
            view.set_full(now - 10 * 3600, now)
            view.y_lo, view.y_hi = 0.0, 1000.0     # his zoom: the rate axis
            settled = False
            end = time.time() + 8.0
            while time.time() < end:
                APP.processEvents()
                window._refresh()          # each tick slides the span's end
                if window._history_points and not window.chart.loading:
                    settled = True
                    break
                time.sleep(0.02)
            reads = len(reader.started)
        finally:
            traffic_history.read_history = original
            window.close()
    if not settled:
        print(f"  FAIL: the overlay never came down on a sliding zoomed span "
              f"({reads} reads started in 3 s — the read storm, his log)")
        return False
    print(f"  ok: the overlay came down and the data landed ({reads} read(s))")
    return True


def check_a_zoom_on_the_oldest_slice_recovers() -> bool:
    """T110's OTHER drifting view — a plain TIME zoom, and the reason
    adoption may not recompute the key.

    The Y zoom above is the one his log caught. A time zoom drifts too, on
    the OLDEST part of a sliding span: "Last 10 hours" slides its START
    forward as well as its end, so a view zoomed onto the oldest hour falls
    out through the left edge and `ViewRange._clamp` pushes it forward one
    second per second. `is_time_zoomed()` does not save that case and is not
    meant to — the view really IS time-zoomed and its bounds really do move,
    so re-reading is CORRECT. What must not happen is that the answer we
    ASKED for is thrown away as foreign the moment it lands, which is what a
    key recomputed after the asking does: with a read slower than the drift
    it never converges, and the overlay never comes down.

    So this is an END-TO-END check and not a check on the key: the question
    is whether the WINDOW recovers, and only the window can answer it.

    PLANTED: `_refresh` computing `key = traffic_spans.history_key(kind, view)` instead of
    reading `self._requested_key` — the overlay stays up and the reads pile
    up, his own symptom.
    """
    with _isolated():
        reader = _StagedReader(delay=1.2)   # slower than the drift, as his file is
        original, traffic_history.read_history = traffic_history.read_history, reader
        try:
            window = tw.TrafficWindow()
            window.show()
            window.span_combo.setCurrentIndex(_index_of("last10h"))
            APP.processEvents()
            now = time.time()
            view = window.chart.view
            view.set_full(now - 10 * 3600, now)
            # The oldest hour — deliberately AT the left edge, where the
            # slide pushes a view out.
            view.set_view(now - 10 * 3600, now - 9 * 3600)
            settled = False
            end = time.time() + 8.0
            while time.time() < end:
                APP.processEvents()
                window._refresh()
                if window._history_points and not window.chart.loading:
                    settled = True
                    break
                time.sleep(0.02)
            drifted = view.start > now - 10 * 3600 + 1.0
            reads = len(reader.started)
        finally:
            traffic_history.read_history = original
            window.close()
    if not drifted:
        print("  FAIL: the staged view never drifted — the check would be "
              "measuring nothing")
        return False
    if not settled:
        print(f"  FAIL: the overlay never came down on a drifting time zoom "
              f"({reads} reads started)")
        return False
    print(f"  ok: a drifting time zoom recovered ({reads} read(s))")
    return True


CHECKS = [
    ("a result carries its own span key", check_result_carries_its_key),
    ("a superseded read clears nothing", check_superseded_read_keeps_its_hands_off),
    ("a foreign span's result is dropped", check_a_foreign_result_is_dropped),
    ("a switch never shows the other span's data",
     check_switch_never_shows_the_other_spans_data),
    ("a switch starts its own read", check_switch_starts_its_own_read),
    ("the overlay cannot outlive the work", check_overlay_cannot_outlive_the_work),
    ("Today is local midnight", check_today_is_local_midnight),
    ("the new spans are file-backed", check_new_spans_are_file_backed_and_offered),
    ("the picker fits its widest name", check_picker_fits_its_widest_name),
    ("a sliding zoomed span keeps ONE key",
     check_a_sliding_zoomed_span_keeps_one_key),
    ("a zoom on the oldest slice recovers",
     check_a_zoom_on_the_oldest_slice_recovers),
    ("the overlay comes down on a sliding zoomed span",
     check_the_overlay_comes_down_on_a_sliding_zoomed_span),
]


def main() -> int:
    failures = 0
    for title, fn in CHECKS:
        print(f"[traffic spans] {title}")
        try:
            ok = fn()
        except Exception as e:                      # a raising check is a fail
            print(f"  FAIL: {type(e).__name__}: {e}")
            ok = False
        if not ok:
            failures += 1
    if failures:
        print(f"\nTRAFFIC SPANS GATE FAILED — {failures} check(s)")
        return 1
    print("\nTRAFFIC SPANS GATE PASSED")
    return 0


def test_gate():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
