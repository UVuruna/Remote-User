# Gates

**Script:** [Gates (script)](../gates.py) · **Flow:** [flow](../__flow/gates.md)

## Purpose
The fail-closed gate suite — every check a build must survive before a single byte is packaged.

## Why it is its own file
Split out of [Build](build.md) on 2026-08-12 (THE STRUCTURE LAW). `build.py` had reached 1,000 lines and the overwhelming majority of them were this one function: a gate is added to it in almost every round, while the steps that actually assemble an installer — version info, icons, vendor payloads, PyInstaller, signing, NSIS — have barely changed in months.

That is two responsibilities with two completely different rates of change sharing a file, which is the seam the law exists to find. This module answers *may this tree ship at all*; `build.py` answers *how is it packaged*. Nothing here knows about PyInstaller or NSIS; nothing there knows what a gate proves.

## Connections

### Uses
- Every `tests/test_*.py` gate, run as a subprocess under the same interpreter
- `PROJECT_DIR`, computed from this file's own path
- [Gates — desktop windows](gates_desktop.md) — `desktop_gates(step, run)`, the last thing `input_gate` calls. Split out on 2026-08-16 by RESPONSIBILITY: everything here proves something about the wire and the phone, those four prove something about the PC's own Qt windows
- [Gates — the picture](gates_picture.md) — `picture_gates(step, run)`, called from inside `input_gate`. Split out the same day by RESPONSIBILITY: those seven prove the capture/encode/decode/draw path — that the owner actually sees a picture
- [Gates — the use log](gates_log.md) — `log_gates(step, run)`, called from inside `input_gate`. Split out on 2026-08-17, the third crossing of the wall, by RESPONSIBILITY: everything here is a claim about the wire and the phone while the session is alive, those five prove the run can answer for itself once it is over

### Used by
- [Build](build.md) — `input_gate(step, run)`, called before anything is generated. `step` and `run` are PASSED IN rather than imported: `build.py` owns the console's voice and the subprocess policy (masking, failure handling), and importing them back would be a cycle for no gain

## The rule every entry obeys
A gate is **fail-closed**. A missing dependency (playwright, Chromium, node) fails the BUILD — it is never skipped silently, because a gate that quietly stops running is worse than no gate: it reports green.

Each gate is added with a comment saying which live failure it exists to prevent, and each of its checks was proven by planting the defect it is meant to catch. A gate that passes against a fixture built to match itself proves nothing — the lesson of the `actions.json` merge, recorded in [CLAUDE.md](../../CLAUDE.md).

## Ordering
The order in the function is the order they run, and it is deliberate at one point only: the cheapest refusals come first, so a tree that cannot ship costs as little as possible to find out.
