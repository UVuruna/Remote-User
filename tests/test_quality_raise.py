"""QUALITY RAISE GATE (task 131): the PC's card is a default, not a wall.

THE OWNER'S DECISION. The phone's quality panel could only ever go BELOW the
desktop Settings card — lowering is free, because it happens inside this
client's own ffmpeg and touches nobody. His decision is that raising must work
too, and that the cost is stated rather than hidden: the shared capture has to
grab faster or wider, so every encoder running off it is rebuilt and THE
PICTURE BLINKS ONCE. The panel says so on every raised step before he taps it.

It is affordable for one reason and it is a design rule, not luck: ONE DEVICE
AT A TIME (a second authenticated socket closes the first with 4409). There is
never another client whose picture a raise could disturb.

This matters more since task 130 lowered the shipped encoder width to 2560 to
stop starving the phone: "Native" is how he asks for his 4K monitor back.

What is proven here:

  A. A raise really reaches the camera — the capture is asked for the higher
     rate and the encoder is told to expect it. Being told the DESKTOP's rate
     while frames arrive faster would insert an `fps` filter that throws away
     the very frames the raise asked for, which is a silent no-op wearing a
     working feature's clothes.
  B. A raise really rebuilds — the running encoders end, because every one of
     them was built for the old size.
  C. Lowering is NOT a raise: it must never touch capture. This is the check
     that keeps the feature honest; without it "always rebuild" would pass
     everything above.
  D. A request at or below the desktop's own numbers is not a raise either,
     and asking twice for the same thing rebuilds once.
  E. Letting go gives the desktop its numbers back — a phone that raised the
     ceiling and left must not leave the PC grabbing at 60 fps forever.
  F. The width raise never UPSCALES past the monitor itself.

Run:  .venv\\Scripts\\python tests/test_quality_raise.py
"""

import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

# The fake dxcam of the capture handover gate — same factory semantics, one
# copy. Importing it also installs it into sys.modules before `capture` loads.
from test_capture_handover import FACTORY  # noqa: E402,F401

import capture  # noqa: E402
import h264_streamer  # noqa: E402
from config import SETTINGS  # noqa: E402

DESKTOP_FPS = 30
DESKTOP_WIDTH = 2560
MONITOR_W, MONITOR_H = 3840, 2160


def _fresh() -> capture.RawFrameSource:
    FACTORY.cameras.clear()
    capture._OWNERS.clear()
    object.__setattr__(SETTINGS, "target_fps", DESKTOP_FPS)
    object.__setattr__(SETTINGS, "h264_max_width", DESKTOP_WIDTH)
    return capture.RawFrameSource()


def _encoder_fps(source) -> tuple[int, bool]:
    """What the ffmpeg command really says: its input rate, and whether it
    carries an `fps` filter (which DROPS frames)."""
    session = h264_streamer.H264Session.__new__(h264_streamer.H264Session)
    session._source = source
    session._encoder = "libx264"
    session._quality = {}
    session._crop = None  # full frame — the region crop is test_region_stream's job
    session.width, session.height = source.stream_w, source.stream_h
    cmd = session._ffmpeg_cmd()
    return int(cmd[cmd.index("-r") + 1]), any("fps=" in str(a) for a in cmd)


# ── The checks ──────────────────────────────────────────────────────────────

def check_a_raise_reaches_the_camera() -> bool:
    """A. Both halves: the camera is asked for 60, and the encoder is told 60.
    A mismatch here is the silent failure — ffmpeg would drop back to 30."""
    source = _fresh()
    changed = source.raise_limits(60, MONITOR_W)
    source.start()
    camera_fps = FACTORY.cameras[0].running and source.capture_fps
    rate, drops = _encoder_fps(source)
    source.close()
    return (changed and camera_fps == 60 and rate == 60 and not drops
            and source.stream_w == MONITOR_W)


def check_a_raise_rebuilds_the_encoders() -> bool:
    """B. The blink. Every session was built for the old frame size, so a raise
    has to end them — the stream loop then opens the next one correctly."""
    _fresh()
    manager = h264_streamer.H264Manager("test")

    class _Session:
        def __init__(self): self.stopped = False
        def stop(self): self.stopped = True

    session = _Session()
    manager._sessions.add(session)
    manager._source.start()
    manager._source_running = True
    changed = manager.raise_limits(60, None)
    ok = changed and session.stopped and manager._source.capture_fps == 60
    manager._sessions.clear()
    manager.shutdown()
    return ok


def check_lowering_never_touches_capture() -> bool:
    """C. The check that keeps this honest. Lowering lives inside the client's
    own ffmpeg — it must not report a rebuild, or every quality tap would
    blink the picture and the feature would be worse than none."""
    _fresh()
    manager = h264_streamer.H264Manager("test")
    manager._source.start()
    manager._source_running = True
    ok = (manager.raise_limits(None, None) is False
          and manager.raise_limits(10, 1280) is False
          and manager._source.capture_fps == DESKTOP_FPS
          and manager._source.max_width == DESKTOP_WIDTH)
    manager.shutdown()
    return ok


def check_asking_twice_rebuilds_once() -> bool:
    """D. The panel re-sends the whole quality on every tap and on every
    connect. A raise already in force must be a no-op, not a second blink."""
    source = _fresh()
    first = source.raise_limits(60, None)
    second = source.raise_limits(60, None)
    source.close()
    return first is True and second is False


def check_letting_go_gives_the_desktop_back() -> bool:
    """E. A phone that raised the ceiling and disconnected must not leave the
    PC grabbing at 60 fps for the rest of the evening."""
    source = _fresh()
    source.raise_limits(60, MONITOR_W)
    released = source.raise_limits(None, None)
    ok = (released is True
          and source.capture_fps == DESKTOP_FPS
          and source.max_width == DESKTOP_WIDTH
          and source.stream_w == DESKTOP_WIDTH)
    source.close()
    return ok


def check_a_raise_never_upscales() -> bool:
    """F. The width cap is a ceiling on what the encoder is FED. Asking for
    more than the monitor has buys nothing and must simply be the monitor —
    never an upscale, which costs pixels and adds no detail."""
    source = _fresh()
    source.raise_limits(None, 7680)
    ok = source.stream_w == MONITOR_W and source.stream_h == MONITOR_H
    source.close()
    return ok


CHECKS = [
    ("a raise reaches the camera AND the encoder", check_a_raise_reaches_the_camera),
    ("a raise rebuilds the running encoders", check_a_raise_rebuilds_the_encoders),
    ("lowering never touches capture", check_lowering_never_touches_capture),
    ("asking twice rebuilds once", check_asking_twice_rebuilds_once),
    ("letting go gives the desktop its numbers back",
     check_letting_go_gives_the_desktop_back),
    ("a width raise never upscales past the monitor", check_a_raise_never_upscales),
]


def main() -> int:
    fps, width = SETTINGS.target_fps, SETTINGS.h264_max_width
    print("=== QUALITY RAISE GATE (task 131) ===")
    failed = 0
    try:
        for name, fn in CHECKS:
            started = time.monotonic()
            try:
                ok = fn()
            except Exception as e:          # a crashing check is a failing check
                ok = False
                print(f"  ERROR {name}: {e!r}")
            print(f"  {'PASS' if ok else 'FAIL'}  {name}  "
                  f"({time.monotonic() - started:.1f}s)")
            failed += 0 if ok else 1
    finally:
        object.__setattr__(SETTINGS, "target_fps", fps)
        object.__setattr__(SETTINGS, "h264_max_width", width)
    print()
    if failed:
        print(f"QUALITY RAISE GATE FAILED — {failed} check(s).")
        return 1
    print("QUALITY RAISE GATE PASSED — the PC's card is a default, and a raise blinks once.")
    return 0


def test_quality_raise():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
