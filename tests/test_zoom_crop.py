"""ZOOM CROP GATE — round 3: the zoom raises the RESOLUTION, never the crop.

Owner report 2026-08-14 (T76), round 2's own condemnation. Round 2 made a
pinch narrow the encoder's CROP — and the live result was worse than the bug
it fixed: H.264 has no base layer, so panning past a crop showed the page's
own background; every pan step cost a 1-2 s ffmpeg rebuild; and one decoder
hiccup in that storm reconnected with the zoom erased ("keeps throwing me
back to the desktop"). His OWN design, delivered as eight diagrams and
quoted directly in server/layout_api.py: "the zoom must never send less that
way ... the phone is now looking at part of the screen and not the whole",
so the crop stays exactly what a focused layout already sends (or the full
frame at the desktop) and the pinch only raises the ENCODED RESOLUTION, in
quantized power-of-two steps, up to native and never past it.

ROUND 5 (owner report 2026-08-18): piece 1 below is CORRECTED — the step is
no longer "the LARGER-fraction axis" but the ratio of the DRAWN picture to the
PANEL (his portrait tablet letterboxes a 16:9 monitor, so the height fraction
read 1.0 through every zoom he used and the step never left 1); the sentence
is kept as the evidence, section 13 holds the new rule with his numbers, and
sections 1–2 still hold for a page that sends no `drawn`.

THE THREE PIECES THIS GATE PROVES, one per file the round-3 design touched:

  1. `layout_api.zoom_step(conn)` — the ONE derivation of the step, read from
     the settled `conn["zoom"]` rect against the base picture (the focused
     layout's region, or the full frame): the LARGER-fraction axis decides,
     quantized to a power of two, capped at ZOOM_MAX_STEP. `stream_crop`
     keeps meaning exactly what it meant before this round — the layout's
     region and nothing else — so the crop and the step are two independent
     answers a pinch can no longer confuse.
  2. The choke point (`send_layout_state`) and `zoom_region`: a PAN keeps the
     rect's SIZE, so it keeps the step and reaches nothing past the
     `ZOOM_MIN_DELTA` guard — panning is free, exactly the point of this
     design. Only a step CROSSING reaches `send_layout_state`'s reset
     comparison, which now asks two questions instead of one (crop mismatch
     OR step mismatch) through the SAME two-reads-of-one-derivation rule the
     crop half has carried since 2026-08-12.
  3. `H264Session._scale_size(..., zoom=N)` — the panel ceiling raised by the
     step and clamped at native (1.0); `_reference_size` always asks with the
     DEFAULT zoom=1, so the T79 cellular bitrate reference keeps meaning "a
     full screen on this panel" whatever the connection is zoomed to, and a
     deep zoom's bitrate can rise toward the rung but never past it.

Round 2's live wiring failure (the config self-erasing the zoom, then the
SAME loop through `layout_state`) is a lesson about client/connection.js that
outlives round 2's crop design: a config or layout_state frame that changed
nothing the phone is watching must never reset the view. Round 3 keeps that
promise under new names — `h264ConfigSeen`/`regionUnchanged` for `config`
(the stream_region itself is now stable across a pure zoom-step rebuild,
since the crop never moves) and the pre-existing `focusUnchanged` for
`layout_state`, untouched by this round because the choke point's own frame
shape (`active`, `region`) did not change.

Run:  .venv\\Scripts\\python tests/test_zoom_crop.py
Requires: node on PATH — a HARD requirement (the test_view_anchor.py
precedent). Never skip it silently.
"""

import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import config  # noqa: E402
import h264_streamer  # noqa: E402
import layout_api  # noqa: E402

WEB = (PROJECT / "server" / "web.py").read_text(encoding="utf-8")
H264_SRC = (PROJECT / "server" / "h264_streamer.py").read_text(encoding="utf-8")
CONFIG_API = (PROJECT / "server" / "config_api.py").read_text(encoding="utf-8")
CONN_JS = (PROJECT / "client" / "connection.js").read_text(encoding="utf-8")
STATE_JS = (PROJECT / "client" / "state.js").read_text(encoding="utf-8")
QUALITY_JS = (PROJECT / "client" / "quality.js").read_text(encoding="utf-8")
MODULE = PROJECT / "client" / "zoom-crop.js"

# His own live layout (server.log 2026-08-12 14:39:49) — a VS Code layout on
# his 4K monitor, a quarter of its width. The same rect test_region_stream.py
# is driven with, deliberately.
HIS_REGION = {"x": 0.3736979166666667, "y": 0.000462962962962963,
              "w": 0.25234375, "h": 0.9708333333333333}

FULL = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}


# ═══════════════════════ 1. THE STEP ARITHMETIC ═══════════════════════
def check_zoom_step_arithmetic_at_the_desktop() -> None:
    """No region — the base picture is the full frame. The LARGER of the two
    axis fractions decides, quantized to a power of two, capped at
    ZOOM_MAX_STEP; and past the cap the step never moves again."""
    def step(zoom):
        return layout_api.zoom_step({"active": None, "region": None, "zoom": zoom})

    assert step(None) == 1, "no zoom at all must be the old world — step 1"
    assert step({"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}) == 2, \
        "half the desktop per axis did not earn a x2 step"
    assert step({"x": 0.375, "y": 0.375, "w": 0.25, "h": 0.25}) == 4, \
        "a quarter per axis did not earn a x4 step"
    assert step({"x": 0.44, "y": 0.44, "w": 0.125, "h": 0.125}) == 8, \
        "an eighth per axis did not reach the x8 cap"
    for w in (0.08, 0.03, 0.01, 0.001):
        assert step({"x": 0.4, "y": 0.4, "w": w, "h": w}) == \
            layout_api.ZOOM_MAX_STEP, \
            f"a deeper pinch (w={w}) exceeded the cap of {layout_api.ZOOM_MAX_STEP}"
    assert step({"x": 0.2, "y": 0.2, "w": 0.6, "h": 0.6}) == 1, \
        "0.6 of an axis earned a step above 1 — it should not cross the x2 boundary"
    # Asymmetric: the LARGER fraction decides, so a narrow-but-tall rect earns
    # only what its tall axis justifies, never what its narrow one would.
    assert step({"x": 0.4, "y": 0.2, "w": 0.2, "h": 0.6}) == 1, \
        "an asymmetric rect was decided by the SMALLER fraction, not the larger"
    print("  desktop zoom_step: 1 / 2 / 4 / 8 (capped) — the larger axis decides")


def check_zoom_step_arithmetic_inside_a_layout() -> None:
    """The base picture is the LAYOUT's region, not the full frame — a
    'half the screen' pinch inside a quarter-width layout means something
    different from the same rect at the desktop."""
    region = {"x": 0.375, "y": 0.0, "w": 0.25, "h": 1.0}

    def step(zoom):
        return layout_api.zoom_step(
            {"active": 0, "region": region, "zoom": zoom})

    # Half the region's WIDTH, full height: the width fraction is 0.5, the
    # height fraction is 1.0/1.0 = 1.0 — the LARGER one decides, and 1.0
    # earns nothing past the x2 boundary (1/1.0 = 1 < 2).
    half_width_full_height = {"x": region["x"] + region["w"] * 0.25,
                              "y": region["y"], "w": region["w"] * 0.5,
                              "h": region["h"]}
    assert step(half_width_full_height) == 1, (
        "a rect full-height in the region earned a step above 1 — the tall "
        "axis (fraction 1.0) must be the one that decides")
    # Half of BOTH axes: both fractions are 0.5, so the step is x2.
    half_both = {"x": region["x"] + region["w"] * 0.25,
                "y": region["y"] + region["h"] * 0.25,
                "w": region["w"] * 0.5, "h": region["h"] * 0.5}
    assert step(half_both) == 2, \
        "half of both the layout's own axes did not earn a x2 step"
    # A rect that is 80% of the region's WIDTH (its width fraction — 0.8 —
    # dominates over its own tiny height fraction, so this genuinely exercises
    # the region's width): against the layout's own 0.25-wide region that
    # earns nothing past step 1 (0.8 does not cross the x2 boundary). Measured
    # against the FULL monitor instead (a base-picture bug that ignores the
    # region) the same absolute width is only a 0.2 fraction of the whole
    # screen — enough to reach step 4. The two answers disagree, which is
    # exactly what proves this check reads the LAYOUT's region and not the
    # full frame.
    width_dominant = {"x": region["x"] + region["w"] * 0.05,
                      "y": region["y"], "w": region["w"] * 0.8, "h": 0.1}
    assert step(width_dominant) == 1, (
        "a rect covering 80% of the layout's own width earned a step above 1 "
        "— the base picture is not really the layout's region")
    print("  layout zoom_step: the layout's OWN region is the base picture")


# ═══════════════════════ 2. THE STEP NEVER MOVES CROP ═══════════════════════
def check_stream_crop_never_reads_the_zoom() -> None:
    """`stream_crop` is the ONE derivation the crop side asks — round 3's
    whole point is that it must answer exactly as it did before a zoom ever
    existed, whatever the zoom rect says."""
    lay = {"active": 0, "region": dict(HIS_REGION),
           "zoom": {"x": 0.4, "y": 0.1, "w": 0.05, "h": 0.05}}
    assert layout_api.stream_crop(lay) == HIS_REGION, \
        "stream_crop moved for a zoomed-in layout — the crop must never narrow"
    lay["zoom"] = dict(FULL)
    assert layout_api.stream_crop(lay) == HIS_REGION, \
        "a full-frame zoom rect changed the layout's own crop"
    desk = {"active": None, "region": None,
           "zoom": {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}}
    assert layout_api.stream_crop(desk) is None, \
        "a desktop zoom produced a crop — the desktop is never cropped by a pinch"
    print("  stream_crop ignores the zoom entirely, in a layout and at the desktop")


# ═══════════════════ 3. A PAN NEVER REBUILDS ═══════════════════
def _install_send_state_stub():
    calls = []

    async def fake(ws, layouts, conn, resuming=None):
        calls.append(conn.get("zoom"))

    original = layout_api.send_layout_state
    layout_api.send_layout_state = fake
    return calls, original


class _Layouts:
    def state(self, active, region):
        return {"type": "layout_state", "layouts": [], "active": active,
                "region": region, "orient": "landscape"}


class _WS:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(json.loads(text))


def check_a_pan_never_rebuilds_the_session() -> None:
    """Seeded at step 2 (a real, settled zoom). A rect the SAME SIZE at a
    different position moved far enough to pass the delta guard, but keeps
    the step — so the choke point (stubbed here) must never be reached, and
    the settled rect is still recorded for the next pan/pinch to compare
    against."""
    calls, original = _install_send_state_stub()
    try:
        conn = {"active": None, "region": None,
               "zoom": {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5},
               "stream_zoom": 2}
        pan_rect = {"x": 0.35, "y": 0.25, "w": 0.5, "h": 0.5}  # moved, same size
        assert layout_api._rect_delta(pan_rect, conn["zoom"]) >= layout_api.ZOOM_MIN_DELTA
        asyncio.run(layout_api.zoom_region(_WS(), _Layouts(), conn, pan_rect))
        assert not calls, "a pure pan reached the choke point — a rebuild for nothing"
        assert conn["zoom"] == pan_rect, \
            "the pan's own settled rect was not recorded"
    finally:
        layout_api.send_layout_state = original
    print("  a pan (same step, new position) rebuilds nothing")


def check_a_step_crossing_rebuilds_the_session() -> None:
    """Same seed, but the rect HALVES — a real step crossing — so the choke
    point must be reached exactly once."""
    calls, original = _install_send_state_stub()
    try:
        conn = {"active": None, "region": None,
               "zoom": {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5},
               "stream_zoom": 2}
        deeper = {"x": 0.375, "y": 0.375, "w": 0.25, "h": 0.25}  # step 4
        asyncio.run(layout_api.zoom_region(_WS(), _Layouts(), conn, deeper))
        assert len(calls) == 1, \
            f"a step crossing reached the choke point {len(calls)} times, not once"
        assert conn["zoom"] == deeper
    finally:
        layout_api.send_layout_state = original
    print("  a step crossing (2 -> 4) reaches the choke point exactly once")


# ═══════════════ 4. THE CHOKE POINT ITSELF ═══════════════
def check_the_choke_point_resets_on_a_step_mismatch_alone() -> None:
    """`send_layout_state`, unstubbed and real: the crop can match exactly
    while the STEP does not, and that alone must still end the session — the
    owner's whole design depends on the step being a first-class reason to
    rebuild, not a footnote to the region comparison."""
    fired = []
    conn = {"active": None, "region": None, "stream_region": None,
           "zoom": {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5},  # step 2
           "stream_zoom": 1,  # the running session was opened at step 1
           "reset_stream": lambda: fired.append(1)}
    asyncio.run(layout_api.send_layout_state(_WS(), _Layouts(), conn))
    assert fired, "a step mismatch with an unchanged region never reset the stream"

    fired.clear()
    conn["stream_zoom"] = layout_api.zoom_step(conn)  # now they agree
    asyncio.run(layout_api.send_layout_state(_WS(), _Layouts(), conn))
    assert not fired, \
        "matching region AND matching step still reset the stream — a needless blink"
    print("  the choke point fires on a step mismatch alone, and only then")


# ═══════════════════ 5. ZOOM_MIN_DELTA ═══════════════════
def check_a_sub_threshold_drift_changes_nothing() -> None:
    """A rect that moved less than the delta must not even reach the step
    comparison — `conn["zoom"]` stays the exact same object, never replaced."""
    calls, original = _install_send_state_stub()
    try:
        seeded = {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}
        conn = {"active": None, "region": None, "zoom": seeded, "stream_zoom": 2}
        drift = {"x": 0.2503, "y": 0.2502, "w": 0.4998, "h": 0.5001}
        asyncio.run(layout_api.zoom_region(_WS(), _Layouts(), conn, drift))
        assert conn["zoom"] is seeded, \
            "a sub-threshold drift replaced the settled rect"
        assert not calls, "a sub-threshold drift reached the choke point"
    finally:
        layout_api.send_layout_state = original
    print("  a pixel of drift under ZOOM_MIN_DELTA changes nothing at all")


# ═══════════════ 6. A FOCUS CHANGE DROPS THE ZOOM ═══════════════
def check_a_focus_change_drops_the_zoom_it_was_measured_in() -> None:
    """The settled rect belongs to the picture it was measured in. Carrying it
    into the next layout would earn a resolution step off a slice that no
    longer exists."""
    conn = {"active": 0, "region": dict(HIS_REGION),
           "zoom": {"x": 0.4, "y": 0.2, "w": 0.1, "h": 0.3}}
    conn["stream_region"] = layout_api.stream_crop(conn)
    conn["stream_zoom"] = layout_api.zoom_step(conn)

    class _Moved:
        def state(self, active, region):
            return {"type": "layout_state", "layouts": [], "active": 1,
                    "region": region, "orient": "landscape"}

    asyncio.run(layout_api.send_layout_state(_WS(), _Moved(), conn))
    assert conn["zoom"] is None, \
        "the previous layout's zoom followed him into the next one"
    print("  a focus change drops the zoom measured in the layout he left")


# ═══════════════════ 7. _scale_size(zoom=N) ═══════════════════
def _bare_session(width=3840, height=2160, panel=(1920, 1200), quality=None,
                  zoom=1) -> h264_streamer.H264Session:
    s = object.__new__(h264_streamer.H264Session)
    s._quality = quality or {}
    s._panel = panel
    s.width, s.height = width, height
    s._zoom = zoom
    return s


def check_scale_size_zoom_raises_the_ceiling_and_clamps_at_native() -> None:
    s = _bare_session()
    assert s._scale_size(3840, 2160, zoom=1) == (1920, 1080), \
        "zoom=1 must be the old panel-capped downscale, to the pixel"
    assert s._scale_size(3840, 2160, zoom=2) is None, \
        "zoom=2 should land EXACTLY on native (0.5 panel factor x2) — a real " \
        "scale means the ceiling was not raised far enough"
    assert s._scale_size(3840, 2160, zoom=8) is None, \
        "zoom=8 must clamp at native, never scale ABOVE the source"
    # A mid case where the doubled factor still lands below 1 — an 8K source
    # on the same panel, zoom=2: panel factor 1920/7680 = 0.25, x2 = 0.5.
    mid = s._scale_size(7680, 4320, zoom=2)
    assert mid == (3840, 2160), f"a mid-zoom scale came out {mid}, not (3840, 2160)"
    print("  _scale_size(zoom=N): raises the ceiling, clamps at native, scales proportionally")


def check_reference_size_ignores_the_session_s_own_zoom() -> None:
    """The T79 reference — 'a full screen on this panel' — must mean the same
    thing whatever this connection happens to be zoomed to, or the cellular
    bitrate rungs stop meaning what they say."""
    s = _bare_session(zoom=1)
    baseline = s._reference_size()
    s._zoom = 8
    assert s._reference_size() == baseline, \
        "the bitrate reference size changed with the session's own zoom step"
    print(f"  _reference_size() == {baseline} whatever self._zoom is set to")


# ══════════ 8. THE BITRATE FOLLOWS THE PIXELS, EVEN ZOOMED (T79) ══════════
PANEL = {"w": 1920, "h": 1200}
CELL = {"res": "full", "bitrate": "saver"}   # the saving profile, unclamped res


def _sess(region, quality, panel=PANEL, zoom=1):
    class _FakeSource:
        stream_w, stream_h = 3840, 2160
        capture_fps = 60
    return h264_streamer.H264Session(
        _FakeSource(), "libx264", lambda b: None, lambda: None,
        quality=quality, region=region, panel=panel, zoom=zoom)


def _bvi(session) -> int:
    cmd = session._ffmpeg_cmd()
    return config.bitrate_bps(cmd[cmd.index("-b:v") + 1])


def check_a_deep_zoom_raises_the_cellular_bitrate_but_never_past_the_rung() -> None:
    """A zoomed session encodes more pixels of the SAME crop, so its cellular
    bitrate may rise with it — but the rung and the floor are absolute, and
    neither may ever be crossed, zoomed or not."""
    rung = config.bitrate_bps(config.bitrate_for_level("saver"))
    steps = (1, 2, 4, 8)
    values = [_bvi(_sess(dict(HIS_REGION), dict(CELL), zoom=z)) for z in steps]
    for z, v in zip(steps, values):
        assert v <= rung, f"zoom x{z} raised the bitrate to {v}, above the rung {rung}"
        assert v >= h264_streamer.BITRATE_FLOOR_BPS, \
            f"zoom x{z} fell below the {h264_streamer.BITRATE_FLOOR_BPS} bps floor"
    assert all(a <= b for a, b in zip(values, values[1:])), \
        f"the bitrate did not rise (or hold) with a deeper zoom: {values}"
    assert values[-1] > values[0], \
        "the deepest zoom did not really spend more than the shallowest"
    assert values[-1] >= rung * 0.9, \
        (f"the deepest zoom only reached {values[-1]} of the rung's {rung} — "
         "the ceiling was not really raised toward native")
    print(f"  cellular bitrate by zoom step {dict(zip(steps, values))} — "
          f"never above the rung ({rung})")


def check_wi_fi_bitrate_is_untouched_by_zoom() -> None:
    """Nothing on Wi-Fi may change with the zoom step, exactly as nothing
    changed with the crop before this round."""
    wifi = {"res": "full", "bitrate": "max"}
    for zoom in (1, 2, 4, 8):
        s = _sess(dict(HIS_REGION), dict(wifi), zoom=zoom)
        assert s.bitrate_factor == 1.0, \
            f"Wi-Fi was scaled at zoom x{zoom}: {s.bitrate_factor}"
    print("  Wi-Fi: the bitrate factor is 1.0 at every zoom step")


# ═══════════════════════════ 9. THE WIRING ═══════════════════════════
def check_web_py_derives_and_records_the_zoom_step() -> None:
    assert "req_zoom = layout_api.zoom_step(conn)" in WEB, \
        "web.py no longer derives the zoom step through the one shared function"
    assert re.search(
        r"manager\.open_session,[\s\S]*?req_region,[\s\S]*?req_zoom,\n\s*\)",
        WEB), \
        "open_session is no longer handed the derived zoom step"
    assert re.search(r'^\s*conn\["stream_zoom"\] = req_zoom\s*$', WEB, re.M), \
        "the opened session's zoom step is no longer recorded on the connection"
    assert "await layout_api.zoom_region(ws, layouts, conn, msg)" in WEB, \
        "the H.264 viewport branch no longer routes through zoom_region"
    print("  web.py: zoom_step derived once, handed to open_session, and recorded")


def check_h264_session_accepts_and_logs_its_zoom() -> None:
    assert re.search(r"def __init__\(self,[^)]*zoom: int = 1", H264_SRC, re.S), \
        "H264Session no longer accepts a zoom argument"
    assert "self._zoom = max(1, int(zoom or 1))" in H264_SRC, \
        "the session no longer stores its own zoom step"
    assert re.search(r"session\._zoom > 1[\s\S]{0,60}zoom x%d", H264_SRC), \
        "a zoom above 1 is no longer named in the session's own log line"
    print("  H264Session: zoom stored on the instance and named in the open log")


def check_the_choke_point_compares_two_derivations_not_two_copies() -> None:
    lay_src = (PROJECT / "server" / "layout_api.py").read_text(encoding="utf-8")
    assert 'stream_crop(conn) != conn.get("stream_region")' in lay_src, \
        "the choke point no longer compares the crop derivation"
    assert 'zoom_step(conn) != conn.get("stream_zoom", 1)' in lay_src, \
        "the choke point no longer compares the zoom-step derivation"
    print("  the choke point asks both derivations, never a second copy of either")


def _send_config_payload(zoom: int) -> dict:
    """Drives the REAL `send_config` end to end (its helper calls stubbed —
    tailscale/monitor/quality/version lookups are none of this check's
    business) and returns the exact JSON it put on the wire, so the presence
    or absence of `stream_zoom` is proven on the PAYLOAD, never on the source
    text alone — a text check would have missed an `if True:` that still
    happened to keep the literal assignment line intact."""
    import config_api

    class _Stream:
        width, height, mode = 3840, 2160, "h264"
        monitor_index = 0

    sent = {}

    class _WS:
        async def send_text(self, text):
            sent["payload"] = json.loads(text)

    orig = {
        "get_tailscale_ip": config_api.pairing.get_tailscale_ip,
        "config_fields": config_api.monitor_api.config_fields,
        "stream_base": config_api.config.stream_base,
        "ui_config": config_api.ui_config,
        "apk_version": config_api.apk_version,
        "app_version": config_api.app_version,
    }
    config_api.pairing.get_tailscale_ip = lambda: None
    config_api.monitor_api.config_fields = lambda stream: {"monitor": 0, "monitors": []}
    config_api.config.stream_base = lambda stream: {}
    config_api.ui_config = lambda: {}
    config_api.apk_version = lambda: "0.0.0"
    config_api.app_version = lambda: "0.0.0"
    try:
        asyncio.run(config_api.send_config(_WS(), _Stream(), "tok", zoom=zoom))
    finally:
        config_api.pairing.get_tailscale_ip = orig["get_tailscale_ip"]
        config_api.monitor_api.config_fields = orig["config_fields"]
        config_api.config.stream_base = orig["stream_base"]
        config_api.ui_config = orig["ui_config"]
        config_api.apk_version = orig["apk_version"]
        config_api.app_version = orig["app_version"]
    return sent["payload"]


def check_config_carries_the_zoom_step_only_above_1() -> None:
    """The decode ceiling is blind to the zoom unless `config` tells it what
    the encoder really did — but the field must be ABSENT at step 1, or every
    old page reading `config` gets a wire change it never asked for. Driven
    on the real PAYLOAD `send_config` puts on the wire, not on its source
    text — a text check alone cannot tell an `if zoom > 1:` from an
    `if True:` that happens to keep the assignment line intact."""
    at_one = _send_config_payload(1)
    assert "stream_zoom" not in at_one, \
        f"stream_zoom rode the wire at step 1 — {at_one.get('stream_zoom')!r} " \
        "— an old page would see a field it has never had to ignore before"
    at_two = _send_config_payload(2)
    assert at_two.get("stream_zoom") == 2, \
        f"a real zoom step 2 did not carry stream_zoom={2!r}: {at_two.get('stream_zoom')!r}"
    at_eight = _send_config_payload(8)
    assert at_eight.get("stream_zoom") == 8, \
        f"a real zoom step 8 did not carry stream_zoom={8!r}: {at_eight.get('stream_zoom')!r}"
    assert re.search(r"async def send_config\([^)]*zoom: int = 1", CONFIG_API), \
        "send_config no longer accepts a zoom argument"
    assert re.search(
        r"await _send_config\(ws, manager, token, codec=session\.codec,\s*"
        r"region=session\.region, zoom=session\._zoom\)", WEB), \
        "the H.264 loop no longer hands send_config the session's own zoom step"
    print("  config: stream_zoom rides the wire only when the step is above 1")


# ══════════ 10. THE CLIENT NEVER RESETS ITS OWN VIEW ON ITS OWN ECHO ══════════
def check_h264_config_seen_starts_false_and_flips_once_per_config() -> None:
    assert "h264ConfigSeen = false;" in STATE_JS, \
        "state.js no longer declares h264ConfigSeen"
    onopen = re.search(r"sock\.onopen = .*?\n\s*\};", CONN_JS, re.S)
    assert onopen and "h264ConfigSeen = false;" in onopen.group(0), \
        "a fresh connection no longer resets h264ConfigSeen — the FIRST config " \
        "of a new socket would then wrongly be treated as an echo"
    handler = re.search(r'msg\.type === "config"\) \{(.*?)\} else if', CONN_JS, re.S)
    assert handler and "h264ConfigSeen = true;" in handler.group(0), \
        "the config handler no longer marks a config as seen"
    print("  h264ConfigSeen: false on a fresh socket, true after its first config")


def check_an_unchanged_config_region_keeps_the_view() -> None:
    """The self-erasing loop round 2 shipped (owner report 2026-08-14, round
    2 of T76): every zoom-step rebuild ends with a fresh `config`, and if that
    handler resets the view unconditionally the reset UNDOES the very zoom
    that triggered it, forever, within a second. Since round 3 the crop never
    moves, so a zoom-step rebuild's `config` carries the SAME stream_region —
    and only an unchanged region on a connection that has already seen one
    config may skip the reset."""
    handler = re.search(r'msg\.type === "config"\) \{(.*?)\} else if', CONN_JS, re.S)
    assert handler, "no config handler found in connection.js"
    body = handler.group(0)
    assert re.search(
        r"const regionUnchanged = streamMode === \"h264\" && h264ConfigSeen "
        r"&&\s*zoomRectDelta\(prevRegion \|\| FULL_RECT, "
        r"streamRegion \|\| FULL_RECT\) < 1e-6;", body), \
        "the config handler no longer recognises an unchanged stream_region"
    assert re.search(
        r"if \(regionUnchanged\) \{[^}]*\} else \{[^}]*resetViewHome\(\);"
        r"[^}]*scheduleViewport\(\);", body, re.S), \
        "resetViewHome()/scheduleViewport() run unconditionally again — the " \
        "self-erasing loop that killed every zoom on his tablet"
    kept = re.search(r"if \(regionUnchanged\) \{(.*?)\} else", body, re.S)
    assert kept and "resetViewHome" not in kept.group(1) \
        and "scheduleViewport" not in kept.group(1), \
        "the unchanged-region branch itself resets the view"
    print("  config: a config that changed nothing he watches keeps his view")


def check_an_unchanged_layout_state_never_undoes_the_zoom() -> None:
    """The SECOND path of the same class of loop, unrelated to round 3's own
    changes but still load-bearing: `zoom_region` re-sends `layout_state`
    through the choke point BEFORE the encoder rebuild, on every zoom, and the
    client's `layout_state` handler must not reset the view when neither the
    focus nor the region actually changed."""
    assert re.search(
        r"const focusUnchanged =\s*\(msg\.active \?\? null\) === layoutActive &&\s*"
        r"zoomRectDelta\(msg\.region \|\| prevFull, layoutRegion \|\| prevFull\)",
        CONN_JS), \
        "the layout_state handler no longer asks what the frame changed"
    assert re.search(
        r"if \(focusUnchanged\) \{[^}]*\} else \{[^}]*resetViewHome\(\);[^}]*"
        r"scheduleViewport\(\);", CONN_JS, re.S), \
        ("resetViewHome()/scheduleViewport() run on every layout_state again "
         "— the self-erasing path fired by every single zoom")
    unchanged = re.search(r"if \(focusUnchanged\) \{(.*?)\} else", CONN_JS, re.S)
    assert unchanged and "resetViewHome" not in unchanged.group(1) \
        and "scheduleViewport" not in unchanged.group(1), \
        "the unchanged-focus branch itself resets the view"
    print("  layout_state: an unchanged focus keeps the pinch too")


# ═══════════════════════ 11. THE PURE PAGE-SIDE MODULE ═══════════════════════
def _node(script: str) -> object:
    if not shutil.which("node"):
        raise AssertionError(
            "node is required for the zoom crop gate (it runs the REAL "
            "client/zoom-crop.js rules) — install Node.js. Never skip a gate "
            "silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_zoom_gate_"))
    try:
        f = work / "run.js"
        f.write_text(
            f"const Z = require({json.dumps(str(MODULE))});\n" + script,
            encoding="utf-8")
        out = subprocess.run([shutil.which("node"), str(f)],
                             capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def check_the_settle_suppresses_a_gesture_in_progress() -> None:
    """A whole pinch, tick by tick at 60 ms, through the REAL rules: while a
    finger is down NOTHING settles however long it lasts, and after the lift
    it settles EXACTLY ONCE, once the threshold of stillness has really
    passed — including a pause MID-pinch, which is not a settle either."""
    sends = _node("""
      let st = {sample: null, changedAt: 0};
      const out = [];
      let t = 0, w = 1.0;
      for (let i = 0; i < 20; i++, t += 60) {
        w -= 0.03;
        st = Z.zoomSettleStep(st, {now: t, pointersDown: true,
          rect: {x: 0.1, y: 0.1, w: w, h: w}, settleMs: 280});
        out.push({t, phase: "down", settled: st.settled});
      }
      for (let i = 0; i < 8; i++, t += 60) {
        st = Z.zoomSettleStep(st, {now: t, pointersDown: true,
          rect: {x: 0.1, y: 0.1, w: w, h: w}, settleMs: 280});
        out.push({t, phase: "down", settled: st.settled});
      }
      for (let i = 0; i < 12; i++, t += 60) {
        st = Z.zoomSettleStep(st, {now: t, pointersDown: false,
          rect: {x: 0.1, y: 0.1, w: w, h: w}, settleMs: 280});
        out.push({t, phase: "up", settled: st.settled});
      }
      console.log(JSON.stringify(out));
    """)
    during = [s for s in sends if s["phase"] == "down" and s["settled"]]
    assert not during, f"the region changed MID-GESTURE ({len(during)} times) — a blink storm"
    after = [s for s in sends if s["phase"] == "up" and s["settled"]]
    assert after, "the gesture ended and the region never followed — a blurry picture forever"
    last_moving = [s for s in sends if s["phase"] == "down"][-1]["t"]
    assert after[0]["t"] - last_moving >= 280, (
        f"settled {after[0]['t'] - last_moving} ms after the last movement — "
        "under the threshold")
    print(f"  nothing settles under the finger; the first settle is "
          f"{after[0]['t'] - last_moving} ms after the last movement")


def check_the_floor_rule_is_the_module_the_page_runs() -> None:
    """The margin the page adds may never be what widens the rect past the
    layout, and an empty intersection falls back to the floor itself."""
    r = HIS_REGION
    out = _node(f"""
      const floor = {json.dumps(r)};
      const home = Z.zoomFloorRect(floor, floor, 0.15);
      const inner = Z.zoomFloorRect({{x: {r['x'] + r['w'] * 0.3}, y: 0.3,
                                      w: {r['w'] * 0.4}, h: 0.4}}, floor, 0.15);
      const stray = Z.zoomFloorRect({{x: 0, y: 0, w: 0.1, h: 0.1}}, floor, 0.15);
      const fullFrame = {{x: 0, y: 0, w: 1, h: 1}};
      const desktop = Z.zoomFloorRect(fullFrame, fullFrame, 0.15);
      console.log(JSON.stringify({{home, inner, stray, desktop}}));
    """)
    for name in ("home", "inner", "stray"):
        rect = out[name]
        assert rect["w"] >= 0 and rect["h"] >= 0, \
            f"the page's {name} rect came out with a NEGATIVE size {rect} — an " \
            "empty intersection must fall back to the floor, not be returned raw"
        assert rect["x"] >= r["x"] - 1e-9 and rect["y"] >= r["y"] - 1e-9 and \
            rect["x"] + rect["w"] <= r["x"] + r["w"] + 1e-9 and \
            rect["y"] + rect["h"] <= r["y"] + r["h"] + 1e-9, \
            f"the page's {name} rect escaped the layout floor: {rect}"
    assert abs(out["home"]["w"] - r["w"]) < 1e-9, \
        "at home the page asks for something other than the layout's own region"
    assert out["inner"]["w"] < r["w"], "zooming in did not narrow on the page side"
    # A rect that has drifted entirely off the layout (an EMPTY intersection)
    # must fall back to the floor itself, byte for byte — never a raw,
    # negative-sized rect that merely happens to sit within the floor's bounds.
    assert out["stray"] == r, \
        f"a stray rect with no intersection did not fall back to the floor: {out['stray']}"
    d = out["desktop"]
    assert abs(d["x"]) < 1e-9 and abs(d["y"]) < 1e-9 and \
        abs(d["w"] - 1) < 1e-9 and abs(d["h"] - 1) < 1e-9, \
        f"the desktop floor is not the full frame: {d}"
    print("  the page's own rect never leaves its floor, margin included; "
          "the desktop floor is the full frame")


def check_the_decode_ceiling_judges_the_raised_width() -> None:
    """The independent verifier's own gap: `effectiveWidth` used to cap the
    decode ceiling at the panel-scaled width even while a deep zoom pushed
    the encoder past it — the 2026-08-12 "4K60 = no picture" failure, back
    for a zoomed session. The fix is one multiply and one clamp, both
    load-bearing: raise by the step, then never past the crop's own native
    size (the same wall `_scale_size` enforces server-side)."""
    fn = re.search(r"function effectiveWidth\(p\) \{(.*?)\n\}", QUALITY_JS, re.S)
    assert fn, "effectiveWidth no longer exists in quality.js"
    body = fn.group(1)
    assert re.search(
        r"const scaled = panelScaledWidth\(cropW, cropH, devicePanel\(\)\);",
        body), "effectiveWidth no longer computes the panel-scaled width"
    assert re.search(r"scaled \* \(streamZoom \|\| 1\)", body), \
        "effectiveWidth no longer raises the ceiling by the zoom step"
    assert re.search(r"return Math\.min\(cropW, scaled \* \(streamZoom \|\| 1\)\);",
                     body), \
        "the raised width is no longer clamped at the crop's own native size " \
        "(cropW) — a deep zoom could push the ceiling past what the encoder " \
        "can ever really send"
    # ORDER MATTERS: `streamZoom` must be assigned from the frame BEFORE
    # `restateQualityIfChanged()` reads the ceiling it feeds, or a region
    # change and a zoom-step change riding the SAME config would restate
    # quality off the stale step from the PREVIOUS session.
    handler = re.search(r'msg\.type === "config"\) \{(.*?)\} else if', CONN_JS, re.S)
    assert handler, "no config handler found in connection.js"
    body_js = handler.group(0)
    zoom_pos = body_js.find("streamZoom = Math.max(1, Number(msg.stream_zoom) || 1);")
    restate_pos = body_js.find("restateQualityIfChanged();")
    assert zoom_pos >= 0, "the config handler no longer assigns streamZoom from the frame"
    assert restate_pos >= 0, "the config handler no longer restates quality"
    assert zoom_pos < restate_pos, (
        "streamZoom is assigned AFTER restateQualityIfChanged() runs — the "
        "ceiling would judge the previous session's step")
    print("  quality.js: the ceiling is raised by the zoom step and clamped "
          "at the crop's native size; streamZoom is assigned before it is read")


# ════════════════ 12. THE PAGE MUST NOT OUTLIVE ITS OWN PROTOCOL ════════════
# T94, owner report 2026-08-14: the round-3 zoom was correct in this tree and
# still self-erased on his tablet, because the PC had UPDATED ITSELF while his
# page stayed loaded — a v0.0.205 document against a v0.0.209 server, and the
# old page's zoom-echo guard undid every pinch (reproduced byte for byte in a
# real-browser harness against the extracted v0.0.205 client). No gate that
# imports only the current tree can express two versions facing each other, so
# what IS gated is the structural rule that ends the whole class: a config
# whose app_version differs from the one the document was first served under
# reloads the document, before anything else acts on the frame.
PAGE_VERSION = PROJECT / "client" / "page-version.js"
INDEX_HTML = (PROJECT / "client" / "index.html").read_text(encoding="utf-8")


def check_a_version_skew_reloads_the_page() -> None:
    """The REAL module, a whole document lifetime: the first versioned config
    arms the memory and never reloads; a same-version restatement (every
    later config of an ordinary evening) keeps quiet; a DIFFERENT version —
    newer or older alike — reloads; a version-less frame (an older server)
    decides nothing and never arms the memory."""
    out = _node(f"""
      const P = require({json.dumps(str(PAGE_VERSION))});
      let v = "";
      const log = [];
      for (const cfg of [null, "0.0.209", "0.0.209", "0.0.210", "0.0.208"]) {{
        const r = P.pageVersionStep(v, cfg);
        v = r.servedVersion;
        log.push({{cfg, v, reload: r.reload}});
      }}
      console.log(JSON.stringify(log));
    """)
    assert not out[0]["reload"] and out[0]["v"] == "", \
        "a version-less config armed the memory or reloaded — an older " \
        "server would reload the page forever"
    assert not out[1]["reload"] and out[1]["v"] == "0.0.209", \
        "the first versioned config did not arm the memory quietly"
    assert not out[2]["reload"], \
        "a same-version restatement reloaded the page — every reconnect " \
        "would flash a reload"
    assert out[3]["reload"], \
        "a NEWER server did not reload the page — the exact 2026-08-14 " \
        "failure: last hour's client undoing this hour's server"
    assert out[3]["v"] == "0.0.209", \
        "the reload rewrote the served version — a reload that fails would " \
        "then never fire again"
    assert out[4]["reload"], \
        "an OLDER server (a rollback) did not reload — a rollback changes " \
        "the wire just as surely as an update"
    print("  page-version.js: arms once, restates quietly, reloads on any skew")


def check_the_config_handler_reloads_before_acting() -> None:
    """connection.js really asks the module, really reloads, and does it
    BEFORE the frame's protocol-bearing work (initMse, the view decision) —
    a page that first acted on a foreign frame and then reloaded would have
    already done the damage the reload exists to prevent. And the module is
    loaded by the page at all (the grid-icons lesson: a pure module nobody
    loads is a feature that does not exist)."""
    handler = re.search(r'msg\.type === "config"\) \{(.*?)\} else if', CONN_JS, re.S)
    assert handler, "no config handler found in connection.js"
    body = handler.group(0)
    call = body.find("pageVersionStep(pageServedVersion, msg.app_version)")
    assert call >= 0, "the config handler no longer asks pageVersionStep"
    reload_pos = body.find("location.reload();")
    assert reload_pos > call, "the skew decision no longer reloads the document"
    assert re.search(r"location\.reload\(\);\s*\n\s*return;", body), \
        "the reload does not return — the handler would act on a frame from " \
        "a protocol this page predates before the reload lands"
    mse_pos = body.find("initMse(")
    assert mse_pos > reload_pos, \
        "the version decision runs AFTER initMse — the stale page rebuilds " \
        "its pipeline on the foreign frame before reloading"
    assert 'let pageServedVersion = ""' in STATE_JS, \
        "pageServedVersion is no longer per-document state in state.js"
    assert "/static/page-version.js" in INDEX_HTML, \
        "index.html no longer loads page-version.js — the config handler " \
        "would throw on its first frame"
    assert INDEX_HTML.find("/static/page-version.js") \
        < INDEX_HTML.find("/static/connection.js"), \
        "page-version.js loads after connection.js"
    print("  connection.js reloads on a version skew before acting on the frame")


# ═══════ 13. ROUND 5 — THE STEP IS MAGNIFICATION, NOT A FRACTION ═══════
# Owner report 2026-08-18: his tablet in PORTRAIT over a 16:9 monitor, zoomed
# ~2x, showed the panel-capped 1922x1080 magnified — "not even a quarter of
# the resolution the desktop delivers", and it is exactly a quarter of the
# pixels. His log: not one `zoom` session between 19:35 and 19:41; the step
# stayed 1. The round-3 rule (the LARGER visible fraction decides) is blind to
# a LETTERBOXED picture — its full height stays in view up to 2.84x, so the
# height fraction reads 1.0 and no zoom he ever used earned a step. Round 5:
# the phone sends the size it DRAWS the picture at, and the step is the ratio
# of drawn to panel — the mirror of `_scale_size`, so the two cancel.
HIS_PANEL = {"w": 1200, "h": 1920}      # canvas=1200x1920 in his own log


def _his_tablet(z: float, drawn: bool = True) -> dict:
    """His portrait tablet at zoom z: the 16:9 monitor fits 1200x675 and the
    margin-widened visible rect the page really computes at that zoom."""
    w = min(1.0, 1.3 / z)                     # 1/z widened by 2 x 0.15
    h = min(1.0, 1.3 * 1920 / (675 * z))
    rect = None if (w >= 1.0 and h >= 1.0) else \
        {"x": (1 - w) / 2, "y": (1 - h) / 2, "w": w, "h": h}
    conn = {"active": None, "region": None, "panel": HIS_PANEL, "zoom": rect}
    if drawn:
        conn["zoom_drawn"] = {"w": 1200 * z, "h": 675 * z}
    return conn


def check_a_letterboxed_picture_earns_its_step_from_the_drawn_size() -> None:
    """His exact numbers. At 2.07x (his 19:39:22 caret line, pic width 2485
    of 1200) the old fraction rule answers 1 — the height fraction is 1.0 —
    and that IS the blur he photographed; the drawn/panel ratio answers 2,
    which `_scale_size` turns into native. Below ~1.6x one encoded pixel still
    covers one panel pixel, so nothing is raised — the step is never eager."""
    step = layout_api.zoom_step
    assert step(_his_tablet(1.0)) == 1, "the fitted view earned a step"
    assert step(_his_tablet(1.5)) == 1, \
        "1.5x (ratio 0.94 — still no magnification) earned a step for nothing"
    assert step(_his_tablet(2.07)) == 2, \
        "his 2.07x zoom on a letterboxed picture earned NO step — the blur he photographed"
    assert step(_his_tablet(2.07, drawn=False)) == 1, \
        "the plant: without `drawn` the old fraction rule must still answer 1 — " \
        "otherwise this check proves nothing about the new derivation"
    assert step(_his_tablet(3.0)) == 2, "3x (ratio 1.9) is x2, not more"
    assert step(_his_tablet(6.0)) == 4, "his ZOOM_MAX of 6x (ratio 3.75) is x4"
    print("  his portrait tablet: 1.5x -> x1, 2.07x -> x2 (old rule: x1), 6x -> x4")


def check_the_layout_region_scales_the_drawn_base() -> None:
    """The region is the base picture: the drawn size of the WHOLE monitor
    is multiplied by the region before it meets the panel."""
    conn = _his_tablet(3.0)
    conn["region"] = {"x": 0.25, "y": 0.0, "w": 0.5, "h": 1.0}
    # base drawn = 1800 x 2025; long/long = 2025/1920 = 1.05, short/short =
    # 1800/1200 = 1.5 -> ratio 1.5 -> step 2 (a full-frame 3x was 3.75 -> 4).
    assert layout_api.zoom_step(conn) == 2, \
        "the region did not scale the drawn base (expected x2 for a half-width layout at 3x)"
    conn["region"] = {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}
    # 1800 x 1012: 1800/1920 = 0.94, 1012/1200 = 0.84 -> no magnification
    assert layout_api.zoom_step(conn) == 1, \
        "a quarter region at 3x is not magnified on his panel — expected x1"
    print("  a layout region scales the drawn base before it meets the panel")


def check_a_pinch_that_keeps_the_rect_full_still_reaches_the_choke_point() -> None:
    """A landscape phone at 1.2x: the margin-widened rect still clamps to the
    full frame (1/1.2 + 0.25 > 1), so `conn["zoom"]` stays None and the old
    delta guard would return before recording anything — yet every encoded
    pixel is now lit 1.2x. The drawn size must carry it through to the step
    (x2), and a drift within the slack must still not."""
    calls, original = _install_send_state_stub()
    try:
        panel = {"w": 1920, "h": 1200}
        conn = {"active": None, "region": None, "panel": panel,
                "zoom": None, "zoom_drawn": {"w": 1920, "h": 1080},
                "stream_zoom": 1}
        full = {"x": 0, "y": 0, "w": 1, "h": 1}
        asyncio.run(layout_api.zoom_region(
            _WS(), _Layouts(), conn,
            {**full, "drawn": {"w": 1920 * 1.2, "h": 1080 * 1.2}}))
        assert len(calls) == 1, \
            "a 1.2x pinch with a full rect never reached the choke point"
        assert conn["zoom_drawn"] == {"w": 2304.0, "h": 1296.0}
        assert layout_api.zoom_step(conn) == 2
        calls.clear()
        asyncio.run(layout_api.zoom_region(
            _WS(), _Layouts(), conn,
            {**full, "drawn": {"w": 2304 * 1.01, "h": 1296 * 1.01}}))
        assert not calls and conn["zoom_drawn"] == {"w": 2304.0, "h": 1296.0}, \
            "a 1 % drift in the drawn size (inside the slack) bought a recompute"
        # An older page: no `drawn` at all — nothing recorded, old world.
        conn2 = {"active": None, "region": None, "panel": panel,
                 "zoom": None, "stream_zoom": 1}
        asyncio.run(layout_api.zoom_region(_WS(), _Layouts(), conn2, full))
        assert conn2.get("zoom_drawn") is None and not calls
    finally:
        layout_api.send_layout_state = original
    print("  a full-rect pinch reaches the choke point by its drawn size; a 1 % drift does not")


def check_a_focus_change_drops_the_drawn_size_too() -> None:
    conn = {"active": 0, "region": {"x": 0, "y": 0, "w": 0.5, "h": 1},
            "zoom": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
            "zoom_drawn": {"w": 4000, "h": 2250}, "stream_region": None,
            "stream_zoom": 1, "reset_stream": lambda: None}

    class _Moved:
        def state(self, active, region):
            return {"type": "layout_state", "layouts": [], "active": 1,
                    "region": region, "orient": "landscape"}

    asyncio.run(layout_api.send_layout_state(_WS(), _Moved(), conn))
    assert conn["zoom"] is None and conn["zoom_drawn"] is None, \
        "a focus change kept the drawn size of the picture he left"
    print("  a focus change drops the drawn size with the rect")


def check_the_page_sends_its_drawn_size_and_guards_on_it() -> None:
    """The shipped render.js: the settled send carries `drawn` measured from
    drawnRect() (canvas px = panel px), and the do-not-resend guard asks the
    drawn size as well as the rect — else the full-rect pinch above is never
    sent at all. And the pure helper the guard runs, whole, in node."""
    src = (PROJECT / "client" / "render.js").read_text(encoding="utf-8")
    assert 'send({ type: "viewport", ...rect, drawn });' in src, \
        "render.js does not send `drawn` with the settled viewport"
    assert "const D = drawnRect();\n    const drawn = { w: D.w, h: D.h };" in src, \
        "`drawn` is not measured from drawnRect()"
    assert "&& !zoomDrawnMoved(lastSentZoom.drawn, drawn)) return;" in src, \
        "the resend guard ignores the drawn size — a full-rect pinch is never sent"
    got = _node("""
      const a = {w: 1920, h: 1080};
      console.log(JSON.stringify({
        same: Z.zoomDrawnMoved(a, {w: 1920 * 1.01, h: 1080}),
        moved: Z.zoomDrawnMoved(a, {w: 1920 * 1.2, h: 1080 * 1.2}),
        none: Z.zoomDrawnMoved(null, a),
      }));""")
    assert got == {"same": False, "moved": True, "none": True}, got
    print("  render.js sends `drawn` and guards on it; zoomDrawnMoved is the shipped rule")


CHECKS = [
    check_zoom_step_arithmetic_at_the_desktop,
    check_zoom_step_arithmetic_inside_a_layout,
    check_stream_crop_never_reads_the_zoom,
    check_a_pan_never_rebuilds_the_session,
    check_a_step_crossing_rebuilds_the_session,
    check_the_choke_point_resets_on_a_step_mismatch_alone,
    check_a_sub_threshold_drift_changes_nothing,
    check_a_focus_change_drops_the_zoom_it_was_measured_in,
    check_scale_size_zoom_raises_the_ceiling_and_clamps_at_native,
    check_reference_size_ignores_the_session_s_own_zoom,
    check_a_deep_zoom_raises_the_cellular_bitrate_but_never_past_the_rung,
    check_wi_fi_bitrate_is_untouched_by_zoom,
    check_web_py_derives_and_records_the_zoom_step,
    check_h264_session_accepts_and_logs_its_zoom,
    check_the_choke_point_compares_two_derivations_not_two_copies,
    check_config_carries_the_zoom_step_only_above_1,
    check_the_decode_ceiling_judges_the_raised_width,
    check_h264_config_seen_starts_false_and_flips_once_per_config,
    check_an_unchanged_config_region_keeps_the_view,
    check_an_unchanged_layout_state_never_undoes_the_zoom,
    check_the_settle_suppresses_a_gesture_in_progress,
    check_the_floor_rule_is_the_module_the_page_runs,
    check_a_version_skew_reloads_the_page,
    check_the_config_handler_reloads_before_acting,
    check_a_letterboxed_picture_earns_its_step_from_the_drawn_size,
    check_the_layout_region_scales_the_drawn_base,
    check_a_pinch_that_keeps_the_rect_full_still_reaches_the_choke_point,
    check_a_focus_change_drops_the_drawn_size_too,
    check_the_page_sends_its_drawn_size_and_guards_on_it,
]


def main() -> int:
    print("ZOOM CROP GATE - round 3: the zoom raises the resolution, never the crop")
    for check in CHECKS:
        check()
    print("OK - all zoom crop checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
