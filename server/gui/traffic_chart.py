"""The Traffic chart widget — axes, the idle band, the two series, the
hover card, and (owner request 2026-08-15) the ZOOM: a mouse drag draws a
rectangle over the plot and zooms the time axis to it, +/−/Reset step it,
and the hover card names what the encoder was doing at that second.

Split off `traffic_window.py` on 2026-08-15 at the structure law's wall, by
RESPONSIBILITY: the window owns the numbers, the picker and the recording
footer; this owns the PICTURE. `traffic_zoom.ViewRange` (pure) is the one
place both sides read the time window from — the chart maps pixels through
it, the window decides what to READ for it.
"""

import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

import traffic_devices
import traffic_history
import traffic_stream
from gui import traffic_zoom
from gui.theme import TOKENS, device_color
from gui.traffic_axis import (
    X_TICK_COUNT, _alpha, _axis_unit, _format_axis_value, _x_label, _x_ticks,
    _y_ticks, _y_ticks_range, human_rate,
)


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


def _point_from_sample(sample) -> traffic_history.Point:
    """A raw per-second sample as a `Point` with avg == max (nothing to
    average — it already IS one second)."""
    return traffic_history.Point(
        t=sample.t, out_avg=sample.out_bytes, out_max=sample.out_bytes,
        in_avg=sample.in_bytes, in_max=sample.in_bytes, clients=sample.clients,
        device=sample.device, stream=sample.stream)


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
        chunk_stream = None
        for p in chunk:
            if p.device and (p.out_avg or p.in_avg or p.out_max or p.in_max):
                chunk_device = p.device
            if p.stream and (p.out_avg or p.in_avg or p.out_max or p.in_max):
                chunk_stream = p.stream
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
            stream=chunk_stream,
        ))
        i += ratio
    return merged


class TrafficChart(QWidget):
    """The graph itself: axes, the idle band, two filled/avg lines, a faint
    max hairline on downsampled spans, the hover crosshair + card, and the
    zoom rectangle (T105).

    `view` is the time window drawn; the window that owns this chart sets its
    FULL span with every refresh and reads `view.start/end` back to decide
    what to fetch. `zoomed` fires whenever the drag or the buttons changed
    the view — the window then re-reads a file-backed span for it."""

    zoomed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.view = traffic_zoom.ViewRange()
        # The drag: in the FULL view a rectangle (x0,y0 → x1,y1) that will be
        # zoomed to; ZOOMED, a pan — the press point plus the view it started
        # from (owner decision 2026-08-15, option B: "zoomed = only move,
        # full view = only zoom").
        self._drag_x0: float | None = None
        self._drag_y0: float | None = None
        self._drag_x1: float | None = None
        self._drag_y1: float | None = None
        self._pan_from: tuple | None = None   # (x, y, start, end, y_lo, y_hi)
        self._panned = False                   # a pan happened → re-read on release
        self.points: list = []
        self.start = 0.0
        self.end = 0.0
        self.y_lo = 0.0          # the rate window really drawn (auto or set)
        self.y_hi = 1.0
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
        self._hover_y: float | None = None
        self._plot = None   # the last painted plot QRect — hit-testing needs it

    def set_data(self, points: list, start: float, end: float, span_label: str,
                 downsampled: bool, loading: bool = False) -> None:
        """`start`/`end` is the FULL span the picker selected; the plot draws
        `self.view` (all of it unless zoomed) and shows only the points that
        fall inside it."""
        self.view.set_full(start, end)
        self.points = points
        self.start, self.end = self.view.start, self.view.end
        self.span_label, self.downsampled, self.loading = span_label, downsampled, loading
        self.update()

    # -- zoom (T104 / T105, 2D since the owner's option B) -----------------

    def zoom_in(self) -> None:
        if self.view.zoom_in_at(self._hover_time(), self._hover_rate()):
            self._view_changed()

    def zoom_out(self) -> None:
        if self.view.zoom_out_at(self._hover_time(), self._hover_rate()):
            self._view_changed()

    def zoom_reset(self) -> None:
        if self.view.reset():
            self._view_changed()

    def _hover_time(self) -> float | None:
        if self._hover_x is None or self._plot is None:
            return None
        return traffic_zoom.px_to_time(self._hover_x, self._plot.left(),
                                       self._plot.right(), self.start, self.end)

    def _hover_rate(self) -> float | None:
        if self._hover_y is None or self._plot is None:
            return None
        return traffic_zoom.px_to_rate(self._hover_y, self._plot.top(),
                                       self._plot.bottom(), self.y_lo, self.y_hi)

    def _view_changed(self) -> None:
        self.start, self.end = self.view.start, self.view.end
        self.update()
        self.zoomed.emit()

    def mousePressEvent(self, event) -> None:  # noqa: N802 — Qt override
        pos = event.position()
        if (event.button() == Qt.MouseButton.LeftButton and self._plot is not None
                and self._plot.contains(pos.toPoint())):
            if self.view.is_zoomed():
                # ZOOMED: the drag MOVES the slice (option B).
                v = self.view
                self._pan_from = (pos.x(), pos.y(), v.start, v.end, v.y_lo, v.y_hi)
                self._panned = False
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            else:
                self._drag_x0 = self._drag_x1 = pos.x()
                self._drag_y0 = self._drag_y1 = pos.y()
            self.update()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 — Qt override
        if self._pan_from is not None:
            self._pan_from = None
            self._refresh_cursor()
            if self._panned:
                self._panned = False
                self.zoomed.emit()     # ONE re-read per pan, on release
            return
        if self._drag_x0 is None:
            return super().mouseReleaseEvent(event)
        x0, y0 = self._drag_x0, self._drag_y0
        x1, y1 = event.position().x(), event.position().y()
        self._drag_x0 = self._drag_x1 = self._drag_y0 = self._drag_y1 = None
        if self._plot is not None and traffic_zoom.is_drag(x0, x1):
            plot = self._plot
            t0 = traffic_zoom.px_to_time(x0, plot.left(), plot.right(), self.start, self.end)
            t1 = traffic_zoom.px_to_time(x1, plot.left(), plot.right(), self.start, self.end)
            r0 = r1 = None
            if traffic_zoom.is_drag(y0, y1):
                # A rectangle with HEIGHT limits the rate axis too (2D zoom);
                # a flat one keeps Y automatic.
                r0 = traffic_zoom.px_to_rate(y0, plot.top(), plot.bottom(), self.y_lo, self.y_hi)
                r1 = traffic_zoom.px_to_rate(y1, plot.top(), plot.bottom(), self.y_lo, self.y_hi)
            if self.view.set_view(t0, t1, r0, r1):
                self._view_changed()
                self._refresh_cursor()
                return
        self.update()

    def wheelEvent(self, event) -> None:  # noqa: N802 — Qt override
        """The wheel zooms too — toward the mouse, like every map."""
        self._hover_x = event.position().x()
        self._hover_y = event.position().y()
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_in()
        elif delta < 0:
            self.zoom_out()
        self._refresh_cursor()
        event.accept()

    def _refresh_cursor(self) -> None:
        """An open hand over a zoomed plot says "this drags"; the arrow over
        the full view says "this draws"."""
        if self._pan_from is not None:
            return
        self.setCursor(Qt.CursorShape.OpenHandCursor if self.view.is_zoomed()
                       else Qt.CursorShape.ArrowCursor)

    # -- hover ---------------------------------------------------------

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 — Qt override
        pos = event.position()
        self._hover_x, self._hover_y = pos.x(), pos.y()
        if self._pan_from is not None and self._plot is not None:
            x, y, start, end, y_lo, y_hi = self._pan_from
            plot = self._plot
            dt = -(pos.x() - x) * (end - start) / max(1.0, plot.width())
            dy = (pos.y() - y) * ((y_hi - y_lo) if y_hi is not None else 0.0) \
                / max(1.0, plot.height())
            # Pan from the press-time view, never incrementally — an
            # incremental pan drifts and can never return to where it began.
            v = self.view
            v.start, v.end, v.y_lo, v.y_hi = start, end, y_lo, y_hi
            if v.pan(dt, dy) or (v.start, v.end) != (start, end):
                self._panned = True
            self.start, self.end = v.start, v.end
        elif self._drag_x0 is not None:
            self._drag_x1, self._drag_y1 = pos.x(), pos.y()
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802 — Qt override
        self._hover_x = self._hover_y = None
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
        # Only what falls inside the VIEW is drawn — the full span's points
        # stay in `self.points`, so a zoom of a live span costs no re-read
        # and a zoom out has them at hand.
        visible = [p for p in self.points if self.start <= p.t <= self.end]
        pts = _coalesce(visible, max(1, plot.width()))
        # THE RATE AXIS: automatic (0 .. the visible peak's top gridline)
        # until a rectangle set it, then exactly the window he drew (2D zoom,
        # owner option B). The whole span's own top gridline is the CEILING
        # a pan or a zoom-out may reach — handed to the view here, since only
        # this paint knows the ladder.
        full_ticks = _y_ticks(max(1024.0, self._peak_of(self.points)))
        self.view.y_cap = full_ticks[-1] if full_ticks[-1] > 0 else 1.0
        if self.view.has_y():
            y_lo, y_hi = self.view.y_lo, self.view.y_hi
            ticks = _y_ticks_range(y_lo, y_hi)
        else:
            peak = max(1024.0, self._peak_of(pts))
            ticks = _y_ticks(peak)
            y_lo, y_hi = 0.0, (ticks[-1] if ticks[-1] > 0 else 1.0)
        self.y_lo, self.y_hi = y_lo, y_hi
        axis_max = y_hi
        y_span = max(1e-9, y_hi - y_lo)

        def x_of(t: float) -> float:
            return plot.left() + plot.width() * max(0.0, min(1.0, (t - self.start) / span))

        def y_of(v: float) -> float:
            # NOT clamped: a value outside the rate window is drawn outside
            # the plot and CLIPPED, so the curve keeps its true slope at the
            # window's edge instead of flattening onto it.
            return plot.bottom() - plot.height() * ((v - y_lo) / y_span)

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
            if y < plot.top() - 1 or y > plot.bottom() + 1:
                continue
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
        painter.save()
        painter.setClipRect(plot)     # the series may leave a zoomed rate window
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
        painter.restore()

        if self._drag_x0 is not None and self._drag_x1 is not None:
            self._paint_drag(painter, plot)
        elif self._hover_x is not None and pts:
            self._paint_hover(painter, plot, pts, x_of, y_of, metrics)

        painter.end()

    def _paint_drag(self, painter: QPainter, plot) -> None:
        """The rectangle he is drawing (T105) — visible WHILE the button is
        held: a translucent accent rectangle, edges clamped to the plot, so
        what will be zoomed to is never a guess. A rectangle too flat to set
        the rate axis (< DRAG_MIN_PX tall) is drawn the full plot height,
        which is exactly what it will zoom to."""
        x0 = min(max(plot.left(), self._drag_x0), plot.right())
        x1 = min(max(plot.left(), self._drag_x1), plot.right())
        left, right = (x0, x1) if x0 <= x1 else (x1, x0)
        y0, y1 = self._drag_y0, self._drag_y1
        if y0 is not None and y1 is not None and traffic_zoom.is_drag(y0, y1):
            top = min(max(plot.top(), min(y0, y1)), plot.bottom())
            bottom = min(max(plot.top(), max(y0, y1)), plot.bottom())
        else:
            top, bottom = plot.top(), plot.bottom()
        rect = QRectF(left, top, max(1.0, right - left), max(1.0, bottom - top))
        painter.setPen(QPen(_alpha(TOKENS["accent"], 200), 1, Qt.PenStyle.DashLine))
        painter.setBrush(_alpha(TOKENS["accent"], 45))
        painter.drawRect(rect)
        if traffic_zoom.is_drag(self._drag_x0, self._drag_x1):
            t0 = traffic_zoom.px_to_time(left, plot.left(), plot.right(), self.start, self.end)
            t1 = traffic_zoom.px_to_time(right, plot.left(), plot.right(), self.start, self.end)
            label = (time.strftime("%H:%M:%S", time.localtime(t0)) + " – "
                     + time.strftime("%H:%M:%S", time.localtime(t1)))
            if bottom - top < plot.height():
                r_lo = traffic_zoom.px_to_rate(bottom, plot.top(), plot.bottom(), self.y_lo, self.y_hi)
                r_hi = traffic_zoom.px_to_rate(top, plot.top(), plot.bottom(), self.y_lo, self.y_hi)
                label += f"  ·  {human_rate(r_lo)} – {human_rate(r_hi)}"
            metrics = QFontMetrics(self.font())
            w = metrics.horizontalAdvance(label) + 12
            lx = min(max(plot.left(), (left + right) / 2 - w / 2), plot.right() - w)
            ly = max(plot.top() + 6, top - metrics.height() - 10)
            if ly + metrics.height() + 6 > bottom and top - metrics.height() - 10 < plot.top():
                ly = plot.top() + 6
            card = QRectF(lx, ly, w, metrics.height() + 6)
            painter.setPen(QPen(_alpha(TOKENS["text2"], 70), 1))
            painter.setBrush(QColor(TOKENS["surface2"]))
            painter.drawRoundedRect(card, 4, 4)
            painter.setPen(QPen(QColor(TOKENS["text"])))
            painter.drawText(int(lx + 6), int(ly + 3 + metrics.ascent()), label)

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
        # WHO and WHAT (T106): the device that owned the second, and what the
        # encoder was doing — quality, the slice, the zoom step. A number
        # without its cause is half a measurement.
        if nearest.device:
            lines.append("device: " + traffic_devices.REGISTRY.label_for_key(nearest.device))
        if nearest.clients or nearest.stream:
            lines.extend(traffic_stream.hover_lines(nearest.stream))

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

