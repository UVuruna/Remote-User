# Cursor API

**Module:** [Cursor API (module)](../cursor_api.py) ·
**Folder:** [server](../___server.md)

## Purpose

The `cursor` message's one sender: the PC pointer's POSITION (normalized,
quantized to 4 decimals) and its SHAPE ([Cursor Shape](cursor_shape.md)) for
the phone's client-drawn virtual cursor, sent only on change at
`SETTINGS.cursor_hz`, plus the injector's self-check alarm ride-along
(`INPUT_BLOCKED_TOAST` — UIPI eating input, the 2026-07-29 dead-mouse
failure, must be SAID on the phone).

Moved out of [Web](web.md) on 2026-08-15 — THE STRUCTURE LAW: web.py stood at
the 1,000-line wall again — the [Config API](config_api.md) precedent (one
module owns one message's wire shape). `web.py` imports `send_cursor` under
its old `_send_cursor` name, so its one call site and
`tests/test_cursor_shape.py` read unchanged.

## Key Functions

- `send_cursor(ws, injector)` — the loop; ends on `WebSocketDisconnect` /
  `RuntimeError` (socket closed under it — normal lifecycle).

## Gate

`tests/test_cursor_shape.py` drives the loop over a fake socket.
