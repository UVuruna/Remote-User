# Main

**Script:** [Main (script)](main.py)

## Purpose
The headless CLI entry point (dev workflow): [Bootstrap](bootstrap.md) `init_process()` first — DPI awareness must precede every screen-touching import, which is why `server_core` is imported inside `main()` — then `ServerController.run_blocking()` with console pairing (URLs, ASCII QR, PNG in a viewer).

The desktop app uses the same core through its own entry point (see [GUI (subfolder)](gui/___gui.md)); everything that used to be wired here lives in [Server Core](server_core.md) now.

## Connections

### Uses
- [Bootstrap](bootstrap.md) — process init
- [Server Core](server_core.md) — the stack itself

### Used by
- Launched by the owner: `python server/main.py`
