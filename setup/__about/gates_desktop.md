# Gates — desktop windows

**Script:** [Gates desktop (script)](../gates_desktop.py) · **Parent:** [Gates](gates.md)

## Purpose
The fail-closed gates that prove the PC's **own Qt windows** — the ones the owner reaches with a mouse, not through his phone.

## Why it is its own file
Split out of [Gates](gates.md) on 2026-08-16 (THE STRUCTURE LAW). `gates.py` stood at exactly 1,000 lines when the widget-orphan gate was added, and the split was made by RESPONSIBILITY rather than by where the line count happened to fall.

Almost everything left in `gates.py` proves something about the **wire and the phone**: a protocol message answers, the page draws, the encoder crops, the shell reports. The four gates here prove something about the **desktop application's own windows**, which have their own toolkit (Qt), their own failure modes and their own rate of change. A widget with no parent is a top-level WINDOW; a background read can land under the wrong span's label. Neither failure has any counterpart on the wire.

## What it holds

| Step | Gate | What it refuses to ship |
|------|------|-------------------------|
| `0b2/6` | [test_traffic_devices.py](../../tests/test_traffic_devices.py) | a per-device identity that changes across a reconnect or a restart, and an old CSV row that stops reading |
| `0b15/6` | [test_traffic_spans.py](../../tests/test_traffic_spans.py) | one span's data drawn under another span's label, and a loading overlay that outlives its work |
| `0b20/6` | [test_traffic_zoom.py](../../tests/test_traffic_zoom.py) | a graph that does not zoom to the rectangle he drew, and a hover point that cannot say what the encoder was doing |
| `0b21/6` | [test_widget_orphan.py](../../tests/test_widget_orphan.py) | a teardown that unparents a still-VISIBLE widget — a window flashed at the centre of his screen |

## Connections

### Uses
- The four `tests/test_*.py` gates above, run as subprocesses under the same interpreter
- `PROJECT_DIR`, computed from this file's own path

### Used by
- [Gates](gates.md) — `desktop_gates(step, run)`, called at the end of `input_gate`. `step` and `run` are PASSED IN for exactly the reason `gates.py` takes them from `build.py`: the caller owns the console's voice and the subprocess policy, and importing them back would be a cycle for no gain

## The rule every entry obeys
Unchanged from its parent — a gate is **fail-closed**, each one carries the live failure it exists to prevent, and each of its checks was proven by planting the defect it is meant to catch.

`0b21` is written as a **SWEEP** over every Qt module rather than as a check on the one call site the owner reported, for the reason constraint 28 names: a rule kept beside one call is read only by somebody already standing there, and this codebase has paid for that twice.
