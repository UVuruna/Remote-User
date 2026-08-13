"""Long-span traffic history: read `traffic.csv` and turn months of
one-second rows into a bounded number of chart points.

Split out of `traffic.py` and `gui/traffic_window.py` on 2026-08-07 (THE
STRUCTURE LAW) for BUILD ROUND R4 — the owner asked for two more spans, "Od
starta" (this server process's whole life) and "Sve (iz fajla)" (everything
the recording ever held), and turning either one into a picture means reading
a file that can hold ~4 months of samples per rotation (`traffic_csv_backups`
keeps one more). Neither `traffic.py` (the live counters) nor
`gui/traffic_window.py` (the paint code) owns "read a CSV that outlives the
running process" — this module does, and it owns nothing else.

The read is a SINGLE STREAMING PASS with O(bucket count) memory, never
O(file size): rows arrive in file order (the meter only ever appends), so
each row's bucket index is non-decreasing and a bucket can be folded into its
`Point` and dropped the moment the next row's index moves past it. A 20 MB
file is ~650k rows; loading them into a list first (a `csv.reader` + Python
list, the obvious naive approach) would hold the whole file in memory just to
throw all but ~2,000 points away immediately after. This way the read never
holds more than a handful of open Python floats beyond the output list — the
same footprint whether the file is 2 MB or 200 MB.

`HistoryJob` is what makes this off-thread: it is the same plain pattern
`gui/main_window.py` already uses for start/stop/update (`threading.Thread` +
an attribute the window's own timer polls, no cross-thread Qt signals) —
never a QThread, because nothing else in this project uses one and the point
of THE STRUCTURE LAW is one way to do a thing, not two.
"""

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from config import SETTINGS

logger = logging.getLogger(__name__)


# ═══════════════════════════ POINT ═══════════════════════════
@dataclass
class Point:
    """One chart point. For a raw per-second sample `avg` and `max` are the
    same number; for a downsampled bucket they differ on purpose — the owner
    asked for both explicitly so a spike inside a wide bucket is never
    smoothed into invisibility by the average alone."""
    t: float          # unix time — bucket MIDPOINT for a downsampled point
    out_avg: float
    out_max: float
    in_avg: float
    in_max: float
    clients: int      # MAX clients seen anywhere in the bucket — a single
                       # connected second inside a wide bucket must not read
                       # as "nobody was here"
    device: str = ""  # the device KEY that owned the LAST active second in
                       # this bucket ("" = nobody / an old pre-device CSV row)
                       # — see `traffic.Sample.device`. A whole-bucket vote
                       # would need holding every row's device in memory,
                       # against this reader's whole point (O(bucket count),
                       # never O(file size)); "last active" is the cheap
                       # answer and, since only one device is ever connected
                       # at a time, is exactly right for every bucket the
                       # session did not switch devices mid-bucket.


# ═══════════════════════════ CSV FILES ═══════════════════════════
def _csv_paths() -> list[Path]:
    """Oldest data first: the one rotated backup (if it exists), then the
    live file — appends are chronological within each, so reading them in
    this order needs no sort."""
    path = SETTINGS.traffic_csv_path
    backup = path.with_name(path.name + ".1")
    paths = []
    if backup.exists():
        paths.append(backup)
    if path.exists():
        paths.append(path)
    return paths


def _iter_rows(paths: list[Path]):
    """Yields raw CSV lines across every file in order, skipping headers.
    One file at a time, one line at a time — the only thing ever held in
    memory from the file itself is the current line."""
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line or line.startswith("time,"):
                        continue
                    yield line
        except OSError as e:
            logger.warning("Traffic history: could not read %s (%s)", path, e)


def _parse_time(text: str) -> float:
    """`"YYYY-MM-DD HH:MM:SS"` (the exact format `traffic.py` writes) to unix
    time. Hand-sliced instead of `time.strptime` — profiled on a 650k-row
    synthetic file, slicing was measurably the cheaper half of the parse and
    this runs off the UI thread on every row of a months-long file."""
    return time.mktime((
        int(text[0:4]), int(text[5:7]), int(text[8:10]),
        int(text[11:13]), int(text[14:16]), int(text[17:19]),
        0, 0, -1))


def _parse_row(line: str):
    """`None` on anything malformed — a torn last line from a killed process,
    a hand-edited file — never raises out of the reader.

    Accepts BOTH the 4-column pre-device format and the 5-column format that
    added `device` (owner request 2026-08-13) — a file spanning the upgrade
    has rows of both widths, and a reader that only accepted one would either
    crash on the tail of an old file or throw away everything written before
    the server was updated. A row shorter than 5 columns reads as device ""
    ("unknown device") rather than failing — silently mis-attributing old
    traffic would be worse than honestly not knowing whose it was."""
    parts = line.rstrip("\n").split(",")
    if len(parts) not in (4, 5):
        return None
    try:
        t, out_b, in_b, clients = (
            _parse_time(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
        device = parts[4] if len(parts) == 5 else ""
        return t, out_b, in_b, clients, device
    except (ValueError, IndexError):
        return None


def _earliest_time(paths: list[Path]) -> float | None:
    """The first real timestamp in the oldest file — the start of "Sve", the
    complete recording. Reads only until the first valid row, never the
    whole file."""
    for row in _iter_rows(paths):
        parsed = _parse_row(row)
        if parsed is not None:
            return parsed[0]
    return None


# ═══════════════════════════ THE DOWNSAMPLE ═══════════════════════════
def read_history(since: float | None, max_buckets: int) -> list[Point]:
    """Every CSV row from `since` (or the recording's own start when `since`
    is None — "Sve") to now, folded into at most `max_buckets` evenly-spaced
    points. `max_buckets` is a ceiling on the DISK read only
    (`SETTINGS.traffic_history_max_buckets`, comfortably above any real
    window width); the chart itself further coalesces down to its actual
    plot width at paint time, so a resize never re-reads the file.

    Rows outside `[since, now]` are skipped without being aggregated — but
    still have to be READ past when `since` sits deep in an old file (the
    worst case this function can be handed: a server that has been running
    for a few seconds against a file that goes back months). That full scan
    is the measured cost quoted in the round report.
    """
    paths = _csv_paths()
    if not paths:
        return []
    start = since if since is not None else _earliest_time(paths)
    if start is None:
        return []
    end = time.time()
    if end <= start:
        return []
    width = max((end - start) / max_buckets, 1e-6)

    points: list[Point] = []
    cur_idx: int | None = None
    cur_out: list[int] = []
    cur_in: list[int] = []
    cur_clients = 0
    cur_device = ""

    def flush() -> None:
        nonlocal cur_idx, cur_out, cur_in, cur_clients, cur_device
        if cur_idx is None or not cur_out:
            return
        points.append(Point(
            t=start + (cur_idx + 0.5) * width,
            out_avg=sum(cur_out) / len(cur_out),
            out_max=max(cur_out),
            in_avg=sum(cur_in) / len(cur_in),
            in_max=max(cur_in),
            clients=cur_clients,
            device=cur_device,
        ))
        cur_out, cur_in, cur_clients, cur_device = [], [], 0, ""

    for line in _iter_rows(paths):
        row = _parse_row(line)
        if row is None:
            continue
        t, out_b, in_b, clients, device = row
        if t < start:
            continue
        idx = min(max_buckets - 1, int((t - start) / width))
        if cur_idx is not None and idx != cur_idx:
            flush()
        cur_idx = idx
        cur_out.append(out_b)
        cur_in.append(in_b)
        cur_clients = max(cur_clients, clients)
        # "Last ACTIVE second wins" (see the Point docstring): a device is
        # only worth recording for a bucket when it actually sent/received
        # something in it, else an idle heartbeat second from a device that
        # is about to be replaced could steal the bucket's colour from the
        # device that did all the real work in it.
        if device and (out_b or in_b):
            cur_device = device
    flush()
    return points


# ═══════════════════════════ BACKGROUND JOB ═══════════════════════════
class HistoryJob:
    """Runs `read_history` on a daemon thread and hands the result to
    whoever polls next. Same shape as `gui/main_window.py`'s `_run_worker` /
    `_guarded` — a plain attribute under a lock, read by the window's own
    1 s timer — never a Qt cross-thread signal, matching the one pattern
    this project already uses for background work.

    `running` and `elapsed_s` are read-only from the GUI side; nothing here
    touches Qt.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token = 0
        self._result: list[Point] | None = None
        self.running = False
        self.elapsed_s = 0.0

    def start(self, since: float | None, max_buckets: int) -> None:
        """Starts a new read, superseding any still-running one — its result
        is discarded on arrival (the `_token` check) so a slow read for a
        span the owner already clicked away from can never overwrite a
        newer one."""
        with self._lock:
            self._token += 1
            token = self._token
        self.running = True
        threading.Thread(target=self._run, args=(token, since, max_buckets),
                         name="traffic-history", daemon=True).start()

    def _run(self, token: int, since: float | None, max_buckets: int) -> None:
        t0 = time.monotonic()
        try:
            points = read_history(since, max_buckets)
        except Exception:  # a background reader may never take the GUI down
            logger.exception("Traffic history read failed")
            points = []
        elapsed = time.monotonic() - t0
        with self._lock:
            if token == self._token:
                self._result = points
                self.elapsed_s = elapsed
            self.running = False

    def poll(self) -> list[Point] | None:
        """The newest ready result, once — `None` if nothing new landed
        since the last poll (keep showing whatever the caller already
        has)."""
        with self._lock:
            result, self._result = self._result, None
            return result
