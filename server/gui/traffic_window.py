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

Everything is drawn with QPainter. No new dependency for a diagnostic window.
"""

import logging
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

import traffic
from config import SETTINGS
from gui.theme import TOKENS, card_shadow
from gui.sizing import settle_minimum

logger = logging.getLogger(__name__)

REFRESH_MS = 1000
# The spans the owner picks between. 2 minutes is "watch it live while I lock
# the phone"; the hour is "I left it overnight, show me".
SPANS = [("Last 2 minutes", 120), ("Last 10 minutes", 600), ("Last hour", 3600)]
OUT_COLOR = QColor(TOKENS["accent"])          # PC -> phone
IN_COLOR = QColor("#F59E0B")                  # phone -> PC (the warning hue,
#                                               reused as a second series)
IDLE_COLOR = QColor(255, 255, 255, 16)        # the "nobody connected" band
CHART_MIN = QSize(520, 220)                   # readable at the smallest useful size


def human_bytes(n: float) -> str:
    """Bytes as the owner reads them, never as raw digits."""
    for unit, step in (("GB", 1 << 30), ("MB", 1 << 20), ("kB", 1 << 10)):
        if n >= step:
            return f"{n / step:.1f} {unit}"
    return f"{int(n)} B"


def human_rate(n: float) -> str:
    return human_bytes(n) + "/s"


class TrafficChart(QWidget):
    """The graph itself: two filled lines plus the idle band behind them."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.samples: list = []
        self.span_s = SPANS[0][1]
        # Grows with the window — the chart IS the content here, so it takes
        # the free space instead of leaving it empty (THE SPACE & LEGIBILITY
        # LAW: nothing starves while its window holds slack).
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(CHART_MIN)

    def set_samples(self, samples: list, span_s: int) -> None:
        self.samples, self.span_s = samples, span_s
        self.update()

    def _peak(self) -> float:
        peak = max((max(s.out_bytes, s.in_bytes) for s in self.samples), default=0)
        return max(peak, 1024.0)   # a floor, so an idle graph is a flat line
        #                            along the bottom and not noise magnified

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        metrics = QFontMetrics(self.font())
        pad_l = metrics.horizontalAdvance("999 MB/s") + 10
        pad_b = metrics.height() + 8
        plot = self.rect().adjusted(pad_l, 6, -8, -pad_b)
        painter.fillRect(self.rect(), QColor(TOKENS["surface0"]))
        if plot.width() < 20 or plot.height() < 20:
            return

        now = time.time()
        start = now - self.span_s
        peak = self._peak()

        def x_of(t: float) -> float:
            return plot.left() + plot.width() * max(0.0, min(1.0, (t - start) / self.span_s))

        def y_of(v: float) -> float:
            return plot.bottom() - plot.height() * min(1.0, v / peak)

        # The idle band FIRST, behind everything: it is the reading the owner
        # came here for, so it must be visible under the lines, not over them.
        run_start = None
        for sample in self.samples:
            if sample.clients == 0 and run_start is None:
                run_start = sample.t
            elif sample.clients > 0 and run_start is not None:
                painter.fillRect(int(x_of(run_start)), plot.top(),
                                 max(1, int(x_of(sample.t) - x_of(run_start))),
                                 plot.height(), IDLE_COLOR)
                run_start = None
        if run_start is not None:
            painter.fillRect(int(x_of(run_start)), plot.top(),
                             max(1, int(x_of(now) - x_of(run_start))),
                             plot.height(), IDLE_COLOR)

        # Axes and the peak label.
        grid = QColor(255, 255, 255, 28)
        painter.setPen(QPen(grid, 1))
        painter.drawLine(plot.left(), plot.bottom(), plot.right(), plot.bottom())
        painter.drawLine(plot.left(), plot.top(), plot.left(), plot.bottom())
        painter.setPen(QPen(QColor(TOKENS["text2"]), 1))
        painter.drawText(4, plot.top() + metrics.ascent(), human_rate(peak))
        painter.drawText(4, plot.bottom() + 2, "0")
        span_label = next((n for n, s in SPANS if s == self.span_s), "")
        painter.drawText(plot.right() - metrics.horizontalAdvance("now"),
                         plot.bottom() + metrics.height(), "now")
        painter.drawText(plot.left(), plot.bottom() + metrics.height(), span_label)

        for color, pick in ((OUT_COLOR, lambda s: s.out_bytes),
                            (IN_COLOR, lambda s: s.in_bytes)):
            if not self.samples:
                continue
            path = QPainterPath()
            path.moveTo(QPointF(x_of(self.samples[0].t), y_of(pick(self.samples[0]))))
            for sample in self.samples[1:]:
                path.lineTo(QPointF(x_of(sample.t), y_of(pick(sample))))
            fill = QPainterPath(path)
            fill.lineTo(QPointF(x_of(self.samples[-1].t), plot.bottom()))
            fill.lineTo(QPointF(x_of(self.samples[0].t), plot.bottom()))
            fill.closeSubpath()
            faded = QColor(color)
            faded.setAlpha(46)
            painter.fillPath(fill, faded)
            painter.setPen(QPen(color, 2))
            painter.drawPath(path)
        painter.end()


class TrafficWindow(QDialog):
    """Header numbers + the chart + the recording footer."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Traffic — what this PC sends to the phone")
        self._settled = False   # the minimum is measured on first show

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        self.out_label = QLabel("—")
        self.in_label = QLabel("—")
        self.phone_label = QLabel("—")
        self.gap_label = QLabel("—")
        for label in (self.out_label, self.in_label, self.phone_label, self.gap_label):
            label.setWordWrap(True)   # ladder step 2: reflow before a wider window
        self.phone_label.setObjectName("caption")
        self.gap_label.setObjectName("caption")
        root.addWidget(self.out_label)
        root.addWidget(self.in_label)
        root.addWidget(self.phone_label)
        root.addWidget(self.gap_label)

        self.chart = TrafficChart(self)
        card_shadow(self.chart)
        root.addWidget(self.chart, 1)   # the chart takes every spare pixel

        legend = QLabel(
            "■ PC → phone     ■ phone → PC     ▨ nobody connected — "
            "a locked phone must be a flat line inside the grey band"
        )
        legend.setObjectName("caption")
        legend.setWordWrap(True)
        root.addWidget(legend)

        controls = QHBoxLayout()
        self.span_combo = QComboBox()
        for name, seconds in SPANS:
            self.span_combo.addItem(name, seconds)
        self.span_combo.currentIndexChanged.connect(self._refresh)
        controls.addWidget(self.span_combo)
        self.record_check = QCheckBox("Record to file")
        self.record_check.setChecked(True)
        self.record_check.setEnabled(False)   # a reading, not a switch
        self.record_check.setToolTip(str(SETTINGS.traffic_csv_path))
        controls.addWidget(self.record_check)
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
        size = settle_minimum(self, self._computed_minimum(), QSize(760, 520))
        self.resize(max(size.width(), 760), max(size.height(), 520))

    def _computed_minimum(self) -> QSize:
        """MEASURED, never guessed (THE SPACE & LEGIBILITY LAW).

        Width = the widest real row this window can show — the legend and the
        recording path are the long ones, and both wrap, so the floor is the
        control row that CANNOT wrap. Height = the four header lines, the
        chart's own minimum, the legend and the footer."""
        metrics = QFontMetrics(self.font())
        button_pad, spacing = 40, 8
        controls_row = (metrics.horizontalAdvance(max((n for n, _ in SPANS), key=len))
                        + 56
                        + metrics.horizontalAdvance("Record to file") + 28
                        + metrics.horizontalAdvance("Open the recording") + button_pad
                        + metrics.horizontalAdvance("Reset counters") + button_pad
                        + 3 * spacing)
        width = max(CHART_MIN.width(), controls_row) + 36
        rows = metrics.height() + 6
        height = (rows * 4            # the four header lines
                  + CHART_MIN.height()
                  + rows * 2          # legend (wraps to two at the floor)
                  + rows * 2          # control row + the path line
                  + 60)               # margins and spacings
        return QSize(width, height)

    # -- refresh -----------------------------------------------------------

    def _refresh(self) -> None:
        try:
            snap = traffic.METER.snapshot()
            span = self.span_combo.currentData() or SPANS[0][1]
            self.chart.set_samples(traffic.METER.history(span), span)
            clients = snap["clients"]
            self.out_label.setText(
                f"PC → phone:  {human_rate(snap['out_per_s'])}"
                f"     ·  this session {human_bytes(snap['total_out'])}"
                f"     ·  {clients} client{'s' if clients != 1 else ''} connected")
            self.in_label.setText(
                f"phone → PC:  {human_rate(snap['in_per_s'])}"
                f"     ·  this session {human_bytes(snap['total_in'])}")
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
            self.record_check.setChecked(bool(snap["recording"]))
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
        self._refresh()

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt override
        self._timer.stop()
        super().closeEvent(event)
