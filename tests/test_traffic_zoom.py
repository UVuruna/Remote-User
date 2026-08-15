"""TRAFFIC ZOOM GATE — the Traffic graph's zoom (T104 + T105) and the
per-second stream descriptor beside every sample (T106), owner requests
2026-08-15 ("usavršavam graph logging za traffic i battery usage" — lang-ok:
owner quote).

WHAT THIS GATE EXISTS TO PREVENT:

  * A zoom that wanders outside the span the picker selected, or shrinks to
    a window with no whole second in it (`traffic_zoom.ViewRange`).
  * A drag rectangle that zooms on a mere click, or that maps its pixels to
    the wrong seconds — held END-TO-END through the real `TrafficChart`
    with real mouse events, because a pure-arithmetic check cannot say what
    the widget does with a press.
  * The rectangle NOT being visible while the button is held — the owner
    asked for exactly that ("vizuelno se prikazuje dok to radimo").
  * A zoomed file-backed span being merely stretched instead of re-read for
    the view (`read_history(..., until)` + the window's zoom key), and a
    result for the whole span being adopted as the zoomed one.
  * The Traffic window losing its minimize/maximize buttons (T103).
  * A CSV row written WITHOUT the stream descriptor while a session
    streams, or an OLD row (4/5/partial columns) failing to read, or an old
    second being shown with an invented "full/high" instead of "not
    recorded" — the hover card names what it knows and says when it does
    not (T106).

Every check is proven by planting its own defect (project gate methodology).
No check touches the owner's own `%LOCALAPPDATA%` files.

Run:  .venv\\Scripts\\python tests/test_traffic_zoom.py
"""

import contextlib
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import traffic  # noqa: E402
import traffic_devices  # noqa: E402
import traffic_history  # noqa: E402
import traffic_stream  # noqa: E402
from config import SETTINGS  # noqa: E402

APP = QApplication.instance() or QApplication([])

from gui import traffic_chart, traffic_window as tw, traffic_zoom  # noqa: E402


# ═══════════════════════════ FIXTURES ═══════════════════════════
@contextlib.contextmanager
def _isolated():
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


def _pt(t: float, out: float = 1000.0, stream=None) -> traffic_history.Point:
    return traffic_history.Point(t=t, out_avg=out, out_max=out, in_avg=1.0,
                                 in_max=1.0, clients=1, device="", stream=stream)


def _chart(points, start, end, w=800, h=300):
    chart = traffic_chart.TrafficChart()
    chart.resize(w, h)
    chart.set_data(points, start, end, "gate", downsampled=False)
    chart.grab()          # paints once → `_plot` is known
    return chart


def _mouse(chart, kind, x, y=150, button=Qt.MouseButton.LeftButton):
    pos = QPointF(x, y)
    ev = QMouseEvent(kind, pos, chart.mapToGlobal(QPoint(int(x), int(y))),
                     button, button if kind != QEvent.Type.MouseMove else Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier)
    if kind == QEvent.Type.MouseButtonPress:
        chart.mousePressEvent(ev)
    elif kind == QEvent.Type.MouseMove:
        chart.mouseMoveEvent(ev)
    else:
        chart.mouseReleaseEvent(ev)


class _Session:
    """The fields `traffic_stream.from_session` reads off a real H264Session."""
    def __init__(self, quality=None, crop=None, scale=None, zoom=1, w=3840, h=2160):
        self._quality = quality or {}
        self._crop = crop
        self._scale = scale
        self._zoom = zoom
        self.width, self.height = w, h


# ═══════════════════════════ 1. THE VIEW RANGE (pure) ═══════════════════════════
def check_view_never_leaves_the_span() -> bool:
    """PLANTED DEFECT: drop the edge clamp in `set_view` — a drag past the
    right edge would show seconds the picker never selected (and the file
    was never read for), or — clamped only by span — collapse to the whole
    span and lose the zoom he drew."""
    v = traffic_zoom.ViewRange()
    v.set_full(1000.0, 2000.0)
    v.set_view(1500.0, 5000.0)
    inside = v.start >= 1000.0 and v.end <= 2000.0 and v.is_zoomed()
    v.zoom_out(); v.zoom_out(); v.zoom_out()
    whole = not v.is_zoomed() and (v.start, v.end) == (1000.0, 2000.0)
    return inside and whole


def check_view_never_narrower_than_the_floor() -> bool:
    """PLANTED DEFECT: `MIN_SPAN_S = 0` — a two-pixel drag becomes a window
    with no whole second, an empty plot with no way to tell why."""
    v = traffic_zoom.ViewRange()
    v.set_full(0.0, 3600.0)
    v.set_view(100.0, 100.5)
    floor = v.span() >= traffic_zoom.MIN_SPAN_S - 1e-6
    for _ in range(40):
        v.zoom_in()
    # The floor must be a real number of seconds — a floor of 0 satisfies
    # every ">= floor" test and is exactly the defect.
    return (traffic_zoom.MIN_SPAN_S >= 1.0 and floor
            and v.span() >= traffic_zoom.MIN_SPAN_S - 1e-6)


def check_zoom_keeps_the_anchor_in_place() -> bool:
    """PLANTED DEFECT: zoom around the middle regardless of the anchor — the
    second under the mouse jumps away on every wheel step."""
    v = traffic_zoom.ViewRange()
    v.set_full(0.0, 1000.0)
    v.zoom_in(anchor=200.0)
    frac_before = 200.0 / 1000.0
    frac_after = (200.0 - v.start) / v.span()
    return abs(frac_before - frac_after) < 1e-9 and abs(v.span() - 500.0) < 1e-9


def check_live_span_sliding_keeps_the_zoom() -> bool:
    """PLANTED DEFECT: `set_full` always resets the view — the live "Last
    hour" span slides forward every second, so a zoom he made would vanish
    on the next refresh tick."""
    v = traffic_zoom.ViewRange()
    v.set_full(0.0, 3600.0)
    v.set_view(1000.0, 1200.0)
    v.set_full(1.0, 3601.0)
    kept = (v.start, v.end) == (1000.0, 1200.0)
    v.reset()
    v.set_full(2.0, 3602.0)
    follows = (v.start, v.end) == (2.0, 3602.0)
    return kept and follows


def check_click_is_not_a_drag() -> bool:
    """PLANTED DEFECT: `DRAG_MIN_PX = 0` — a click that twitched a pixel
    zooms the whole graph to ten seconds."""
    return (not traffic_zoom.is_drag(100, 102)
            and traffic_zoom.is_drag(100, 100 + traffic_zoom.DRAG_MIN_PX))


# ═══════════════════════════ 2. THE CHART (end-to-end) ═══════════════════════════
def check_drag_zooms_to_the_drawn_seconds() -> bool:
    """A press at 25% and a release at 75% of the plot must zoom to exactly
    the middle half of the span, and `zoomed` must fire once. PLANTED
    DEFECT: map pixels against the WIDGET width instead of the plot's."""
    start, end = 1_700_000_000.0, 1_700_000_000.0 + 1000.0
    pts = [_pt(start + i) for i in range(0, 1000, 10)]
    chart = _chart(pts, start, end)
    plot = chart._plot
    fired = []
    chart.zoomed.connect(lambda: fired.append(1))
    x0 = plot.left() + plot.width() * 0.25
    x1 = plot.left() + plot.width() * 0.75
    _mouse(chart, QEvent.Type.MouseButtonPress, x0)
    _mouse(chart, QEvent.Type.MouseMove, x1)
    _mouse(chart, QEvent.Type.MouseButtonRelease, x1)
    v = chart.view
    return (len(fired) == 1
            and abs(v.start - (start + 250.0)) < 2.0
            and abs(v.end - (start + 750.0)) < 2.0
            and chart.start == v.start and chart.end == v.end)


def check_click_on_the_chart_zooms_nothing() -> bool:
    """PLANTED DEFECT: release without the `is_drag` test."""
    start, end = 1_700_000_000.0, 1_700_000_000.0 + 1000.0
    chart = _chart([_pt(start + i) for i in range(0, 1000, 10)], start, end)
    x = chart._plot.left() + 100
    _mouse(chart, QEvent.Type.MouseButtonPress, x)
    _mouse(chart, QEvent.Type.MouseButtonRelease, x + 2)
    return not chart.view.is_zoomed()


def check_rectangle_is_visible_while_dragging() -> bool:
    """The owner's own words: the rectangle shows WHILE he drags. Grab the
    widget mid-drag and compare against the same widget idle: the pixels
    inside the band must differ. PLANTED DEFECT: `_paint_drag` returns at
    once."""
    start, end = 1_700_000_000.0, 1_700_000_000.0 + 1000.0
    chart = _chart([_pt(start + i, out=0.0) for i in range(0, 1000, 10)], start, end)
    plot = chart._plot
    idle = chart.grab().toImage()
    x0 = plot.left() + plot.width() * 0.3
    x1 = plot.left() + plot.width() * 0.6
    _mouse(chart, QEvent.Type.MouseButtonPress, x0)
    _mouse(chart, QEvent.Type.MouseMove, x1)
    dragging = chart.grab().toImage()
    sx = int((x0 + x1) / 2)
    sy = int(plot.center().y())
    changed = idle.pixel(sx, sy) != dragging.pixel(sx, sy)
    outside_same = idle.pixel(plot.left() + 5, sy) == dragging.pixel(plot.left() + 5, sy)
    _mouse(chart, QEvent.Type.MouseButtonRelease, x1)
    return changed and outside_same


def check_only_the_view_is_drawn() -> bool:
    """A zoomed chart draws only the points inside its view: the tallest bar
    outside the view must not set the y-axis. PLANTED DEFECT: coalesce
    `self.points` instead of the visible subset."""
    start, end = 1_700_000_000.0, 1_700_000_000.0 + 1000.0
    pts = [_pt(start + i, out=100.0) for i in range(0, 1000, 10)]
    pts[5] = _pt(start + 50, out=10_000_000.0)      # a spike far outside the view
    chart = _chart(pts, start, end)
    chart.view.set_view(start + 500, start + 900)
    chart._view_changed()
    img = chart.grab().toImage()
    plot = chart._plot
    # With the spike gone from the axis, the 100 B/s line sits well above
    # the plot's bottom third; with the spike setting the axis it is flat on
    # the floor. Sample the column at the view's middle.
    x = int(plot.left() + plot.width() * 0.5)
    floor = img.pixel(x, plot.bottom() - 2)
    background = img.pixel(x, plot.top() + 2)
    # The filled series must NOT reach a pixel just under the top — that only
    # happens if the axis is set by data inside the view (peak 100 B/s vs the
    # 1024 minimum → line low but the FILL is drawn from the bottom).
    return floor != background


# ═══════════════════════════ 3. THE WINDOW ═══════════════════════════
def check_window_has_min_max_buttons() -> bool:
    """T103. PLANTED DEFECT: drop the `setWindowFlags` call."""
    with _isolated():
        w = tw.TrafficWindow()
        flags = w.windowFlags()
        return (bool(flags & Qt.WindowType.WindowMinMaxButtonsHint)
                and bool(flags & Qt.WindowType.WindowCloseButtonHint))


def check_zoom_rereads_the_file_for_the_view() -> bool:
    """A zoomed file-backed span asks the reader for [view.start, view.end]
    under its OWN key, and a whole-span result is not adopted for it.
    PLANTED DEFECT: `_history_key` returns `kind` regardless of the zoom."""
    calls = []

    def reader(since, max_buckets, until=None):
        calls.append((since, until))
        base = since if since is not None else 0.0
        return [_pt(base + i) for i in range(4)]

    original = traffic_history.read_history
    traffic_history.read_history = reader
    try:
        with _isolated():
            w = tw.TrafficWindow()
            idx = next(i for i, (_, k, _) in enumerate(tw.SPANS) if k == "last10h")
            w.span_combo.setCurrentIndex(idx)
            for _ in range(20):
                APP.processEvents(); w._refresh(); time.sleep(0.02)
            if not calls or calls[0][1] is not None:
                return False
            whole_key = w._history_kind
            v = w.chart.view
            v.set_view(v.start + 100, v.start + 400)
            w.chart._view_changed()
            for _ in range(30):
                APP.processEvents(); w._refresh(); time.sleep(0.02)
            zoomed_calls = [c for c in calls if c[1] is not None]
            key = w._history_key("last10h")
            return (bool(zoomed_calls)
                    and abs(zoomed_calls[-1][0] - v.start) < 1.0
                    and abs(zoomed_calls[-1][1] - v.end) < 1.0
                    and key != "last10h" and whole_key == "last10h"
                    and w._history_kind == key)
    finally:
        traffic_history.read_history = original


def check_reader_honours_until() -> bool:
    """`read_history(since, n, until)` folds only rows inside the window.
    PLANTED DEFECT: `end = time.time()` regardless of `until`."""
    with _isolated() as d:
        path = Path(d) / "traffic.csv"
        t0 = time.mktime((2026, 8, 1, 10, 0, 0, 0, 0, -1))
        rows = ["time,out_bytes,in_bytes,clients,device"]
        for i in range(600):
            rows.append(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0 + i))
                        + f",{i},0,1,dev")
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        pts = traffic_history.read_history(t0 + 100, 50, until=t0 + 200)
        return (bool(pts) and all(t0 + 100 <= p.t <= t0 + 200 for p in pts)
                and max(p.out_max for p in pts) <= 200)


# ═══════════════════════════ 4. THE STREAM DESCRIPTOR (T106) ═══════════════════════════
def check_descriptor_reads_the_session() -> bool:
    """PLANTED DEFECT: `enc` copied from `crop` — a scaled session would claim
    to send the crop's own size."""
    s = _Session(quality={"fps": 30, "res": "2/3", "bitrate": "low"},
                 crop=(968, 2096, 100, 0), scale=(644, 1394), zoom=2)
    info = traffic_stream.from_session(s)
    return info == {"fps": "30", "res": "2/3", "bitrate": "low",
                    "crop": "968x2096", "enc": "644x1394", "zoom": "2"}


def check_descriptor_round_trips_the_csv() -> bool:
    """A sample taken while a session streams writes eleven cells, and the
    reader hands the same descriptor back. PLANTED DEFECT: `_append_csv`
    still writes five cells."""
    with _isolated() as d:
        meter = traffic.TrafficMeter()
        meter.note_stream(traffic_stream.from_session(
            _Session(quality={"fps": 0}, crop=None, scale=(1920, 1080), zoom=1)))
        meter.set_clients(1)
        meter.add_out(5000)
        meter._take_sample()
        meter.note_stream(None)
        meter._take_sample()
        lines = (Path(d) / "traffic.csv").read_text(encoding="utf-8").splitlines()
        header, streamed, idle = lines[0], lines[1], lines[2]
        row = traffic_history._parse_row(streamed)
        row_idle = traffic_history._parse_row(idle)
        return (header.endswith(",".join(traffic_stream.STREAM_COLUMNS))
                and streamed.count(",") == 10
                and row is not None and row[5] == {
                    "fps": "0", "res": "full", "bitrate": "high",
                    "crop": "3840x2160", "enc": "1920x1080", "zoom": "1"}
                and row_idle is not None and row_idle[5] is None)


def check_old_rows_still_read_and_say_not_recorded() -> bool:
    """4-, 5- and torn 7-cell rows read; none of them invents a descriptor.
    PLANTED DEFECT: `_parse_row` requires 11 cells."""
    r4 = traffic_history._parse_row("2026-08-01 10:00:00,100,50,1")
    r5 = traffic_history._parse_row("2026-08-13 10:00:00,100,50,1,1080x2400")
    r7 = traffic_history._parse_row("2026-08-15 10:00:00,100,50,1,1080x2400,30,full")
    ok = (r4 is not None and r4[5] is None
          and r5 is not None and r5[4] == "1080x2400" and r5[5] is None
          and r7 is not None and r7[5] is None)     # no crop cell → not recorded
    return ok and traffic_stream.hover_lines(None) == ["stream: not recorded"]


def check_hover_card_names_device_and_stream() -> bool:
    """The card under the crosshair carries the device, the quality, the
    slice and the zoom. Held at the widget: paint with a hover over a
    streamed point and read the lines the card would draw. PLANTED DEFECT:
    drop the `hover_lines` extension."""
    with _isolated():
        key = traffic_devices.REGISTRY.note(1920, 1200, "Redmi Pad SE")["key"]
        info = {"fps": "30", "res": "full", "bitrate": "low",
                "crop": "968x2096", "enc": "968x2096", "zoom": "2"}
        start = 1_700_000_000.0
        pts = [traffic_history.Point(t=start + i, out_avg=500.0, out_max=500.0,
                                     in_avg=1.0, in_max=1.0, clients=1,
                                     device=key, stream=info) for i in range(0, 100, 5)]
        chart = _chart(pts, start, start + 100)
        drawn = []
        real = traffic_chart.QPainter.drawText

        def spy(self, *args):
            if len(args) == 3 and isinstance(args[2], str):
                drawn.append(args[2])
            return real(self, *args)

        traffic_chart.QPainter.drawText = spy
        try:
            chart._hover_x = chart._plot.center().x()
            chart.grab()
        finally:
            traffic_chart.QPainter.drawText = real
        text = "\n".join(drawn)
        return ("device: " in text and "Redmi Pad SE" in text
                and "30 fps · full · low (data saver)" in text
                and "slice: 968x2096" in text and "zoom: x2" in text)


CHECKS = [
    ("the view never leaves the selected span", check_view_never_leaves_the_span),
    ("the view is never narrower than the floor", check_view_never_narrower_than_the_floor),
    ("zoom keeps the anchor in place", check_zoom_keeps_the_anchor_in_place),
    ("a sliding live span keeps the zoom", check_live_span_sliding_keeps_the_zoom),
    ("a click is not a drag", check_click_is_not_a_drag),
    ("a drag zooms to the drawn seconds (real chart)", check_drag_zooms_to_the_drawn_seconds),
    ("a click on the chart zooms nothing", check_click_on_the_chart_zooms_nothing),
    ("the rectangle is visible while dragging", check_rectangle_is_visible_while_dragging),
    ("only the view is drawn", check_only_the_view_is_drawn),
    ("the window has minimize/maximize buttons (T103)", check_window_has_min_max_buttons),
    ("a zoom re-reads the file for the view under its own key", check_zoom_rereads_the_file_for_the_view),
    ("read_history honours `until`", check_reader_honours_until),
    ("the descriptor reads the session (T106)", check_descriptor_reads_the_session),
    ("the descriptor round-trips the CSV", check_descriptor_round_trips_the_csv),
    ("old rows still read and say 'not recorded'", check_old_rows_still_read_and_say_not_recorded),
    ("the hover card names device and stream", check_hover_card_names_device_and_stream),
]


def main() -> int:
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = bool(fn())
        except Exception as e:  # noqa: BLE001 — a gate reports, never hides
            ok = False
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    if failed:
        print(f"\nTRAFFIC ZOOM GATE FAILED — {failed} check(s)")
        return 1
    print("\nTRAFFIC ZOOM GATE PASSED — the graph zooms to what he drew, "
          "and every point says what the encoder was doing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
