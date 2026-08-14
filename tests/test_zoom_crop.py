"""ZOOM CROP GATE — the zoom is a crop, and a crop is sharp pixels.

Owner report 2026-08-14 (T76), and he is angry because he asked for this at
the very start. In translation: "why is downscaling done even when the picture
is zoomed — when we zoom on the phone we are enlarging that downscaled
resolution so the picture is blurry, even though the whole screen does not
need to be sent then either, because we are in a slice just like in layout
mode".

The measured gap: `H264Session._crop_rect` cropped ONLY from a region fed by a
focused LAYOUT, and the `viewport` message the pinch has always sent was
discarded outright in H.264 mode ("H.264 streams the full frame — a viewport
from a stale client is noise"). So a zoom magnified pixels that had already
been through the panel-ceiling downscale and asked the PC for nothing. Every
piece needed to fix it already existed — the crop, `config.stream_region`,
render.js's mapping, decode-caps' `effectiveWidth`, the single choke point in
`layout_api.send_layout_state` — and only the wire from the finger to it was
missing.

WHAT IS PROVEN HERE, and why each check computes what it computes. The lesson
this project keeps re-learning (constraint 13, and test_view_anchor.py's own
header) is that a check on a value the user cannot see proves nothing — so
every geometric check below ends at PIXELS of the real `H264Session`, the
thing his eyes grade, and never at a variable's value:

1. A desktop zoom really produces a smaller pixel crop (fewer pixels encoded,
   covering the slice he is looking at).
2. Zooming all the way back out returns to the FULL frame with no residue —
   no crop filter, no `stream_region`.
3. Inside a layout the layout's region is the FLOOR: a zoom can only narrow
   further, and a rect wider than the region (or one belonging to a layout he
   has left) can never widen the crop past it.
4. The settle suppresses everything mid-gesture — the REAL client/zoom-crop.js
   rules, driven in node over a gesture's whole life.
5. A sub-threshold drift never reopens a session (one blink per finished
   gesture; a blink storm is what he will not accept).
6. A client that never sends a zoom behaves exactly as before — the old world,
   byte for byte.
7. The wiring exists end to end: web routes the message, both the session
   opener and the choke point ask ONE derivation, and the page's decode
   ceiling still sizes itself by the crop.

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
RENDER = (PROJECT / "client" / "render.js").read_text(encoding="utf-8")
QUALITY = (PROJECT / "client" / "quality.js").read_text(encoding="utf-8")
INDEX = (PROJECT / "client" / "index.html").read_text(encoding="utf-8")
MODULE = PROJECT / "client" / "zoom-crop.js"

# The owner's own live layout (server.log 2026-08-12 14:39:49) — a VS Code
# layout on his 4K monitor, a quarter of its width. The same rect
# test_region_stream.py is driven with, deliberately: this feature narrows
# exactly that picture.
HIS_REGION = {"x": 0.3736979166666667, "y": 0.000462962962962963,
              "w": 0.25234375, "h": 0.9708333333333333}

FULL = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}


class _FakeSource:
    stream_w, stream_h = 3840, 2160
    capture_fps = 60


def encoded(conn) -> tuple[int, int, int, int] | None:
    """THE PIXELS HE JUDGES: what the REAL encoder would crop for this
    connection, as (w, h, x, y) — or None for the whole frame. Goes through
    the SAME `stream_crop` web.py opens a session with, then the REAL
    H264Session, so nothing here can be true of a variable and false of the
    picture."""
    s = h264_streamer.H264Session(
        _FakeSource(), "libx264", lambda b: None, lambda: None,
        region=layout_api.stream_crop(conn))
    return s._crop


def has_crop_filter(conn) -> bool:
    s = h264_streamer.H264Session(
        _FakeSource(), "libx264", lambda b: None, lambda: None,
        region=layout_api.stream_crop(conn))
    return any("crop=" in a for a in s._ffmpeg_cmd())


# ══════════════════════ 1. A DESKTOP ZOOM IS A CROP ══════════════════════
def check_a_desktop_zoom_becomes_a_real_pixel_crop() -> None:
    """He pinches into the middle of his 4K desktop. Until this round the
    encoder still fed 3840x2160 through the panel ceiling and the phone
    enlarged the result; now the encoder sees only what he sees."""
    desk = {"active": None, "region": None, "zoom": None}
    assert encoded(desk) is None, "the untouched desktop is not a full frame"
    zoomed = {**desk, "zoom": {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}}
    crop = encoded(zoomed)
    assert crop is not None, (
        "a desktop zoom encodes the WHOLE screen — this is the reported bug: "
        "the phone magnifies already-downscaled pixels")
    w, h, x, y = crop
    assert w % 2 == h % 2 == x % 2 == y % 2 == 0, f"odd crop {crop}"
    # The slice he is looking at, in pixels, and a QUARTER of the pixels that
    # used to be encoded for the same picture.
    assert abs(x - 960) <= 2 and abs(y - 540) <= 2, crop
    assert abs(w - 1920) <= 2 and abs(h - 1080) <= 2, crop
    assert w * h * 4 <= 3840 * 2160 + 4, (
        f"the zoom encodes {w}x{h} of 3840x2160 — no real saving")
    print(f"  desktop zoom encodes {w}x{h}+{x}+{y} — a quarter of the pixels")


# ═════════════════ 2. ZOOMING OUT RETURNS TO THE FULL FRAME ═════════════════
def check_zooming_all_the_way_out_returns_the_full_frame() -> None:
    """No residue: the crop filter is GONE and `stream_region` is None, which
    is what tells the page to map the video over the whole monitor again."""
    conn = {"active": None, "region": None,
            "zoom": {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}}
    assert has_crop_filter(conn)
    conn["zoom"] = None                       # he lifted back to home
    assert layout_api.stream_crop(conn) is None, layout_api.stream_crop(conn)
    assert encoded(conn) is None and not has_crop_filter(conn), \
        "a zoomed-out desktop still carries a crop — residue"
    # And a client that says "full frame" in so many words is the same thing:
    # `_is_full` must recognise it, or every zoom-out would leave a 1:1 crop
    # standing and cost a needless rebuild.
    conn["zoom"] = dict(FULL)
    assert layout_api.stream_crop(conn) is None, \
        "an explicit full-frame viewport was not recognised as the full frame"
    print("  zoomed out: no crop filter, no stream_region — the old world")


# ═══════════ 3. INSIDE A LAYOUT THE REGION IS THE FLOOR, NOT A CEILING ═══════
def check_a_zoom_inside_a_layout_never_widens_past_the_region() -> None:
    """His quarter-width VS Code layout. Zooming in narrows further; nothing
    a phone can send widens the crop, because a wider crop would stream the
    windows the layout exists to keep off his screen."""
    lay = {"active": 0, "region": dict(HIS_REGION), "zoom": None}
    base = encoded(lay)
    assert base is not None
    bw, bh, bx, by = base
    # (a) The whole frame asked for: the floor holds — byte for byte the
    #     layout's own crop.
    wide = {**lay, "zoom": dict(FULL)}
    assert encoded(wide) == base, (
        f"a full-frame zoom widened the layout crop {base} -> {encoded(wide)}")
    # (b) A rect belonging to a DIFFERENT part of the screen (a stale one from
    #     the layout he just left) can never move the crop off the layout.
    stray = {**lay, "zoom": {"x": 0.0, "y": 0.0, "w": 0.2, "h": 0.2}}
    sw, sh, sx, sy = encoded(stray)
    assert sx >= bx - 2 and sy >= by - 2 and sx + sw <= bx + bw + 2 and \
        sy + sh <= by + bh + 2, \
        f"a stray zoom escaped the layout: {(sw, sh, sx, sy)} vs {base}"
    # (c) Zooming IN: strictly fewer pixels, strictly inside the region.
    r = HIS_REGION
    inner = {**lay, "zoom": {"x": r["x"] + r["w"] * 0.25, "y": r["y"] + r["h"] * 0.25,
                             "w": r["w"] * 0.5, "h": r["h"] * 0.5}}
    iw, ih, ix, iy = encoded(inner)
    assert iw < bw and ih < bh, f"zooming in did not narrow: {(iw, ih)} vs {(bw, bh)}"
    assert ix >= bx - 2 and iy >= by - 2 and ix + iw <= bx + bw + 2 and \
        iy + ih <= by + bh + 2, "the inner zoom left the region"
    # (d) And back out to home: exactly the layout's crop again, no wider.
    lay["zoom"] = dict(HIS_REGION)
    assert encoded(lay) == base, "returning home did not land on the layout crop"
    print(f"  layout {bw}x{bh}: a zoom narrows to {iw}x{ih}, never wider")


# ═════════════════ 4. THE SETTLE — the gesture is WATCHED ═════════════════
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
    finger is down NOTHING settles however long it lasts (which is why this is
    an observation and not a forbidden estimate of anyone's timing), and after
    the lift it settles EXACTLY ONCE, once the threshold of stillness has
    really passed."""
    sends = _node("""
      let st = {sample: null, changedAt: 0};
      const out = [];
      // 20 ticks of a live pinch: the finger is down and the rect keeps moving.
      let t = 0, w = 1.0;
      for (let i = 0; i < 20; i++, t += 60) {
        w -= 0.03;
        st = Z.zoomSettleStep(st, {now: t, pointersDown: true,
          rect: {x: 0.1, y: 0.1, w: w, h: w}, settleMs: 280});
        out.push({t, phase: "down", settled: st.settled});
      }
      // A PAUSE MID-PINCH: the finger is still down and simply not moving —
      // he is looking at what he has framed before adjusting it. Nothing may
      // settle here, and only the pointer state can say so, because the rect
      // is as still as it will be after the lift.
      for (let i = 0; i < 8; i++, t += 60) {
        st = Z.zoomSettleStep(st, {now: t, pointersDown: true,
          rect: {x: 0.1, y: 0.1, w: w, h: w}, settleMs: 280});
        out.push({t, phase: "down", settled: st.settled});
      }
      // The finger lifts; the rect stops moving.
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
    # The FIRST settle may only come after the whole threshold of stillness,
    # measured from the last tick that saw movement — the last tick with a
    # finger down. (It is one sample earlier than the lift itself: a tick with
    # a pointer down always counts as movement, whatever the rect says.)
    last_moving = [s for s in sends if s["phase"] == "down"][-1]["t"]
    assert after[0]["t"] - last_moving >= 280, (
        f"settled {after[0]['t'] - last_moving} ms after the last movement — "
        "under the threshold")
    print(f"  nothing settles under the finger; the first settle is "
          f"{after[0]['t'] - last_moving} ms after the last movement")


def check_the_floor_rule_is_the_module_the_page_runs() -> None:
    """The same floor rule, on the PAGE side, driven whole: the margin the
    page adds may never be what widens the rect past the layout."""
    r = HIS_REGION
    out = _node(f"""
      const floor = {json.dumps(r)};
      const home = Z.zoomFloorRect(floor, floor, 0.15);
      const inner = Z.zoomFloorRect({{x: {r['x'] + r['w'] * 0.3}, y: 0.3,
                                      w: {r['w'] * 0.4}, h: 0.4}}, floor, 0.15);
      const stray = Z.zoomFloorRect({{x: 0, y: 0, w: 0.1, h: 0.1}}, floor, 0.15);
      console.log(JSON.stringify({{home, inner, stray}}));
    """)
    for name, rect in out.items():
        assert rect["x"] >= r["x"] - 1e-9 and rect["y"] >= r["y"] - 1e-9 and \
            rect["x"] + rect["w"] <= r["x"] + r["w"] + 1e-9 and \
            rect["y"] + rect["h"] <= r["y"] + r["h"] + 1e-9, \
            f"the page's {name} rect escaped the layout floor: {rect}"
    assert abs(out["home"]["w"] - r["w"]) < 1e-9, \
        "at home the page asks for something other than the layout's own region"
    assert out["inner"]["w"] < r["w"], "zooming in did not narrow on the page side"
    print("  the page's own rect never leaves the layout, margin included")


# ══════════ 5/6. THE CHOKE POINT: one blink per gesture, and no more ══════════
class _WS:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(json.loads(text))


class _Layouts:
    def state(self, active, region):
        return {"type": "layout_state", "layouts": [], "active": active,
                "region": region, "orient": "landscape"}


def _zoom(conn, rect):
    ws = _WS()
    asyncio.run(layout_api.zoom_region(ws, _Layouts(), conn, rect))
    return ws


def check_a_sub_threshold_drift_never_reopens_a_session() -> None:
    """One blink per FINISHED gesture. A pinch that ends a hair from where the
    last one ended must cost nothing — a session rebuild is ~470 ms of ffmpeg
    and a visible blink."""
    fired = []
    conn = {"active": None, "region": None, "zoom": None,
            "reset_stream": lambda: fired.append(1)}
    conn["stream_region"] = layout_api.stream_crop(conn)
    # A real zoom: one reset.
    _zoom(conn, {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5})
    assert len(fired) == 1, f"a real zoom fired {len(fired)} resets"
    conn["stream_region"] = layout_api.stream_crop(conn)  # the loop reopened
    # A one-pixel drift on a 4K monitor is ~0.00026 — far under the threshold.
    _zoom(conn, {"x": 0.2503, "y": 0.2502, "w": 0.4998, "h": 0.5001})
    assert len(fired) == 1, "a sub-threshold drift cost him a blink"
    # And a real second zoom still does fire.
    _zoom(conn, {"x": 0.35, "y": 0.35, "w": 0.3, "h": 0.3})
    assert len(fired) == 2, "a second real zoom did not follow"
    print("  one blink per finished gesture; a pixel of drift costs nothing")


def check_a_zoom_that_changes_no_crop_never_reopens_a_session() -> None:
    """Inside a layout, a pinch that stays at home moves the RECT but not the
    CROP — the floor absorbs it — so nothing may be rebuilt."""
    fired = []
    conn = {"active": 0, "region": dict(HIS_REGION), "zoom": None,
            "reset_stream": lambda: fired.append(1)}
    conn["stream_region"] = layout_api.stream_crop(conn)
    # A rect that is NOT the full frame — so it survives the delta guard and
    # really reaches the crop comparison — but is wider than the layout on
    # every side, so the floor absorbs it whole.
    r = HIS_REGION
    _zoom(conn, {"x": r["x"] - 0.05, "y": 0.0,
                 "w": r["w"] + 0.1, "h": 1.0})
    assert conn["zoom"] is not None, "the test's own rect never reached the crop rule"
    assert not fired, "a zoom the floor absorbed still rebuilt the encoder"
    _zoom(conn, {"x": HIS_REGION["x"] + 0.05, "y": 0.2, "w": 0.1, "h": 0.4})
    assert fired, "a real zoom inside the layout changed nothing"
    print("  a gesture the floor absorbs blinks nothing")


def check_an_old_client_is_exactly_the_old_world() -> None:
    """A page that never sends a viewport in H.264 — every release before this
    one. Its connection carries no `zoom` key at all."""
    fired = []
    old = {"active": 0, "region": dict(HIS_REGION),
           "stream_region": dict(HIS_REGION),
           "reset_stream": lambda: fired.append(1)}
    assert layout_api.stream_crop(old) == HIS_REGION, \
        "an old client's crop is no longer the layout's region"
    asyncio.run(layout_api.send_layout_state(_WS(), _Layouts(), old))
    assert not fired, "an old client's unchanged layout reset the stream"
    # …and a layout change still resets it, exactly as before this round.
    old["stream_region"] = None
    asyncio.run(layout_api.send_layout_state(_WS(), _Layouts(), old))
    assert fired, "an old client's layout change no longer resets the stream"
    # A desktop connection with no zoom key: full frame, no crop.
    assert encoded({"active": None, "region": None}) is None
    print("  a client that sends no zoom behaves exactly as before")


def check_a_focus_change_drops_the_zoom_it_was_measured_in() -> None:
    """The settled rect belongs to the picture it was measured in. Carrying it
    into the next layout would crop the new picture to the old one's slice."""
    conn = {"active": 0, "region": dict(HIS_REGION),
            "zoom": {"x": 0.4, "y": 0.2, "w": 0.1, "h": 0.3}}
    conn["stream_region"] = layout_api.stream_crop(conn)

    class _Moved:
        def state(self, active, region):
            return {"type": "layout_state", "layouts": [], "active": 1,
                    "region": region, "orient": "landscape"}

    asyncio.run(layout_api.send_layout_state(_WS(), _Moved(), conn))
    assert conn["zoom"] is None, \
        "the previous layout's zoom followed him into the next one"
    print("  a focus change drops the zoom measured in the layout he left")


# ══════════ 8. THE BITRATE FOLLOWS THE PIXELS — on cellular only (T79) ══════
# His own device: a 3840x2160 desktop watched on a 1920x1200 tablet.
PANEL = {"w": 1920, "h": 1200}
WIFI = {"fps": 0, "res": "full", "bitrate": "max"}
CELL = {"fps": 10, "res": "1/2", "bitrate": "saver"}   # the saving profile


def _sess(region, quality, panel=PANEL):
    return h264_streamer.H264Session(
        _FakeSource(), "libx264", lambda b: None, lambda: None,
        quality=quality, region=region, panel=panel)


def _bv(session) -> str:
    """The exact string handed to ffmpeg as `-b:v`. Compared as a STRING only
    where the promise is "unchanged" — see `_bvi` for every numeric check."""
    cmd = session._ffmpeg_cmd()
    return cmd[cmd.index("-b:v") + 1]


def _bvi(session) -> int:
    """`-b:v` in bits per second, parsed the way ffmpeg reads it.

    Never `_bvi(session)`: a rung's own string is `"2M"`, not a decimal.
    That is deliberate on the product side — when the arithmetic reduces
    nothing, the rung's string goes out exactly as it always did, so a
    full-screen saver session is unchanged in what ffmpeg is handed and in
    what the log prints, not merely in its arithmetic. A gate that assumed a
    decimal was asserting the SHAPE of the number instead of its value.
    """
    return config.bitrate_bps(_bv(session))


def check_wi_fi_bitrate_is_untouched() -> None:
    """Rule 1, and it is a FEATURE, not an oversight: a focused layout coming
    out sharper at the same nominal quality is what `_scale_size` bought him.
    Nothing on Wi-Fi may change — full frame, layout crop or deep zoom."""
    for region in (None, dict(HIS_REGION), {"x": 0.4, "y": 0.3, "w": 0.08, "h": 0.1}):
        s = _sess(region, dict(WIFI))
        assert s.bitrate_factor == 1.0, f"Wi-Fi was scaled: {s.bitrate_factor}"
        assert _bv(s) == config_bitrate(WIFI["bitrate"]), (
            f"Wi-Fi bitrate changed to {_bv(s)} for region {region}")
    # A client that reports no transport at all — an old page, a browser — is
    # exactly this case: no saving profile, no scaling.
    s = _sess(dict(HIS_REGION), None)
    assert s.bitrate_factor == 1.0 and _bv(s) == config_bitrate(None), \
        "a client with no quality override was scaled"
    print("  Wi-Fi / no transport: the bitrate is exactly what it was")


def config_bitrate(level):
    import config as _c
    return _c.bitrate_for_level(level)


def check_an_unreduced_bitrate_keeps_the_rung_s_own_string() -> None:
    """UNCHANGED MEANS UNCHANGED — the string, not merely the value.

    This defect SHIPPED and was caught by the build, not by this gate: when
    the arithmetic reduced nothing, `_bitrate` still returned a decimal, so a
    full-screen saver session handed ffmpeg "2000000" where it had always been
    handed "2M". Numerically identical and still wrong twice over — it is what
    the session log prints, and `tests/test_quality_reset.py` deliberately
    holds the rung as the literal "2M" so a silent change to a shipped default
    fails there by name. Two of its checks went red and the whole build
    stopped. The promise is asserted HERE too, beside the feature that broke
    it, rather than left to a gate that happens to notice.

    PLANTED DEFECT this catches: deleting the `applied >= nominal_bps` branch
    in `H264Session._bitrate`."""
    s = _sess(None, dict(CELL))
    assert s.bitrate == config_bitrate("saver"), (
        f"an unreduced cellular session handed ffmpeg {s.bitrate!r} instead of "
        f"the rung's own {config_bitrate('saver')!r}")
    print("  an unreduced bitrate is the rung's own string, not a decimal")


def check_a_cellular_full_screen_is_also_untouched() -> None:
    """The reference is "a full screen on this panel", so the rung keeps
    meaning what it says: on cellular WITHOUT a crop the number is the rung's
    own, to the bit."""
    import config as _c
    rung = _c.bitrate_bps(config_bitrate("saver"))
    # EVERY panel, not only his own: the reference is DERIVED from the panel
    # through the same `_scale_size` the real size goes through. A reference
    # that happened to be right for one device would be silently wrong for
    # every other one — and it is exactly the kind of constant that reads fine
    # in a diff.
    for panel in (PANEL, {"w": 1280, "h": 720}, {"w": 2400, "h": 1080}, None):
        s = _sess(None, dict(CELL), panel)
        assert s.bitrate_factor == 1.0, (panel, s.bitrate_factor)
        assert _bvi(s) == rung, \
            f"a cellular full screen on panel {panel} was scaled to {_bv(s)}"
    print(f"  cellular full screen: {rung} bps on every panel — the rung, unchanged")


def check_a_cellular_below_panel_crop_spends_less() -> None:
    """The overspend the owner asked about, closed: a crop that falls BELOW
    the panel is sent at its own small size, and now the ceiling follows it."""
    full = _sess(None, dict(CELL))
    lay = _sess(dict(HIS_REGION), dict(CELL))
    assert lay.bitrate_factor < 0.5, (
        f"his quarter-width layout still claims x{lay.bitrate_factor} of the rung")
    assert _bvi(lay) < _bvi(full), (
        f"a below-panel crop still asks for {_bv(lay)} — the reported overspend")
    ew, eh = lay._encoded_size()
    rw, rh = full._encoded_size()
    # The bits per pixel per frame may never come out WORSE than the reference
    # picture he already accepts — that is what the floor is for.
    assert _bvi(lay) / (ew * eh) >= _bvi(full) / (rw * rh), \
        "the crop is given fewer bits per pixel than a full screen"
    print(f"  cellular layout crop {ew}x{eh}: {_bv(lay)} bps vs {_bv(full)} "
          f"full-screen — x{lay.bitrate_factor:.3f}")


def check_the_bitrate_is_never_scaled_up() -> None:
    """DOWNWARD ONLY, absolutely (task 131 — the phone may not raise the
    bitrate). No arithmetic here may ever exceed the rung's own number, and a
    panel bigger than the source is exactly the case that would try."""
    import config as _c
    rung = _c.bitrate_bps(config_bitrate("saver"))
    for panel in ({"w": 3840, "h": 2160}, {"w": 7680, "h": 4320}, None):
        for region in (None, dict(HIS_REGION)):
            s = _sess(region, dict(CELL), panel)
            assert s.bitrate_factor <= 1.0, s.bitrate_factor
            assert _bvi(s) <= rung, (
                f"panel {panel} region {region} raised the bitrate to {_bv(s)} "
                f"above the rung's {rung}")
    # AND THE CLAMP ITSELF, at the method boundary (the test_layout_member.py
    # lesson): today the factor cannot exceed 1 because `_scale_size` makes
    # the crop no bigger than the frame, so the cases above can only prove the
    # arithmetic that happens to be here now. The RULE is that no arithmetic
    # may ever raise the rung, so it is driven directly — a reference that
    # ever came out smaller than the encoded size must still cost nothing.
    s = _sess(dict(HIS_REGION), dict(CELL))
    s._reference_size = lambda: (16, 16)
    raised, factor = s._bitrate()
    assert config.bitrate_bps(raised) <= rung, (
        f"a reference smaller than the crop raised the bitrate to {raised} — "
        f"the phone may never raise the bitrate (task 131)")
    print("  no panel, crop or arithmetic ever raises the rung's number")


def check_a_tiny_crop_lands_on_the_floor() -> None:
    """A deep zoom cannot collapse into mush: the floor is a wall, and it is
    the SAME wall however small the crop gets."""
    tiny = _sess({"x": 0.5, "y": 0.5, "w": 0.02, "h": 0.02}, dict(CELL))
    tinier = _sess({"x": 0.5, "y": 0.5, "w": 0.005, "h": 0.005}, dict(CELL))
    assert _bvi(tiny) == _bvi(tinier) == h264_streamer.BITRATE_FLOOR_BPS, \
        f"a deep zoom fell through the floor: {_bv(tiny)} / {_bv(tinier)}"
    print(f"  a deep zoom stops at the {h264_streamer.BITRATE_FLOOR_BPS} bps floor")


def check_the_applied_number_and_the_factor_are_logged() -> None:
    """His own reason: without them there is no telling "the encoder did not
    spend because nothing moved" from "we capped it"."""
    src = (PROJECT / "server" / "h264_streamer.py").read_text(encoding="utf-8")
    log = re.search(r'rate = " bitrate .*?\n.*?\n', src)
    assert log, "the applied bitrate is no longer logged with the session"
    assert "session.bitrate" in log.group(0) and \
        "session.bitrate_factor" in log.group(0), \
        "the log line names neither the applied number nor the factor"
    assert re.search(r'logger\.info\("H\.264 session opened[^"]*%s%s%s"', src), \
        "the bitrate is computed for the log and then not printed"
    print("  the session log names the applied bitrate and its factor")


# ═══════════════════════════ 7. THE WIRING ═══════════════════════════
def check_the_wiring_end_to_end() -> None:
    assert re.search(r"layout_api\.zoom_region\(ws, layouts, conn, msg\)", WEB), \
        "web.py drops the viewport message in H.264 again — the reported bug"
    assert "req_region = layout_api.stream_crop(conn)" in WEB, \
        "the session is opened from something other than the one derivation"
    assert "stream_crop(conn) != conn.get(\"stream_region\")" in \
        (PROJECT / "server" / "layout_api.py").read_text(encoding="utf-8"), \
        "the choke point compares something other than the crop it opens with"
    assert re.search(r'streamMode !== "jpeg"[^}]*scheduleZoomRegion\(\);', RENDER, re.S), \
        "the page no longer settles and sends the zoom rect in H.264 mode"
    assert "zoomFloorRect(" in RENDER and "zoomSettleStep(" in RENDER, \
        "render.js grew its own copy of the rules instead of running the module"
    assert "zoom-crop.js" in INDEX, "the pure module is not loaded by the page"
    assert re.search(r"function effectiveWidth[^}]*streamRegion", QUALITY, re.S), \
        "the decode ceiling ignores the crop — a desktop cap would outlive it"
    print("  wiring: finger -> viewport -> stream_crop -> encoder -> page, present")


def check_the_config_echo_never_undoes_the_zoom() -> None:
    """T76 ROUND 2 (owner report 2026-08-14): every check above was GREEN
    while the zoom did not work at all on his tablet, because none of them
    reads connection.js — where the config handler ran resetViewHome() +
    scheduleViewport() unconditionally. Every zoom rebuild ends with a fresh
    `config`, so that pair was a self-erasing loop: the reset dropped
    `lastSentZoom` and snapped the view out, the re-armed watcher measured the
    reset view as the full frame and SENT it, and the server undid the zoom it
    had just applied. This check holds the guard: a config whose stream_region
    echoes the rect this page itself asked for keeps the pinch and re-arms
    nothing."""
    conn_js = (PROJECT / "client" / "connection.js").read_text(encoding="utf-8")
    assert re.search(
        r"const zoomEcho = [^;]*lastSentZoom[^;]*streamRegion[^;]*"
        r"zoomRectDelta\(lastSentZoom, streamRegion\) < ZOOM_MIN_DELTA", conn_js), \
        "the config handler no longer recognises its own zoom's echo"
    assert re.search(
        r"if \(zoomEcho\) \{[^}]*\} else \{[^}]*resetViewHome\(\);[^}]*"
        r"scheduleViewport\(\);", conn_js, re.S), \
        ("resetViewHome()/scheduleViewport() run unconditionally on config "
         "again — the self-erasing loop that killed every zoom on his tablet")
    echo_branch = re.search(r"if \(zoomEcho\) \{(.*?)\} else", conn_js, re.S)
    assert echo_branch and "resetViewHome" not in echo_branch.group(1) \
        and "scheduleViewport" not in echo_branch.group(1) \
        and "lastSentZoom = null" not in echo_branch.group(1), \
        "the echo branch itself resets the view or forgets the sent rect"
    print("  config echo: the zoom's own rebuild keeps the pinch and sends nothing")


def check_an_unchanged_layout_state_never_undoes_the_zoom() -> None:
    """THE SECOND PATH of the same loop, found by the adversarial verify of
    the config-echo fix and not by the fix's author: `zoom_region` re-sends
    `layout_state` through the choke point BEFORE the encoder rebuild, on
    EVERY zoom — and the client's layout_state handler ended with the same
    unconditional resetViewHome() + scheduleViewport(). A frame that changed
    neither the focus nor the region must keep the pinch."""
    conn_js = (PROJECT / "client" / "connection.js").read_text(encoding="utf-8")
    assert re.search(
        r"const focusUnchanged =\s*\(msg\.active \?\? null\) === layoutActive &&\s*"
        r"zoomRectDelta\(msg\.region \|\| prevFull, layoutRegion \|\| prevFull\)",
        conn_js), \
        "the layout_state handler no longer asks what the frame changed"
    assert re.search(
        r"if \(focusUnchanged\) \{[^}]*\} else \{[^}]*resetViewHome\(\);[^}]*"
        r"scheduleViewport\(\);", conn_js, re.S), \
        ("resetViewHome()/scheduleViewport() run on every layout_state again "
         "— the second self-erasing path, fired by every single zoom")
    unchanged = re.search(r"if \(focusUnchanged\) \{(.*?)\} else", conn_js, re.S)
    assert unchanged and "resetViewHome" not in unchanged.group(1) \
        and "scheduleViewport" not in unchanged.group(1) \
        and "lastSentZoom = null" not in unchanged.group(1), \
        "the unchanged-focus branch itself resets the view or forgets the rect"
    print("  layout_state echo: an unchanged focus keeps the pinch too")


CHECKS = [
    check_the_config_echo_never_undoes_the_zoom,
    check_an_unchanged_layout_state_never_undoes_the_zoom,
    check_a_desktop_zoom_becomes_a_real_pixel_crop,
    check_zooming_all_the_way_out_returns_the_full_frame,
    check_a_zoom_inside_a_layout_never_widens_past_the_region,
    check_the_settle_suppresses_a_gesture_in_progress,
    check_the_floor_rule_is_the_module_the_page_runs,
    check_a_sub_threshold_drift_never_reopens_a_session,
    check_a_zoom_that_changes_no_crop_never_reopens_a_session,
    check_an_old_client_is_exactly_the_old_world,
    check_a_focus_change_drops_the_zoom_it_was_measured_in,
    check_wi_fi_bitrate_is_untouched,
    check_an_unreduced_bitrate_keeps_the_rung_s_own_string,
    check_a_cellular_full_screen_is_also_untouched,
    check_a_cellular_below_panel_crop_spends_less,
    check_the_bitrate_is_never_scaled_up,
    check_a_tiny_crop_lands_on_the_floor,
    check_the_applied_number_and_the_factor_are_logged,
    check_the_wiring_end_to_end,
]


def main() -> int:
    print("ZOOM CROP GATE - the zoom is a crop, and a crop is sharp pixels")
    for check in CHECKS:
        check()
    print("OK - all zoom crop checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
