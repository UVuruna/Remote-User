# Traffic Stream

**Module:** [Traffic Stream (module)](../traffic_stream.py) ·
**Folder:** [server](../___server.md)

## Purpose

What the encoder was DOING when these bytes went out — the per-second stream
descriptor beside every traffic sample (owner request 2026-08-15, T106:
every hover point must also say which device, which quality settings, the
resolution of the slice, the zoom). A traffic number without its cause is
half a measurement; 2 MB/s at native 4K and 2 MB/s at a quarter crop are two
different findings, and until this module `traffic.csv` could not tell them
apart.

## Key Functions

- `from_session(session)` — the descriptor of a live
  [H264 Streamer](h264_streamer.md) session, read off the SAME resolved
  fields `open_session` logs (`_quality`, `_crop`, `_scale`, `_zoom`): so
  the CSV and the server log can never disagree.
- `to_csv_fields(info)` / `from_csv_fields(parts)` — the six cells
  (`STREAM_COLUMNS` = fps, res, bitrate, crop, enc, zoom), APPENDED after
  the five base columns; a row of any older width reads as `empty()`.
- `is_recorded(info)` — a descriptor at all (the `crop` cell is the one
  every recorded second has).
- `hover_lines(info)` — the chart card's lines: `quality: 30 fps · full ·
  low (data saver)`, `slice: 968x2096 → sent 644x1394`, `zoom: x2`;
  `stream: not recorded` for an old row or an idle second — never an
  invented default.

## Wiring

[Web](web.md) calls `traffic.METER.note_stream(from_session(session))` the
moment an H.264 session opens and `note_stream(None)` in the same `finally`
that closes it; [Traffic](traffic.md) writes the descriptor into every
sample and CSV row taken in between; [Traffic History](traffic_history.md)
reads it back per bucket ("last active second wins", the `device` rule) and
[Traffic Chart](../gui/__about/traffic_chart.md) shows it. Fields are strings
on the wire; `""` = not recorded.

## Gate

`tests/test_traffic_zoom.py` §4 — the descriptor reads the session, round-
trips the CSV (eleven cells while streaming, `None` on the idle row), old
4/5/torn rows still read and say "not recorded", and the card names it.
