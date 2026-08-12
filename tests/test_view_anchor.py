"""THE POSITION LIVES ON THE PHONE — the letterboxed picture sits where the
Move handle put it.

Why this gate exists, and why it computes what it computes. This is the
FOURTH round of one feature (owner decree 2026-08-09). The previous three
each shipped green through a gate — and each gate measured window rects on
the PC MONITOR, a screen the owner never sees. The server crops the layout's
region and streams the SAME picture wherever the windows sit inside the
monitor, so moving windows along the free axis changed nothing on his tablet:
he dragged the Move handle to the TOP, pressed Apply, and the app stayed
centred, every time. The geometry HE judges — where the picture lands between
the letterbox bars on his own screen — was computed by no check, which is the
process failure this file answers: a gate must compute the thing the owner
grades the feature by, or it proves the wrong screen.

So the fit-and-anchor math lives in a PURE module, client/view-anchor.js
(no DOM, no socket — the caret.js / voice.js pattern), render.js's
`computeViewHome` runs it, and this gate drives it WHOLE in node with the
cases he would try: pos 0 flush to the near edge of the slack axis, 1 to the
far edge, 0.5 centred, both orientations, and no effect at all when nothing
is letterboxed. The wiring checks then prove the math is the math the page
actually runs and that the server still feeds it — a pure function nobody
calls is a feature that does not exist (the actions.json lesson,
2026-08-07).

Run:  .venv\\Scripts\\python tests/test_view_anchor.py
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
MODULE = PROJECT / "client" / "view-anchor.js"
RENDER = PROJECT / "client" / "render.js"
STATE = PROJECT / "client" / "state.js"
INDEX = PROJECT / "client" / "index.html"
WM = PROJECT / "server" / "window_manager.py"
REGISTRY = PROJECT / "server" / "layout_registry.py"

# A phone-ish stage, both ways up. The numbers only have to make ONE axis
# slack — every check names the situation it puts the region in.
PORTRAIT = (1080, 2340)
LANDSCAPE = (2340, 1080)


def run(calls: list[dict]) -> list[dict]:
    """Evaluate fitAnchorRect() for each call, in one node process."""
    if not shutil.which("node"):
        raise AssertionError(
            "node is required for the view anchor gate (it runs the REAL "
            "client/view-anchor.js math) — install Node.js. Never skip a "
            "gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_anchor_gate_"))
    script = work / "run.js"
    script.write_text(
        f"const {{ fitAnchorRect }} = require({json.dumps(str(MODULE))});\n"
        f"const calls = {json.dumps(calls)};\n"
        "console.log(JSON.stringify(calls.map(c => "
        "fitAnchorRect(c.cw, c.ch, c.region, c.pos))));\n",
        encoding="utf-8")
    try:
        out = subprocess.run([shutil.which("node"), str(script)],
                             capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def call(canvas, region_wh, pos, region_xy=(0, 0)):
    cw, ch = canvas
    return {"cw": cw, "ch": ch,
            "region": {"x": region_xy[0], "y": region_xy[1],
                       "w": region_wh[0], "h": region_wh[1]},
            "pos": pos}


# A WIDE region on a PORTRAIT canvas: full width, vertical slack — the
# owner's own case (a 16:9 layout on his portrait tablet).
WIDE = (1600, 900)
# A TALL region on a LANDSCAPE canvas: full height, horizontal slack.
TALL = (900, 1600)


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def check_pos_zero_is_flush_to_the_near_edge() -> None:
    """His exact gesture, three rounds old: handle at the TOP → the app at the
    TOP of the screen, empty space BELOW. And the landscape twin: flush LEFT."""
    portrait, landscape = run([call(PORTRAIT, WIDE, 0.0),
                               call(LANDSCAPE, TALL, 0.0)])
    if abs(portrait["y"]) > 0.01:
        raise AssertionError(
            f"pos 0 on a portrait canvas drew the picture at y={portrait['y']}"
            " — not flush to the top edge")
    if abs(landscape["x"]) > 0.01:
        raise AssertionError(
            f"pos 0 on a landscape canvas drew the picture at x={landscape['x']}"
            " — not flush to the left edge")


def check_pos_one_is_flush_to_the_far_edge() -> None:
    portrait, landscape = run([call(PORTRAIT, WIDE, 1.0),
                               call(LANDSCAPE, TALL, 1.0)])
    want_y = PORTRAIT[1] - portrait["h"]
    if abs(portrait["y"] - want_y) > 0.01:
        raise AssertionError(
            f"pos 1 on a portrait canvas drew the picture at y={portrait['y']},"
            f" expected flush bottom {want_y}")
    want_x = LANDSCAPE[0] - landscape["w"]
    if abs(landscape["x"] - want_x) > 0.01:
        raise AssertionError(
            f"pos 1 on a landscape canvas drew the picture at x={landscape['x']},"
            f" expected flush right {want_x}")


def check_pos_half_is_centred() -> None:
    portrait, landscape = run([call(PORTRAIT, WIDE, 0.5),
                               call(LANDSCAPE, TALL, 0.5)])
    if abs(portrait["y"] - (PORTRAIT[1] - portrait["h"]) / 2) > 0.01:
        raise AssertionError(
            f"pos 0.5 did not centre the portrait letterbox: y={portrait['y']}")
    if abs(landscape["x"] - (LANDSCAPE[0] - landscape["w"]) / 2) > 0.01:
        raise AssertionError(
            f"pos 0.5 did not centre the landscape letterbox: x={landscape['x']}")


def check_the_pinned_axis_never_moves() -> None:
    """Only ONE axis has slack. Whatever the pos, the fitted axis stays put
    and the picture keeps its full fitted size — an anchor that changed the
    SIZE would be the aspect panel's job done twice."""
    rects = run([call(PORTRAIT, WIDE, p) for p in (0.0, 0.5, 1.0)])
    for r in rects:
        if abs(r["x"]) > 0.01 or abs(r["w"] - PORTRAIT[0]) > 0.01:
            raise AssertionError(
                f"the pinned axis moved or resized with pos: {r}")
    if len({round(r["h"], 3) for r in rects}) != 1:
        raise AssertionError("the fitted height changed with pos")


def check_matching_aspects_make_pos_irrelevant() -> None:
    """No letterbox, nothing to anchor: a region of the canvas's own shape
    fills it edge to edge for EVERY pos."""
    rects = run([call(PORTRAIT, (540, 1170), p) for p in (0.0, 0.5, 1.0)])
    for r in rects:
        ok = (abs(r["x"]) <= 0.01 and abs(r["y"]) <= 0.01
              and abs(r["w"] - PORTRAIT[0]) <= 0.01
              and abs(r["h"] - PORTRAIT[1]) <= 0.01)
        if not ok:
            raise AssertionError(
                f"with matching aspects pos still moved the picture: {r}")


def check_a_missing_pos_means_centred() -> None:
    """An old server sends no pos at all — the picture must sit where it
    always sat: in the middle. Null and undefined are both 'no answer'."""
    a, b = run([call(PORTRAIT, WIDE, None),
                {**call(PORTRAIT, WIDE, 0.5), "pos": None}])
    centre = (PORTRAIT[1] - a["h"]) / 2
    for r in (a, b):
        if abs(r["y"] - centre) > 0.01:
            raise AssertionError(
                f"a missing pos was not read as centred: y={r['y']}")


def check_an_out_of_range_pos_stops_at_the_edge() -> None:
    low, high = run([call(PORTRAIT, WIDE, -0.5), call(PORTRAIT, WIDE, 1.7)])
    if abs(low["y"]) > 0.01:
        raise AssertionError(f"pos -0.5 overshot the top edge: y={low['y']}")
    if abs(high["y"] - (PORTRAIT[1] - high["h"])) > 0.01:
        raise AssertionError(f"pos 1.7 overshot the bottom edge: y={high['y']}")


def check_a_region_off_origin_still_lands_on_the_anchor() -> None:
    """The region render.js passes is a SUB-RECT of the base canvas (a layout
    region), not something at (0,0) — the transform must cancel its origin.
    Getting this wrong is invisible at (0,0), which is why the case exists."""
    (r,) = run([call(PORTRAIT, WIDE, 0.0, region_xy=(137, 411))])
    if abs(r["y"]) > 0.01 or abs(r["x"]) > 0.01:
        raise AssertionError(
            f"a region off the origin missed its anchor: {r}")


# ═══════════════ the wiring — the math the page actually runs ═══════════════
def check_render_home_view_runs_this_math_with_the_layout_pos() -> None:
    """A pure function nobody calls is a feature that does not exist. The HOME
    transform — the fitted view, and the wall pinch-zoom bottoms out at — must
    come from fitAnchorView, fed with the focused layout's own pos."""
    src = RENDER.read_text(encoding="utf-8")
    m = re.search(r"function computeViewHome\(\)\s*\{(.*?)\n\}", src, re.S)
    if not m:
        raise AssertionError("computeViewHome() left client/render.js")
    body = m.group(1)
    if "fitAnchorView(" not in body:
        raise AssertionError(
            "computeViewHome no longer runs fitAnchorView — the page centres "
            "on its own again and the Move handle is dead on the phone")
    if "layoutAnchorPos()" not in body:
        raise AssertionError(
            "computeViewHome does not read layoutAnchorPos() — the anchor "
            "would be a constant, not the owner's choice")
    m = re.search(r"function layoutAnchorPos\(\)\s*\{(.*?)\n\}",
                  STATE.read_text(encoding="utf-8"), re.S)
    if not m or "layoutActive" not in m.group(1) or ".pos" not in m.group(1):
        raise AssertionError(
            "layoutAnchorPos() does not read the focused layout's pos from "
            "layout_state — the phone would anchor by nothing")


def check_the_page_loads_the_module_before_render() -> None:
    html = INDEX.read_text(encoding="utf-8")
    anchor = html.find("/static/view-anchor.js")
    render = html.find("/static/render.js")
    if anchor == -1:
        raise AssertionError("index.html never loads view-anchor.js")
    if not -1 < anchor < render:
        raise AssertionError(
            "view-anchor.js must load BEFORE render.js — computeViewHome "
            "calls it")


def check_the_module_stays_pure() -> None:
    """This gate runs the module WHOLE in node — possible only while it
    touches no DOM, no socket, no bridge (the caret.js rule)."""
    code = "\n".join(ln for ln in MODULE.read_text(encoding="utf-8").splitlines()
                     if not ln.lstrip().startswith(("//", "*", "/*")))
    for banned in ("document", "window.", "canvas.", "send(", "Android",
                   "fetch("):
        if banned in code:
            raise AssertionError(
                f"client/view-anchor.js reaches for {banned!r} — it is no "
                "longer pure and this gate can no longer prove it")


def check_the_server_still_feeds_the_anchor_and_centres_the_windows() -> None:
    """The other end of the chain, pinned here so one gate tells the whole
    story: the registry must not slide windows by pos any more (that is the
    wrong screen), and `layout_state` must still carry pos — the hop the
    phone anchors by. Losing either silently un-fixes round four."""
    reg = REGISTRY.read_text(encoding="utf-8")
    m = re.search(r"layout_region\([^)]*\)", reg)
    if not m:
        raise AssertionError("layout_registry no longer calls layout_region")
    for use in re.findall(r"layout_region\([^)]*\)", reg):
        if "pos" in use:
            raise AssertionError(
                f"placement follows pos again on the PC monitor: {use!r} — "
                "that is the screen the owner never sees (decree 2026-08-09)")
    if '"pos": round(lay.pos, 3)' not in reg:
        raise AssertionError(
            "layout_state no longer echoes pos — the phone would have "
            "nothing to anchor the picture by")
    wm_src = WM.read_text(encoding="utf-8")
    if "from layout_registry import Layout, LayoutRegistry" not in wm_src:
        raise AssertionError(
            "window_manager no longer re-exports the registry — every "
            "caller and gate imports it through window_manager")


def check_the_reanchor_validates_the_base_rect_itself() -> None:
    """Owner report 2026-08-12 (the aspect panel's bottom-cut picture):
    viewBounds() reads baseRect, and the `layout_state` handler re-anchored
    against a baseRect the current canvas size had never validated — only the
    `config` path paired computeBaseRect() with the re-anchor, which is why a
    lock/unlock drew the same state correctly. The pairing now lives INSIDE
    resetViewHome(), where no caller can skip it; this check keeps it there."""
    render = RENDER.read_text(encoding="utf-8")
    m = re.search(r"function resetViewHome\(\)\s*{([^}]*)}", render)
    if not m:
        raise AssertionError("render.js lost resetViewHome()")
    body = m.group(1)
    if "computeBaseRect()" not in body:
        raise AssertionError(
            "resetViewHome() no longer re-derives baseRect first — a "
            "layout_state arriving without a config re-anchors against a "
            "stale canvas and the letterboxed picture can clip again "
            "(owner report 2026-08-12)")
    if body.index("computeBaseRect()") > body.index("computeViewHome()"):
        raise AssertionError(
            "resetViewHome() derives the home view BEFORE validating "
            "baseRect — the order is the whole fix")


CHECKS = [
    ("pos 0 is flush to the near edge (his gesture: app at the TOP)",
     check_pos_zero_is_flush_to_the_near_edge),
    ("the re-anchor validates baseRect itself (no caller can skip it)",
     check_the_reanchor_validates_the_base_rect_itself),
    ("pos 1 is flush to the far edge", check_pos_one_is_flush_to_the_far_edge),
    ("pos 0.5 is centred", check_pos_half_is_centred),
    ("the pinned axis never moves and the size never changes",
     check_the_pinned_axis_never_moves),
    ("matching aspects make pos irrelevant",
     check_matching_aspects_make_pos_irrelevant),
    ("a missing pos means centred (an old server keeps working)",
     check_a_missing_pos_means_centred),
    ("an out-of-range pos stops at the edge",
     check_an_out_of_range_pos_stops_at_the_edge),
    ("a region off the origin still lands on the anchor",
     check_a_region_off_origin_still_lands_on_the_anchor),
    ("render.js runs THIS math with the layout's own pos",
     check_render_home_view_runs_this_math_with_the_layout_pos),
    ("the page loads the module before render.js",
     check_the_page_loads_the_module_before_render),
    ("the module stays pure, so this gate can run it whole",
     check_the_module_stays_pure),
    ("the server centres the windows and still feeds the anchor",
     check_the_server_still_feeds_the_anchor_and_centres_the_windows),
]


def main() -> int:
    print("\n=== VIEW ANCHOR GATE ===")
    if shutil.which("node") is None:
        print("VIEW ANCHOR GATE FAILED — node is required (it runs the REAL "
              "client/view-anchor.js math) and is not on PATH. Never skip a "
              "gate silently.")
        return 1
    failed = 0
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nVIEW ANCHOR GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nVIEW ANCHOR GATE PASSED — the picture sits where the Move "
          "handle put it, on the screen he actually sees.")
    return 0


def test_view_anchor():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
