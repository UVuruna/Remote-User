# Traffic Window — Flow

**About:** [description](../__about/traffic_window.md)

## Algorithm — one byte, from the socket to the graph

```mermaid
flowchart TB
    A["ws.accept()"] --> B["traffic.MeteredSocket wraps the socket ONCE"]
    B --> C["every send_text / send_bytes → METER.add_out(len)"]
    B --> D["every receive_text → METER.add_in(len)"]
    E["/upload, /upload_files"] --> F["METER.add_in(len(blob))"]
    G["client hb {net} / away {net}"] --> H["METER.note_phone — the phone's OWN totals"]
    C --> I["sampler thread, once a second"]
    D --> I
    F --> I
    I --> J["Sample(t, out, in, clients) → ring buffer (1 h) + traffic.csv"]
    J --> K["TrafficWindow._refresh, once a second"]
    K --> L["chart.set_samples(history(span), span)"]
    H --> M["snapshot()['phone'] and ['away_gap'] → the header lines"]
```

## Algorithm — painting one frame

```mermaid
flowchart TB
    A["paintEvent"] --> B["peak = max(out, in) over the span, floored at 1 kB/s"]
    B --> C["FIRST: the idle band — every run of samples with clients == 0"]
    C --> D["axes + the peak label + the span labels"]
    D --> E["for each series (out, then in)"]
    E --> F["path through every sample"]
    F --> G["filled area at 18% alpha, then the 2 px line"]
```

The idle band is drawn **behind** the lines, not over them: it is the reading
the owner came here for, so it has to be visible under whatever the lines do.

## Algorithm — what the away-gap line says

```mermaid
flowchart TB
    A["phone connected — note_phone on every heartbeat"] --> B["phone_last keeps the newest reading"]
    B --> C["clients drop to 0 (locked / app closed)"]
    C --> D["_gap_from = phone_last"]
    D --> E["... the phone is away ..."]
    E --> F["it comes back and reports again"]
    F --> G["away_gap = new reading − _gap_from, per counter"]
    G --> H["'While the phone was away for N min: this app used X, the whole phone Y'"]
```

X is what our app spent with the screen off, counted by Android itself. Y is
what the whole phone spent in the same stretch, which is the yardstick that
tells a real leak from a phone simply being a phone.
