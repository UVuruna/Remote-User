# Config API

**Module:** [Config API (module)](../config_api.py) ·
**Folder:** [server](../___server.md)

## Purpose

The `config` message's wire shape — the one frame after which the phone tears
down and rebuilds its whole view/decode pipeline. Sent after auth and after
EVERY stream (re)start (monitor switch, H.264 session reset, quality change).
Moved out of [Web](web.md) on 2026-08-12: web.py stood at the 1,000-line wall
again, and the [Actions API](actions_api.md) precedent applies — the module
that owns a message's wire shape is ONE module, so no second sender can ever
carry different fields.

## Key Functions

- `send_config(ws, stream, token, codec=None, region=None)` — assembles and
  sends the frame. Most fields are built elsewhere and only shipped here:
  `monitor`/`monitors` ([Monitor API](monitor_api.md)), `base` and `ui`
  ([Config](config.md)), `tailscale_url` ([Pairing](pairing.md), checked
  fresh per config so a login mid-run shows on reconnect), `app_version` /
  `apk_version` (the phone updates from THIS PC, never the internet). Two
  fields are optional and session-specific:
  - `codec` — the exact MSE string parsed from the live init segment
    ([H264 Streamer](h264_streamer.md)), never guessed;
  - `stream_region` — the monitor-normalized rect THIS stream covers (owner
    order 2026-08-12: the per-client encoder crops to the focused layout, so
    the phone never decodes pixels it does not show). Absent = full frame —
    a page that predates the field changes nothing.

## Used by

- [Web](web.md) — the H.264 loop (per session, with codec + region), the
  JPEG path and the monitor-switch resend
- `client/connection.js` — the consumer of every field
