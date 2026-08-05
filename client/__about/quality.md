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
rows:

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
