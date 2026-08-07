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
    K --> L{"span kind?"}
    L -- "recent (2 min/10 min/1 h)" --> M["chart.set_data(history(span) as Points, downsampled=False)"]
    L -- "since_start / all" --> N["traffic_history.HistoryJob — see its own flow doc"]
    N --> O["chart.set_data(job result, downsampled=True)"]
    H --> P["snapshot()['phone'] and ['away_gap'] → the header lines"]
```

The long spans do not read `traffic.csv` on this same tick — `_maybe_start_
history` only (re)starts the background job when the span just changed or
the 30 s refresh interval elapsed; every other tick just polls for a result
that may not be ready yet.

## Algorithm — painting one frame

```mermaid
flowchart TB
    A["paintEvent"] --> A2["fillRect(rect, surface0) — the WINDOW's own colour"]
    A2 --> A3["fillRect(plot, surface1) + hairline border — the plot reads as a PANEL"]
    A3 --> B{"loading?"}
    B -- yes --> C["'Reading traffic.csv…' — nothing else drawn"]
    B -- no --> D["pts = _coalesce(points, plot.width()) — never > 1 point/px"]
    D --> E["peak = max(out_max, in_max) over pts, floored at 1 kB/s"]
    E --> F["ticks = _y_ticks(peak) — the 1/2/5 x 10^n ladder"]
    F --> G["FIRST: the idle band — every run of pts with clients == 0"]
    G --> H["Y gridlines + labels, X axis + time labels"]
    H --> I["for each series (out, then in): avg line + fill"]
    I --> J{"downsampled?"}
    J -- yes --> K["+ faint dotted MAX hairline"]
    J -- no --> L["skip — avg == max already"]
    K --> M{"mouse over the plot?"}
    L --> M
    M -- yes --> N["crosshair at the nearest point + the hover card (English text), flipped if it would run off the widget"]
```

Below the chart, `_LegendMark` (a small `QPainter` widget, not a `QLabel`
full of glyph characters) draws the legend's four swatches and the
recording-status dot — each reading its colour from a `color_fn` callable at
PAINT time, exactly like `out_color()` / `in_color()` above it, so a runtime
theme flip is never frozen into a stale swatch.

The idle band is drawn **behind** the lines, not over them: it is the reading
the owner came here for, so it has to be visible under whatever the lines do.
`_coalesce` runs on EVERY paint, for every span — for the two long spans it
is the thing that actually enforces "never more than one point per pixel" at
the window's current width; for the three short spans it is usually a no-op
(their point count already fits most window widths).

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

## Build round R3 (2026-08-07) — themes

```
paintEvent
   fillRect(TOKENS["surface0"])          <- read LIVE, every frame
   idle band   _alpha(TOKENS["text2"], 26)
   gridlines   _alpha(TOKENS["text2"], 40)
   series      out_color()  <- FUNCTIONS since R3, not module QColors
               in_color()
   hover card  TOKENS["surface2"] + _alpha(TOKENS["text2"], 70)
```

## Build round R6 (2026-08-07) — independent grade fixes

```
paintEvent
   fillRect(rect, TOKENS["surface0"])    <- window background, unchanged
   fillRect(plot, TOKENS["surface1"])    <- NEW: the plot is a panel
   drawRect(plot, _alpha(text2, 35))     <- NEW: hairline panel edge
   ... unchanged from here ...

legend / status row
   _LegendMark(color_fn, kind)           <- NEW: drawn swatches, not glyphs
     kind "series" -> faded fill + solid top line, in the series' own colour
     kind "band"   -> the idle-band colour, bordered
     kind "dotted" -> a dashed line, text2
     kind "dot"    -> a filled circle, success/error (recording status)
```

See [About — Build round R6](../__about/traffic_window.md#build-round-r6-2026-08-07--the-independent-grades-six-findings)
for the full list of what each fix answers.
