# Traffic Spans

**Script:** [Traffic Spans (script)](../traffic_spans.py)

## Purpose

Which stretch of the recording a span NAME means, and how a zoomed view keys
its read. Split out of [Traffic Window](traffic_window.md) on 2026-08-18 (THE
STRUCTURE LAW): the window owns widgets, this module owns the two questions
that decide WHICH DATA is asked for.

Both answers are pure functions of their arguments, and that is the point -
`tests/test_traffic_spans.py` can assert that "Today" really is local midnight,
and `tests/test_traffic_zoom.py` that a zoomed key is quantized, without
building a window at all.

## Connections

### Uses
- `traffic` - `PROCESS_START`, for the "Since start" span

### Used by
- [Traffic Window](traffic_window.md) - the span picker, `_on_span_changed`,
  `_maybe_start_history` and `_refresh`
- [Traffic History](../../__about/traffic_history.md) - indirectly: it is handed the `since`
  and the key these two functions produce

## Functions

- `SPANS`: the seven spans he picks between, `(label, kind, seconds)`
- `history_since(kind, now)`: where a file-backed span STARTS
- `history_key(kind, view)`: the read a file-backed span needs right now,
  quantized to a plot column when the view is time-zoomed

## The file-backed spans
The live in-memory ring buffer only reaches one hour, so everything longer
reads `traffic.csv`: **Last 10 hours**, **Today** (local midnight — his day,
never a rolling 24 hours), **Since start** and **All (from file)**. The two
shorter ones are the owner's request of 2026-08-14 — an evening's work had
no picture between "Last hour" and his whole server session. They are not a
cheaper READ (the reader still scans past every row before their `since`;
measured numbers in [Traffic History](../../__about/traffic_history.md)),
they are a readable time resolution. Each span's start is one pure function,
`history_since(kind, now)`.

Selecting any of them starts a `traffic_history.HistoryJob` on a background thread — never the UI thread, since either span
can mean reading a file with ~4 months of one-second rows. While the first
read for a freshly-picked span is still running the chart shows "Reading
traffic.csv…" instead of a stale or empty graph;

**Which span's data is on the screen is decided by the RESULT's own key**
(owner report 2026-08-14: "All (from file)" and "Since start" drew the same
four hours, his screenshots reading 11:48 -> 15:42 for both). Two rules,
both structural:

- a span switch made while a read is in flight **supersedes** it and issues
  its own read. The old code returned early on `HistoryJob.running`, so the
  switch started nothing, and the older read's data landed one tick later
  and was stamped with the newly selected span.
- a polled result is adopted **only under its own key** (`got_kind == kind`)
  and otherwise dropped — never re-labelled.

The overlay follows from the same place: it is up exactly while
`HistoryJob.pending_key` names the SELECTED span and nothing for that span
has arrived. There is no window-owned `_history_loading` flag any more — a
flag only a successful poll can clear is stuck the first time a result is
dropped, which is the shape of "loads forever".

Gate: `tests/test_traffic_spans.py`, fail-closed in `setup/gates.py`
(0b15/6).
 once loaded it re-reads
every `SETTINGS.traffic_history_refresh_s` (30 s) so a long watch still sees
new samples land, without re-scanning the file on every 1 s GUI tick. A
window **resize never re-reads the file** — `traffic_history` already bounds
its output to `SETTINGS.traffic_history_max_buckets`, comfortably above any
real window width, and the chart's own `_coalesce` does the final,
cheap, in-memory downsample to the exact current plot width on every paint
(so the on-screen "never more than one point per pixel" guarantee holds
regardless of window size, without touching disk again).

## T110 — "Reading traffic.csv…" that never came down

His THIRD report on this window (2026-08-16), after two rounds closed it
wrongly: the first fixed a symptom, the second put the right hypothesis and
then declared it refuted because its harness could not reproduce it.

**Reproduced from his own `server.log`**, which had named the mechanism all
along — consecutive lines one second apart, both bounds incrementing by
exactly 1:

```
dropped 'last10h|1786797517-1786833517' while showing 'last10h|1786797518-1786833518'
```

`_history_key` built a zoomed read's key out of the chart view's own bounds.
A file-backed span may SLIDE with the clock ("Last 10 hours" is
`now - 10h .. now`), `_refresh` hands that moving end to the chart on every
tick, and `ViewRange._clamp` correctly pushes a view that has fallen out of
the span forward with it. So the key changed every second; every tick started
a read that superseded the one before it, no read ever finished, no result
was ever surfaced, and the overlay — which is up exactly while a read for the
selected key is pending and nothing is held for it — could never come down.

**The arithmetic in his log says which zoom it was**: `1786833517 - 1786797517`
is exactly 36000, the whole ten hours. The view was never narrowed in TIME at
all — he had zoomed the RATE axis, and `is_zoomed()` answers yes to that too.

Two defences, and each is load-bearing (proven by planting the other's fix
back and watching only its own check fail):

- **A rate zoom does not key — or narrow — a file read.** `ViewRange` grew
  `is_time_zoomed()`, and `_history_key` / `_maybe_start_history` ask that
  one. Which rows are read from `traffic.csv` is a question about time; the
  rate axis is a window on the picture, not on the file.
- **A real time zoom is keyed to a PLOT COLUMN** (`PLOT_COLUMNS`), not to
  raw seconds. A time zoom drifts too — on the OLDEST slice of a sliding
  span, where the view falls out through the left edge — and there the
  re-read is CORRECT; what must not happen is a fresh read per second, each
  killing the last. A shift that cannot move one pixel of the picture he
  judges is not a different read.

Why two rounds missed it: their harnesses drove FIXED-start spans, where
nothing moves however it is zoomed. The defect needs a span whose end tracks
the clock AND a zoom — and, for the overlay half, a read slower than one
tick, which his 3.7 MB file is and a fast stub is not.

`ViewRange.set_full` deliberately still asks `is_zoomed()`: whether a view
that is the whole span FOLLOWS a slide is a different question, the clamp
answers it identically, and a change there could not be proven by a check.

Gate: `tests/test_traffic_spans.py` — three checks (the rate-zoom key, the
oldest-slice recovery end-to-end, the sliding-span overlay end-to-end), each
proven by planting its own defect.
