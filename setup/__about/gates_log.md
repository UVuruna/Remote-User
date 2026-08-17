# Gates — the use log

**Script:** [Gates log (script)](../gates_log.py) · **Parent:** [Gates](gates.md)

## Purpose
The fail-closed gates that prove the app can **account for its own run** — the use log opened, written, rolled, closed, shipped and summed, and a monitor changing under it reported rather than guessed at.

## Why it is its own file
Split out of [Gates](gates.md) on 2026-08-17 (THE STRUCTURE LAW), the third time that file crossed the 1,000-line wall and the third time the answer was a module rather than a ratchet — after [Gates — desktop windows](gates_desktop.md) and [Gates — the picture](gates_picture.md), both split on 2026-08-16 for the same reason and by the same rule: by RESPONSIBILITY, never by where the line count happened to fall.

Almost everything left in `gates.py` proves a **protocol** message answers, a **layout** behaves, **input** lands, an **action** reaches the owner's own file, or a **doc** stays linked — claims about the wire and the phone, while the session is alive. These five prove something the session can only be asked AFTER it is over: that there is a record of it, that the record is honest about where it ended, and that it was not deleted before it arrived anywhere.

They are one family and they fail as one face of a single defect. A log that is never opened, a log whose footer is never written and a log deleted before its transfer is confirmed all leave the same hole: the run cannot answer for itself afterwards, which is exactly the moment anybody looks at it.

## What it holds

| Step | Gate | What it refuses to ship |
|------|------|-------------------------|
| `0b24/6` | [test_log_wiring.py](../../tests/test_log_wiring.py) | four log modules that are written but never CALLED, an open that runs before the previous run is repaired, or a display change that never reaches capture and the GUI |
| `0b25/6` | [test_session_log.py](../../tests/test_session_log.py) | a header that can go stale, a file that never rolls, a footer written twice, or an unclosed file mistaken for a closed one |
| `0b26/6` | [test_log_shipper.py](../../tests/test_log_shipper.py) | a local file deleted before its transfer is confirmed |
| `0b27/6` | [test_log_summary.py](../../tests/test_log_summary.py) | span/total arithmetic that is wrong at the edges its own docstring names |
| `0b28/6` | [test_display_watch.py](../../tests/test_display_watch.py) | a monitor change that is guessed at instead of reported |

## Connections

### Uses
- The five `tests/test_*.py` gates above, run as subprocesses under the same interpreter
- `PROJECT_DIR`, computed from this file's own path

### Used by
- [Gates](gates.md) — `log_gates(step, run)`, called from inside `input_gate` at the position the first of these five gates used to occupy, so the overall gate order the build runs in does not change. `step` and `run` are PASSED IN for exactly the reason `gates.py` takes them from `build.py`: the caller owns the console's voice and the subprocess policy, and importing them back would be a cycle for no gain

## The rule every entry obeys
Unchanged from its parent — a gate is **fail-closed**, each one carries the live failure it exists to prevent, and each of its checks was proven by planting the defect it is meant to catch.
