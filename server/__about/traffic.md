# Traffic Meter

**Script:** [Traffic Meter (script)](../traffic.py)

## Purpose
Measure every byte this PC sends to and receives from the phone, so a question
that had been running on assurances can be settled with a reading.

The owner asked for it by name (2026-08-05). He was convinced the app keeps
talking to a locked phone and eating its battery; nothing in the project could
tell either of us whether it does, so every round ended in a claim — *"it
stops, I checked"* — which is exactly what he had stopped believing.

## What it counts, and where
| Path | Where it is counted |
|------|---------------------|
| WebSocket text + binary, both directions | `MeteredSocket`, wrapped **once** around the socket at accept |
| `/upload`, `/upload_files` | `METER.add_in(len(...))` at the read |
| the phone's own totals | `note_phone()` from every `hb` and the parting `away` |

One wrapper, not counters at a dozen send call sites: the socket is what every
handler in [Web Layer](web.md) is handed, so it is the only place that can be
COMPLETE — and an instrument built to settle an argument is worth nothing if it
measures *most* of the traffic.

`MeteredSocket` delegates everything it does not override (`accept`, `close`,
`client`, …), so the rest of the server cannot tell the difference — including
the `is` comparisons that decide which device owns the session, because the
wrapper is what every one of them sees.

## The data model
- **`Sample`** — one second: `t`, `out_bytes`, `in_bytes`, `clients`.
  `clients` is part of the reading on purpose: a zero line means nothing until
  you can see whether anybody was connected to produce it.
- **History** — a ring buffer of `SETTINGS.traffic_history_samples` (3600 = one
  hour) sampled by a daemon thread every `SETTINGS.traffic_sample_s`.
- **Recording** — every sample is appended to `SETTINGS.traffic_csv_path`
  (`%LOCALAPPDATA%/RemoteUser/traffic.csv`), rotated at
  `traffic_csv_max_bytes`, so a night can be read back in the morning. A disk
  failure stops the recording and says so **once**; the live graph continues.
- **The phone's side** — `app_rx/app_tx` (our UID) and `dev_rx/dev_tx` (the
  whole device), cumulative since the phone booted. `snapshot()["phone"]` is
  the delta since it connected; `snapshot()["away_gap"]` is the delta measured
  **across its last absence**, which is the number that answers the battery
  question — measured by the phone, not inferred by us.

The meter is a module singleton (`METER`) and outlives any single server run:
the owner restarts the server from the window (Apply & restart), and an
overnight measurement must not be lost to one settings change. Sampling starts
with the first server start and never stops, so a stopped server reads as a
line of ZEROS rather than a hole in the graph.

**`PROCESS_START`** (BUILD ROUND R4, 2026-08-07) is a module-level constant —
when THIS PROCESS started, set once at import. Deliberately separate from
`METER.since`, which the window's Reset button rewinds: the Traffic window's
**"Od starta"** span names the process's real lifetime, and a stray click on
Reset must never touch that answer. Long-span reads of the recording
(`traffic.csv`) — both "Od starta" and "Sve (iz fajla)" — live in
[Traffic History](traffic_history.md), which this module does not import.

## Connections
### Uses
- [Config](config.md) — sample interval, history length, CSV path and rotation

### Used by
- [Web Layer](web.md) — wraps the socket, counts uploads, forwards `hb.net`
- [Server Core](server_core.md) — starts the sampler
- [Traffic Window](../gui/__about/traffic_window.md) — draws `history()` and
  `snapshot()`
