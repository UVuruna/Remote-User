# Encoders

**Script:** [Encoders (script)](encoders.py)

## Purpose
Picks the H.264 encoder to use on THIS machine so the app runs on any PC — NVIDIA (NVENC), Intel iGPU (QuickSync), AMD (AMF), or no GPU at all (libx264 software). Being *listed* by ffmpeg is necessary but not sufficient (a listed GPU encoder still fails without the hardware/driver), so each candidate is proven by **actually test-encoding** a few synthetic frames before selection.

Preference order (config `h264_encoder_order`): `h264_nvenc → h264_qsv → h264_amf → libx264`. The first that genuinely encodes wins; if none do (no ffmpeg), the caller falls back to the JPEG path.

## Connections

### Uses
- [Config](config.md) — ffmpeg path + preference order

### Used by
- [H.264 Streamer](h264_streamer.md), [Main](main.md) — encoder selection at startup

## Functions
- `detect_encoder()`: returns the first working encoder name, or `None`
- `encoder_args(encoder)`: low-latency ffmpeg args per family (nvenc `-tune ll`, qsv `-low_power`, amf `-usage lowlatency`, x264 `-tune zerolatency`), all with `-bf 0`
