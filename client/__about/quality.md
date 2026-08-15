# quality.js — stream quality: this device's overrides of the PC's settings

Split out of `controls.js` (prefs) and `panels.js` (panel) on 2026-08-05 —
THE STRUCTURE LAW: quality is one responsibility whose two halves only make
sense together, and `controls.js` had reached the 1000-line ceiling. Loads
after `panels.js` (same global scope: it uses `prefGet`/`prefSet` and the
wheel's `keepFocus` from controls.js, [`keepRowTap`](row-tap.md) for anything
inside the scrolling card, `ghostClickArmor` from panels.js).

## The rule: a hierarchy, not two dials

The Vibe Coder window on the PC sets the **base** — frame rate, encoded
width, bitrate. This panel may only go **below** it. That was already how the
server behaved, but the phone never said so: it happily showed "30 fps"
selected while a 10 fps PC ignored the choice, and the bitrate steps were
fixed numbers that threw the PC's own choice away entirely. Read as "the
desktop settings do nothing" (owner 2026-08-05).

Two fixes, one on each side:

- The server sends `config.base` — `{fps, width, height, bitrate, level,
  bitrate_mid, bitrate_low}` — after auth and on every stream restart
  (`config.stream_base`). `level` is the ladder rung the PC is on.
- The bitrate steps are **the owner's four levels as ABSOLUTE numbers**
  (`QUALITY_LEVELS`, his ticked verdict 2026-08-12) — Max 20 / Smooth 12 /
  Sharp 6 / Data saver 2 Mbps, the same four the desktop STREAM card offers.
  This phone may pick any rung **at or below** the PC's; rungs above it are
  greyed out rather than clamped in silence.

`QUALITY_LEVELS` is a MIRROR of `config.QUALITY_LADDER` and is gated as one:
`tests/test_stream_card.py` parses this literal out of the real page source
and compares it rung for rung with the server's table, so a rung retuned on
one side alone fails the build. It is written JSON-shaped for that reason.

**The percentages are gone.** `h264_bitrate_mid_pct` / `_low_pct` made Mid
and Low fractions of the PC's bitrate; that rule was written into the record
as the owner's decision of 2026-08-05 and it was never his (his correction,
2026-08-12). What it cost: the desktop's Data saver step and this panel's own
cellular level stopped agreeing whenever the base moved, which got documented
as unavoidable instead of fixed. As absolute rungs they are the same numbers
by construction. A saved pref still saying `"mid"`/`"low"` is TRANSLATED onto
a rung (`LEGACY_BR`), never dropped to a default he never picked; `"high"`
survives as the **follow-the-PC** sentinel, which is what keeps a reconnect's
restatement comparing equal.

## What the panel shows (`openQualityPanel`)

A header stating the PC's live values ("This PC is set to 10 fps · 3840×2160
· 6 Mbps — change that in the Vibe Coder window on the PC"), then segment
rows built by `segRow` — which lived here as `qualitySegRow` until
2026-08-11, when the Phone card needed the identical control and it moved
to panels.js as the one builder both call:

| Row | Steps | Base-aware |
|-----|-------|------------|
| FPS | Max / 10 / 15 / 30 / 60 | steps above the PC's rate wear **↑** (raises, task 131); the device's own decode ceiling caps what is actually requested (below) |
| Resolution | Native / Full / ⅔ / ½ | **Full** = the width the PC's own card encodes (`h264_max_width`); **Native** = the monitor's real pixels — a raise (↑) when the card is set lower, greyed when they are the same picture; ⅔ and ½ scale Full; half PER AXIS is quarter pixels, so the middle step is ⅔ (owner) |
| Quality | Max · 20 Mbps / Smooth · 12 / Sharp · 6 / Data saver · 2 | the four absolute levels; rungs above the PC's own (`pcLevel()`) are greyed out. Picking the PC's own rung saves the `"high"` follow-the-PC sentinel, so a PC that later moves takes this phone with it instead of pinning it to a number he never chose |

Plus "save data on mobile networks" — while `Android.transport()` reports
cellular, `effectiveQuality()` overrides the saved choices with
`dataSaverQuality()`, re-evaluated on every (re)connect (a network switch
reconnects by rule). That function is DERIVED from the ladder's bottom rung
rather than typed out, so it is `config.DATA_SAVER` exactly — 10 fps, ½
resolution, the 2 Mbps Data saver level — and moving the bottom rung moves
the cellular profile with it. Gated in `tests/test_stream_card.py`.

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

## The device's decoder ceiling (owner report 2026-08-12)

"Native 20 Mbps still sends no picture" was the tablet drowning in 4K@60: his
log shows 3840×2160@30 playing smoothly (jumps=0) and the same device throwing
the picture forward ten times every 15 s the moment the PC card went to 60 fps
— H.264 level 5.2 is past what that SoC decodes in real time. The PC cannot
know a phone's decoder; the phone asks its own `mediaCapabilities`. The rules
live in the pure module `client/decode-caps.js` (gate:
`tests/test_decode_caps.py`, fail-closed in build.py); the wiring here:

- `refreshDecodeCeilings()` (called by connection.js on every h264 `config`)
  probes each resolution step's width with the exact codec string that stream
  would carry, keeps the highest SMOOTH fps per width, and persists it
  per-device (probes only ever LOWER a stored ceiling).
- `effectiveQuality()` caps the requested fps at the ceiling for the chosen
  width — lowering is per-client and free, and a capped stream that plays
  beats an uncapped one that freezes. The cap is SAID: a toast on the first
  send it changes, and a line in the panel while it bites.
- `noteDecodeStruggle()` is the runtime backstop, fed by render.js with each
  15 s live window's jump count: two drowning windows in a row lower this
  SESSION's ceiling one step — spec sheets flatter, the live pipeline does not.
- `effectiveWidth()` is REGION- and PANEL-aware: the step's width narrowed
  by `stream_region` and then run through `panelScaledWidth` — the ceiling
  must judge the width the server really encodes (owner order 2026-08-12,
  the panel cap; see [Decode Caps](decode-caps.md)).

`raiseRequest()` puts `raise_fps` / `raise_width` on the existing `quality`
message as OPTIONAL fields (the cursor-shape pattern): a PC that predates this
ignores them and the panel simply cannot go above its card — exactly the old
behaviour. Server side: `capture.RawFrameSource.raise_limits` decides,
`H264Manager.raise_limits` rebuilds. Gate:
[`tests/test_quality_raise.py`](../../tests/___tests.md).
