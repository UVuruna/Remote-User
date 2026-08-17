# Cube (phone) — the spinning-cube gadget itself

[← client](../___client.md) · code: [cube.js](../cube.js)

The owner's own logo, as an independent, reusable motion — the corner-view
tilt, the idle spin speed and the momentum-burst decay that used to live
entirely inside `loading.js`.

## Why it exists

Extracted 2026-08-17 when the in-app update card (`update-banner.js`) needed
the SAME cube spinning as a small badge while an APK downloads — the owner's
explicit request, and one this monorepo's root CLAUDE.md already names
directly: priority C, "inheritance over duplication — never write the same
function twice", and `tests/test_loading_kind.py`'s own docstring had
already anticipated the move ("so the eventual move to the shared Loading
Cube gadget has the whole inventory in one grep").

## What moved, and what did not

Everything about the MOTION moved here, unchanged in value:

- `CUBE_VIEWS` — the six corner views (top → left → back → right → front →
  bottom), the owner's own face order and tilt/angle numbers.
- `CUBE_BASE_SPEED` (70 deg/s idle) and `CUBE_BURST` (300 deg per whip).
- The `requestAnimationFrame` loop's own dt-clamped integration and the
  burst-decay formula (`min(burst * 3, 720)` deg/s of extra speed, decaying
  by the same amount it grants).

Nothing about WHEN a cube spins, what stands behind it, or what a caller's
loading animation MEANS moved here — that stays entirely with the caller
(`loading.js`'s full-screen overlay, `update-banner.js`'s small badge). This
module has no opinion on the two loading kinds (constraint 16 of the root
CLAUDE.md) — it is not itself a "loading animation" in that sense, it is the
piece of art both kinds of loading animation may choose to spin.

## API

`createCube(el)` — `el` is the `.cube` element itself (the parent carrying
the six `.cube-face` children), nothing more. Returns a handle:

- `start()` — begins spinning; idempotent (calling it while already
  spinning does nothing, so a caller need not track its own boolean).
- `stop()` — cancels the animation frame loop.
- `nextFace()` — opens the cube on the next view of `CUBE_VIEWS`, in order,
  looping — "each next time from a different angle" (owner 2026-08-03).
  Resets any burst in flight.
- `whip()` — one momentum burst: the caller's own "a step happened" signal
  (one window created, one chunk of download bytes landed), decaying back
  toward the idle spin. Named `whip`, not `cubeNext` — `cubeNext` is
  `loading.js`'s OWN public name for its face advance, called from
  `connection.js`; this module must never shadow that meaning with a
  same-named export doing something else.
- `isSpinning()` — whether the internal animation frame loop is running.

Every `createCube()` call is a fully independent instance — its own view
index, angle, burst and animation-frame id — so two cubes can spin on screen
at once (the full-screen overlay and the update card's badge, mid-download)
without fighting over shared module state.

## Node / test contract

No DOM beyond the element it is handed — `el.style.transform` is the only
thing this module touches on it. A node test can pass a bare object with a
`.style = {}` and drive `start()`/`nextFace()`/`whip()` exactly like
`settle-motion.js` / `grid-icons.js` / `view-anchor.js`'s own pure-module
pattern; `module.exports` carries `createCube` plus the three constants
(`CUBE_VIEWS`, `CUBE_BASE_SPEED`, `CUBE_BURST`) for a gate that wants to pin
the numbers themselves.

## Used by

- [Loading](loading.md) — `loading.js`'s `#lay-cube`, the full-screen
  overlay's own cube (`LOADING_FULL`/`LOADING_CUBE`, constraint 16).
- [Update Banner](update-banner.md) — `update-banner.js`'s `#update-cube`,
  the small badge that spins while the APK downloads/installs. **This
  badge is not itself either of the two loading kinds** — see Loading's own
  doc for why the two-kind inventory is unaffected by its existence.
