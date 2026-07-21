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
    jpeg_quality: int = 70          # 1-100, higher = sharper + more bandwidth (JPEG fallback path)
    max_stream_width: int = 1600    # frames wider than this are downscaled before encoding
                                    # (a 4K monitor at native res is ~216 Mbps — too much for Wi-Fi)

    # H.264 streaming (hardware-encoded, inter-frame compressed — the responsive path).
    # The encoder is auto-detected at startup from a preference order (see below);
    # the JPEG path remains as the ultimate fallback if even software H.264 fails.
    use_h264: bool = True
    ffmpeg_path: str = "ffmpeg"     # on PATH here; a minimal build is bundled for distribution
    # Preference order tried at startup — first one that actually encodes on THIS machine wins.
    # Covers NVIDIA, Intel iGPU, AMD, then pure-software (works on any CPU, no GPU needed).
    h264_encoder_order: tuple[str, ...] = ("h264_nvenc", "h264_qsv", "h264_amf", "libx264")
    h264_bitrate: str = "8M"        # target video bitrate
    h264_gop: int = 60              # keyframe every N frames (reconnect/seek granularity)
    h264_fragment_us: int = 16000   # fMP4 fragment target (µs) — below one frame interval,
                                    # so every encoded frame ships in its own fragment
    h264_head_timeout: float = 5.0  # seconds to wait for ffmpeg's init segment (ftyp+moov)
    h264_queue_chunks: int = 64     # per-client outbound chunk queue; a full queue means the
                                    # client cannot keep up — its session is reset, not delayed

    # Virtual cursor — DXGI capture never includes the mouse pointer, so the
    # server streams the cursor position and the client draws it.
    cursor_hz: int = 30             # position polls per second (sent only on change)

    # Pairing
    token_bytes: int = 16           # entropy of the pairing token
    persist_token: bool = True      # reuse the token across restarts (no re-scan after
                                    # every server update); delete token_path to rotate
    token_path: Path = PROJECT_ROOT / "logs" / "token.txt"

    # Remote access — a Cloudflare "quick tunnel" gives an https URL that works
    # from anywhere (no account, no login, no open port). Opt-in per run: turning
    # it on makes the PC reachable over the internet by anyone holding the URL+token.
    # (The future desktop GUI turns this into a one-tap toggle.)
    use_tunnel: bool = False
    cloudflared_path: Path = PROJECT_ROOT / "bin" / "cloudflared.exe"
    cloudflared_url: str = (
        "https://github.com/cloudflare/cloudflared/releases/latest/download/"
        "cloudflared-windows-amd64.exe"
    )
    tunnel_timeout: int = 25        # seconds to wait for the tunnel URL
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
