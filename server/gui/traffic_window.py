"""The Traffic window: what this PC actually sends to and receives from the phone.

The owner asked for this by name (2026-08-05) and he asked for it for a
reason: he was sure the app keeps talking to a locked phone and eating its
battery, and there was no way for either of us to KNOW. Every previous round
ended in a claim — "it stops, I checked" — and a claim is exactly what he had
already stopped believing.

So this window measures instead of arguing. It draws two lines over time:

- PC -> phone, and phone -> PC, in bytes per second, counted at the socket
  itself (`traffic.MeteredSocket`), so nothing can slip past them.
- A GREY BAND wherever no client was connected. That band is the point of the
  whole window: a locked phone must show a flat zero line INSIDE a grey band,
  and if it ever shows traffic there, this is the evidence.

Underneath, the phone's own numbers (Android TrafficStats, reported in every
heartbeat): what OUR app spent and what the whole device spent, and — the one
that settles the battery question — how much our app spent WHILE IT WAS AWAY,
measured by the phone across the gap it was gone.

BUILD ROUND R4 (owner-approved 2026-08-07, "both spans" answered on P3) adds:

- Two more spans — "Since start" (this process's whole life) and "All (from
  file)" (the complete recording) — read off the UI thread by
  `traffic_history.HistoryJob` and downsampled so a months-long file never
  costs more than a bounded read (see `traffic_history.py`).
- A real Y axis (the 1/2/5 x 10^n round-value ladder) and X-axis time labels,
  replacing the old bare max-and-zero.
- A hover crosshair + readout card, confined to the chart and flipped to the
  other side of the crosshair near an edge so it can never leave the window.

The 2026-08-07 independent grade (Finding 2) caught the Y axis reading in a
DIFFERENT unit per gridline ("1.5 kB/s" over "1000 B/s" over "500 B/s") —
every tick called `human_rate()` on its own value. `_axis_unit` now reads
ONE unit off the axis's own top gridline and `_format_axis_value` labels
every tick as a bare number in it; the unit itself is drawn once, top-left
of the plot.

Everything is drawn with QPainter. No new dependency for a diagnostic window.
"""

import html
import logging
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

import traffic
import traffic_devices
import traffic_history
from config import SETTINGS
from gui.theme import TOKENS, card_shadow, device_color
from gui.traffic_battery import battery_sentence
from gui.sizing import WrapLabel, clamp_to_screen, settle_minimum
from gui.traffic_axis import (
    X_TICK_COUNT, _alpha, _axis_unit, _format_axis_value, _x_label, _x_ticks,
    _y_ticks, human_bytes, human_rate,
)

logger = logging.getLogger(__name__)

REFRESH_MS = 1000
# The spans the owner picks between. "recent" spans read the live in-memory
# ring buffer (traffic.METER.history); every other kind reads traffic.csv
# through traffic_history.HistoryJob — a slower, off-thread path, so they
# carry no `seconds` (their own start time is computed, not fixed: see
# `_history_since`).
#
# "Last 10 hours" and "Today" are the owner's own request (2026-08-14): the
# live ring buffer stops at one hour and the next step up was his whole
# server session, so an evening's work had no picture between the two. They
# are file-backed like the two long spans and cost the same read — a short
# span is NOT a cheaper read, because `read_history` still scans past every
# row before its `since` (measured numbers in `traffic_history.py`'s
# docstring). What they buy is a picture at a readable time resolution, not
# a faster one.
SPANS = [
    ("Last 2 minutes", "recent", 120),
    ("Last 10 minutes", "recent", 600),
    ("Last hour", "recent", 3600),
    ("Last 10 hours", "last10h", None),
    ("Today", "today", None),
    ("Since start", "since_start", None),
    ("All (from file)", "all", None),
]
TEN_HOURS_S = 10 * 3600

def out_color() -> QColor:      # PC -> phone
    """FUNCTIONS, not constants (build round R3). These were two module-level
    QColors, and a module-level palette read evaluates ONCE at import — the
    chart would have kept the dark theme's bright cyan and amber on a white
    card forever, which is precisely the failure DESIGN.md → Live theme
    switching names. Everything else in this file already read TOKENS at
    paint time; these two did not."""
    return QColor(TOKENS["accent"])


def in_color() -> QColor:       # phone -> PC (the warning hue, reused as a
    return QColor(TOKENS["warning"])      # second series)


CHART_MIN = QSize(560, 260)                   # readable at the smallest useful
#                                                size, with room for the axes
HOVER_MARGIN = 12       # px between the crosshair and the card


def history_since(kind: str, now: float) -> float | None:
    """Where a file-backed span STARTS, as unix time — `None` for "All",
    which means "the recording's own beginning" to `read_history`.

    A pure function of (kind, now) on purpose: it is the one place a span's
    meaning is written down, so its gate can assert "Today" really is local
    midnight (never `now - 86400`) without building a window.
    """
    if kind == "since_start":
        return traffic.PROCESS_START
    if kind == "last10h":
        return now - TEN_HOURS_S
    if kind == "today":
        # LOCAL midnight — the owner's own day, not UTC's and not a rolling
        # 24 hours: "Today" that starts at 04:17 because that is when the
        # clock was 24 hours ago would be a different question than the one
        # he asked.
        lt = time.localtime(now)
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    return None      # "all"


def _point_from_sample(sample) -> traffic_history.Point:
    """A raw per-second sample as a `Point` with avg == max (nothing to
    average — it already IS one second)."""
    return traffic_history.Point(
        t=sample.t, out_avg=sample.out_bytes, out_max=sample.out_bytes,
        in_avg=sample.in_bytes, in_max=sample.in_bytes, clients=sample.clients,
        device=sample.device)


def _coalesce(points: list, target: int) -> list:
    """At most one point per pixel, enforced HERE regardless of where the
    points came from: the disk reader already bounds itself to
    `traffic_history_max_buckets` (a few thousand, comfortably above any
    real window width), and this is the cheap second pass that turns that
    into an exact pixel-for-pixel budget for THIS paint — so a window resize
    never has to re-read the file, only re-run this O(n) merge on an
    already-small list."""
    if target <= 0 or len(points) <= target:
        return points
    ratio = len(points) / target
    merged = []
    n = len(points)
    i = 0.0
    while int(i) < n:
        j = min(n, int(i + ratio))
        if j <= int(i):
            j = int(i) + 1
        chunk = points[int(i):j]
        # Same "last ACTIVE device wins" rule as the disk reader
        # (`traffic_history.read_history`) — an idle heartbeat second from a
        # device about to be replaced must not steal a merged pixel's colour
        # from the device that actually sent the bytes in it.
        chunk_device = ""
        for p in chunk:
            if p.device and (p.out_avg or p.in_avg or p.out_max or p.in_max):
                chunk_device = p.device
        # ...and, exactly like the disk reader, the device CARRIES FORWARD
        # across a merged pixel that moved no bytes at all. Without this the
        # live spans have the same defect the long spans had (owner report
        # 2026-08-14): the line sits at zero most of the time, an all-idle
        # pixel keeps "", and "" paints as the neutral grey. The two paths
        # must agree or the same session colours differently depending on
        # which span happens to be open — which is what
        # `test_coalesce_agrees_with_the_disk_reader` exists to hold.
        if not chunk_device and merged:
            chunk_device = merged[-1].device
        merged.append(traffic_history.Point(
            t=chunk[len(chunk) // 2].t,
            out_avg=sum(p.out_avg for p in chunk) / len(chunk),
            out_max=max(p.out_max for p in chunk),
            in_avg=sum(p.in_avg for p in chunk) / len(chunk),
            in_max=max(p.in_max for p in chunk),
            clients=max(p.clients for p in chunk),
            device=chunk_device,
        ))
        i += ratio
    return merged


class _LegendMark(QWidget):
    """One legend/status swatch — DRAWN with QPainter, never a font glyph or
    emoji. This project's rule holds on desktop exactly as it does on the
    phone: the owner's phone once rendered a glyph mark (✥) as a blunt
    cross, and DESIGN.md's icon rule ("a mark is drawn, never a font
    character") applies here too, not just to SVG toolbar icons.

    `color_fn` is a CALLABLE, not a QColor — same reason `out_color()` /
    `in_color()` above are functions: a color captured once at construction
    would freeze whichever palette was active when the window was built and
    never follow a runtime theme flip (DESIGN.md → Live theme switching).
    """

    def __init__(self, color_fn, kind: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._color_fn = color_fn
        self._kind = kind
        self.setFixedSize(20, 14)  # layout-law: exempt - a fixed-size decorative colour swatch, never a text-carrying widget; its sibling QLabel carries the real content and wraps freely

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self._color_fn()
        rect = QRectF(self.rect()).adjusted(1, 2, -1, -2)
        if self._kind == "series":
            # Mirrors what the chart itself draws for this series — a faded
            # fill under a solid line — so the swatch reads as "this IS that
            # line's colour", not an arbitrary decoration.
            fill = QColor(color)
            fill.setAlpha(46)
            painter.fillRect(rect, fill)
            painter.setPen(QPen(color, 2))
            top = rect.top() + 2
            painter.drawLine(QPointF(rect.left(), top), QPointF(rect.right(), top))
        elif self._kind == "band":
            painter.fillRect(rect, color)
            painter.setPen(QPen(_alpha(TOKENS["text2"], 60), 1))
            painter.drawRect(rect)
        elif self._kind == "dotted":
            painter.setPen(QPen(color, 2, Qt.PenStyle.DotLine))
            y = rect.center().y()
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        elif self._kind == "dot":
            d = min(rect.width(), rect.height())
            circle = QRectF(rect.center().x() - d / 2, rect.center().y() - d / 2, d, d)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(circle)
        painter.end()


class TrafficChart(QWidget):
    """The graph itself: axes, the idle band, two filled/avg lines, a faint
    max hairline on downsampled spans, and the hover crosshair + card."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.points: list = []
        self.start = 0.0
        self.end = 0.0
        self.span_label = ""
        self.downsampled = False
        self.loading = False
        # Grows with the window — the chart IS the content here, so it takes
        # the free space instead of leaving it empty (THE SPACE & LEGIBILITY
        # LAW: nothing starves while its window holds slack).
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(CHART_MIN)
        self.setMouseTracking(True)
        self._hover_x: float | None = None
        self._plot = None   # the last painted plot QRect — hit-testing needs it

    def set_data(self, points: list, start: float, end: float, span_label: str,
                 downsampled: bool, loading: bool = False) -> None:
        self.points, self.start, self.end = points, start, end
        self.span_label, self.downsampled, self.loading = span_label, downsampled, loading
        self.update()

    # -- hover ---------------------------------------------------------

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 — Qt override
        self._hover_x = event.position().x()
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802 — Qt override
        self._hover_x = None
        self.update()
        super().leaveEvent(event)

    # -- painting --------------------------------------------------------

    def _peak_of(self, points: list) -> float:
        peak = 0.0
        for p in points:
            peak = max(peak, p.out_max, p.in_max)
        return peak

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        metrics = QFontMetrics(self.font())
        # Bare numbers only now — the unit is stated ONCE (below), not per
        # label — so the left margin only has to fit the widest plain number.
        pad_l = max(metrics.horizontalAdvance("999.9"),
                    metrics.horizontalAdvance("GB/s")) + 10
        pad_t = metrics.height() + 4      # room for that one-time unit label
        pad_b = metrics.height() + 10
        plot = self.rect().adjusted(pad_l, pad_t, -10, -pad_b)
        painter.fillRect(self.rect(), QColor(TOKENS["surface0"]))
        self._plot = plot
        if plot.width() < 20 or plot.height() < 20:
            painter.end()
            return

        # The plot reads as a PANEL, not as the window's own background — the
        # confirmed-but-mild finding from the independent grade: filling it
        # with `surface0` (identical to the fillRect above) left the chart
        # looking flat, with nothing separating "plot" from "window". One
        # step up the elevation ladder (surface1, the same step every card in
        # this app sits on) plus a hairline edge is the cheap fix.
        painter.fillRect(plot, QColor(TOKENS["surface1"]))
        painter.setPen(QPen(_alpha(TOKENS["text2"], 35), 1))
        painter.drawRect(QRectF(plot).adjusted(0.5, 0.5, -0.5, -0.5))

        if self.loading:
            painter.setPen(QPen(QColor(TOKENS["text2"]), 1))
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter,
                             "Reading traffic.csv…")
            painter.end()
            return

        span = max(1e-6, self.end - self.start)
        pts = _coalesce(self.points, max(1, plot.width()))
        peak = max(1024.0, self._peak_of(pts))
        ticks = _y_ticks(peak)
        axis_max = ticks[-1] if ticks[-1] > 0 else 1.0

        def x_of(t: float) -> float:
            return plot.left() + plot.width() * max(0.0, min(1.0, (t - self.start) / span))

        def y_of(v: float) -> float:
            return plot.bottom() - plot.height() * min(1.0, v / axis_max)

        # The idle band FIRST, behind everything: it is the reading the
        # owner came here for, so it must be visible under the lines, not
        # over them.
        idle_color = _alpha(TOKENS["text2"], 26)
        run_start = None
        for p in pts:
            if p.clients == 0 and run_start is None:
                run_start = p.t
            elif p.clients > 0 and run_start is not None:
                painter.fillRect(int(x_of(run_start)), plot.top(),
                                 max(1, int(x_of(p.t) - x_of(run_start))),
                                 plot.height(), idle_color)
                run_start = None
        if run_start is not None:
            painter.fillRect(int(x_of(run_start)), plot.top(),
                             max(1, int(x_of(self.end) - x_of(run_start))),
                             plot.height(), idle_color)

        # Y gridlines + round-value labels (the 1/2/5 x 10^n ladder), all in
        # ONE unit read off the axis's own top value (Finding 2, 2026-08-07).
        # The unit is drawn ONCE, top-left of the plot, in the padding this
        # paintEvent reserved for it above; every gridline below it is a bare
        # number in that same unit.
        grid = _alpha(TOKENS["text2"], 40)
        axis_unit, axis_div = _axis_unit(axis_max)
        painter.setPen(QPen(QColor(TOKENS["text2"]), 1))
        painter.drawText(4, metrics.ascent(), axis_unit)
        for tick in ticks:
            y = y_of(tick)
            painter.setPen(QPen(grid, 1))
            painter.drawLine(plot.left(), int(y), plot.right(), int(y))
            painter.setPen(QPen(QColor(TOKENS["text2"]), 1))
            label = "0" if tick == 0 else _format_axis_value(tick, axis_div)
            ly = int(y) + (metrics.ascent() // 2 if tick > 0 else metrics.ascent())
            ly = max(plot.top() + metrics.ascent(), min(ly, plot.bottom()))
            painter.drawText(4, ly, label)

        # X axis + time labels.
        painter.setPen(QPen(grid, 1))
        painter.drawLine(plot.left(), plot.bottom(), plot.right(), plot.bottom())
        painter.setPen(QPen(QColor(TOKENS["text2"]), 1))
        for t in _x_ticks(self.start, self.end, X_TICK_COUNT):
            label = _x_label(t, span)
            w = metrics.horizontalAdvance(label)
            lx = min(max(plot.left(), x_of(t) - w / 2), plot.right() - w)
            painter.drawText(int(lx), plot.bottom() + metrics.ascent() + 3, label)

        # PER-DEVICE COLOUR (owner request 2026-08-13). T75 correction
        # (2026-08-14, from his own screenshot): the predicate used to be
        # "does the VISIBLE SPAN hold >1 device" — so a span where only the
        # phone talked fell back to the plain direction colour (blue) while
        # the legend beside it already listed two devices and gave the phone
        # its OWN colour there. Blue meant two things in one window. Rule:
        # once this PC has EVER seen >1 device, always colour by device.
        # `traffic_devices.REGISTRY` is the "ever seen" source — it persists
        # across restarts, which is why the "Devices seen" list can name a
        # device that sent nothing in the visible span at all.
        multi_device = len(traffic_devices.REGISTRY.all()) > 1

        def _segment_color(base: QColor, device: str) -> QColor:
            if not multi_device:
                return base
            if not device:
                # THE DIRECTION'S OWN COLOUR, NEVER GREY (owner order
                # 2026-08-14: "svaki uredjaj na grafikonu se prikazuje svojom
                # bojom" — and grey is not a device's colour, it is the
                # absence of an answer). A stretch reaches here only when the
                # recording itself never named a device for it: `traffic.csv`
                # grew its `device` column on 2026-08-13, so every row older
                # than that carries no attribution at all and no amount of
                # carrying-forward (see `traffic_history.read_history`) can
                # invent one. Painting it the first-known device's colour
                # WOULD invent one. So it falls back to exactly what this
                # chart drew before device colours existed — the direction's
                # own blue/orange — which claims nothing about whose traffic
                # it was. Grey survives for the `Nobody connected` band alone,
                # which is a different statement and has its own legend row.
                return base
            return QColor(device_color(traffic_devices.REGISTRY.index_for(device)))

        # Direction vs identity: once `multi_device` colours BOTH series by
        # device, colour alone no longer says which direction a segment is.
        # Direction stays readable via PEN STYLE instead: out is always the
        # plain solid line this chart has always drawn; in is DASHED whenever
        # `multi_device` is active — no new legend layout needed (task rule),
        # since the two direction items already read "PC → phone" / "phone
        # → PC" and only need one more cue to stay apart from device colour.
        for base_color, avg_pick, max_pick, is_out in (
                (out_color(), lambda p: p.out_avg, lambda p: p.out_max, True),
                (in_color(), lambda p: p.in_avg, lambda p: p.in_max, False)):
            if not pts:
                continue
            line_style = (Qt.PenStyle.SolidLine if (is_out or not multi_device)
                          else Qt.PenStyle.DashLine)
            # Split into RUNS of consecutive points sharing one device — a
            # plain single run, coloured `base_color`, when the span has at
            # most one device (multi_device is False): identical output to
            # before this feature existed.
            runs: list[list] = []
            for p in pts:
                key = p.device if multi_device else ""
                if runs and runs[-1][0] == key:
                    runs[-1][1].append(p)
                else:
                    runs.append([key, [p]])
            prev_last = None
            for key, run_pts in runs:
                color = _segment_color(base_color, key)
                # A one-point run cannot draw a line — borrow the previous
                # run's last point so adjacent segments still connect
                # visually instead of leaving a gap at every device switch.
                seg = ([prev_last] if prev_last is not None else []) + run_pts
                prev_last = run_pts[-1]
                if len(seg) < 2:
                    continue
                path = QPainterPath()
                path.moveTo(QPointF(x_of(seg[0].t), y_of(avg_pick(seg[0]))))
                for p in seg[1:]:
                    path.lineTo(QPointF(x_of(p.t), y_of(avg_pick(p))))
                fill = QPainterPath(path)
                fill.lineTo(QPointF(x_of(seg[-1].t), plot.bottom()))
                fill.lineTo(QPointF(x_of(seg[0].t), plot.bottom()))
                fill.closeSubpath()
                faded = QColor(color)
                faded.setAlpha(46)
                painter.fillPath(fill, faded)
                painter.setPen(QPen(color, 2, line_style))
                painter.drawPath(path)
                if self.downsampled:
                    # The bucket MAX, as a faint hairline above the average —
                    # a spike that a wide bucket's average would otherwise
                    # smooth out of existence stays visible here.
                    mx_path = QPainterPath()
                    mx_path.moveTo(QPointF(x_of(seg[0].t), y_of(max_pick(seg[0]))))
                    for p in seg[1:]:
                        mx_path.lineTo(QPointF(x_of(p.t), y_of(max_pick(p))))
                    mx_color = QColor(color)
                    mx_color.setAlpha(150)
                    painter.setPen(QPen(mx_color, 1, Qt.PenStyle.DotLine))
                    painter.drawPath(mx_path)

        if self._hover_x is not None and pts:
            self._paint_hover(painter, plot, pts, x_of, y_of, metrics)

        painter.end()

    def _paint_hover(self, painter: QPainter, plot, points: list, x_of, y_of,
                     metrics: QFontMetrics) -> None:
        x = self._hover_x
        if x < plot.left() or x > plot.right():
            return
        nearest = min(points, key=lambda p: abs(x_of(p.t) - x))
        px = x_of(nearest.t)

        crosshair = _alpha(TOKENS["text"], 110)
        painter.setPen(QPen(crosshair, 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(px), plot.top(), int(px), plot.bottom())

        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(nearest.t))
        out_line = f"PC → phone: {human_rate(nearest.out_avg)}"
        if self.downsampled and nearest.out_max > nearest.out_avg * 1.05:
            out_line += f"  (peak {human_rate(nearest.out_max)})"
        in_line = f"phone → PC: {human_rate(nearest.in_avg)}"
        if self.downsampled and nearest.in_max > nearest.in_avg * 1.05:
            in_line += f"  (peak {human_rate(nearest.in_max)})"
        if nearest.clients == 0:
            state = "nobody connected"
        elif nearest.clients == 1:
            state = "1 client connected"
        else:
            state = f"{nearest.clients} clients connected"
        lines = [when, out_line, in_line, state]

        card_w = max(metrics.horizontalAdvance(line) for line in lines) + 16
        card_h = len(lines) * (metrics.height() + 2) + 10

        # Flip to the other side of the crosshair whenever the default side
        # would run the card off the widget — it must never leave the
        # window (THE SPACE & LEGIBILITY LAW: nothing the user must read is
        # ever cut off).
        cx = px + HOVER_MARGIN
        if cx + card_w > self.width() - 4:
            cx = px - HOVER_MARGIN - card_w
        cx = max(4, min(cx, self.width() - card_w - 4))
        cy = plot.top() + 8
        cy = max(4, min(cy, self.height() - card_h - 4))

        card_rect = QRectF(cx, cy, card_w, card_h)
        painter.setPen(QPen(_alpha(TOKENS["text2"], 70), 1))
        painter.setBrush(QColor(TOKENS["surface2"]))
        painter.drawRoundedRect(card_rect, 6, 6)
        painter.setPen(QPen(QColor(TOKENS["text"])))
        ty = cy + metrics.ascent() + 5
        for line in lines:
            painter.drawText(int(cx + 8), int(ty), line)
            ty += metrics.height() + 2


class TrafficWindow(QDialog):
    """Header numbers + the chart + the recording footer."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Traffic — what this PC sends to the phone")
        self._settled = False   # the minimum is measured on first show

        self._history = traffic_history.HistoryJob()
        self._history_points: list = []
        self._history_kind: str | None = None
        self._history_next_at = 0.0
        # NO `_history_loading` flag lives here any more: the overlay is
        # derived from `HistoryJob.pending_key` (see `_refresh`), because a
        # flag only a successful poll could clear is a flag that outlives
        # the work the moment a result is dropped.

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        self.out_label = WrapLabel("—")
        self.in_label = WrapLabel("—")
        # SESSION LENGTH + RATE (owner request 2026-08-13, his first two
        # asks beside "this session X MB"): one line, always shown — it
        # needs no phone connected to mean something, unlike the phone/gap
        # lines below it, which stay honest about what they cannot say yet.
        self.duration_label = WrapLabel("—")
        # WHICH DEVICES (owner's own refinement of the same request): "list
        # them — a device with this resolution, a device with that
        # resolution — and even better with a name". ONE ROW PER DEVICE, a
        # DRAWN swatch (`_LegendMark`, same as the legend below — DESIGN.md:
        # marks are drawn, not painted characters) beside a PLAIN, single-
        # line QLabel — never a rich-text paragraph that wraps.
        #
        # Round 2 (owner's coordinator, 2026-08-13, after photographing this
        # window with two real devices staged): the first version put the
        # whole sentence — title, both devices, both HTML colour spans — into
        # ONE wrapping RichText QLabel. It measured differently under every
        # tool that looked at it: Qt's own `heightForWidth` (rich-text
        # document layout) said 42px, the audit's plain
        # `QFontMetrics.boundingRect` over the same markup-laden STRING said
        # 54px, and forcing the label to the larger of the two then starved
        # its SIBLINGS of the vertical budget `_computed_minimum` had given
        # them. Three unrelated numbers fighting over one box is not a size
        # bug to patch, it is the wrong widget: a sentence that WRAPS can
        # never be measured the same way twice by three different callers,
        # so this list no longer wraps at all — each device is its own row,
        # each row is short enough at the window's floor width that it never
        # needs a second line, and "how tall is one line of plain text" is a
        # question every measurer in this codebase already agrees on.
        self.devices_title = QLabel("Devices seen:")
        self.devices_title.setObjectName("caption")
        self.devices_rows_layout = QVBoxLayout()
        self.devices_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.devices_rows_layout.setSpacing(2)
        self._device_row_widgets: list[QWidget] = []
        self.phone_label = WrapLabel("—")
        self.gap_label = WrapLabel("—")
        # WHAT THE APP COSTS THE BATTERY WHILE IT RUNS (T80d, owner request
        # 2026-08-14). It sits beside the traffic because it answers the same
        # class of question with the same method: the PHONE measures itself
        # and reports it on the existing heartbeat, so every device answers
        # for its own hardware, not only his —
        # lang-ok: owner quote
        # "nije samo do mog uređaja već za svaki treba da predvidimo".
        # A simulated number was refused and may not return: an emulator has
        # no battery and reports a fixed fake value, which would look
        # authoritative and mean nothing. The line that matters most to him is
        # the RUNNING cost, not the background one, which is why the draw is
        # reported per session and averaged over the readings that carried one.
        self.battery_label = WrapLabel("—")
        for label in (self.out_label, self.in_label, self.duration_label,
                      self.phone_label, self.gap_label, self.battery_label):
            label.setWordWrap(True)   # ladder step 2: reflow before a wider window
            # AND THE LAYOUT MUST ACTUALLY ASK (found 2026-08-13 by the Qt
            # audit, the first time this window was photographed with real
            # data in it). `setWordWrap(True)` alone only lets a QLabel wrap —
            # it does not make its parent layout allocate the second line,
            # because a QVBoxLayout consults `heightForWidth` ONLY when the
            # widget's size policy says it has one. Without this the device
            # legend wrapped to two lines inside a 32 px box and the audit
            # read it as ELIDED: 'needs 48px height, has 32'. The whole
            # reflow step of the ladder was mute here, and it was invisible
            # for as long as every one of these lines happened to be short
            # enough to fit — which is exactly until a second device appeared.
            policy = label.sizePolicy()
            policy.setHeightForWidth(True)
            label.setSizePolicy(policy)
        self.duration_label.setObjectName("caption")
        self.phone_label.setObjectName("caption")
        self.gap_label.setObjectName("caption")
        self.battery_label.setObjectName("caption")
        root.addWidget(self.out_label)
        root.addWidget(self.in_label)
        root.addWidget(self.duration_label)
        root.addWidget(self.devices_title)
        root.addLayout(self.devices_rows_layout)
        root.addWidget(self.phone_label)
        root.addWidget(self.gap_label)
        root.addWidget(self.battery_label)

        self.chart = TrafficChart(self)
        card_shadow(self.chart)
        root.addWidget(self.chart, 1)   # the chart takes every spare pixel

        # The legend, as a grid of discrete ITEMS — never a wrapping sentence.
        # It used to be one QLabel with "■"/"▨"/"····" glyph characters, which
        # failed two ways at once: every glyph painted in the same caption
        # grey (the two series are the window's whole subject and the legend
        # could not tell them apart, worst on light where both squares came
        # out identically dark), and the sentence wrapped mid-item, orphaning
        # "grey band" onto its own line between two keys. Each item here is
        # one atomic (mark, label) pair that can never be split, and the
        # marks are DRAWN in the chart's own live colours (`out_color()` /
        # `in_color()`), not painted text.
        legend_grid = QGridLayout()
        legend_grid.setContentsMargins(0, 0, 0, 0)
        legend_grid.setHorizontalSpacing(24)
        legend_grid.setVerticalSpacing(4)
        legend_items = [
            (out_color, "series", "PC → phone"),
            # T75: once >1 device has ever connected, both lines colour by
            # DEVICE and direction is told apart by pen style instead — the
            # word "dashed" here is the reader's only cue, since the swatch
            # itself stays a plain solid mark (no new legend layout, per
            # task) and always shows the plain direction colour.
            (in_color, "series", "phone → PC (dashed once >1 device is known)"),
            (lambda: _alpha(TOKENS["text2"], 26), "band", "Nobody connected"),
            (lambda: QColor(TOKENS["text2"]), "dotted", "Peak within a bucket (long spans only)"),
        ]
        for i, (color_fn, kind, text) in enumerate(legend_items):
            row, col = divmod(i, 2)
            item = QHBoxLayout()
            item.setSpacing(6)
            item.addWidget(_LegendMark(color_fn, kind))
            label = QLabel(text)
            label.setObjectName("caption")
            item.addWidget(label)
            item.addStretch()
            legend_grid.addLayout(item, row, col)
        root.addLayout(legend_grid)

        # The explanation moved OUT of the legend (rules/GUI.md's own fix for
        # this exact pattern) — free prose that is allowed to wrap, next to a
        # legend whose items never do.
        legend_note = QLabel(
            "A locked phone must show a flat line inside the grey band — "
            "that is the evidence this window exists to give."
        )
        legend_note.setObjectName("caption")
        legend_note.setWordWrap(True)
        root.addWidget(legend_note)

        controls = QHBoxLayout()
        self.span_combo = QComboBox()
        for i, (name, _, _) in enumerate(SPANS):
            self.span_combo.addItem(name, i)
        self.span_combo.currentIndexChanged.connect(self._on_span_changed)
        controls.addWidget(self.span_combo)
        # "Record to file" used to be a CHECKBOX the user cannot click
        # (setEnabled(False)) standing in for a status the app decides on its
        # own — nothing turns recording off except a disk write failure (see
        # `traffic.py`'s `_append_csv`). A disabled control that offers a
        # tick affordance is a promise the window does not keep; an honest
        # status line makes no such promise. Same drawn-mark rule as the
        # legend, reused rather than re-invented.
        self._recording = True
        record_row = QWidget()
        record_layout = QHBoxLayout(record_row)
        record_layout.setContentsMargins(0, 0, 0, 0)
        record_layout.setSpacing(6)
        self.record_dot = _LegendMark(
            lambda: QColor(TOKENS["success"] if self._recording else TOKENS["error"]),
            "dot")
        self.record_label = QLabel("Recording to file")
        self.record_label.setObjectName("caption")
        record_layout.addWidget(self.record_dot)
        record_layout.addWidget(self.record_label)
        record_row.setToolTip(str(SETTINGS.traffic_csv_path))
        controls.addWidget(record_row)
        controls.addStretch()
        open_btn = QPushButton("Open the recording")
        open_btn.clicked.connect(self._open_recording)
        controls.addWidget(open_btn)
        reset_btn = QPushButton("Reset counters")
        reset_btn.clicked.connect(self._reset)
        controls.addWidget(reset_btn)
        root.addLayout(controls)

        self.path_label = QLabel(str(SETTINGS.traffic_csv_path))
        self.path_label.setObjectName("caption")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.path_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(REFRESH_MS)
        self._refresh()

    # -- the law's computed minimum ----------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802 — Qt override
        """Measured on first SHOW, never in __init__ — the theme's font only
        resolves when Qt polishes the widget, and measuring before that
        under-shoots every string by roughly a tenth (the 2026-08-05 lesson
        that cost the Controls editor a second release)."""
        super().showEvent(event)
        if self._settled:
            return
        self._settled = True
        # The theme's `min-width: 92px` is a floor for an EMPTY combo, and Qt
        # takes it as permission to shrink this one under its own longest
        # entry — "Last 10 minutes" came out cut at 131 px against the 140 it
        # needs. Measured here, after the polish that resolves the QSS font:
        # in the constructor the same call pinned the UNTHEMED 114 and made it
        # worse. The control asks for what its content needs (ladder step 1);
        # the settle below then has to honour it (step 3).
        self.span_combo.setMinimumWidth(self.span_combo.sizeHint().width())
        # One implementation for every window (gui/sizing.py): the loop that
        # used to live here asked `minimumSizeHint`, which quotes a WRAPPING
        # label at one line — and this window's away-gap sentence is exactly
        # such a label. It cost this window 16 px, and Qt spends a shortfall by
        # OVERLAPPING: the chart was drawn across the caption underneath it.
        size = settle_minimum(self, self._computed_minimum(), QSize(760, 560))
        self.resize(max(size.width(), 760), max(size.height(), 560))
        # LAST, after the resize — this is where the geometry is final, and
        # this window grows the most of the three (owner report 2026-08-12:
        # a child grown in place hangs off whichever edge it opened near).
        clamp_to_screen(self)

    def _computed_minimum(self) -> QSize:
        """MEASURED, never guessed (THE SPACE & LEGIBILITY LAW).

        Width = the widest real row this window can show — the recording
        path wraps and the legend is now a 2-column grid of short items, so
        the floor is the control row, which cannot wrap. Height = the four
        header lines, the chart's own minimum, the legend grid + its
        explanatory note, and the footer."""
        metrics = QFontMetrics(self.font())
        button_pad, spacing = 40, 8
        record_label_w = max(metrics.horizontalAdvance("Recording to file"),
                             metrics.horizontalAdvance("Recording stopped"))
        controls_row = (metrics.horizontalAdvance(max((n for n, _, _ in SPANS), key=len))
                        + 56
                        + record_label_w + 20 + 6 + 20   # dot mark + spacing + margins
                        + metrics.horizontalAdvance("Open the recording") + button_pad
                        + metrics.horizontalAdvance("Reset counters") + button_pad
                        + 3 * spacing)
        width = max(CHART_MIN.width(), controls_row) + 36
        rows = metrics.height() + 6
        height = (rows * 6            # out/in/duration/phone/gap/battery: one
                                      # line each
                  + rows * 3          # devices title + up to two device rows —
                                      # a FLOOR ONLY: `settle_minimum` grows
                                      # this in place from the real, currently-
                                      # built rows (`_rebuild_device_rows`,
                                      # single-line, never wrapping), so a
                                      # third or fourth device widens the
                                      # window's declared minimum on its own
                                      # rather than needing a bigger guess here
                  + CHART_MIN.height()
                  + rows * 2          # legend grid (two rows of marks)
                  + rows * 2          # legend note (wraps to two at the floor)
                  + rows * 2          # control row + the path line
                  + 60)               # margins and spacings
        return QSize(width, height)

    # -- refresh -----------------------------------------------------------

    def _on_span_changed(self) -> None:
        """A span switch to a file-backed span drops whatever the last one
        showed and forces an immediate read — a stale "All (from file)"
        graph must never be shown under a "Since start" label just because
        the file read has not finished yet."""
        idx = self.span_combo.currentData()
        if idx is None:
            return
        _, kind, _ = SPANS[idx]
        if kind != "recent":
            self._history_points = []
            self._history_kind = None
            self._history_next_at = 0.0
        self._refresh()

    def _maybe_start_history(self, kind: str, since: float | None) -> None:
        """Kicks off a background read when the span just changed, or the
        periodic re-read interval elapsed.

        A read already in flight for THIS SAME span is left alone (a second
        one would read the same file for the same answer). A read in flight
        for a DIFFERENT span is SUPERSEDED, never waited for — that early
        return was the 2026-08-14 defect: a span switch made while a read
        was running started no read of its own, and the older read's data
        then landed and was drawn under the new span's label.
        """
        now = time.time()
        if kind == self._history_kind and now < self._history_next_at:
            return
        if self._history.pending_key == kind:
            return
        self._history.start(kind, since, SETTINGS.traffic_history_max_buckets)
        self._history_next_at = now + SETTINGS.traffic_history_refresh_s

    def _rebuild_device_rows(self, known: list[dict]) -> None:
        """One row per device — a DRAWN colour swatch (`_LegendMark`) + a
        PLAIN, single-line `QLabel` — never the wrapping rich-text paragraph
        this used to be (see the constructor's own note on why: three
        different Qt/audit measurers disagreed about how tall one wrapping
        RichText label needed to be). `setUpdatesEnabled(False)` around the
        teardown/rebuild avoids a visible flash on every 1 s tick when the
        list has not actually changed — cheap insurance since this runs on
        every refresh."""
        self.devices_rows_layout.setEnabled(False)
        for widget in self._device_row_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self._device_row_widgets = []
        if not known:
            row = QLabel("No device has connected since this server started.")
            row.setObjectName("caption")
            self.devices_rows_layout.addWidget(row)
            self._device_row_widgets.append(row)
        else:
            for entry in known:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(6)
                color = device_color(entry["index"])
                mark = _LegendMark(lambda c=color: QColor(c), "dot")
                label = QLabel(entry["label"])
                label.setObjectName("caption")
                row_layout.addWidget(mark)
                row_layout.addWidget(label)
                row_layout.addStretch()
                self.devices_rows_layout.addWidget(row)
                self._device_row_widgets.append(row)
        self.devices_rows_layout.setEnabled(True)

    def _refresh(self) -> None:
        try:
            snap = traffic.METER.snapshot()
            idx = self.span_combo.currentData()
            idx = idx if idx is not None else 0
            name, kind, seconds = SPANS[idx]
            now = time.time()

            if kind == "recent":
                samples = traffic.METER.history(seconds)
                points = [_point_from_sample(s) for s in samples]
                self.chart.set_data(points, now - seconds, now, name, downsampled=False)
            else:
                since = history_since(kind, now)
                self._maybe_start_history(kind, since)
                result = self._history.poll()
                if result is not None:
                    got_kind, points = result
                    # THE RULE, and it is the whole fix (2026-08-14): a
                    # result is adopted only under ITS OWN key. A read for a
                    # span the owner has clicked away from is DROPPED — it is
                    # never re-labelled as the span now selected.
                    if got_kind == kind:
                        self._history_points = points
                        self._history_kind = kind
                    else:
                        logger.info("Traffic window: dropped a %r result while "
                                    "showing %r", got_kind, kind)
                # The overlay is read off the JOB, never off a flag of our
                # own: it is up exactly while a read for the SELECTED span is
                # in flight and we hold nothing for that span yet, so it
                # cannot outlive the work (the job clears `pending_key` in a
                # `finally`) and it cannot linger over another span's data.
                loading = (self._history.pending_key == kind
                           and self._history_kind != kind)
                start = since if since is not None else (
                    self._history_points[0].t if self._history_points else now)
                self.chart.set_data(self._history_points, start, now, name,
                                    downsampled=True, loading=loading)

            clients = snap["clients"]
            self.out_label.setText(
                f"PC → phone:  {human_rate(snap['out_per_s'])}"
                f"     ·  this session {human_bytes(snap['total_out'])}"
                f"     ·  {clients} client{'s' if clients != 1 else ''} connected")
            self.in_label.setText(
                f"phone → PC:  {human_rate(snap['in_per_s'])}"
                f"     ·  this session {human_bytes(snap['total_in'])}")

            # SESSION LENGTH + RATE (owner's asks #1 and #2, 2026-08-13).
            duration_s, mb_h = traffic_devices.duration_and_rate(
                snap["total_out"] + snap["total_in"], snap["since"], now)
            self.duration_label.setText(
                f"Session length: {traffic_devices.human_duration(duration_s)}"
                + (f"  ·  average rate: {mb_h:.1f} MB/h"
                   if mb_h is not None else ""))

            # WHICH DEVICES (owner's own refinement, same request): every
            # resolution — named where a name was ever learned — that has
            # connected on this PC, oldest first, each with the same colour
            # swatch its line segments wear on the chart above. Rebuilt every
            # tick — a device list changes rarely (once per NEW resolution
            # ever seen), so tearing down and re-adding a handful of rows a
            # second costs nothing worth avoiding, and it is the only way a
            # newly-seen device's row appears without a window resize.
            self._rebuild_device_rows(traffic_devices.REGISTRY.all())

            phone = snap["phone"]
            self.phone_label.setText(
                "The phone's own count since it connected — this app "
                f"{human_bytes(phone['app_rx'] + phone['app_tx'])}, "
                f"whole phone {human_bytes(phone['dev_rx'] + phone['dev_tx'])}"
                if phone else
                "The phone reports its own counters while it is connected.")
            gap = snap["away_gap"]
            self.gap_label.setText(
                "While the phone was away for "
                f"{int(gap['seconds'] // 60)} min {int(gap['seconds'] % 60)} s: "
                f"this app used {human_bytes(gap['app_rx'] + gap['app_tx'])}, "
                f"the whole phone {human_bytes(gap['dev_rx'] + gap['dev_tx'])}"
                if gap else
                "Lock the phone and unlock it: this line then says what the "
                "app spent while it was gone, measured by the phone itself.")
            # T80d — what the app costs the phone's battery while it RUNS.
            # `battery_sentence` owns every word of it, including the two
            # honest "this device does not report it" cases: the number can
            # only be measured on the handset, and a device that refuses must
            # say so rather than show a blank or a zero.
            self.battery_label.setText(
                battery_sentence(traffic.METER.battery(), clients))
            self._recording = bool(snap["recording"])
            self.record_label.setText(
                "Recording to file" if self._recording else "Recording stopped")
            self.record_dot.update()
        except Exception:
            # A diagnostic window may never be the thing that takes the app
            # down — the whole point of it is to survive a bad moment.
            logger.exception("Traffic window refresh failed")

    def _open_recording(self) -> None:
        import os
        import subprocess
        path = Path(SETTINGS.traffic_csv_path)
        try:
            if path.exists():
                subprocess.Popen(["explorer.exe", "/select,", str(path)])
            else:
                os.startfile(str(path.parent))
        except OSError as e:
            logger.error("Could not open the recording folder: %s", e)

    def _reset(self) -> None:
        traffic.METER.reset()
        self._history_points = []
        self._history_kind = None
        self._history_next_at = 0.0
        self._refresh()

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt override
        self._timer.stop()
        super().closeEvent(event)
