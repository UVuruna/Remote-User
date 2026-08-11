# quality.js — stream quality: this device's overrides of the PC's settings

Split out of `controls.js` (prefs) and `panels.js` (panel) on 2026-08-05 —
THE STRUCTURE LAW: quality is one responsibility whose two halves only make
sense together, and `controls.js` had reached the 1000-line ceiling. Loads
after `panels.js` (same global scope: it uses `prefGet`/`prefSet` and the
wheel's `keepFocus` from controls.js, `ghostClickArmor` from panels.js).

## The rule: a hierarchy, not two dials

The Remote User window on the PC sets the **base** — frame rate, encoded
width, bitrate. This panel may only go **below** it. That was already how the
server behaved, but the phone never said so: it happily showed "30 fps"
selected while a 10 fps PC ignored the choice, and the bitrate steps were
fixed numbers that threw the PC's own choice away entirely. Read as "the
desktop settings do nothing" (owner 2026-08-05).

Two fixes, one on each side:

- The server sends `config.base` — `{fps, width, height, bitrate,
  bitrate_mid, bitrate_low}` — after auth and on every stream restart
  (`_stream_base` in server/web.py).
- `h264_bitrate_mid_pct` / `h264_bitrate_low_pct` replaced the absolute
  `"5M"` / `"1200k"`: Mid and Low are now percentages of the PC's own bitrate
  (`config.bitrate_for_level`), so lowering the PC lowers all three steps.

## What the panel shows (`openQualityPanel`)

A header stating the PC's live values ("This PC is set to 10 fps · 3840×2160
· 6 Mbps — change that in the Remote User window on the PC"), then segment
rows built by `segRow` — which lived here as `qualitySegRow` until
2026-08-11, when the Phone card needed the identical control and it moved
to panels.js as the one builder both call:

| Row | Steps | Base-aware |
|-----|-------|------------|
| FPS | Max / 10 / 15 / 30 / 60 | steps ≥ the PC's fps are struck through and inert (`fpsUnreachable`, CSS `.q-seg button.out`) — the server clamps them away anyway |
| Resolution | Full / ⅔ / ½ | half PER AXIS is quarter pixels, so the middle step is ⅔ (owner) |
| Bitrate | labelled with the real Mbps the PC's choice yields | every step is reachable by construction (percentages ≤ 100 %) |

Plus "save data on mobile networks" — while `Android.transport()` reports
cellular, `effectiveQuality()` overrides the saved choices with 10 fps / ½ /
low, re-evaluated on every (re)connect (a network switch reconnects by rule).

Every tap saves and sends immediately; the server resets this client's
encoder within a second. Done just closes.

## Stored state

`qualityPrefs` in the per-device prefs bridge (`prefGet`/`prefSet` — NOT bare
localStorage, which is per-origin and split state between the LAN and
Tailscale addresses). `rawQualityPrefs()` is what is stored;
`qualityPrefs()` is that clamped against the current base, and
`setStreamBase()` rewrites a stored fps that a lowered PC has just made
impossible — a lit step that cannot happen is a lie.

## Raising the ceiling (owner decision, task 131)

The PC's card is a **default, not a wall**. Lowering is free — it happens
inside this client's own ffmpeg on the PC and touches nothing else. Raising is
not: the shared capture has to grab faster or wider, so every encoder running
off it is rebuilt and **the picture blinks once**. That is affordable only
because one device at a time is a hard rule (4409), and it is never done
silently — every raised step is marked **↑** and the panel's own subtitle says
it will blink, before he taps.

Two axes can be raised, and they are the two the PC's defaults take away:

- **FPS** — steps above the PC's rate. They used to be greyed out on the
  belief that the server would clamp them away; `fpsRaises()` replaced
  `fpsUnreachable()`, which now returns `false` for everything.
- **Resolution → "Native"** — the monitor's own width when the PC's encoder is
  set lower. This matters because task 130 lowered the shipped encoder width to
  2560 to stop starving the phone; "Native" is how he asks for his 4K monitor
  back. Greyed (not offered as a phantom upgrade) when the PC already streams
  the full monitor.
- **Bitrate cannot be raised.** Its steps are PERCENTAGES of the PC's own
  choice by the owner's 2026-08-05 rule, so there is no number above "High" to
  ask for. Stated rather than silently missing.

`raiseRequest()` puts `raise_fps` / `raise_width` on the existing `quality`
message as OPTIONAL fields (the cursor-shape pattern): a PC that predates this
ignores them and the panel simply cannot go above its card — exactly the old
behaviour. Server side: `capture.RawFrameSource.raise_limits` decides,
`H264Manager.raise_limits` rebuilds. Gate:
[`tests/test_quality_raise.py`](../../tests/___tests.md).
