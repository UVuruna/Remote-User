# Traffic History

**Script:** [Traffic History (script)](../traffic_history.py) ·
**Flow:** [diagram](../__flow/traffic_history.md)

## Purpose
Turns `traffic.csv` — potentially months of one-second rows — into a bounded
number of chart points for the Traffic window's two long spans, **"Od
starta"** (this server process's whole life) and **"Sve (iz fajla)"** (the
complete recording). Built for BUILD ROUND R4 (owner-approved 2026-08-07,
"both spans" answered on the round's open question).

Split out of [Traffic Meter](traffic.md) (which owns the LIVE counters and
the CSV writer) and [Traffic Window](../gui/__about/traffic_window.md) (which
owns painting): neither file owns "read a file that outlives the running
process", and this one owns nothing else.

## The read
A **single streaming pass**, `O(bucket count)` memory, never `O(file size)`:
rows arrive in file order (the meter only ever appends), so each row's bucket
index is non-decreasing and a bucket folds into its `Point` and gets dropped
the moment the next row's index moves past it. A 20 MB file is roughly 650k
rows; loading them into a list first (the obvious `csv.reader` approach)
would hold the whole file in memory just to throw away all but ~2,000 points
immediately after — this way the read's memory footprint is the same whether
the file is 2 MB or 200 MB.

`_parse_time` hand-slices the fixed `"YYYY-MM-DD HH:MM:SS"` format `traffic.py`
writes instead of calling `time.strptime` — measurably cheaper per row, and
this runs on every row of a months-long file.

Rows outside `[since, now]` are skipped without being aggregated, but still
have to be **read past** when `since` sits deep in an old file — the worst
case this module can be handed is a server that has been running for a few
seconds against a recording that goes back months, and the full scan that
produces is the cost measured in the round report.

**MEASURED (2026-08-14, the owner's own PC)** — this module's honest answer
to "what does the biggest span cost", because his report was that the long
spans "load for a very long time, if not never":

| file | rows | span | `read_history` |
|------|------|------|----------------|
| his real `traffic.csv`, 3.7 MB | 138,540 | 2.5 days | **0.23 s** |
| the rotation ceiling: a full 20 MB live file + its one backup, 53 MB | 1.28 M | ~14 months | **2.5 s** |

So no span this module can be asked for costs more than a few seconds, and
"All (from file)" was NOT the reason the window appeared to load forever —
that was `gui/traffic_window.py`'s job bookkeeping (see its own doc). The
second row is the number to quote for a SHORT span too: `since` decides
which rows are AGGREGATED, never which are READ, so at that same 53 MB
ceiling "Last 10 hours" cost **2.1 s** against "All"'s 2.5 s. The saving is
the fold, not the I/O.

`max_buckets` (`SETTINGS.traffic_history_max_buckets`) bounds the DISK read
only — comfortably above any real window width. The chart itself
(`gui/traffic_window.py`'s `_coalesce`) further downsamples to its actual
plot width at paint time, so a window resize never triggers a re-read.

## Off the UI thread
`HistoryJob` runs `read_history` on a daemon thread and hands the result to
whoever polls next — the exact shape `gui/main_window.py` already uses for
start/stop/update (`threading.Thread` + a plain attribute the window's own
1 s timer polls), never a `QThread` or a cross-thread Qt signal: nothing else
in this project uses one, and THE STRUCTURE LAW wants one way to do a thing,
not two. A `_token` discards a still-running read's result if a newer one was
started first (span switched again before the first read finished).

**Every read carries a KEY** — the caller's own name for the span — and the
key travels WITH the result: `poll()` answers `(key, points)`, never bare
points (owner report 2026-08-14). The caller used to poll bare points and
stamp them with whatever span was selected when they arrived, so a read
still in flight when the owner changed span had its data drawn under the NEW
span's label. A key that rides with the data makes that impossible to write
rather than merely unlikely. `pending_key` is the second half: the key of
the newest read in flight, `None` when nothing runs, and the one thing the
window's loading overlay is derived from — cleared in a `finally`, so an
overlay read off it cannot outlive the work. A SUPERSEDED read clears
nothing at all (before this round `_run` cleared `running` unconditionally,
so a stale thread could clear the flag belonging to a newer read).

## Connections
### Uses
- [Config](config.md) — `traffic_csv_path`/`traffic_csv_backups` (which
  files), `traffic_history_max_buckets` (the read's own bound)

### Used by
- [Traffic Window](../gui/__about/traffic_window.md) — the "Od starta" /
  "Sve (iz fajla)" spans

## Classes
### Point
One chart point — `t`, `out_avg`/`out_max`, `in_avg`/`in_max`, `clients`,
`device`. A bucket that moved no bytes INHERITS the device last seen before
it (T87, owner report 2026-08-14): a quiet stretch belongs to whoever was
connected across it, and leaving it blank painted 96% of his chart the
neutral grey. `""` therefore means only "no device has been named yet at this
point in the file".
For a raw per-second sample `avg == max`; for a downsampled bucket they
differ on purpose, so a spike inside a wide bucket is never smoothed into
invisibility by the average alone.

### HistoryJob
The background-thread wrapper: `start(key, since, max_buckets)`, `poll()`
(the newest ready result, once, as `(key, points)`),
`running`/`pending_key`/`elapsed_s` (read-only from the GUI side).

## Functions
- `read_history(since, max_buckets)`: the streaming downsample itself
- `_csv_paths()`: the rotated backup (if it exists) then the live file,
  oldest data first
- `_earliest_time(paths)`: the recording's own start, for "Sve" (`since=None`)
