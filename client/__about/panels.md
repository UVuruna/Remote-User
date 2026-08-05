# panels.js — Settings overlay panels (Sets picker + Quality)

Split out of `controls.js` on 2026-08-05 (THE STRUCTURE LAW): `controls.js`
owns the D-pad groups, the wheel and the button actions; this module owns the
full-screen card overlays those actions open. Loads right after `controls.js`
(same global scope — it uses its prefs helpers, wheel state and `keepFocus`).

## Sets picker (`openSetsPanel`)

Chooses which sets ride in the wheel on THIS phone: required built-ins are
locked on; optional shipped sets and desktop-made custom sets toggle up to
`WHEEL_MAX` total, plus the app-shortcuts toggle. Stored per device via the
prefs bridge (`prefGet`/`prefSet` in controls.js) — origin-independent, see
the bridge note there (owner bug 2026-08-05: pure localStorage split state
between the LAN and Tailscale origins, the picker "rotated").

## Quality panel (`openQualityPanel`)

Owner 2026-08-05 — replaces the old full/reduced cycler. Segment rows for
FPS (Max/10/15/30/60), resolution (Full/⅔/½ — half per axis is quarter
pixels, so the middle step is ⅔) and bitrate (High/Mid/Low), plus the
"save data on mobile networks" checkbox. Every tap saves (`qualityPrefs` in
controls.js) and sends the EFFECTIVE values to the server, which re-opens
this client's encoder; "Max/Full/High" mean "no override — the desktop
Settings defaults apply".

## Dictation setup card (`openDictationPanel`, owner round 2 2026-08-05)

The dictation language is a USER CHOICE — round-1 evidence: pinning to the
phone's first system locale transcribed the owner's Serbian as English
garbage (his phone lists English first). Opens on the FIRST Mic tap (no
choice stored, or `__voiceEnd("nolang")`) and from Settings → Language.
Rows come from `Android.voiceLangs()` (system locales + keyboard languages)
with plain-language statuses: "ready on this phone" / "model will download —
online until it arrives" / "recognized over the internet"; a radio tap calls
`Android.voiceSetLang(tag)` and re-renders (a download may have just
started). Never a transient toast — the card stays until Done/backdrop.
Round 4 (owner 2026-08-05): languages beyond the phone's own (`extra` —
downloadable models + the online service's list) sit behind a collapsed
"More languages (N)…" row (the chosen one always surfaces), and a
"Mute listening beeps" checkbox (default ON) drives
`Android.voiceSetMuteBeeps` — the round tones stay quiet while dictating.

## Ghost-click armor (all panels)

The tap that OPENS a panel can deliver a late synthetic click that lands on
whichever row opened under the finger, silently toggling it. A capture-phase
click handler swallows every click within `GHOST_CLICK_MS` of opening.
