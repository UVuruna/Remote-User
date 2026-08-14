# Traffic History — Flow

**About:** [description](../__about/traffic_history.md)

## Algorithm — the streaming downsample

```mermaid
flowchart TB
    A["read_history(since, max_buckets)"] --> B["_csv_paths(): backup (.1) then live file"]
    B --> C{"since given?"}
    C -- "no — 'Sve'" --> D["_earliest_time(): peek the first real row"]
    C -- "yes — 'Od starta'" --> E["start = traffic.PROCESS_START"]
    D --> F["width = (now - start) / max_buckets"]
    E --> F
    F --> G["stream every row, oldest file first"]
    G --> H{"t < start?"}
    H -- yes --> G
    H -- no --> I["idx = (t - start) / width"]
    I --> J{"idx changed from the open bucket?"}
    J -- yes --> K["flush the open bucket -> Point(avg, max, clients)"]
    J -- no --> L["fold the row into the open bucket"]
    K --> L
    L --> G
    G -- "EOF" --> M["flush the last open bucket"]
    M --> N["return points — at most max_buckets"]
```

Pseudocode:

    paths = [backup_if_it_exists, live_file_if_it_exists]
    start = since IF since given ELSE first real timestamp in paths
    IF start is None OR now <= start: RETURN []
    width = (now - start) / max_buckets

    bucket = None   # (index, out[], in[], clients_max)
    FOR EACH row IN stream(paths):        # ONE pass, ONE line in memory at a time
        IF row.t < start: CONTINUE        # still has to be READ, just not aggregated
        idx = min(max_buckets - 1, (row.t - start) / width)
        IF bucket is not None AND idx != bucket.index:
            emit Point(bucket)            # avg + max, per direction, plus max(clients)
            bucket = None
        bucket = fold(row INTO bucket at idx)
    IF bucket is not None: emit Point(bucket)

The loop never holds more than the current open bucket beyond the output
list — memory is `O(max_buckets)`, not `O(file size)`, because CSV rows are
strictly chronological (the meter only appends) so a bucket index never goes
backwards once it has advanced.

## Algorithm — off the UI thread

```mermaid
flowchart TB
    A["TrafficWindow: span combo -> Last 10 hours / Today / Since start / All"] --> B["HistoryJob.start(key, since, max_buckets)"]
    B --> C["token += 1; threading.Thread(daemon=True).start()"]
    C --> D["background thread: read_history(...)"]
    D --> E{"token still current?"}
    E -- yes --> F["_result = points; running = False"]
    E -- no (a newer span was picked meanwhile) --> G["result discarded"]
    H["TrafficWindow._refresh(), every 1 s"] --> I["HistoryJob.poll() -> (key, points)"]
    I --> J{"result ready?"}
    J -- yes --> K["chart shows the new points; loading = False"]
    J -- no --> L["keep showing the last points (or 'Reading traffic.csv…' if none yet)"]
```

Same pattern as `gui/main_window.py`'s `_run_worker`/`_guarded` — a plain
attribute under a lock, polled by the window's own timer, never a
cross-thread Qt signal.
