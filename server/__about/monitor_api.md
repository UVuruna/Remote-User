# Monitor API

**Script:** [Monitor API (script)](../monitor_api.py)

## Purpose
The phone's MONITOR protocol: which screens the PC can stream, and moving the stream to one of them. Split out of [Web Layer](web.md) on 2026-08-09 under THE STRUCTURE LAW — that file was sitting exactly on the 1,000-line limit when task 155 needed two more `config` fields, and "which monitor" is a coherent responsibility with one engine underneath it, exactly like [Layout API](layout_api.md) next door.

**What task 155 changed (owner 2026-08-09).** Monitor used to be a CYCLER in the phone's Settings set: it stepped to the next output and told you where you had landed *afterwards*. His instruction was to take it out of Settings and give it to the layout panels — the single "Desktop" row becomes one row per monitor, each naming its resolution, so it is a list you choose from instead of a button you press until the right screen appears. That needs the two things this module owns: the LIST that rides the existing `config` frame, and a switch that can be told WHICH monitor rather than only "the next one".

## Connections

### Uses
- [Monitors](monitors.md) — `describe()` for the list, `rect_for_size()` for the injector's new rect
- [Layout API](layout_api.md) — `toast()`, and `send_layout_state()` when a switch leaves a focused layout

### Used by
- [Web Layer](web.md) — `config_fields()` in `_send_config`, `switch()` on the `monitor_switch` message

## Functions
- `config_fields(stream)`: the two OPTIONAL `config` keys — `monitor` (the output being streamed) and `monitors` (`{index, width, height, primary}` for every streamable output). Optional on purpose: a phone too old to read them draws the single "Desktop" row it always did, so nothing on the wire became required. Read fresh per config, and `config` is re-sent after every stream restart — a monitor switch included — so the phone's idea of which screen it is looking at is refreshed by the very event that changes it, with no second message to keep in step.
- `switch(ws, injector, stream, layouts, conn, index, send_config)`: move the stream. `index` is the monitor the phone asked for and is OPTIONAL — `None`, or anything outside the range of real outputs, falls back to the cycle this message has always performed, so an older page keeps working and a stale index from an unplugged monitor cannot address nothing. A switch LEAVES a focused layout (it stands always-on-top on a screen the phone can no longer see — audit 2026-08-05), swaps the injector's monitor rect, and re-sends `config` in JPEG mode only (an H.264 client gets one from its fresh session).

## Notes
`send_config` is passed IN rather than imported: it belongs to the socket in [Web Layer](web.md), and a module reaching back for it would make this split a name change instead of a boundary.
