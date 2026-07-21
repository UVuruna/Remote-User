"""Pairing: token generation, LAN address discovery, QR code display."""

import logging
import os
import secrets
import socket

import qrcode

from config import SETTINGS

logger = logging.getLogger(__name__)


def generate_token() -> str:
    return secrets.token_urlsafe(SETTINGS.token_bytes)


def get_lan_ip() -> str:
    """The LAN IP the tablet must reach — found by routing a UDP socket outward (no traffic sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def show_pairing(token: str) -> str:
    """Print the pairing URL + ASCII QR to the console, save/open the QR PNG. Returns the URL."""
    url = f"http://{get_lan_ip()}:{SETTINGS.port}/?token={token}"

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)

    print(f"\n  Scan with the tablet camera, or open manually:\n  {url}\n")
    qr.print_ascii(invert=True)

    SETTINGS.qr_image_path.parent.mkdir(exist_ok=True)
    qr.make_image().save(SETTINGS.qr_image_path)
    if SETTINGS.open_qr_image:
        os.startfile(SETTINGS.qr_image_path)

    logger.info("Pairing URL ready at %s", url)
    return url
