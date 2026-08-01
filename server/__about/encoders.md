# Encoders

**Script:** [Encoders (script)](../encoders.py) ·
**Flow:** [diagram](../__flow/encoders.md)

## Purpose
Picks the H.264 encoder to use on THIS machine so the same app runs on any PC — NVIDIA (NVENC), Intel iGPU (QuickSync), AMD (AMF), or no GPU at all (libx264 software). Being *listed* by `ffmpeg -encoders` is necessary but not sufficient — a listed GPU encoder still fails without the matching hardware/driver — so every candidate is proven by actually test-encoding a few synthetic frames before selection. This preference-order-with-verification is the reason the module gets its own flow diagram despite its small size: it is the decision that determines the whole streaming path (H.264 vs JPEG fallback) for the rest of the session.

## Connections

### Uses
- [Config](config.md) — ffmpeg path + `h264_encoder_order` preference list

### Used by
- [Server Core](server_core.md) — `detect_encoder()` decides H.264 vs JPEG at startup
- [H.264 Streamer](h264_streamer.md) — `encoder_args()` for each session's ffmpeg command

## Functions
- `_listed_encoders()`: parses `ffmpeg -encoders` output for names ffmpeg was built with (video encoders only — line starts with `V`); empty set (and a logged error) when ffmpeg itself is not runnable
- `_test_encode(encoder)`: encodes 8 synthetic frames (`testsrc`) with the candidate and its low-latency args to `-f null -`; `True` only on a clean exit — the only reliable proof the encoder works on this GPU/driver right now
- `detect_encoder()`: walks `SETTINGS.h264_encoder_order`, returns the first name that is both listed and test-encodes; `None` when even software encoding is unavailable (the caller falls back to JPEG)
- `encoder_args(encoder)`: the low-latency ffmpeg argument set for the chosen family (`-bf 0` plus a family-specific low-latency knob — `-tune ll` for NVENC, `-low_power 1` for QSV, `-usage lowlatency` for AMF, `-tune zerolatency` for libx264); unknown names fall back to the libx264 args
