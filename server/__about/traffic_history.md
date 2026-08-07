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

## Connections
### Uses
- [Config](config.md) — `traffic_csv_path`/`traffic_csv_backups` (which
  files), `traffic_history_max_buckets` (the read's own bound)

### Used by
- [Traffic Window](../gui/__about/traffic_window.md) — the "Od starta" /
  "Sve (iz fajla)" spans

## Classes
### Point
One chart point — `t`, `out_avg`/`out_max`, `in_avg`/`in_max`, `clients`.
For a raw per-second sample `avg == max`; for a downsampled bucket they
differ on purpose, so a spike inside a wide bucket is never smoothed into
invisibility by the average alone.

### HistoryJob
The background-thread wrapper: `start(since, max_buckets)`, `poll()` (the
newest ready result, once), `running`/`elapsed_s` (read-only from the GUI
side).

## Functions
- `read_history(since, max_buckets)`: the streaming downsample itself
- `_csv_paths()`: the rotated backup (if it exists) then the live file,
  oldest data first
- `_earliest_time(paths)`: the recording's own start, for "Sve" (`since=None`)
