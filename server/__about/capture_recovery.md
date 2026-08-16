# Capture Recovery

**Script:** [Capture Recovery (script)](../capture_recovery.py)

## Purpose
Brings a DEAD camera back — the job [Screen Capture](capture.md) deliberately does not own. `capture.py` owns a LIVE camera's life (open, grab, hand on, put down); this module owns the case where that camera has stopped producing pictures and cannot be talked to any more, which needs different rules: nothing here may block, nothing here may trust dxcam to let go, and every rung of its ladder must SAY which rung brought the picture back.

## The failure this exists for (owner report 2026-08-16)

He connected from the tablet at 19:19:24. Everything worked EXCEPT the picture: his running apps were listed, he built a layout, the layout really was created on the PC — and the canvas stayed the blue `--canvas-bg` the whole time. The control path never touches capture, which is exactly why it looked healthy while the one thing he wanted was dead.

His log dated every step:

```
19:19:24,309  dxcam: Frame buffer build(start): 3840x2160
19:19:24,334  Desktop duplication access loss detected (HRESULT=0x887A0026)
19:19:24,335  Output recovery attempt 1 failed (Output is not attached to
              desktop.); retrying in 0.250s.
19:19:41,353  Camera stop: Capture thread did not stop within timeout
19:19:51,376  ERROR web: H.264 session failed to open: Capture is already
              running. Call stop() first.
...          the same three lines every ~12 s, for 3.8 HOURS
23:04:37,876  Output recovery attempt 2760 failed (Output is not attached
              to desktop.); retrying in 5.000s.
```

FOUR mechanisms had to line up, and naming all four is the point — fixing any one alone leaves the blue screen reachable by the other three:

1. `dxcam/core/display_recovery.py` retries in a bare `while True` with no give-up and no stop-flag check, so the camera's own thread parks in there for as long as the process lives.
2. `dxcam/core/output_recovery.py::_refresh_output_desc` re-enumerates the adapter's outputs only when `update_desc()` raises a transient COM error. When the descriptor reads back fine but says `AttachedToDesktop == False`, it keeps the SAME `IDXGIOutput` and raises "Output is not attached to desktop." forever, against an object that can never change its mind.
3. `dxcam.DXFactory` is a singleton built at IMPORT time; its `Output` objects are enumerated once for the process's whole life. So even [Screen Capture](capture.md)'s own task-193 eviction path (`close()` → `dxcam.create()`) hands the new camera the SAME stale output — re-opening was never going to work.
4. `BaseCapture.start()`'s 2026-07-29 reset-and-retry assumes `stop()` can stop the camera. Against a parked recovery thread it cannot: dxcam's `stop()` joins ten seconds, gives up, leaves the "capturing" flag standing, and the next `start()` raises the identical error — the 12-second cycle repeating in his log for 3.8 hours, every H.264 session failing to open.

MEASURED, not reasoned: while that loop was still failing on his machine, a fresh `dxcam.create()` in a SEPARATE PROCESS grabbed 3840x2160 frames instantly. The display was attached the whole time — only the in-process DXGI objects were stale. That measurement is what makes the ladder below a fix rather than a hope, and it is why the re-enumerate rung exists at all.

## Connections

### Uses
- `dxcam` directly (the DXFactory singleton and camera release/re-enumeration internals) — this is the one place outside [Screen Capture](capture.md) allowed to reach into dxcam's privates, and only through the one function that does it

### Used by
- [Screen Capture](capture.md) — `BaseCapture.rebuild_camera()` calls `abandon_camera()` then `reenumerate_dxgi()` as its ladder's rungs 1 and 3; rung 2 (reopen) is a plain `dxcam.create()` on the capture's own side
- [H.264 Streamer](h264_streamer.md) — `H264Manager` owns one `CaptureGuard`, watching its `RawFrameSource`'s frame clock and wired to `on_capture_state` so the phone is told

## The ladder

```
rung 1  abandon      — give up on the parked camera WITHOUT waiting for it
rung 2  reopen        — a fresh dxcam.create() on the existing enumeration
rung 3  re-enumerate  — rebuild dxcam's factory so brand-new Output objects
                         exist, then reopen
```

Every rung is logged with its outcome, so the next report answers the question this one could not.

### `abandon_camera(camera, wait_s=RELEASE_WAIT_S)` — rung 1
Stops owning the camera and tries to FREE its duplication for real — dropping it without releasing is not enough, because DXGI allows one desktop duplication per output and the replacement's `DuplicateOutput` fails with `E_INVALIDARG` against a handle the old camera still holds. That is not a theory: it is what this module's own smoke test did on the first attempt against a HEALTHY camera, which would have made the whole ladder a no-op on every case except the one it was written for.

The real release runs on a THROWAWAY thread and is waited on for `RELEASE_WAIT_S` (2.5 s — the line between "it answered" and "it is never going to," not an estimate of how long anything should take, constraint 15). A healthy camera lets go at once. A parked one never will, because its own thread is inside dxcam's infinite retry loop — there the wait is abandoned, the instance is marked `_is_released = True` so dxcam's factory drops it from its registry, and the parked thread is knowingly LEAKED. A leaked idle daemon thread is the price of a picture coming back; it is bounded by the guard's cooldown and named in the log rather than hidden. Returns True only when the camera really let go; never raises — this runs on the path that exists because something already went wrong.

### `reenumerate_dxgi()` — rung 3
Rebuilds dxcam's `DXFactory` singleton so its `Output` objects are enumerated AGAIN — the answer to mechanism 3 above. It reaches into dxcam's privates deliberately isolated to this one function: a dxcam release that changes its factory shape breaks exactly this call and it returns False with a warning instead of taking capture down with it. Verified on the owner's machine: a rebuilt factory produces a camera that grabs at full resolution. Returns True only when the factory object genuinely changed.

### `phone_notice(ws, loop, toast)`
Bridges the guard (a plain thread, no event loop) to one phone's status pill. Lives HERE rather than in the web layer because telling the owner the picture died is part of RECOVERING from it, not part of serving a socket — and `web.py` stood at the structure law's 1,000-line wall when this was written, the law noticing the same thing. `toast` is passed in rather than imported so this module keeps no opinion about the protocol; a send that fails is dropped and logged, never raised, because a guard that dies of a broken pipe takes the only way back with it.

### `CaptureGuard`
Watches ONE capture's frame clock (`capture.frame_age()`) and runs the ladder when it stalls. It judges by the only fact that matters to the owner — did a picture arrive — and never by whether dxcam reported an error, because the failure it exists for reports at INFO level to its own logger and otherwise looks exactly like a healthy idle camera.

- `is_wanted`: asked before every verdict, so an idle server (nobody connected, capture deliberately stopped) is never judged "stalled"
- `on_state(ok, detail)`: fired on every transition (down → up, up → down) — the [H.264 Streamer](h264_streamer.md) wires this to `on_capture_state`, which the web layer points at the connected phone's toast
- `stall_seconds` (default 8.0): the give-up point dxcam itself does not have — dxcam's own recovery backs off to a 5 s retry, so anything shorter would fire during a legitimate transient (a mode switch, a fullscreen game taking the output) dxcam does heal by itself
- `cooldown_s` (default 20.0): never runs the ladder faster than this — a rebuild can leak a parked thread (rung 1), so a tight loop would trade a blue screen for a thread leak; the cooldown is what keeps the cure bounded
- `poll_s` (default 1.0): how often the guard looks — it only reads a float, so this is free
- `tick()`: one judgement, split out from the run loop so a gate can drive it with its own clock instead of sleeping through real seconds
- `start()` / `stop()`: one daemon thread, idempotent, joined with a 2 s timeout on stop

## Design decisions

- **Judged by the frame clock, never by an error.** The one honest evidence that capture is alive is that a picture arrived — see [Screen Capture](capture.md) → `frame_age()`. Anything keyed on an exception or a log line misses exactly this failure, because dxcam's own recovery loop reports it at INFO and keeps running, looking idle-and-healthy the whole time.
- **A defect found by RUNNING the fix, not reading it.** The first version of `abandon_camera` dropped the camera without attempting a real release, and DXGI's one-duplication-per-output rule meant the replacement's `DuplicateOutput` failed with `E_INVALIDARG` — against a HEALTHY camera, in the module's own smoke test. That is why rung 1 waits briefly for a real release before giving up on it.
- **`_fresh_camera` proves a camera by grabbing a frame from it**, not by whether it constructed — a camera that constructs and never yields would report the blue screen as fixed while changing nothing the owner can see.
- **The phone is told.** A blue canvas that says nothing is half of what he actually lived through — he could not tell a dead capture from a dead app, and there was nothing on the page to read. `phone_notice` exists so a lost picture and its return both reach the status pill.
