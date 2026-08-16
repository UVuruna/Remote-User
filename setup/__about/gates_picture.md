# Gates — the picture

**Script:** [Gates picture (script)](../gates_picture.py) · **Parent:** [Gates](gates.md)

## Purpose
The fail-closed gates that prove the owner actually **SEES** something — the capture/encode/decode/draw path, from the PC's own camera through to the frame the phone draws.

## Why it is its own file
Split out of [Gates](gates.md) on 2026-08-16 (THE STRUCTURE LAW), the same day [Gates — desktop windows](gates_desktop.md) was split for the same reason: `gates.py` had reached 1,000 lines again, and the split was made by RESPONSIBILITY rather than by where the line count happened to fall.

Almost everything left in `gates.py` proves a **protocol** message answers, a **layout** behaves, **input** lands, an **action** reaches the owner's own file, or a **doc** stays linked. The seven gates here prove the **picture** itself — that capture is alive, the encoder crops right, the phone's own decoder can drink what it is sent, and the page actually draws the frame that arrives. That is the exact failure class of 2026-08-16: his blue canvas, where every control on the phone kept answering and there was no picture behind any of them.

## What it holds

| Step | Gate | What it refuses to ship |
|------|------|-------------------------|
| `0g/6` | [test_stream_lifecycle.py](../../tests/test_stream_lifecycle.py) | a client that is gone but whose encoder keeps running |
| `0r/6` | [test_quality_reset.py](../../tests/test_quality_reset.py) | a bitrate change that kills the whole app |
| `0ao/6` | [test_decode_caps.py](../../tests/test_decode_caps.py) | a stream request the phone's own decoder cannot drink |
| `0ap/6` | [test_region_stream.py](../../tests/test_region_stream.py) | an encoder that does not crop to the focused layout, or a page that maps the crop back wrong |
| `0b18/6` | [test_redraw_rate.py](../../tests/test_redraw_rate.py) | a phone that redraws on the panel's refresh rate instead of on frame arrival |
| `0b13/6` | [test_zoom_crop.py](../../tests/test_zoom_crop.py) | a zoom that upscales blur instead of cropping the encoder, or a cellular bitrate that ignores the crop |
| `0b23/6` | [test_capture_recovery.py](../../tests/test_capture_recovery.py) | a dead camera the phone cannot tell apart from a dead app |

## Connections

### Uses
- The seven `tests/test_*.py` gates above, run as subprocesses under the same interpreter
- `PROJECT_DIR`, computed from this file's own path

### Used by
- [Gates](gates.md) — `picture_gates(step, run)`, called from inside `input_gate` at the position the first of these seven gates used to occupy, so the overall gate order the build runs in does not change. `step` and `run` are PASSED IN for exactly the reason `gates.py` takes them from `build.py`: the caller owns the console's voice and the subprocess policy, and importing them back would be a cycle for no gain

## The rule every entry obeys
Unchanged from its parent — a gate is **fail-closed**, each one carries the live failure it exists to prevent, and each of its checks was proven by planting the defect it is meant to catch.
