"""The Traffic chart's TIME WINDOW — what stretch of the span the graph is
looking at (owner request 2026-08-15, T104 + T105: Zoom + / − / Reset, and
a mouse drag that draws a rectangle over the graph and zooms to it).

Pure arithmetic over unix times and pixel columns; nothing here knows Qt.
`ViewRange` holds the FULL span (`full_start`..`full_end`, what the picker
selected) and the VIEW inside it (`start`..`end`, what the plot shows). Every
step keeps the view INSIDE the full span and never narrower than
`MIN_SPAN_S`, so a zoom can never wander into a stretch the file was not
asked for, nor shrink to a window with no whole second in it.

Why a state object rather than four numbers in the widget: the chart maps
pixels to time and the window decides what to READ for a zoomed view (a
file-backed span is re-read for exactly the view, at the same bucket count —
that is what makes a zoomed graph finer instead of merely stretched); both
must agree on the same view, so both ask this one object.
"""

MIN_SPAN_S = 10.0     # a view narrower than this holds too few seconds to draw
MIN_Y_SPAN = 64.0     # bytes/s — a Y window narrower than this is a line, not a curve
ZOOM_FACTOR = 2.0     # + halves the view, − doubles it, around the anchor
DRAG_MIN_PX = 6       # a press-and-release that moved less is a click, not a drag


# THE ZOOM IS 2D (owner decision 2026-08-15, option B): a rectangle limits
# BOTH the time axis and the rate axis, "so the Y scale is not always
# 0..MAX and the curve can be seen in detail". While the view is the whole
# span the Y axis is AUTO — 0 up to the visible peak's gridline, exactly as
# before; a drawn rectangle sets `y_lo..y_hi`, and from then on the drag
# PANS the slice along both axes (his B: zoomed = move, full view = zoom).


class ViewRange:
    def __init__(self) -> None:
        self.full_start = 0.0
        self.full_end = 0.0
        self.start = 0.0
        self.end = 0.0
        # The rate window; None = automatic (0 .. the visible peak's top
        # gridline). `y_cap` is the CEILING a pan/zoom-out may reach — the
        # whole span's own top gridline, told to us by the chart at paint,
        # since only the chart knows the ladder its axis uses.
        self.y_lo: float | None = None
        self.y_hi: float | None = None
        self.y_cap: float = 0.0

    # -- the span the picker selected --------------------------------------

    def set_full(self, start: float, end: float) -> None:
        """A new full span (a picker change, or the live span sliding with the
        clock). A view that was the WHOLE previous span follows the new one;
        a zoomed view is kept but clamped inside it, so a live span sliding
        forward does not silently drop the zoom he made."""
        was_whole = not self.is_zoomed()
        self.full_start, self.full_end = float(start), float(end)
        if was_whole or self.end <= self.start:
            self.start, self.end = self.full_start, self.full_end
        else:
            self._clamp()

    def is_time_zoomed(self) -> bool:
        """TIME only — deliberately NOT `is_zoomed()`, which also answers yes
        to a rate-axis (Y) zoom.

        This distinction is the T110 fix (owner report 2026-08-16, his third
        on the Traffic window: "Reading traffic.csv…" forever). A Y zoom
        changes nothing about WHICH ROWS are read from `traffic.csv` — it is
        a window on the rate axis — but the reader was narrowed, and the read
        was KEYED, on `is_zoomed()`. On a span whose end tracks the clock
        ("Last 10 hours"), a Y-only zoom therefore took this path: the view's
        bounds still equal the full span, `set_full` sees `was_whole` False
        and clamps, and the clamp drags both bounds forward one second per
        second. Every tick invented a new key, nothing in flight could match
        it by the time it landed, every result was dropped and the overlay
        could never come down. His own log, one line per second:

            dropped 'last10h|1786797517-1786833517' while showing
                    'last10h|1786797518-1786833518'

        — and the give-away that says Y and not time: 1786833517 - 1786797517
        is exactly 36000, the whole ten hours. The view was never narrowed in
        time at all.

        Ask this one wherever the question is "what should be READ"; ask
        `is_zoomed()` where the question is "has he changed the view at all"
        (the Reset button, the zoom-out floor).
        """
        return (self.start > self.full_start + 1e-6
                or self.end < self.full_end - 1e-6)

    def is_zoomed(self) -> bool:
        return self.is_time_zoomed() or self.has_y()

    def has_y(self) -> bool:
        return self.y_lo is not None and self.y_hi is not None

    def y_span(self) -> float:
        return (self.y_hi - self.y_lo) if self.has_y() else 0.0

    def span(self) -> float:
        return max(0.0, self.end - self.start)

    # -- the buttons -----------------------------------------------------

    def zoom_in(self, anchor: float | None = None) -> bool:
        """Halves the view around `anchor` (unix time; the view's middle when
        None). False when already at the floor — the button then did nothing
        and the caller may say so."""
        return self._zoom_by(1.0 / ZOOM_FACTOR, anchor)

    def zoom_out(self, anchor: float | None = None) -> bool:
        """Doubles the view around `anchor`, clamped to the full span. False
        when the view already IS the full span."""
        return self._zoom_by(ZOOM_FACTOR, anchor)

    def reset(self) -> bool:
        """Back to the full span, Y automatic again. False when nothing was
        zoomed."""
        if not self.is_zoomed():
            return False
        self.start, self.end = self.full_start, self.full_end
        self.y_lo = self.y_hi = None
        return True

    def _zoom_by(self, factor: float, anchor: float | None,
                 y_anchor: float | None = None) -> bool:
        cur = self.span()
        full = max(0.0, self.full_end - self.full_start)
        if cur <= 0 or full <= 0:
            return False
        changed = False
        new_span = min(full, max(MIN_SPAN_S, cur * factor))
        if abs(new_span - cur) >= 1e-6:
            if anchor is None or not (self.start <= anchor <= self.end):
                anchor = (self.start + self.end) / 2
            # Keep the anchor at the same FRACTION of the view — zooming
            # toward the mouse keeps what is under it in place.
            frac = (anchor - self.start) / cur
            self.start = anchor - frac * new_span
            self.end = self.start + new_span
            self._clamp()
            changed = True
        # The rate axis follows ONLY once a rectangle has set it — an
        # automatic Y stays automatic, so − / + on a plain time zoom keep the
        # old picture to the pixel.
        if self.has_y() and self.y_cap > 0:
            cur_y = self.y_span()
            new_y = min(self.y_cap, max(MIN_Y_SPAN, cur_y * factor))
            if abs(new_y - cur_y) >= 1e-9:
                if y_anchor is None or not (self.y_lo <= y_anchor <= self.y_hi):
                    y_anchor = (self.y_lo + self.y_hi) / 2
                fy = (y_anchor - self.y_lo) / cur_y if cur_y > 0 else 0.5
                self.y_lo = y_anchor - fy * new_y
                self.y_hi = self.y_lo + new_y
                self._clamp_y()
                changed = True
        return changed

    def zoom_in_at(self, anchor: float | None, y_anchor: float | None) -> bool:
        return self._zoom_by(1.0 / ZOOM_FACTOR, anchor, y_anchor)

    def zoom_out_at(self, anchor: float | None, y_anchor: float | None) -> bool:
        return self._zoom_by(ZOOM_FACTOR, anchor, y_anchor)

    # -- the drag ---------------------------------------------------------

    def set_view(self, start: float, end: float,
                 y_lo: float | None = None, y_hi: float | None = None) -> bool:
        """The rectangle he drew: unix times (either order) and, when the
        rectangle had height, the rate window (either order, bytes/s).
        Clamped and widened to the floors; False when nothing changes. Only
        `y_lo`/`y_hi` BOTH given set the rate axis — a flat rectangle keeps
        Y automatic."""
        before = (self.start, self.end, self.y_lo, self.y_hi)
        if y_lo is not None and y_hi is not None:
            self.y_lo, self.y_hi = (y_lo, y_hi) if y_lo <= y_hi else (y_hi, y_lo)
            self._clamp_y()
        lo, hi = (start, end) if start <= end else (end, start)
        # The rectangle's EDGES are clamped first — a drag that ran past the
        # plot means "up to the end", not "the whole span".
        lo = min(max(lo, self.full_start), self.full_end)
        hi = min(max(hi, self.full_start), self.full_end)
        if hi - lo < MIN_SPAN_S:
            mid = (lo + hi) / 2
            lo, hi = mid - MIN_SPAN_S / 2, mid + MIN_SPAN_S / 2
        self.start, self.end = lo, hi
        self._clamp()
        return (self.start, self.end, self.y_lo, self.y_hi) != before

    # -- the pan (option B: zoomed = the drag MOVES the slice) -----------

    def pan(self, dt: float, dy: float) -> bool:
        """Shift the view by `dt` seconds and `dy` bytes/s (Y only when a
        rectangle has set it), clamped inside the full span and 0..y_cap.
        False when nothing moved (already at an edge)."""
        before = (self.start, self.end, self.y_lo, self.y_hi)
        span = self.span()
        if dt and span > 0:
            self.start = min(max(self.full_start, self.start + dt), self.full_end - span)
            self.end = self.start + span
            self._clamp()
        if dy and self.has_y():
            ys = self.y_span()
            self.y_lo = min(max(0.0, self.y_lo + dy), max(0.0, self.y_cap - ys))
            self.y_hi = self.y_lo + ys
            self._clamp_y()
        return (self.start, self.end, self.y_lo, self.y_hi) != before

    def _clamp_y(self) -> None:
        if not self.has_y():
            return
        cap = self.y_cap if self.y_cap > 0 else max(self.y_hi, MIN_Y_SPAN)
        span = min(max(self.y_span(), min(MIN_Y_SPAN, cap)), cap)
        self.y_lo = max(0.0, self.y_lo)
        if self.y_lo + span > cap:
            self.y_lo = max(0.0, cap - span)
        self.y_hi = self.y_lo + span

    def _clamp(self) -> None:
        full = self.full_end - self.full_start
        span = min(max(self.span(), min(MIN_SPAN_S, full)), full)
        if self.start < self.full_start:
            self.start = self.full_start
        if self.start + span > self.full_end:
            self.start = max(self.full_start, self.full_end - span)
        self.end = min(self.full_end, self.start + span)


def px_to_time(x: float, plot_left: float, plot_right: float,
               start: float, end: float) -> float:
    """A pixel column of the plot as unix time inside [start, end] — the
    inverse of the chart's `x_of`, clamped to the plot's own edges."""
    width = max(1.0, plot_right - plot_left)
    frac = min(1.0, max(0.0, (x - plot_left) / width))
    return start + frac * (end - start)


def px_to_rate(y: float, plot_top: float, plot_bottom: float,
               y_lo: float, y_hi: float) -> float:
    """A pixel ROW of the plot as bytes/s inside [y_lo, y_hi] — the inverse
    of the chart's `y_of` (the bottom is `y_lo`), clamped to the plot."""
    height = max(1.0, plot_bottom - plot_top)
    frac = min(1.0, max(0.0, (plot_bottom - y) / height))
    return y_lo + frac * (y_hi - y_lo)


def is_drag(x0: float, x1: float) -> bool:
    """A press-and-release counts as a rectangle only past `DRAG_MIN_PX` — a
    click that twitched a pixel must never zoom the graph to ten seconds."""
    return abs(x1 - x0) >= DRAG_MIN_PX
