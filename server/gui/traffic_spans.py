"""Which stretch of the recording a traffic span means, and how a zoomed view
keys its read.

Split out of `gui/traffic_window.py` on 2026-08-18 (THE STRUCTURE LAW). The
window owns widgets; this module owns the two questions that decide WHICH
DATA is asked for, and both of them are pure functions of their arguments —
which is exactly why `tests/test_traffic_spans.py` and `tests/test_traffic_zoom.py`
can assert a span's meaning without building a window at all.

Nothing here draws, and nothing here reads the file: `traffic_history.py` does
the reading, and it is handed the answers these two functions produce.
"""

import time

import traffic

# ══════════════════════════ THE SPANS HE PICKS BETWEEN ══════════════════════
# "recent" spans read the live in-memory ring buffer (traffic.METER.history);
# every other kind reads traffic.csv through traffic_history.HistoryJob — a
# slower, off-thread path, so they carry no `seconds` (their own start time is
# computed, not fixed: see `history_since`).
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
    ("Last 60 seconds", "recent", 60),
    ("Last 5 minutes", "recent", 300),
    ("Last hour", "recent", 3600),
    ("Last 10 hours", "last10h", None),
    ("Today", "today", None),
    ("Since start", "since_start", None),
    ("All (from file)", "all", None),
]
TEN_HOURS_S = 10 * 3600
# How finely a zoomed view is keyed for the file read (T110). One plot
# column: wider than any chart this window can be shown at, so the key can
# never be coarser than what the owner can actually see, and never finer
# than a difference the picture could carry.
PLOT_COLUMNS = 2048


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


def history_key(kind: str, view) -> str:
    """The read a file-backed span needs RIGHT NOW: the span itself, or —
    zoomed — the span plus the view's own bounds, so a result for the
    whole span is never adopted as the zoomed read and vice versa (the
    same "a result carries its own key" rule the spans gate holds).

    THE BOUNDS ARE QUANTIZED TO THE READ'S OWN BUCKET, and that is the
    fix for the owner's report 2026-08-16 (T110, his THIRD on this
    window: "Reading traffic.csv…" forever on a file-backed span). His
    own server log named the mechanism, one line per second, both bounds
    incrementing by exactly 1:

        dropped 'last10h|1786797517-1786833517' while showing
                'last10h|1786797518-1786833518'

    A file-backed span may SLIDE with the clock ("Last 10 hours" is
    `now - 10h .. now`), `_refresh` hands that moving end to
    `set_data` every tick, and `ViewRange.set_full` correctly clamps a
    zoomed view forward inside it — so the view's own bounds move one
    second per second. Keyed on the raw bounds, every tick invented a
    NEW key: the read in flight could never match the key by the time it
    landed (it takes longer than a tick), so every result was dropped, a
    fresh read was started in its place, and `loading` — which is true
    exactly while a read for the selected key is pending and nothing is
    held for it — could never come down. A read storm and a permanently
    stuck overlay, from one expression.

    Quantizing is the honest rule and not a fudge: the read returns at
    most `traffic_history_max_buckets` buckets across the view, so two
    views differing by less than one bucket produce the SAME picture.
    A key that changes when the answer cannot is not identifying the
    read, it is identifying the clock.

    Why the earlier round could not reproduce it: its harness drove
    FIXED-start spans ("Today", "Since start" measured from a frozen
    clock), where the bounds never move and this expression is stable.
    The defect needs a span whose end tracks `now` AND a zoom.
    """
    if not view.is_time_zoomed():
        return kind
    # QUANTIZED TO A PLOT COLUMN, and that is the T110 fix's second half.
    # A zoomed view on a span that slides with the clock keeps MOVING —
    # `ViewRange._clamp` pushes a view that has fallen out of the span
    # forward one second per second — so a key built from the raw bounds
    # is a new key every tick. Every tick then started a fresh read that
    # superseded the one before it, so no read ever finished, no result
    # was ever surfaced, and the "Reading traffic.csv…" overlay could
    # never come down. His log, one line per second, both bounds +1:
    #
    #     dropped 'last10h|1786797517-1786833517' while showing
    #             'last10h|1786797518-1786833518'
    #
    # The quantum is one PLOT COLUMN, not one read bucket: the picture is
    # what he judges, and a shift that cannot move a single pixel of it
    # must not count as a different read. Below that the view is the same
    # question and the answer already in flight is the answer.
    width = max(1.0, view.span() / PLOT_COLUMNS)
    lo = int(view.start // width)
    hi = int(view.end // width)
    return f"{kind}|{lo}-{hi}@{int(width)}"
