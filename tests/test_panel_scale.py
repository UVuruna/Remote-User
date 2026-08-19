"""PANEL SCALE GATE — the PC never encodes more pixels than the glass can show.

Owner order 2026-08-12, approved on a ballot: "what is the point of the PC
sending 4K if the Android device cannot receive it? A Redmi Pad is 1920x1200
and we send it 4K in desktop mode. It should be downscaled ON THE PC to the
resolution the Android device can accept. And when Android zooms, that is a
crop again."

The rule: `scale = min(crop, device panel)` — never up. Upscaling a small crop
to the panel spends bitrate inventing nothing, which is why a focused layout
comes out SHARPER than before at the same bitrate.

What is proven here, with the REAL `H264Session` (fake frame source, no ffmpeg
spawn — only the command and the arithmetic) and the REAL client mirror run in
node:

1. His own case: a 3840x2160 monitor on a 1920x1200 panel encodes 1920 wide,
   even in both dimensions, the monitor's aspect preserved.
2. A crop NARROWER than the panel is never scaled up — no scale filter at all.
3. crop and scale compose in the right ORDER in the actual ffmpeg argv, and
   there is exactly ONE scale filter (the resolution step and the panel cap
   reconcile into one size, the smallest winning).
4. An auth with NO panel field behaves exactly as today — byte for byte the
   old command.
5. The wiring exists end to end: the page sends real panel pixels, web reads
   them off auth and passes them into open_session, and the client's decode
   ceiling judges the SCALED width (server and page compute the same number).

Run:  .venv\\Scripts\\python tests/test_panel_scale.py
Requires: node on PATH for the client mirror (the test_decode_caps.py
precedent, registered fail-closed in setup/build.py). Never skip it silently.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import h264_streamer  # noqa: E402

WEB = (PROJECT / "server" / "web.py").read_text(encoding="utf-8")
CONNECTION = (PROJECT / "client" / "connection.js").read_text(encoding="utf-8")
QUALITY = (PROJECT / "client" / "quality.js").read_text(encoding="utf-8")
CAPS = PROJECT / "client" / "decode-caps.js"

# His tablet, in real panel pixels.
PANEL = {"w": 1920, "h": 1200}
# His own live layout (server.log 2026-08-12 14:39:49) — a quarter-width slice
# of the 4K desktop, which comes out 968x2096: narrower than the panel.
HIS_REGION = {"x": 0.3736979166666667, "y": 0.000462962962962963,
              "w": 0.25234375, "h": 0.9708333333333333}


class _FakeSource:
    stream_w, stream_h = 3840, 2160
    capture_fps = 60


def session(region=None, quality=None, panel=None):
    return h264_streamer.H264Session(
        _FakeSource(), "libx264", lambda b: None, lambda: None,
        quality=quality, region=region, panel=panel)


def vf(s):
    cmd = s._ffmpeg_cmd()
    return cmd[cmd.index("-vf") + 1].split(",") if "-vf" in cmd else []


def check_his_4k_desktop_on_a_1920x1200_tablet():
    s = session(panel=PANEL)
    assert s._scale is not None, "the 4K desktop was sent whole to a 1920 panel"
    w, h = s._scale
    assert w == 1920, f"panel width is the ceiling — got {w}"
    assert w % 2 == 0 and h % 2 == 0, f"odd encoded size {s._scale}"
    # 16:9 preserved: 1920x1080, not the panel's own 1920x1200.
    assert h == 1080, f"aspect not preserved — got {w}x{h}"
    assert vf(s) == ["scale=1920:1080"], vf(s)
    print(f"  his 4K desktop encodes {w}x{h} for a 1920x1200 tablet — a quarter of the pixels")


def check_a_crop_narrower_than_the_panel_is_not_scaled_up():
    s = session(region=HIS_REGION, panel=PANEL)
    cw, ch = s._crop[:2]
    assert cw < PANEL["w"], f"pick a narrower crop for this check — {cw}"
    # Long side against long side: 2096 tall against the panel's 1920 long
    # side is a real, honest downscale — but it may NEVER go the other way.
    if s._scale:
        w, h = s._scale
        assert w <= cw and h <= ch, f"a {cw}x{ch} crop was UPSCALED to {w}x{h}"
    # A crop smaller in BOTH axes than the panel must not be touched at all.
    small = session(region={"x": 0, "y": 0, "w": 0.25, "h": 0.25}, panel=PANEL)
    assert small._crop[:2] == (960, 540), small._crop
    assert small._scale is None, f"a 960x540 crop grew a scale: {small._scale}"
    assert not any(p.startswith("scale=") for p in vf(small)), vf(small)
    print("  a crop smaller than the panel keeps its own size — no upscale, ever")


def check_crop_and_scale_compose_in_the_right_order():
    s = session(region=HIS_REGION, quality={"fps": 30, "res": "1/2", "bitrate": "high"},
                panel=PANEL)
    parts = vf(s)
    assert parts[0].startswith("crop="), f"crop is not first: {parts}"
    scales = [i for i, p in enumerate(parts) if p.startswith("scale=")]
    assert len(scales) == 1, f"the step and the panel cap made TWO scales: {parts}"
    assert scales[0] == 1, f"scale must follow the crop directly: {parts}"
    assert any(p.startswith("fps=") for p in parts[2:]), f"fps override lost: {parts}"
    # The step is what wins here (half of 968x2096), being smaller than the
    # panel cap — the smallest factor wins, and it is applied to the CROP.
    cw, ch = s._crop[:2]
    w, h = s._scale
    assert w <= cw // 2 and h <= ch // 2 + 2, f"the 1/2 step was lost: {s._scale} of {cw}x{ch}"
    print(f"  chain {','.join(parts)} — crop, then one reconciled scale, then fps")


def check_no_panel_field_is_exactly_todays_behaviour():
    for quality in (None, {"fps": 0, "res": "full", "bitrate": "high"},
                    {"fps": 30, "res": "1/2", "bitrate": "low"}):
        for region in (None, HIS_REGION):
            old = session(region=region, quality=quality)._ffmpeg_cmd()
            for panel in (None, {}, {"w": 0, "h": 0}, {"w": "x", "h": None}):
                got = session(region=region, quality=quality, panel=panel)._ffmpeg_cmd()
                assert got == old, f"panel={panel} changed the command: {got}"
    # And the old full-frame world still has no filters whatsoever.
    assert "-vf" not in session()._ffmpeg_cmd(), "a bare session grew a filter chain"
    print("  no panel field (or a nonsense one): the command is byte-for-byte today's")


def _node(body):
    if not shutil.which("node"):
        raise AssertionError(
            "node is required for the panel scale gate (it runs the REAL "
            "client/decode-caps.js mirror) — install Node.js. Never skip a "
            "gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_panel_gate_"))
    script = work / "run.js"
    script.write_text(f"const M = require({json.dumps(str(CAPS))});\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    try:
        out = subprocess.run([shutil.which("node"), str(script)],
                             capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def check_the_page_computes_the_same_width_as_the_server():
    cases = [((3840, 2160), 1920), ((1920, 1080), 1920), ((960, 540), 960)]
    got = _node("[" + ",".join(
        f"M.panelScaledWidth({w},{h},{{w:1920,h:1200}})" for (w, h), _ in cases) + "]")
    for ((w, h), want), have in zip(cases, got):
        server = session(panel=PANEL)  # same rule, exercised below on the real crop
        assert have == want, f"page says {have} for {w}x{h}, expected {want}"
    assert server._scale[0] == got[0], "page and server disagree on the 4K case"
    # An unknown panel caps nothing — the page must never invent one either.
    assert _node("M.panelScaledWidth(3840,2160,null)") == 3840
    print("  the page mirrors the server's width exactly, and caps nothing without a panel")


def check_the_wiring_end_to_end():
    assert "panel: devicePanel()" in CONNECTION, \
        "the page no longer sends its real panel pixels on auth"
    assert "screen: { w: window.screen.width" in CONNECTION, \
        "`screen` was repurposed — an older PC reads it as an aspect"
    assert "devicePixelRatio" in CAPS.read_text(encoding="utf-8"), \
        "devicePanel no longer converts CSS px to real panel pixels"
    assert re.search(r'"panel": first\.get\("panel"\)', WEB), \
        "web no longer reads the panel off the auth message"
    assert re.search(r"manager\.open_session,(?:.|\n){0,500}?conn\.get\(\"panel\"\),\n", WEB), \
        "the panel is not passed into open_session"
    assert re.search(r"function effectiveWidth[^}]*panelScaledWidth", QUALITY, re.S), \
        "the decode ceiling ignores the panel cap — a 4K cap would outlive the 4K"
    print("  wiring: page -> auth -> web -> session -> ceiling, all present")


def main():
    print("PANEL SCALE GATE - the PC never encodes more pixels than the glass shows")
    check_his_4k_desktop_on_a_1920x1200_tablet()
    check_a_crop_narrower_than_the_panel_is_not_scaled_up()
    check_crop_and_scale_compose_in_the_right_order()
    check_no_panel_field_is_exactly_todays_behaviour()
    check_the_page_computes_the_same_width_as_the_server()
    check_the_wiring_end_to_end()
    print("OK - all panel scale checks passed")


def test_gate():
    main()


if __name__ == "__main__":
    sys.exit(main())
