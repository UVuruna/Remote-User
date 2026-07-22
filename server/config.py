"""All tunable values for the Remote User server. No other file may hardcode these.

Two layers:
- `Settings` defaults (this file) — the single source of every tunable.
- A user settings JSON with overrides — written by the desktop GUI, loaded at
  startup. Only keys in USER_ADJUSTABLE may be overridden; bad values are
  logged and skipped, never fatal.

Paths depend on how the app runs:
- Dev (repo checkout): everything stays inside the project (logs/, PAIRING_QR.png,
  actions.json, ffmpeg from PATH).
- Installed EXE (PyInstaller onedir): user data (settings, token, logs, QR,
  edited actions.json) lives in %LOCALAPPDATA%/RemoteUser — Program Files is
  not writable; bundled read-only data (client/, default actions.json) comes
  from the PyInstaller bundle dir, and the installer places ffmpeg/ next to
  the exe.

The module-level SETTINGS instance is the only one, shared by every module.
Changing values at runtime goes through apply() (controlled mutation of the
shared instance — a plain assignment raises, catching accidental writes).
"""

import json
import logging
import os
import sys
from dataclasses import dataclass, fields
from pathlib import Path

logger = logging.getLogger(__name__)

FROZEN = getattr(sys, "frozen", False)
PROJECT_ROOT = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))  # onedir: <app>/_internal
USER_DIR = (
    Path(os.environ["LOCALAPPDATA"]) / "RemoteUser" if FROZEN else PROJECT_ROOT / "logs"
)
SETTINGS_PATH = USER_DIR / "settings.json"

# Keys the desktop GUI may override (persisted in settings.json).
USER_ADJUSTABLE = {
    "port", "monitor_index", "target_fps", "use_h264",
    "h264_max_width", "h264_bitrate", "jpeg_quality", "open_qr_image",
}


def _default_ffmpeg() -> str:
    if FROZEN:
        bundled = PROJECT_ROOT / "ffmpeg" / "ffmpeg.exe"
        if bundled.exists():
            return str(bundled)
    return "ffmpeg"  # dev: on PATH


def _default_actions() -> Path:
    if FROZEN:
        user_copy = USER_DIR / "actions.json"
        if user_copy.exists():
            return user_copy  # owner-edited copy wins over the bundled default
        return BUNDLE_DIR / "actions.json"
    return PROJECT_ROOT / "actions.json"


@dataclass(frozen=True)
class Settings:
    # Network
    host: str = "0.0.0.0"
    port: int = 8777

    # Streaming
    monitor_index: int = 0          # which monitor to capture (0 = primary)
    target_fps: int = 30
    jpeg_quality: int = 70          # 1-100, higher = sharper + more bandwidth (JPEG fallback path)
    max_stream_width: int = 1600    # JPEG path: frames wider than this are downscaled before
                                    # encoding (a 4K monitor as JPEG at native res is ~216 Mbps)

    # H.264 streaming (hardware-encoded, inter-frame compressed — the responsive path).
    # The encoder is auto-detected at startup from a preference order (see below);
    # the JPEG path remains as the ultimate fallback if even software H.264 fails.
    use_h264: bool = True
    ffmpeg_path: str = _default_ffmpeg()
    # Preference order tried at startup — first one that actually encodes on THIS machine wins.
    # Covers NVIDIA, Intel iGPU, AMD, then pure-software (works on any CPU, no GPU needed).
    h264_encoder_order: tuple[str, ...] = ("h264_nvenc", "h264_qsv", "h264_amf", "libx264")
    h264_max_width: int = 3840      # H.264 path cap — native 4K streams fine (inter-frame
                                    # compression keeps a static screen at a few Mbps) and zoom
                                    # stays sharp; lower it only for weak decoders/links
    h264_bitrate: str = "12M"       # target bitrate cap — reached only on heavy motion; static
                                    # screens use a fraction of it regardless of resolution
    h264_gop: int = 60              # keyframe every N frames (reconnect/seek granularity)
    h264_fragment_us: int = 16000   # fMP4 fragment target (µs) — below one frame interval,
                                    # so every encoded frame ships in its own fragment
    h264_head_timeout: float = 5.0  # seconds to wait for ffmpeg's init segment (ftyp+moov)
    h264_queue_chunks: int = 256    # per-client outbound chunk queue (~4 s at full bitrate); a
                                    # full queue means the client cannot keep up — its session
                                    # is reset instead of building latency

    # Virtual cursor — DXGI capture never includes the mouse pointer, so the
    # server streams the cursor position and the client draws it.
    cursor_hz: int = 30             # position polls per second (sent only on change)

    # Pairing
    token_bytes: int = 16           # entropy of the pairing token
    persist_token: bool = True      # reuse the token across restarts (no re-scan after
                                    # every server update); delete token_path to rotate
    token_path: Path = USER_DIR / "token.txt"

    # Remote access — a Cloudflare "quick tunnel" gives an https URL that works
    # from anywhere (no account, no login, no open port). Opt-in per run: turning
    # it on makes the PC reachable over the internet by anyone holding the URL+token.
    # (The desktop GUI can turn this into a one-tap toggle.)
    use_tunnel: bool = False
    cloudflared_path: Path = PROJECT_ROOT / "bin" / "cloudflared.exe"
    cloudflared_url: str = (
        "https://github.com/cloudflare/cloudflared/releases/latest/download/"
        "cloudflared-windows-amd64.exe"
    )
    tunnel_timeout: int = 25        # seconds to wait for the tunnel URL
    open_qr_image: bool = not FROZEN  # CLI: open the QR PNG in a viewer; the GUI shows it itself
    # Kept where the owner can reopen it; regenerated on every server start.
    qr_image_path: Path = (USER_DIR if FROZEN else PROJECT_ROOT) / "PAIRING_QR.png"

    # Logging
    log_dir: Path = USER_DIR if FROZEN else PROJECT_ROOT / "logs"
    log_file: str = "server.log"
    log_max_bytes: int = 1_000_000
    log_backups: int = 3

    # Client files (bundled read-only in the installed app)
    client_dir: Path = BUNDLE_DIR / "client" if FROZEN else PROJECT_ROOT / "client"
    favicon_path: Path = (BUNDLE_DIR if FROZEN else PROJECT_ROOT) / "assets" / "logo.svg"
    # The Android app, served at /app.apk when present ("Get the app" on the
    # phone page — no manual file shuffling). Built by setup/build_apk.py;
    # the desktop installer ships a copy next to the exe.
    apk_path: Path = PROJECT_ROOT / ("RemoteUser.apk" if FROZEN else "dist/RemoteUser.apk")

    # Action sets (chord shortcuts shown in the radial wheels) — hand-edited by
    # the owner; re-read on every client connection, so edits show on refresh.
    actions_path: Path = _default_actions()


SETTINGS = Settings()


def apply(**changes) -> None:
    """Controlled mutation of the one shared SETTINGS instance — every module
    that imported it sees the new values (the dataclass stays frozen against
    accidental assignment). Server components must be restarted to pick up
    changes that shape them (port, monitor, encoder settings)."""
    for key, value in changes.items():
        object.__setattr__(SETTINGS, key, value)


def _coerced(key: str, value):
    """Validates a user-file override against the dataclass field type.
    Returns the coerced value, or None when the value is unusable.
    (fields() reports the annotation as a class here; the string forms are
    accepted too in case deferred annotations are ever enabled.)"""
    kind = {f.name: f.type for f in fields(Settings)}[key]
    try:
        if kind in (bool, "bool"):  # bool first — bool is a subclass of int
            if not isinstance(value, bool):
                raise ValueError(f"expected true/false, got {value!r}")
            return value
        if kind in (int, "int"):
            return int(value)
        if kind in (float, "float"):
            return float(value)
        if kind in (str, "str"):
            return str(value)
    except (TypeError, ValueError) as e:
        logger.warning("settings.json: bad value for %s (%s) — using default", key, e)
        return None
    logger.warning("settings.json: %s has unsupported type %s — using default", key, kind)
    return None


def load_user_settings() -> None:
    """Applies overrides from the user settings file onto SETTINGS. Call once
    at startup, after logging is configured. Missing file = defaults."""
    try:
        # utf-8-sig: tolerate a BOM — editors and PowerShell redirects add one
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return
    except (json.JSONDecodeError, OSError) as e:
        logger.error("settings.json unreadable (%s) — using defaults", e)
        return
    accepted = {}
    for key, value in raw.items():
        if key not in USER_ADJUSTABLE:
            logger.warning("settings.json: %r is not a user-adjustable key — ignored", key)
            continue
        coerced = _coerced(key, value)
        if coerced is not None:
            accepted[key] = coerced
    if accepted:
        apply(**accepted)
        logger.info("User settings applied: %s", accepted)


def save_user_settings(changes: dict) -> None:
    """Persists the given overrides (merged over the existing file) and applies
    them to the running SETTINGS. The GUI is the only writer."""
    current = {}
    try:
        current = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    unknown = set(changes) - USER_ADJUSTABLE
    if unknown:
        raise ValueError(f"Not user-adjustable: {sorted(unknown)}")
    current.update(changes)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(current, indent=2), encoding="utf-8")
    apply(**changes)
    logger.info("User settings saved: %s", changes)
