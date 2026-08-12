# Decode Caps

**Script:** [Decode Caps (script)](../decode-caps.js) ·
**Folder:** [client](../___client.md)

## Purpose

The device's own H.264 decode ceiling — the pure rules for what THIS phone or
tablet can decode smoothly, so the quality pipeline never requests a stream
the SoC cannot drink. [Quality](quality.md) owns all the wiring (probing,
persistence, the cap in `effectiveQuality()`, the toast); this module owns
only the arithmetic, kept pure so its gate can run it whole.

## Why it exists (owner report 2026-08-12 — "native 20 Mbps still sends no picture")

His server log held the whole story: at 3840×2160@30 (H.264 level 5.1) the
tablet played smoothly — `behind=0.31s` steady, `jumps=0` for two minutes —
and the moment the PC card went to 60 fps every session opened level 5.2 and
the SAME tablet threw the picture forward ten times every 15 s, seconds
behind. The encoder and the network were fine; the tablet's decoder tops out
below 4K@60, and nothing anywhere asked it. The PC cannot know what a phone
decodes; the phone can ask its own `mediaCapabilities` — so the ceiling lives
on the page, and what cannot run smoothly is lowered BEFORE it is requested,
with the cap said out loud instead of discovered as a frozen picture.

## Key Functions

- `h264Codec(w, h, fps)` — the exact MSE codec string a Main-profile stream
  of that shape carries, from the standard level table. Verified against the
  live sessions in his log (2560×1440@30 → `avc1.4D4032`, 3840×2160@30 →
  `4D4033`, @60 → `4D4034`): probing with the wrong level is a question about
  a different stream, and 5.2-vs-5.1 is precisely the boundary his tablet
  sits on.
- `stepWidth(res, baseW, monitorW)` — the width each panel resolution step
  actually encodes ("native" = the monitor, the rest scale the PC card).
- `smoothCeiling(smooth, steps)` — the highest fps a probe marked smooth; a
  device that flatters nothing still answers the floor (a slideshow beats a
  black canvas).
- `capFps(want, baseFps, ceiling)` — the request capped by the ceiling.
  `want` 0 is "follow the PC"; uncapped answers echo the request untouched so
  the wire keeps its old shape, and a missing ceiling or unknown base caps
  nothing — never invent.
- `struggleCeiling(runFps, steps)` — the runtime backstop's one-step-down
  answer, 0 at the floor.
- `combinedCeiling(probed, session)` — two opinions, the lower wins.
- `probeSmoothFps(w, h, bitrate, steps)` — the one browser-touching wrapper:
  `navigator.mediaCapabilities.decodingInfo` per step, `null` on a device
  without the API (nothing is ever capped there), and a step whose call
  throws is marked smooth — an API that errors must never lower anything.
- `devicePanel()` — this device's REAL panel pixels (CSS px x
  `devicePixelRatio`), or `null` when they cannot be read. `connection.js`
  sends it on `auth` as the NEW `panel` field.
- `panelScaledWidth(w, h, panel)` — the width a `w`x`h` crop is really
  encoded at once the panel caps it: the MIRROR of the server's
  `h264_streamer._scale_size` (long side against long side, short against
  short, never above 1, even for yuv420p). An unknown panel caps nothing.

## Design Decisions

- **Pure by design** (the [View Anchor](view-anchor.md) pattern): the gate
  `tests/test_decode_caps.py` runs the module whole in node, fail-closed in
  `setup/build.py`, with codec strings and jump counts taken from the owner's
  real log.
- **Probes only ever lower; struggle ceilings are session-only.** The spec
  sheet flatters (a decoder can accept 4K@60 on paper and drown in it), so
  the live backstop exists — but one bad evening on hotel Wi-Fi must not
  permanently dull the stream, so its verdicts die with the session and
  re-arrive within a minute wherever they were true.
- **The panel cap is a SECOND, different wall** (owner order 2026-08-12:
  "what is the point of the PC sending 4K if the Android device cannot
  receive it — a Redmi Pad is 1920x1200"). The decode ceiling is about how
  FAST the SoC turns bytes into frames; the panel is about how many pixels
  the glass can light up at all. They compose, and the SERVER applies the
  panel one — this module mirrors the arithmetic only so the decode ceiling
  judges the size that is really encoded, or a cap earned by a full 4K
  desktop would go on holding an already-downscaled stream at the capped
  fps. Gate: `tests/test_panel_scale.py`, fail-closed in build.py (0aq/6).
- **The cap is never silent** — a toast the first time each distinct decision
  acts, a line in the quality panel while it bites ([Quality](quality.md)).

## Used by

- [Quality](quality.md) — `effectiveQuality()` cap, `refreshDecodeCeilings()`
  probe, `noteDecodeStruggle()` backstop
- [Render](render.md) — feeds each live window's jump count to the backstop
- `tests/test_decode_caps.py` — the gate, fail-closed in `setup/build.py`
