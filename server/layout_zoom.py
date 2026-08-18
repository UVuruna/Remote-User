"""THE T76 ZOOM ARITHMETIC: what the encoder crops to, and what resolution
step the pinch has earned.

Split out of `layout_api.py` on 2026-08-18 (THE STRUCTURE LAW, VC-R6). Every
function here is PURE — a dict in, a number or a dict out — and none of them
calls anything else in the layout protocol. That is the whole reason this is
the seam: these are the numbers the owner corrected across FIVE rounds
(`docs/DECISIONS.md` section 27), they are the ones `tests/test_zoom_crop.py`
drives check by check, and a file they share with thirty protocol handlers is
a file where a later patch aimed at a handler can reach them by accident.

The handler that USES them stayed next door: `layout_api.zoom_region` re-enters
`send_layout_state`, the one choke point that decides whether the running
session still matches, and moving a caller of that choke point out of the
module that owns it would be a second teardown path — which is exactly what
the 2026-08-07 orphan was made of.

NOTHING HERE WAS REWRITTEN. Every body is byte-identical to the one that stood
in `layout_api.py`, because on this file the audit's own risk note is the
point: round 5 of T76 exists because a documented rule measured the wrong
thing, and a split is not the place to have an opinion about which one.
"""

# THE ZOOM RAISES THE RESOLUTION, IT NEVER MOVES THE CROP (the owner's OWN
# design, round 3 of T76, 2026-08-14, delivered as eight diagrams; his words,
# translated: "the zoom must never send less that way ... we are not solving
# the desktop slice at all — the zoom may simply send a better resolution
# than the phone can accept, because the phone is now looking at part of the
# screen and not the whole"). Round 2 cropped the ENCODER to the zoomed
# slice, and the live result condemned the whole shape: panning past the crop
# showed the page's own background (H.264 has no base layer), every pan step
# was a 1–2 s ffmpeg rebuild, and one decoder hiccup in that storm
# reconnected with the zoom erased — his "keeps throwing me back to the
# desktop". His design removes the failure class instead of patching it: the
# stream ALWAYS covers the whole picture (desktop = full frame, layout = the
# layout's region, exactly as before), and the pinch changes only the
# RESOLUTION that picture is encoded at — in quantized steps, up to native
# 1:1 and never past it — because a zoomed phone shows only part of the
# picture, so the encoded size may exceed the panel. Panning is then FREE:
# the full picture is always underneath, nothing blanks, nothing rebuilds,
# and only a pinch that crosses a step boundary costs the one blink a
# rebuild always did.
#
# HOW MUCH THE RECT MUST MOVE before the wire is even consulted. A pinch that
# ends a hair from where it ended last time must not buy a recompute, in
# monitor-normalized units so it means the same thing on every monitor.
ZOOM_MIN_DELTA = 0.02

# The quantized resolution steps the zoom may ask for, PER AXIS (his ZOOM 1x /
# 2x / 16x drawings, folded to powers of two so a pinch crosses few
# boundaries): 1 = the ordinary panel-capped downscale, each doubling halves
# the downscale, and `_scale_size` clamps the product at native — his ZOOM 20x
# drawing: past native there is nothing left to raise and the step saturates.
ZOOM_MAX_STEP = 8

# HOW MUCH MAGNIFICATION IS "NONE" (round 5 of T76, owner report 2026-08-18).
# The step is earned from the ratio of DRAWN pixels to PANEL pixels (see
# `zoom_step`); a ratio of 1.0 means one encoded pixel lands on one panel
# pixel. Float noise in the phone's own canvas arithmetic (1920.0001 / 1920)
# must never buy a rebuild, and 2 % of magnification is below anything an eye
# can call blur — so a ratio inside this slack still reads as "no step".
ZOOM_STEP_SLACK = 0.02


def _norm(rect: dict) -> dict:
    """A wire rect clamped into the unit square and never inside-out. The
    phone computes it from its own canvas arithmetic; a rect that walks off
    the frame would crop nothing or crop garbage."""
    x = min(max(float(rect.get("x", 0.0)), 0.0), 1.0)
    y = min(max(float(rect.get("y", 0.0)), 0.0), 1.0)
    w = min(max(float(rect.get("w", 1.0)), 0.0), 1.0 - x)
    h = min(max(float(rect.get("h", 1.0)), 0.0), 1.0 - y)
    return {"x": x, "y": y, "w": w, "h": h}


def _is_full(r: dict) -> bool:
    return r["x"] <= 0.0 and r["y"] <= 0.0 and r["w"] >= 1.0 and r["h"] >= 1.0


def stream_crop(conn: dict) -> dict | None:
    """WHAT THE ENCODER MUST CROP TO — the ONE derivation of it, asked by
    both callers (web.py when it opens a session, `send_layout_state` when it
    decides whether the running one still matches) so the equality there
    stays exact.

    Since the owner's round-3 design this is the focused layout's region and
    NOTHING ELSE: the pinch no longer narrows the crop (round 2 did exactly
    that, and panning past the crop showed background over a 1–2 s rebuild
    per step — the shape he condemned live). The zoom acts on the encoded
    RESOLUTION instead — see `zoom_step`. The function stays, rather than
    being inlined away, because the choke-point rule it carries ("two reads
    of one derivation, never two copies") is what made the layout crop
    trustworthy and is worth keeping a name for."""
    return conn.get("region")


def zoom_step(conn: dict) -> int:
    """THE RESOLUTION STEP THE ZOOM HAS EARNED — the ONE derivation of it,
    asked by web.py when it opens a session and by `send_layout_state` when
    it decides whether the running session still matches (the same two-reads
    rule as `stream_crop`).

    THE STEP IS MAGNIFICATION, NOT A FRACTION (round 5 of T76, owner report
    2026-08-18 — his tablet held in PORTRAIT over a 16:9 monitor). Rounds 3
    and 4 derived the step from the LARGER visible fraction of the two axes
    of the settled rect: "the step may not exceed what the narrower zoom axis
    justifies". That sentence is true of a picture that FILLS the screen and
    false of one that does not: a landscape monitor on a portrait tablet is
    letterboxed — its full height stands in 675 of 1920 canvas px — so the
    height fraction reads 1.0 until the pinch passes 2.84x and stays above
    0.5 until 5.7x, and the step therefore stayed 1 through every zoom he
    ever used, while the encoded 1922x1080 was being magnified 1.25x, 1.6x,
    2x on his panel. What blur IS is one thing only: more panel pixels lit
    per encoded pixel than one. So the phone now sends, beside the rect, the
    size its picture is DRAWN at (`drawn {w, h}`, canvas = panel px — the
    measurement rounds 3/4 never asked for), and the step is the smallest
    power of two that brings the encoded picture up to that drawn size:
    ratio = drawn base size / panel size, long side to long and short to
    short — the mirror of `H264Session._scale_size`, which is what decides
    the encoded size in the first place, so the two cancel exactly (the
    binding pair there is the binding pair here). Native remains the wall
    (`_scale_size` clamps the product at 1). A PAN keeps the drawn size,
    therefore the step, therefore the session — the owner's design unchanged.

    `conn["zoom"]` is the settled monitor-normalized rect (None = the whole
    picture); `conn["zoom_drawn"]` is the drawn size that came with it. A page
    that sends no `drawn` (an older page) is decided by the old fraction rule,
    byte for byte; a connection with no `panel` caps nothing in `_scale_size`
    and so has nothing to raise. Zoomed fully out (or never zoomed) = 1."""
    drawn = conn.get("zoom_drawn")
    panel = conn.get("panel")
    region = conn.get("region")
    if region:
        r = _norm(region)
        bw, bh = max(r["w"], 1e-9), max(r["h"], 1e-9)
    else:
        bw = bh = 1.0
    if drawn and panel:
        base_w = float(drawn.get("w", 0)) * bw
        base_h = float(drawn.get("h", 0)) * bh
        pw, ph = float(panel.get("w", 0)), float(panel.get("h", 0))
        if base_w > 0 and base_h > 0 and pw > 0 and ph > 0:
            ratio = max(max(base_w, base_h) / max(pw, ph),
                        min(base_w, base_h) / min(pw, ph))
            step = 1
            while step < ZOOM_MAX_STEP and ratio > step * (1.0 + ZOOM_STEP_SLACK):
                step *= 2
            return step
    zoom = conn.get("zoom")
    if not zoom:
        return 1
    z = _norm(zoom)
    # THE OLD RULE, kept only for a page that sends no `drawn`: the LARGER
    # visible fraction decides. Wrong on a letterboxed picture (see above),
    # right on one that fills the screen; an older page gets what it had.
    frac = max(z["w"] / bw, z["h"] / bh)
    frac = min(max(frac, 1e-6), 1.0)
    step = 1
    while step * 2 <= ZOOM_MAX_STEP and step * 2.0 <= 1.0 / frac:
        step *= 2
    return step


def _drawn_of(msg: dict) -> dict | None:
    """The `drawn {w, h}` a viewport message carries — canvas px the phone
    draws the whole monitor at — or None for a page that sends none."""
    d = msg.get("drawn")
    if not isinstance(d, dict):
        return None
    try:
        w, h = float(d.get("w", 0)), float(d.get("h", 0))
    except (TypeError, ValueError):
        return None
    return {"w": w, "h": h} if w > 0 and h > 0 else None


def _drawn_moved(a: dict | None, b: dict | None) -> bool:
    """Did the drawn size change enough to be worth the wire — by more than
    the slack the step itself ignores? None vs a size is a whole change."""
    if (a is None) != (b is None):
        return True
    if a is None:
        return False
    return abs(a["w"] - b["w"]) > ZOOM_STEP_SLACK * max(b["w"], 1e-9)


def _rect_delta(a: dict | None, b: dict | None) -> float:
    """How far one rect moved from another, as the largest edge move. None vs
    a rect is a whole change (the full frame is a different picture)."""
    if (a is None) != (b is None):
        return 1.0
    if a is None:
        return 0.0
    return max(abs(a[k] - b[k]) for k in ("x", "y", "w", "h"))
