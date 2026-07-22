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
import shutil
import socket
import subprocess
from pathlib import Path

import qrcode

from config import SETTINGS

logger = logging.getLogger(__name__)

TAILSCALE_NET = ipaddress.ip_network("100.64.0.0/10")  # CGNAT range Tailscale uses
TAILSCALE_DEFAULT = Path(r"C:\Program Files\Tailscale\tailscale.exe")
CREATE_NO_WINDOW = 0x08000000  # a console app must never flash a window from the GUI exe


def tailscale_exe() -> str | None:
    """The tailscale CLI, whether or not it is on this process's PATH — a
    fresh install updates the SYSTEM path, but already-running processes keep
    their cached environment (bit us live: the login was done, the server
    still reported no Tailscale). The default install location is the fallback."""
    found = shutil.which("tailscale")
    if found:
        return found
    if TAILSCALE_DEFAULT.exists():
        return str(TAILSCALE_DEFAULT)
    return None


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
    """The PC's Tailscale IPv4 if Tailscale is installed and signed in, else
    None. A URL on this address reaches the PC from any network."""
    exe = tailscale_exe()
    if exe is None:
        return None
    try:
        out = subprocess.run(
            [exe, "ip", "-4"], capture_output=True, text=True, timeout=3,
            creationflags=CREATE_NO_WINDOW,
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


def pairing_urls(token: str) -> dict:
    """The addresses a client can use. `qr` is ALWAYS the LAN address: the
    first scan happens at home, and a phone without Tailscale cannot open a
    Tailscale URL at all. The client page then GUIDES the phone to the
    `tailscale` anywhere-address itself (in-page wizard, one time) — the user
    follows on-screen steps, never a chat/manual instruction."""
    lan_ip = get_lan_ip()
    ts_ip = get_tailscale_ip()
    lan_url = f"http://{lan_ip}:{SETTINGS.port}/?token={token}"
    ts_url = f"http://{ts_ip}:{SETTINGS.port}/?token={token}" if ts_ip else None
    return {"qr": lan_url, "lan": lan_url, "tailscale": ts_url, "tailscale_ip": ts_ip}


def qr_png(url: str) -> bytes:
    """The pairing QR as PNG bytes — the desktop GUI renders these directly."""
    import io
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image().save(buf, format="PNG")
    return buf.getvalue()


def show_pairing(token: str) -> str:
    """Console pairing: print the URL(s) + an ASCII QR, save (and optionally
    open) the QR PNG. Returns the QR's URL. Used by the CLI entry point; the
    desktop GUI shows the QR in-window via pairing_urls() + qr_png() instead."""
    urls = pairing_urls(token)
    qr_url, lan_url = urls["qr"], urls["lan"]

    print("\n  Scan with the tablet camera, or open manually:")
    if urls["tailscale"]:
        print(f"  Home Wi-Fi (QR):      {lan_url}")
        print(f"  Anywhere (Tailscale): {urls['tailscale']}")
        print("  (the phone page offers a guided switch to the anywhere link)\n")
    else:
        print(f"  {lan_url}")
        print("  (LAN only — the desktop app guides the Tailscale setup)\n")

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
