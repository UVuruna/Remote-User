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
ZOOM_FACTOR = 2.0     # + halves the view, − doubles it, around the anchor
DRAG_MIN_PX = 6       # a press-and-release that moved less is a click, not a drag


class ViewRange:
    def __init__(self) -> None:
        self.full_start = 0.0
        self.full_end = 0.0
        self.start = 0.0
        self.end = 0.0

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

    def is_zoomed(self) -> bool:
        return (self.start > self.full_start + 1e-6
                or self.end < self.full_end - 1e-6)

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
        """Back to the full span. False when nothing was zoomed."""
        if not self.is_zoomed():
            return False
        self.start, self.end = self.full_start, self.full_end
        return True

    def _zoom_by(self, factor: float, anchor: float | None) -> bool:
        cur = self.span()
        full = max(0.0, self.full_end - self.full_start)
        if cur <= 0 or full <= 0:
            return False
        new_span = min(full, max(MIN_SPAN_S, cur * factor))
        if abs(new_span - cur) < 1e-6:
            return False
        if anchor is None or not (self.start <= anchor <= self.end):
            anchor = (self.start + self.end) / 2
        # Keep the anchor at the same FRACTION of the view — zooming toward
        # the mouse keeps what is under it in place.
        frac = (anchor - self.start) / cur
        self.start = anchor - frac * new_span
        self.end = self.start + new_span
        self._clamp()
        return True

    # -- the drag ---------------------------------------------------------

    def set_view(self, start: float, end: float) -> bool:
        """The rectangle he drew, in unix time (either order). Clamped and
        widened to `MIN_SPAN_S`; False when it would change nothing."""
        lo, hi = (start, end) if start <= end else (end, start)
        # The rectangle's EDGES are clamped first — a drag that ran past the
        # plot means "up to the end", not "the whole span".
        lo = min(max(lo, self.full_start), self.full_end)
        hi = min(max(hi, self.full_start), self.full_end)
        if hi - lo < MIN_SPAN_S:
            mid = (lo + hi) / 2
            lo, hi = mid - MIN_SPAN_S / 2, mid + MIN_SPAN_S / 2
        before = (self.start, self.end)
        self.start, self.end = lo, hi
        self._clamp()
        return (self.start, self.end) != before

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


def is_drag(x0: float, x1: float) -> bool:
    """A press-and-release counts as a rectangle only past `DRAG_MIN_PX` — a
    click that twitched a pixel must never zoom the graph to ten seconds."""
    return abs(x1 - x0) >= DRAG_MIN_PX
