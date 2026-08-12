"""THE DEVICE'S OWN DECODER IS A WALL — and the phone must never request a
stream it cannot drink.

Why this gate exists (owner report 2026-08-12: "native 20 Mbps still sends no
picture"). His server log held the whole story: at 3840x2160@30 (level 5.1)
the tablet played smoothly — behind=0.31s steady, jumps=0 for two minutes —
and the moment the PC card went to 60 fps every session opened level 5.2 and
the SAME tablet threw the picture forward ten times every 15 s, seconds
behind. The encoder and the network were fine; the SoC's H.264 decoder tops
out below 4K@60, and no component asked it. The PC cannot know what a phone
decodes; the phone can ask its own `mediaCapabilities` — so the rules live in
the PURE module client/decode-caps.js (the view-anchor.js pattern) and this
gate drives them WHOLE in node, with the codec strings and jump counts taken
from his real log, not invented ones.

Run:  .venv\\Scripts\\python tests/test_decode_caps.py
Requires: node on PATH — a HARD requirement (registered fail-closed in
setup/build.py, the test_voice_dedup.py precedent). Never skip it silently.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MODULE = PROJECT / "client" / "decode-caps.js"
QUALITY = PROJECT / "client" / "quality.js"
CONNECTION = PROJECT / "client" / "connection.js"
RENDER = PROJECT / "client" / "render.js"
INDEX = PROJECT / "client" / "index.html"


def run_js(body: str):
    """Evaluate a snippet with the REAL module required, print JSON."""
    if not shutil.which("node"):
        raise AssertionError(
            "node is required for the decode caps gate (it runs the REAL "
            "client/decode-caps.js rules) — install Node.js. Never skip a "
            "gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_decode_gate_"))
    script = work / "run.js"
    script.write_text(
        f"const M = require({json.dumps(str(MODULE))});\n"
        f"console.log(JSON.stringify({body}));\n",
        encoding="utf-8")
    try:
        out = subprocess.run([shutil.which("node"), str(script)],
                             capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def check_codec_strings_match_his_log():
    """h264Codec must reproduce the EXACT strings his sessions carried —
    2560x1440@30 -> avc1.4D4032, 3840x2160@30 -> 4D4033, @60 -> 4D4034.
    A probe asked with the wrong level is a question about a different
    stream, and 5.2-vs-5.1 is precisely the boundary his tablet sits on."""
    got = run_js("[M.h264Codec(2560,1440,30), M.h264Codec(3840,2160,30),"
                 " M.h264Codec(3840,2160,60), M.h264Codec(1280,720,30)]")
    assert got[0] == "avc1.4D4032", f"2560x1440@30 -> {got[0]}"
    assert got[1] == "avc1.4D4033", f"3840x2160@30 -> {got[1]}"
    assert got[2] == "avc1.4D4034", f"3840x2160@60 -> {got[2]}"
    assert got[3] == "avc1.4D401F", f"1280x720@30 -> {got[3]}"
    print("  codec strings: match the live sessions in his log")


def check_the_ceiling_is_the_highest_smooth_step():
    got = run_js("["
                 "M.smoothCeiling({60:true,30:true,15:true,10:true}, M.DECODE_FPS_STEPS),"
                 "M.smoothCeiling({60:false,30:true,15:true,10:true}, M.DECODE_FPS_STEPS),"
                 "M.smoothCeiling({60:false,30:false,15:false,10:false}, M.DECODE_FPS_STEPS)"
                 "]")
    assert got[0] == 60, f"everything smooth must not cap: {got[0]}"
    assert got[1] == 30, f"his tablet's case — 30 smooth, 60 not: {got[1]}"
    assert got[2] == 10, ("a device that flatters nothing still streams at "
                          f"the floor, never 0/black: {got[2]}")
    print("  smoothCeiling: highest smooth step, floor when nothing is")


def check_the_cap_only_ever_lowers_and_never_invents():
    got = run_js("["
                 "M.capFps(0, 60, 30),"    # follow-PC on his 60fps card, tablet ceiling 30
                 "M.capFps(60, 60, 30),"   # explicit 60, same ceiling
                 "M.capFps(15, 60, 30),"   # already below the ceiling
                 "M.capFps(0, 60, 0),"     # no ceiling known — never cap
                 "M.capFps(0, 0, 30),"     # no base known — never invent a rate
                 "M.capFps(30, 60, 30)"    # exactly at the ceiling — no cap
                 "]")
    assert got[0] == {"fps": 30, "capped": True}, got[0]
    assert got[1] == {"fps": 30, "capped": True}, got[1]
    assert got[2] == {"fps": 15, "capped": False}, got[2]
    assert got[3] == {"fps": 0, "capped": False}, got[3]
    assert got[4] == {"fps": 0, "capped": False}, got[4]
    assert got[5] == {"fps": 30, "capped": False}, got[5]
    print("  capFps: caps his exact case, touches nothing else")


def check_the_backstop_steps_down_one_step_and_stops_at_the_floor():
    got = run_js("[M.struggleCeiling(60, M.DECODE_FPS_STEPS),"
                 " M.struggleCeiling(30, M.DECODE_FPS_STEPS),"
                 " M.struggleCeiling(15, M.DECODE_FPS_STEPS),"
                 " M.struggleCeiling(10, M.DECODE_FPS_STEPS)]")
    assert got == [30, 15, 10, 0], got
    print("  struggleCeiling: one step down, honest 0 at the floor")


def check_two_ceilings_lower_wins():
    got = run_js("[M.combinedCeiling(30, 15), M.combinedCeiling(0, 30),"
                 " M.combinedCeiling(30, 0), M.combinedCeiling(0, 0)]")
    assert got == [15, 30, 30, 0], got
    print("  combinedCeiling: the lower opinion wins, silence is 0")


def check_step_widths_mirror_the_panel():
    got = run_js("[M.stepWidth('native', 2560, 3840), M.stepWidth('full', 2560, 3840),"
                 " M.stepWidth('2/3', 2560, 3840), M.stepWidth('1/2', 2560, 3840),"
                 " M.stepWidth('native', 2560, 0)]")
    assert got == [3840, 2560, 1707, 1280, 2560], got
    print("  stepWidth: native is the monitor, the rest scale the card")


def check_bitrate_parsing_never_answers_zero():
    got = run_js("[M.bitrateBits('20M'), M.bitrateBits('4800k'),"
                 " M.bitrateBits('12000000'), M.bitrateBits('')]")
    assert got == [20e6, 4.8e6, 12e6, 12e6], got
    print("  bitrateBits: units parsed, garbage answers a sane default")


def check_the_drowning_threshold_matches_his_log():
    """His healthy windows counted jumps=0; the drowning ones 9-10. The
    threshold must sit between those worlds or the backstop either never
    fires or fires on a healthy stream."""
    steps = run_js("[M.DECODE_BAD_JUMPS, M.DECODE_BAD_WINDOWS]")
    assert 1 < steps[0] <= 10, f"DECODE_BAD_JUMPS {steps[0]} not between his worlds"
    assert steps[1] >= 2, ("one bad window can be a network burp — the "
                           f"backstop must want a run, got {steps[1]}")
    print("  thresholds: sit between his healthy and drowning windows")


def check_the_wiring_really_exists():
    """A pure function nobody calls is a feature that does not exist (the
    actions.json lesson, 2026-08-07)."""
    idx = INDEX.read_text(encoding="utf-8")
    assert '"/static/decode-caps.js"' in idx, "index.html does not load decode-caps.js"
    assert idx.index('"/static/decode-caps.js"') < idx.index('"/static/quality.js"'), \
        "decode-caps.js must load before quality.js (quality wires it)"
    q = QUALITY.read_text(encoding="utf-8")
    assert re.search(r"function effectiveQuality\(\)(?:.|\n){0,900}?decodeCapState", q), \
        "effectiveQuality() no longer runs the cap — the wall is decorative"
    assert "probeSmoothFps(" in q and "refreshDecodeCeilings" in q, \
        "quality.js no longer probes the device"
    assert "noteDecodeStruggle" in q, "quality.js lost the runtime backstop"
    assert re.search(r"capped[^}]*showToast|showToast[^;]*fps", q, re.S), \
        "the cap went silent — it must be SAID, never guessed at"
    c = CONNECTION.read_text(encoding="utf-8")
    assert "refreshDecodeCeilings()" in c, \
        "connection.js no longer probes on config — first session unprotected"
    r = RENDER.read_text(encoding="utf-8")
    assert re.search(r"noteDecodeStruggle\(liveSeeks\)", r), \
        "render.js no longer feeds the live window's jump count to the backstop"
    print("  wiring: probed on config, capped in effectiveQuality, fed by render")


def main():
    print("DECODE CAPS GATE - the phone never requests a stream its own "
          "decoder cannot drink")
    check_codec_strings_match_his_log()
    check_the_ceiling_is_the_highest_smooth_step()
    check_the_cap_only_ever_lowers_and_never_invents()
    check_the_backstop_steps_down_one_step_and_stops_at_the_floor()
    check_two_ceilings_lower_wins()
    check_step_widths_mirror_the_panel()
    check_bitrate_parsing_never_answers_zero()
    check_the_drowning_threshold_matches_his_log()
    check_the_wiring_really_exists()
    print("OK - all decode caps checks passed")


if __name__ == "__main__":
    sys.exit(main())
