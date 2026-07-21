# Pairing

**Script:** [Pairing (script)](pairing.py)

## Purpose
Everything needed to connect the tablet the first time: generates the session token, discovers the PC's LAN IP (outbound-routing UDP socket trick — no traffic is actually sent), and presents the pairing URL as console text, console ASCII QR, and a PNG opened in the default image viewer.

The token doubles as the authentication credential — scanning the QR both opens the client page and authorizes it.

## Connections

### Uses
- [Config](config.md) — port, token entropy, QR paths

### Used by
- [Main](main.md) — at startup, before serving

## Functions
- `generate_token()`: `secrets.token_urlsafe`
- `get_lan_ip()`: the IP the tablet must reach
- `show_pairing(token)`: prints/saves/opens the QR; returns the URL
