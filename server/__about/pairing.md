# Pairing

**Script:** [Pairing (script)](../pairing.py)

## Purpose
Everything needed to connect the tablet the first time: generates and persists the pairing token, discovers the PC's LAN IP and (if present) its Tailscale IPv4, and presents the pairing URL as console text + ASCII QR + a PNG (the desktop GUI renders the same PNG bytes in-window instead of the console path).

The server binds all interfaces, so it is reachable on both the LAN and a Tailscale mesh; the QR always encodes the LAN address (a phone's first scan happens at home, and a phone without Tailscale cannot open a Tailscale URL at all) — the client page then guides the phone to the Tailscale "anywhere" address itself, in its own wizard.

The token doubles as the authentication credential — scanning the QR both opens the client page and authorizes it.

## Connections

### Uses
- [Config](config.md) — port, token entropy/persistence path, QR image path

### Used by
- [Server Core](server_core.md) — token + URLs at server startup, `show_pairing()` for console mode
- [Web Layer](web.md) — `get_tailscale_ip()` on every `config` message (checked fresh so a Tailscale sign-in mid-run shows up on reconnect)
- `gui/main_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — renders `qr_png()` in the QR card

## Functions
- `generate_token()`: `secrets.token_urlsafe(token_bytes)`, persisted to `token_path` and reused across restarts so the owner's saved page survives server updates without re-scanning; delete the file (or set `persist_token=False`) to force a rotation
- `get_lan_ip()`: the LAN IP the tablet must reach, found by routing a UDP socket outward (no traffic actually sent)
- `tailscale_exe()`: the `tailscale` CLI wherever it is — `shutil.which` first, then the default install path — because a fresh install updates the SYSTEM PATH, but an already-running server process keeps its cached environment (bit this live: login done, server still reported no Tailscale)
- `get_tailscale_ip()`: the PC's Tailscale IPv4 via `tailscale ip -4`, validated inside `100.64.0.0/10` (the Tailscale CGNAT range), or `None` when not installed/signed in
- `pairing_urls(token)`: `{qr, lan, tailscale, tailscale_ip}` — `qr` and `lan` are always the LAN URL; `tailscale` is the full anywhere-URL or `None`
- `qr_png(url)`: the QR as PNG bytes, for the desktop GUI's in-window card
- `show_pairing(token)`: console pairing (CLI path) — prints both URLs + an ASCII QR, saves the PNG (opens it too when `open_qr_image`); returns the QR's URL
