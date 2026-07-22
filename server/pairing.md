# Pairing

**Script:** [Pairing (script)](pairing.py)

## Purpose
Everything needed to connect the tablet the first time: generates the session token, discovers the PC's LAN IP (outbound-routing UDP socket trick — no traffic is actually sent), and presents the pairing URL as console text, console ASCII QR, and a PNG opened in the default image viewer.

The token doubles as the authentication credential — scanning the QR both opens the client page and authorizes it.

## Connections

### Uses
- [Config](config.md) — port, token entropy, QR paths

### Used by
- [Server Core](server_core.md) — token + URLs at startup
- [Main Window](gui/main_window.md) — renders `qr_png()` in the QR card

## Functions
- `generate_token()`: `secrets.token_urlsafe`, **persisted** to the token file and reused across restarts so the owner's saved page survives server updates without re-scanning; delete the file (or set `persist_token=False`) to rotate
- `get_lan_ip()`: the LAN IP the tablet must reach on the home Wi-Fi
- `get_tailscale_ip()`: the PC's Tailscale IPv4 (via `tailscale ip -4`, validated in 100.64.0.0/10) if installed, else `None` — a URL on this address reaches the PC from any network (see [Remote Access](../README.md#remote-access))
- `tailscale_exe()`: the tailscale CLI wherever it is — PATH or the default install dir (a fresh install updates the SYSTEM path, but running processes keep their cached environment; bit us live). All callers (IP lookup, GUI login button) go through this
- `pairing_urls(token)`: the address set — `qr` (ALWAYS the LAN address: first scan happens at home, and a phone without Tailscale cannot open a Tailscale URL; the client page then guides the switch), `lan`, `tailscale` (full anywhere-URL or None), `tailscale_ip`
- `qr_png(url)`: the QR as PNG bytes — the desktop GUI renders these directly in-window
- `show_pairing(token)`: console pairing (CLI path) — prints both URLs + ASCII QR, saves/opens the PNG; returns the QR's URL
