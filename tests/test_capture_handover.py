"""CAPTURE HANDOVER GATE (task 193): changing a setting must not kill the picture.

THE FAILURE, DATED IN THE OWNER'S OWN LOG. His report was
"najhitniji bag ... pada cele aplikacije" — changing the bitrate quality brings
the whole app down. 0.0.399 fixed the PHONE's half (the per-client encoder
re-open). This is the DESKTOP's half, and it is a different mechanism
entirely — `%LOCALAPPDATA%\\RemoteUser\\server.log.1`, 2026-08-11:

    00:32:48,546  User settings saved: {... 'h264_bitrate': '20M' ...}
    00:32:48,551  uvicorn: Shutting down
    00:32:58,558  ERROR  Server thread did not stop within 10s
    00:32:58,817  RawFrameSource ready — monitor 0 (3840x2160)
    00:32:58,817  WARNING dxcam: DXCamera instance already exists for device=0
                          output=0 backend=dxgi; returning existing instance.

Apply & restart gives the old server thread ten seconds and then builds the new
one anyway. dxcam's factory is a SINGLETON PER OUTPUT: the new
`RawFrameSource` is handed the OLD run's camera. Moments later the old run's
own `finally` reaches `stream.shutdown()` — and stops the camera the NEW
server is already serving from. The picture dies, ffmpeg is fed nothing, and
the next session cannot even write an init segment.

Nothing in that sequence logs the word "crash", which is why it survived so
long: every line of it looks like an ordinary restart, and the one line that
tells the truth is a warning from a third-party library.

The rule this gate pins: a capture OWNS its monitor, a new capture EVICTS the
previous owner before opening, and `close()` RELEASES the dxcam instance —
releasing being the only thing that makes the factory build a genuinely new
camera rather than hand back the corpse.

Proven with a fake dxcam that reproduces the real factory's semantics exactly
(one instance per output, released instances dropped), so the checks below can
fail — the shipped code passes them, and the real dxcam is not installable in
a test.

Run:  .venv\\Scripts\\python tests/test_capture_handover.py
"""

import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))


class FakeCamera:
    """dxcam's DXCamera, reduced to what capture.py touches — and to the one
    behaviour this gate is about: it can be stopped by whoever holds it."""

    def __init__(self, index):
        self.index = index
        self.width, self.height = 3840, 2160
        self.running = False
        self.stops = 0
        self.is_released = False

    def start(self, **kwargs):
        if self.is_released:
            raise RuntimeError("DXCamera has been released and cannot be reused.")
        self.running = True

    def stop(self):
        self.stops += 1
        self.running = False

    def release(self):
        self.is_released = True

    def get_latest_frame(self):
        time.sleep(0.01)
        if self.is_released:
            raise RuntimeError("DXCamera has been released and cannot be reused.")
        return _FRAME


class FakeFactory:
    """The real factory's rule, which is the whole bug: one instance per
    output, handed back to every later caller — unless it has been RELEASED,
    in which case it is dropped and a new one is built."""

    def __init__(self):
        self.cameras: dict[int, FakeCamera] = {}
        self.builds = 0
        self.reuses = 0

    def create(self, output_idx=0, output_color="BGR"):
        existing = self.cameras.get(output_idx)
        if existing is not None and existing.is_released:
            del self.cameras[output_idx]
            existing = None
        if existing is not None:
            self.reuses += 1
            return existing
        self.builds += 1
        self.cameras[output_idx] = FakeCamera(output_idx)
        return self.cameras[output_idx]

    @staticmethod
    def output_info():
        return "Device[0] Output[0]:"


FACTORY = FakeFactory()

# Installed BEFORE capture is imported — it does `import dxcam` at module level.
sys.modules["dxcam"] = types.SimpleNamespace(
    create=lambda output_idx=0, output_color="BGR": FACTORY.create(output_idx, output_color),
    output_info=FACTORY.output_info,
)

import numpy as np  # noqa: E402

_FRAME = np.zeros((2160, 3840, 3), dtype=np.uint8)

import capture  # noqa: E402
import h264_streamer  # noqa: E402


def _fresh():
    FACTORY.cameras.clear()
    FACTORY.builds = FACTORY.reuses = 0
    capture._OWNERS.clear()


# ── The checks ──────────────────────────────────────────────────────────────

def check_a_restart_gets_its_own_camera() -> bool:
    """THE bug. The second capture — the one Apply & restart builds while the
    old thread is still unwinding — must NOT be handed the first one's
    camera."""
    _fresh()
    old = capture.RawFrameSource()
    new = capture.RawFrameSource()          # the restart, ten seconds early
    ok = old._camera is not new._camera and FACTORY.builds == 2
    new.close()
    return ok


def check_the_dying_run_cannot_stop_the_live_one() -> bool:
    """THE consequence, which is what he actually SAW: the old run's `finally`
    reaches `stream.shutdown()` a moment after the new server is already
    serving. It must stop its OWN camera and nothing else."""
    _fresh()
    old_mgr = h264_streamer.H264Manager("test")
    new_mgr = h264_streamer.H264Manager("test")   # Apply & restart
    live_camera = new_mgr._source._camera
    new_mgr._source.start()
    assert live_camera.running, "the new server never got its capture going"

    old_mgr.shutdown()                            # the superseded run, unwinding

    ok = live_camera.running and not live_camera.is_released
    new_mgr.shutdown()
    return ok


def check_close_releases_so_the_next_create_is_real() -> bool:
    """The mechanism itself: only a RELEASED instance makes dxcam's factory
    build a new one. A capture that merely stops is still the camera the next
    server run will be handed."""
    _fresh()
    first = capture.RawFrameSource()
    camera = first._camera
    first.stop()                       # the IDLE cycle — the instance is kept
    if camera.is_released or FACTORY.create(0) is not camera:
        return False
    first.close()                      # the END of its life — released
    if not camera.is_released:
        return False
    return FACTORY.create(0) is not camera


def check_an_evicted_capture_refuses_to_start() -> bool:
    """A superseded run that tries to start again must be refused loudly, not
    quietly steal the monitor back from the server that now owns it."""
    _fresh()
    old = capture.RawFrameSource()
    new = capture.RawFrameSource()
    try:
        old.start()
    except RuntimeError:
        new.close()
        return True
    old.stop()
    new.close()
    return False


def check_close_is_idempotent() -> bool:
    """Every caller of `close()` sits in a teardown where something else may
    have got there first — a double close must be silent, not an exception in
    a `finally`."""
    _fresh()
    source = capture.RawFrameSource()
    source.close()
    source.close()
    source.stop()                       # and a late stop from the idle path
    return source._camera.is_released


def check_shutdown_gives_the_monitor_back() -> bool:
    """The ORDERLY case, and the belt beside the eviction brace: a server stop
    that completes must leave the monitor genuinely free — released, and owned
    by nobody. Eviction would paper over a `shutdown()` that merely stops, so
    this is asserted at the manager's own boundary; without it the belt could
    rot unnoticed behind the brace."""
    _fresh()
    manager = h264_streamer.H264Manager("test")
    camera = manager._source._camera
    manager._source.start()
    manager.shutdown()
    return camera.is_released and not capture._OWNERS


CHECKS = [
    ("a restart gets its OWN camera, not the old run's",
     check_a_restart_gets_its_own_camera),
    ("the dying run cannot stop the live one's capture",
     check_the_dying_run_cannot_stop_the_live_one),
    ("close() releases, so the next create() really creates",
     check_close_releases_so_the_next_create_is_real),
    ("an evicted capture refuses to start", check_an_evicted_capture_refuses_to_start),
    ("close() is idempotent", check_close_is_idempotent),
    ("a completed shutdown gives the monitor back",
     check_shutdown_gives_the_monitor_back),
]


def main() -> int:
    print("=== CAPTURE HANDOVER GATE (task 193) ===")
    failed = 0
    for name, fn in CHECKS:
        started = time.monotonic()
        try:
            ok = fn()
        except Exception as e:              # a crashing check is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  ({time.monotonic() - started:.1f}s)")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"CAPTURE HANDOVER GATE FAILED — {failed} check(s).")
        return 1
    print("CAPTURE HANDOVER GATE PASSED — a restart never inherits a live camera.")
    return 0


def test_capture_handover():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
