"""Pairing: token generation, address discovery (LAN + Tailscale), QR display.

The server binds to all interfaces, so it is reachable both on the LAN and over
a Tailscale (WireGuard) private network. When Tailscale is present its address is
preferred for the QR, because that URL works from anywhere — home Wi-Fi, another
network, or mobile data — with the same end-to-end-encrypted, no-open-ports model.
"""

import ipaddress
import logging
import os
import secrets
import socket
import subprocess

import qrcode

from config import SETTINGS

logger = logging.getLogger(__name__)

TAILSCALE_NET = ipaddress.ip_network("100.64.0.0/10")  # CGNAT range Tailscale uses


def generate_token() -> str:
    """Returns the pairing token — persisted across restarts so the owner's
    saved page keeps working through server updates. Delete the token file
    (or set persist_token=False) to force a rotation."""
    if SETTINGS.persist_token and SETTINGS.token_path.exists():
        token = SETTINGS.token_path.read_text(encoding="utf-8").strip()
        if token:
            logger.info("Reusing persisted pairing token from %s", SETTINGS.token_path)
            return token
    token = secrets.token_urlsafe(SETTINGS.token_bytes)
    if SETTINGS.persist_token:
        SETTINGS.token_path.parent.mkdir(exist_ok=True)
        SETTINGS.token_path.write_text(token, encoding="utf-8")
    return token


def get_lan_ip() -> str:
    """The LAN IP the tablet must reach — found by routing a UDP socket outward (no traffic sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def get_tailscale_ip() -> str | None:
    """The PC's Tailscale IPv4 if Tailscale is installed and up, else None.
    A URL on this address reaches the PC from any network."""
    try:
        out = subprocess.run(
            ["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=3
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None
    for line in out.stdout.splitlines():
        line = line.strip()
        try:
            if ipaddress.ip_address(line) in TAILSCALE_NET:
                return line
        except ValueError:
            continue
    return None


def show_pairing(token: str) -> str:
    """Print the pairing URL(s) + a QR, save/open the QR PNG. Returns the QR's URL.
    Tailscale URL is preferred (works anywhere); LAN URL is shown as well."""
    lan_ip = get_lan_ip()
    ts_ip = get_tailscale_ip()
    lan_url = f"http://{lan_ip}:{SETTINGS.port}/?token={token}"
    qr_url = f"http://{ts_ip}:{SETTINGS.port}/?token={token}" if ts_ip else lan_url

    print("\n  Scan with the tablet camera, or open manually:")
    if ts_ip:
        print(f"  Anywhere (Tailscale): {qr_url}")
        print(f"  Home Wi-Fi (LAN):     {lan_url}\n")
    else:
        print(f"  {lan_url}")
        print("  (LAN only — install Tailscale on the PC and phone to use it away from home)\n")

    qr = qrcode.QRCode(border=1)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)

    SETTINGS.qr_image_path.parent.mkdir(exist_ok=True)
    qr.make_image().save(SETTINGS.qr_image_path)
    if SETTINGS.open_qr_image:
        os.startfile(SETTINGS.qr_image_path)

    logger.info("Pairing QR points at %s (LAN: %s)", qr_url, lan_url)
    return qr_url
