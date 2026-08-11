"""RAW PIXEL GATE (task 130): what the CPU carries to the encoder, per frame.

THE COST THIS FILE PINS. Every frame the H.264 path streams is copied out of
dxcam's ring buffer and pushed down a pipe into ffmpeg. That copy — not the
encoding — is the expensive part: NVENC runs on the GPU, but every pixel is
CARRIED there by the CPU. What it used to carry:

    3840x2160 bgr24   24.88 MB/frame   1.49 GB/s at 60 fps, per client
                                       + ffmpeg converting bgr24 -> yuv420p in
                                         swscale, on the CPU, for every frame

That is the pipeline the owner's phone ran out of frames behind (task 151 —
his log's `behind` going negative and pinning at -11 s for two minutes at
60 fps / 20 Mbps). Two changes, both before the pipe:

    1. I420 on OUR side: half the bytes AND it deletes ffmpeg's conversion.
       Measured on his own 4K monitor: 4.30 ms per frame against 5.56 ms.
    2. The default encoder width capped at 2560: 5.53 MB/frame — 0.33 GB/s at
       60 fps, the target — and no phone panel resolves more.

What is proven here, without dxcam, without ffmpeg and without a 4K monitor:

  A. The capture side really emits I420 — the exact byte count, not "smaller".
  B. The ffmpeg input flags SAY yuv420p. These two are one decision: a
     mismatch does not fail, it produces a picture in the wrong COLOURS, which
     is precisely the class of bug nobody's unit test catches.
  C. The colours survive the round trip — a known BGR patch converted here and
     read back is still that colour, so "half the bytes" is not bought with a
     wrong picture.
  D. The downscale happens BEFORE the pipe and honours `h264_max_width`,
     including the even-dimension rule I420 requires.
  E. The delivered cost per frame at 4K60 is at or under the target.

Run:  .venv\\Scripts\\python tests/test_raw_pixel_cost.py
"""

import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from config import SETTINGS  # noqa: E402

TARGET_GB_S = 0.37   # the owner's brief for task 130, at 60 fps
FPS = 60


def _i420_bytes(w: int, h: int) -> int:
    """I420 is one luma byte per pixel plus two quarter-resolution chroma
    planes — 1.5 bytes per pixel, against bgr24's 3."""
    return w * h * 3 // 2


def check_capture_emits_i420() -> bool:
    """A. The real conversion `RawFrameSource._process` performs, on a frame of
    the shape the owner's monitor produces — and the byte count is asserted
    exactly, because "it got smaller" would also pass for a bug that dropped a
    plane."""
    import capture

    w, h = 2560, 1440
    offered: list[bytes] = []

    class _Src(capture.RawFrameSource):
        def __init__(self):                 # no dxcam, no monitor
            self.stream_w, self.stream_h = w, h
            self._sinks_lock = capture.threading.Lock()
            self._sinks = [type("S", (), {"offer": lambda _s, d: offered.append(d)})()]

    # The REAL `_process`, driven with a real frame — not a re-typed copy of
    # the cv2 call, which would go on passing after somebody edited capture.py
    # back to `frame.tobytes()`.
    _Src()._process(np.zeros((h, w, 3), dtype=np.uint8))
    return (len(offered) == 1
            and len(offered[0]) == _i420_bytes(w, h) == 5_529_600)


def check_ffmpeg_is_told_the_same_format() -> bool:
    """B. The other half of the one decision. Read off the real command
    builder, with a stub source, so the two can never drift apart silently."""
    import h264_streamer

    class _Src:
        stream_w, stream_h = 1920, 1080
        capture_fps = 30                 # task 131: the session reads this

    session = h264_streamer.H264Session.__new__(h264_streamer.H264Session)
    session._source = _Src()
    session._encoder = "libx264"
    session._quality = {}
    session.width, session.height = 1920, 1080
    cmd = session._ffmpeg_cmd()
    # The INPUT pix_fmt is the one that must match capture.py: the flag that
    # comes before "-i". A later "-pix_fmt yuv420p" is the OUTPUT format and
    # has always been there — matching on that would prove nothing.
    head = cmd[:cmd.index("-i")]
    return "bgr24" not in head and head[head.index("-pix_fmt") + 1] == "yuv420p"


def check_the_colours_survive() -> bool:
    """C. Half the bytes must not be bought with a wrong picture. A solid
    patch of a known BGR colour, converted exactly as capture.py converts it
    and read back the way ffmpeg reads it."""
    w, h = 64, 64
    for bgr in ((255, 0, 0), (0, 255, 0), (0, 0, 255), (200, 130, 60)):
        frame = np.full((h, w, 3), bgr, dtype=np.uint8)
        i420 = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
        back = cv2.cvtColor(i420, cv2.COLOR_YUV2BGR_I420)
        # 4:2:0 chroma subsampling is lossy by construction; a solid patch
        # should still come back within a couple of levels per channel.
        if int(np.abs(back.astype(int) - frame.astype(int)).max()) > 4:
            return False
    return True


def check_the_downscale_happens_before_the_pipe() -> bool:
    """D. `_stream_size` is the whole downscale: it runs on the capture thread,
    once per frame, before any sink is offered anything. Driven through the
    real method with the camera faked out."""
    import capture

    class _Src(capture.RawFrameSource):
        def __init__(self, w, h):          # no dxcam, no monitor
            self.width, self.height = w, h
            self.raised_fps = self.raised_width = None   # task 131

    cases = [
        (3840, 2160, 2560),   # his monitor at the new default
        (3840, 2160, 3840),   # a PC that pinned native — untouched
        (1920, 1080, 2560),   # already under the cap — never upscaled
        (1366, 769,  2560),   # odd height — I420 needs even dimensions
    ]
    for mon_w, mon_h, cap in cases:
        object.__setattr__(SETTINGS, "h264_max_width", cap)
        w, h = _Src(mon_w, mon_h)._stream_size()
        if w % 2 or h % 2:
            return False                    # I420 requires even dimensions
        if w > cap or w > mon_w:
            return False                    # never above the cap, never upscaled
        if mon_w <= cap and w != mon_w - (mon_w % 2):
            return False                    # under the cap: left alone
        if mon_w > cap:
            # the aspect ratio is kept, within the even-rounding
            if abs(w / h - mon_w / mon_h) > 0.01:
                return False
    return True


def check_the_delivered_cost_hits_the_target() -> bool:
    """E. The number the task was set against: bytes per second the CPU
    carries at 4K60 with the SHIPPED default.

    Read off the dataclass field, never off the live SETTINGS — the checks
    above move that value around, and an earlier draft of this one set it to
    2560 itself and then congratulated itself on the result. A gate that
    supplies its own subject measures nothing (the lesson of task 173: the
    fake threw the commanded rect away and two rounds closed a live bug)."""
    default = type(SETTINGS).__dataclass_fields__["h264_max_width"].default
    object.__setattr__(SETTINGS, "h264_max_width", default)
    import capture

    class _Src(capture.RawFrameSource):
        def __init__(self):
            self.width, self.height = 3840, 2160
            self.raised_fps = self.raised_width = None   # task 131

    w, h = _Src()._stream_size()
    gb_s = _i420_bytes(w, h) * FPS / 1e9
    old_gb_s = 3840 * 2160 * 3 * FPS / 1e9   # what bgr24 at native cost
    print(f"      {w}x{h} I420 = {_i420_bytes(w, h) / 1e6:.2f} MB/frame "
          f"-> {gb_s:.2f} GB/s at {FPS} fps (was {old_gb_s:.2f})")
    return gb_s <= TARGET_GB_S


CHECKS = [
    ("the capture side emits I420, exactly", check_capture_emits_i420),
    ("ffmpeg's INPUT is told yuv420p, not bgr24",
     check_ffmpeg_is_told_the_same_format),
    ("the colours survive the conversion", check_the_colours_survive),
    ("the downscale runs before the pipe and honours h264_max_width",
     check_the_downscale_happens_before_the_pipe),
    ("the delivered cost at 4K60 meets the target",
     check_the_delivered_cost_hits_the_target),
]


def main() -> int:
    saved = SETTINGS.h264_max_width
    print("=== RAW PIXEL GATE (task 130) ===")
    failed = 0
    try:
        for name, fn in CHECKS:
            started = time.monotonic()
            try:
                ok = fn()
            except Exception as e:            # a crashing check is a failing check
                ok = False
                print(f"  ERROR {name}: {e!r}")
            print(f"  {'PASS' if ok else 'FAIL'}  {name}  "
                  f"({time.monotonic() - started:.1f}s)")
            failed += 0 if ok else 1
    finally:
        object.__setattr__(SETTINGS, "h264_max_width", saved)
    print()
    if failed:
        print(f"RAW PIXEL GATE FAILED — {failed} check(s).")
        return 1
    print("RAW PIXEL GATE PASSED — half the bytes, the right colours, before the pipe.")
    return 0


def test_raw_pixel_cost():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
