# Appearance Panel

**Script:** [Appearance Panel (script)](../appearance-panel.js)

## Purpose
Settings → **Look**: how THIS device looks — theme, whether the controls wear each set's colour, and whether they are outlined or filled.

## Why it exists
Owner ballot, 2026-08-12, approved: *"appearance is also per device, not global, so it belongs on the phone / tablet."*

The three axes lived in the PC's Settings window and rode the `config` frame to every handset. That was the 2026-08-07 answer to P4 — one source of truth, no menu on the phone — and it was right that there must be ONE answer and wrong about where it lives: he uses a tablet AND a phone, held at different distances in different light, and one desktop dropdown could only ever describe one of them. Two devices could not look different, which is exactly what he asked for.

The PC's values are now the DEFAULT. Nothing on the wire changed — `config.ui` still carries all three — and a handset that never opens this card wears them byte for byte.

## Connections

### Uses
- [Theme](theme.md) — `uiLook()`, `uiFollowsPc()`, `uiPcValue()`, `setUiAxis()`, `clearUiAxis()`. Every rule about what a stored choice DOES lives there; this file only asks the question
- [Panels](panels.md) — `segRow` (the shared segmented row) and `ghostClickArmor`
- [Controls](controls.md) — the `prefGet`/`prefSet` bridge underneath `theme.js`
- [Row tap](row-tap.md) — since 2026-08-15 every row of every list here, and every control inside the scrolling card, uses `keepRowTap` instead of `keepFocus`, so a finger landing on one can still scroll

### Used by
- [Panels](panels.md) — `PANEL_KINDS.appearance`, opened by the `appearance` action of the Settings set (`actions.json`)

## The three rows
| Row | Steps | Axis |
|-----|-------|------|
| Theme | PC (…) · Dark · Light | `theme` |
| Controls | PC (…) · Coloured · Plain | `colored` |
| Buttons | PC (…) · Outlined · Filled | `fill` |

## Every row offers the PC back
The first step of each row is **PC (…)**, and the brackets NAME what the PC is currently set to.

Two reasons, and the second is the one that matters. A per-device override with no way home is a trap: he would have to remember what the PC said and re-pick it by hand — and he would then be PINNED to that value instead of following the PC again. Choosing PC deletes the axis from this device's store, so it resumes following the desktop for as long as he leaves it alone. Naming the value in the label is what makes that step a decision rather than a gamble.

## Storage
Through the shell's SharedPreferences bridge (`prefGet`/`prefSet`), under `uiChoice`, holding **only the axes actually chosen** — see [Theme](theme.md) for why a partial store is the feature and not an optimisation. Never bare `localStorage`: that is keyed by ORIGIN and the shell alternates between the LAN and Tailscale addresses, which is how the sets picker came to "rotate" between two states on 2026-08-05.

## Gate
`tests/test_appearance_device.py`, fail-closed in `setup/gates.py` (0as/6). It runs the real `client/theme.js` in node, one fresh module per simulated device, and reads the attributes the page actually writes onto `<body>` — because the promise he will judge is a rendering one, and a check on a stored preference proves nothing about it.
