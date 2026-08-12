"""Region Stream Gate: the phone never decodes pixels it does not show.

Owner order 2026-08-12, in his own words: "zašto bi telefon dekodirao nešto
što ne vidi — zašto 60p na 4K kada mu stiže samo isečak ekrana koji on vidi"
(lang-ok: owner quote). Until this round H.264 always streamed the FULL
monitor: a focused layout covering a quarter of a 4K desktop still cost the
device a full 3840x2160@60 decode, of which three quarters were cropped away
on the canvas. That is what drowned his tablet — and it wasted the strongest
phone on the market just the same.

What is proven here, with the REAL `H264Session` (fake frame source, no
ffmpeg spawn — only the command and the arithmetic) and the REAL
`layout_api.send_layout_state`:

1. The crop is the layout's region, even-aligned (yuv420p subsamples chroma
   2x2 — an odd size fails the encoder, an odd offset shears colours), and
   `session.region` reports the EFFECTIVE normalized rect of that pixel crop.
2. The crop filter comes FIRST in the ffmpeg chain — the res/fps overrides
   apply to the crop, exactly as the phone's panel reads them.
3. A full-frame region or none at all means NO crop and no `stream_region` —
   an old server's world, byte for byte.
4. A region that no longer matches what the running session encodes ends that
   session at the layout choke point (send_layout_state) — and an unchanged
   region never does (a reset per layout_state would blink on every frame).
5. The wiring exists end to end: web passes the region in and records the
   intention copy, config carries `stream_region`, and the page maps the
   video onto it (a crop the page ignores would smear a quarter-screen
   picture over the whole desktop).

Run:  .venv\\Scripts\\python tests/test_region_stream.py
"""

import asyncio
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import h264_streamer  # noqa: E402
import layout_api  # noqa: E402

WEB = (PROJECT / "server" / "web.py").read_text(encoding="utf-8")
CONFIG_API = (PROJECT / "server" / "config_api.py").read_text(encoding="utf-8")
STATE = (PROJECT / "client" / "state.js").read_text(encoding="utf-8")
CONNECTION = (PROJECT / "client" / "connection.js").read_text(encoding="utf-8")
RENDER = (PROJECT / "client" / "render.js").read_text(encoding="utf-8")
QUALITY = (PROJECT / "client" / "quality.js").read_text(encoding="utf-8")

# The owner's own live layout (server.log 2026-08-12 14:39:49) — a VS Code
# layout on his 4K monitor, a quarter of its width.
HIS_REGION = {"x": 0.3736979166666667, "y": 0.000462962962962963,
              "w": 0.25234375, "h": 0.9708333333333333}


class _FakeSource:
    stream_w, stream_h = 3840, 2160
    capture_fps = 60


def session(region, quality=None):
    return h264_streamer.H264Session(
        _FakeSource(), "libx264", lambda b: None, lambda: None,
        quality=quality, region=region)


def check_his_layout_becomes_a_quarter_width_crop():
    s = session(HIS_REGION)
    w, h, x, y = s._crop
    assert w % 2 == h % 2 == x % 2 == y % 2 == 0, f"odd crop {s._crop}"
    assert 0 <= x and x + w <= 3840 and 0 <= y and y + h <= 2160, s._crop
    # A quarter-width, full-height slice — the decode his tablet drowned in
    # was FOUR times this.
    assert 940 <= w <= 980 and 2080 <= h <= 2160, s._crop
    # The effective rect the page maps by is the CROP's own normalization,
    # never the request's decimals.
    assert s.region == {"x": x / 3840, "y": y / 2160, "w": w / 3840, "h": h / 2160}
    print(f"  his 4K layout encodes as {w}x{h}+{x}+{y} — a quarter of the decode")


def check_full_frame_and_none_mean_no_crop():
    for region in (None, {"x": 0, "y": 0, "w": 1, "h": 1}):
        s = session(region)
        assert s._crop is None and s.region is None, (region, s._crop)
        assert not any("crop=" in a for a in s._ffmpeg_cmd()), \
            "a full frame grew a crop filter"
    print("  full frame / no region: no crop, no stream_region — the old world")


def check_the_crop_comes_first_in_the_chain():
    s = session(HIS_REGION, quality={"fps": 30, "res": "1/2", "bitrate": "high"})
    cmd = s._ffmpeg_cmd()
    vf = cmd[cmd.index("-vf") + 1]
    parts = vf.split(",")
    assert parts[0].startswith("crop="), f"crop is not first: {vf}"
    assert any(p.startswith("scale=") for p in parts[1:]), f"res override lost: {vf}"
    assert any(p.startswith("fps=") for p in parts[1:]), f"fps override lost: {vf}"
    print("  ffmpeg chain: crop first, then this client's res/fps overrides")


def check_an_off_grid_region_is_even_aligned():
    s = session({"x": 0.1111, "y": 0.2222, "w": 0.3333, "h": 0.4444})
    w, h, x, y = s._crop
    assert w % 2 == h % 2 == x % 2 == y % 2 == 0, s._crop
    assert w >= 2 and h >= 2, s._crop
    print("  arbitrary decimals land on the even grid the encoder demands")


class _WS:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(json.loads(text))


class _Layouts:
    """The one method send_layout_state calls, echoing the focus back."""

    def state(self, active, region):
        return {"type": "layout_state", "layouts": [], "active": active,
                "region": region, "orient": "landscape"}


def _run_state(conn):
    asyncio.run(layout_api.send_layout_state(_WS(), _Layouts(), conn))


def check_a_region_change_resets_the_session_and_an_unchanged_one_never_does():
    fired = []
    base = {"active": 0, "reset_stream": lambda: fired.append(1)}
    # Unchanged: the running session already encodes this region.
    _run_state({**base, "region": HIS_REGION, "stream_region": HIS_REGION})
    assert not fired, "an unchanged region reset the stream — that blinks on every layout_state"
    # Changed: the phone focused a different layout (or the desktop).
    _run_state({**base, "region": HIS_REGION, "stream_region": None})
    assert fired, "a region change did not end the mismatched session"
    fired.clear()
    # Desktop after a layout: region None, session still cropping.
    _run_state({"active": None, "region": None, "stream_region": HIS_REGION,
                "reset_stream": lambda: fired.append(1)})
    assert fired, "back-to-desktop left the encoder cropping to a dead layout"
    fired.clear()
    # JPEG connections never set the hook — and must never crash here.
    _run_state({"active": 0, "region": HIS_REGION})
    assert not fired
    print("  the choke point resets on change, holds on same, skips JPEG")


def check_the_wiring_end_to_end():
    assert re.search(r"req_region = conn\.get\(\"region\"\)", WEB), \
        "web no longer reads the region for the session"
    assert re.search(r"manager\.open_session,(?:.|\n){0,400}?req_region,\n", WEB), \
        "the region is not passed into open_session"
    assert 'conn["stream_region"] = req_region' in WEB, \
        "the intention copy is gone — layout_api compares against nothing"
    assert re.search(r"_send_config\([^)]*region=session\.region", WEB), \
        "config is not told what the session really crops"
    assert '"stream_region"' in CONFIG_API, "config_api lost the field"
    assert "let streamRegion" in STATE, "state.js lost streamRegion"
    assert re.search(r"streamRegion = msg\.stream_region \|\| null", CONNECTION), \
        "the page no longer reads stream_region"
    assert "restateQualityIfChanged()" in CONNECTION, \
        "a region change no longer re-evaluates the decode ceiling's cap"
    assert re.search(r"streamRegion\s*\?\s*{[^}]*D\.x \+ streamRegion\.x \* D\.w", RENDER), \
        "render.js no longer maps the video onto the region rect"
    assert re.search(r"function effectiveWidth[^}]*streamRegion", QUALITY, re.S), \
        "the decode ceiling ignores the crop — a desktop cap would outlive the desktop"
    print("  wiring: web -> session -> config -> page mapping -> ceiling, all present")


def main():
    print("REGION STREAM GATE - the phone never decodes pixels it does not show")
    check_his_layout_becomes_a_quarter_width_crop()
    check_full_frame_and_none_mean_no_crop()
    check_the_crop_comes_first_in_the_chain()
    check_an_off_grid_region_is_even_aligned()
    check_a_region_change_resets_the_session_and_an_unchanged_one_never_does()
    check_the_wiring_end_to_end()
    print("OK - all region stream checks passed")


if __name__ == "__main__":
    sys.exit(main())
