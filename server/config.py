"""All tunable values for the Remote User server. No other file may hardcode these."""

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    # Network
    host: str = "0.0.0.0"
    port: int = 8777

    # Streaming
    monitor_index: int = 0          # which monitor to capture (0 = primary)
    target_fps: int = 30
    jpeg_quality: int = 70          # 1-100, higher = sharper + more bandwidth
    max_stream_width: int = 1600    # frames wider than this are downscaled before encoding
                                    # (a 4K monitor at native res is ~216 Mbps — too much for Wi-Fi)

    # Pairing
    token_bytes: int = 16           # entropy of the pairing token
    persist_token: bool = True      # reuse the token across restarts (no re-scan after
                                    # every server update); delete token_path to rotate
    token_path: Path = PROJECT_ROOT / "logs" / "token.txt"
    open_qr_image: bool = True      # open the QR PNG in the default viewer on startup
    # Kept in the project root so the owner can reopen it anytime; regenerated on
    # every server start (the token rotates per run, old QR stops working).
    qr_image_path: Path = PROJECT_ROOT / "PAIRING_QR.png"

    # Logging
    log_dir: Path = PROJECT_ROOT / "logs"
    log_file: str = "server.log"
    log_max_bytes: int = 1_000_000
    log_backups: int = 3

    # Client files
    client_dir: Path = PROJECT_ROOT / "client"

    # Action sets (chord shortcuts shown in the radial wheels) — hand-edited by
    # the owner; re-read on every client connection, so edits show on refresh.
    actions_path: Path = PROJECT_ROOT / "actions.json"


SETTINGS = Settings()
