"""Hardware/software H.264 encoder detection and ffmpeg argument building.

The same app must run on any PC: NVIDIA (NVENC), Intel iGPU (QuickSync), AMD
(AMF), or no GPU at all (libx264 software). At startup we probe the preference
order and pick the first encoder that actually encodes a frame on THIS machine —
availability in `ffmpeg -encoders` is necessary but NOT sufficient (a listed
encoder still fails if the GPU/driver is missing), so we verify by test-encoding.
"""

import logging
import subprocess

from config import SETTINGS

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000

# Per-encoder low-latency argument sets. Each hardware family names its knobs
# differently; libx264 uses zerolatency. Kept here so the streamer stays generic.
_ENCODER_ARGS = {
    "h264_nvenc": ["-preset", "p1", "-tune", "ll", "-bf", "0", "-rc-lookahead", "0"],
    "h264_qsv":   ["-preset", "veryfast", "-bf", "0", "-low_power", "1"],
    "h264_amf":   ["-usage", "lowlatency", "-quality", "speed", "-bf", "0"],
    "libx264":    ["-preset", "ultrafast", "-tune", "zerolatency", "-bf", "0"],
}


def _listed_encoders() -> set[str]:
    """Encoders ffmpeg was built with (a name here is necessary but not sufficient)."""
    try:
        out = subprocess.run(
            [SETTINGS.ffmpeg_path, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as e:
        logger.error("ffmpeg not runnable at %r: %s", SETTINGS.ffmpeg_path, e)
        return set()
    names = set()
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V"):
            names.add(parts[1])
    return names


def _test_encode(encoder: str) -> bool:
    """Actually encode a few synthetic frames — the only reliable proof the
    encoder works on this GPU/driver right now."""
    cmd = [
        SETTINGS.ffmpeg_path, "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30",
        "-frames:v", "8", "-c:v", encoder, *_ENCODER_ARGS[encoder],
        "-f", "null", "-",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20,
                           creationflags=CREATE_NO_WINDOW)
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as e:
        logger.warning("Encoder %s test raised: %s", encoder, e)
        return False
    if r.returncode == 0:
        return True
    logger.info("Encoder %s not usable here: %s", encoder, (r.stderr or "").strip()[:200])
    return False


def detect_encoder() -> str | None:
    """First encoder from the preference order that genuinely works, or None if
    even software encoding is unavailable (then the caller uses the JPEG path)."""
    listed = _listed_encoders()
    if not listed:
        return None
    for encoder in SETTINGS.h264_encoder_order:
        if encoder in listed and _test_encode(encoder):
            logger.info("Selected H.264 encoder: %s", encoder)
            return encoder
        logger.info("Skipping encoder %s (not listed or failed test)", encoder)
    return None


def encoder_args(encoder: str) -> list[str]:
    """Low-latency ffmpeg args for the chosen encoder."""
    return _ENCODER_ARGS.get(encoder, _ENCODER_ARGS["libx264"])
