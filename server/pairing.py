"""Pairing: token generation, LAN address discovery, QR code display."""

import logging
import os
import secrets
import socket

import qrcode

from config import SETTINGS

logger = logging.getLogger(__name__)


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
