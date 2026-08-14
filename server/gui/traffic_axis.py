"""How a byte count and a moment in time become the WORDS on the Traffic
chart's axes — and nothing else.

Split out of `gui/traffic_window.py` on 2026-08-14 at THE STRUCTURE LAW's
wall, and split by RESPONSIBILITY rather than by line count: everything here
is a pure function of numbers to text (plus `_alpha`, a colour token at an
alpha the QSS cannot express). None of it knows there is a window, a chart,
a CSV or a span; `traffic_window.py` owns the widget, `traffic_history.py`
owns the file, and this owns the labels. That also means every rule below
can be checked by calling it, with no Qt widget built.

The 2026-08-07 independent grade (Finding 2) is why `_axis_unit` exists:
every tick used to call `human_rate()` on its own value, so a single axis
read "1.5 kB/s" over "1000 B/s" over "500 B/s" — three gridlines, three
units. The unit is read ONCE off the axis's own top gridline and every tick
is a bare number in it.
"""

import math
import time

from PySide6.QtGui import QColor

Y_TICK_MIN = 4           # the owner's "4-5 gridlines" — inclusive of zero
Y_TICK_MAX = 5
X_TICK_COUNT = 4


def human_bytes(n: float) -> str:
    """Bytes as the owner reads them, never as raw digits."""
    for unit, step in (("GB", 1 << 30), ("MB", 1 << 20), ("kB", 1 << 10)):
        if n >= step:
            return f"{n / step:.1f} {unit}"
    return f"{int(n)} B"


def human_rate(n: float) -> str:
    return human_bytes(n) + "/s"


def _alpha(hex_color: str, alpha: int) -> QColor:
    """A theme color at a given alpha. Chart chrome (gridlines, idle band,
    crosshair) needs translucency a bare QPainter has no QSS to give it — but
    the HUE still has to come from a token, never a hardcoded white: a fixed
    white-alpha grid would all but vanish on the light palette headed for
    this file. Read at paint time (cheap — a handful of calls per frame) so
    it never caches a stale value if TOKENS is ever made theme-live."""
    color = QColor(hex_color)
    color.setAlpha(alpha)
    return color


# ═══════════════════════════ AXIS MATH ═══════════════════════════
def _y_ticks(peak: float, min_ticks: int = Y_TICK_MIN,
             max_ticks: int = Y_TICK_MAX) -> list[float]:
    """Round gridlines on the 1 / 2 / 5 x 10^n ladder, instead of an
    arbitrary max-and-zero — the owner's "4-5 gridlines".

    Every step on the ladder within a wide magnitude range is scored by how
    many gridlines it would produce (0 counted); a count already inside
    [min_ticks, max_ticks] scores 0, otherwise the distance to the nearer
    bound — so the search always prefers a step that lands the count in
    range over the "nearest round number" a naive single-formula pick would
    choose (that naive version put a real peak of 1024 at exactly 3 lines,
    one short of the owner's floor, because 1/2/5 steps are coarse near
    round-number boundaries)."""
    if peak <= 0:
        return [0.0]
    best_step = best_score = best_n = None
    for exp in range(-3, 8):
        magnitude = 10 ** exp
        for mult in (1, 2, 5):
            step = mult * magnitude
            n = math.ceil(peak / step) + 1   # ticks 0..top, top always >= peak
            if n < 2:
                continue
            if n < min_ticks:
                score = min_ticks - n
            elif n > max_ticks:
                score = n - max_ticks
            else:
                score = 0
            if (best_score is None or score < best_score
                    or (score == best_score and n > best_n)):
                best_score, best_step, best_n = score, step, n
    return [i * best_step for i in range(best_n)]


def _x_ticks(start: float, end: float, count: int) -> list[float]:
    span = max(1e-6, end - start)
    if count <= 1:
        return [start]
    return [start + span * i / (count - 1) for i in range(count)]


# One axis, one unit — picked ONCE from the axis's own TOP value, never per
# label (Finding 2, 2026-08-07 grade): the old per-tick `human_rate()` call
# let a single axis read "1.5 kB/s" over "1000 B/s" over "500 B/s" — three
# gridlines, three units, because each one picked its own independently. The
# boundaries below match `human_bytes()`'s own ladder so the axis and every
# other number this window prints never disagree about where "kB" starts.
_AXIS_UNITS = (("GB/s", 1 << 30), ("MB/s", 1 << 20), ("kB/s", 1 << 10), ("B/s", 1))


def _axis_unit(axis_max: float) -> tuple[str, float]:
    """The unit the WHOLE axis reads in, chosen from its top gridline."""
    for unit, step in _AXIS_UNITS:
        if axis_max >= step:
            return unit, float(step)
    return "B/s", 1.0


def _format_axis_value(value: float, divisor: float) -> str:
    """A bare number in the axis's chosen unit — the unit itself is stated
    once (see `_axis_unit`), so no label repeats it. Whole numbers stay
    whole ("2"); anything the ladder's 1/2/5 steps leave fractional gets one
    decimal ("1.5") — the same rounding `human_bytes` already uses."""
    scaled = value / divisor
    if abs(scaled - round(scaled)) < 0.05:
        return str(int(round(scaled)))
    return f"{scaled:.1f}"


def _x_label(t: float, span_s: float) -> str:
    """Granularity scales with how wide the span is — seconds matter at
    2 minutes, a date matters at four months."""
    local = time.localtime(t)
    if span_s <= 3600:
        return time.strftime("%H:%M:%S", local)
    if span_s <= 86400:
        return time.strftime("%H:%M", local)
    return time.strftime("%b %d", local)
