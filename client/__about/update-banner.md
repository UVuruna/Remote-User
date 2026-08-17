# Update Banner

**Script:** [Update Banner (script)](../update-banner.js) ·
**Folder:** [client](../___client.md)

## Purpose

The in-app offer to install the newer APK the PC server carries
(`config.apk_version` vs. `Android.appVersion()`) — a pill under the status
that shows only inside the app (`IN_APP`), never in any browser. Split off
[Controls](controls.md) on 2026-08-10 (task 207) to keep that file under THE
STRUCTURE LAW's line ceiling; loads right after [cube.js](cube.md) and
`controls.js`, and reads `IN_APP` / `keepFocus` / `showToast` as globals.

## Rewritten 2026-08-17 — real progress, five states

The original version could only ever show an INDETERMINATE stripe: the
tapped `Android.update(url)` handed the download to Android's own
DownloadManager and returned at once, with no bridge method to ask it for
progress. That has changed — **the shell now downloads the APK itself** and
reports real bytes — so this file was rewritten around the new bridge
contract rather than patched. Nothing here invents a name beyond this list:

| Direction | Call | Meaning |
|---|---|---|
| page → shell | `Android.updateInApp(url)` | returns `true` if the shell took the job |
| page → shell | `Android.updateInstallAllowed()` | boolean — can Android install right now |
| page → shell | `Android.updateAllowInstall()` | opens the OS "allow installs" screen |
| shell → page | `window.__updateProgress(received, total)` | bytes; `total <= 0` = unknown length |
| shell → page | `window.__updateState(state, detail)` | `state` ∈ `permission`/`downloading`/`installing`/`failed` |

**There is no "success" state, anywhere, on purpose.** A successful install
replaces this app's own running process — Android tears it down to install
the new APK over it — so the one outcome the user actually wants can
structurally never be reported back to this page. `installing` is the last
state this file can ever render for a run that goes well; the app simply
reopens on its own, same as any other Android app's self-update.

## The five card states

1. **offer** — unchanged trigger logic (`isNewer`/`versionNumbers`/
   `refreshUpdateBanner`, including the `apk_version` comparison and its
   2026-08-02 phantom-update comment). Tap starts the update.
2. **permission** — Android needs a one-time OK to install packages from
   this PC. The tap opens `Android.updateAllowInstall()`'s OS screen and
   does **not** advance the card itself — the owner's own requirement was
   that guidance continues automatically when he returns, and the shell
   re-checks on resume and sends the next real `__updateState`. A second tap
   before that arrives just reopens the same OS screen, harmlessly.
3. **downloading** — the cube badge (`cube.js`, `#update-cube`) spins;
   `__updateProgress` drives a real determinate fill + percentage once
   `total > 0`, and gives the cube a momentum burst (`whip()`) on every
   tick — the SAME burst system `loading.js`'s `cubeNext()` uses for one
   window per creation step, here one whip per progress tick. `total <= 0`
   (no `Content-Length`) keeps the fill INDETERMINATE and never prints a
   percentage it does not have.
4. **installing** — the cube keeps spinning; the text says Android is
   installing and will reopen the app. No promise of a timeline or a
   completion this page cannot know.
5. **failed** — `detail`'s reason sentence (falling back to a generic one if
   absent/blank); the card becomes tappable again, exactly like "offer".

## The fallback (an older shell)

`Android.updateInApp` may be `undefined` — the shell is installed
separately from this page, so an older install simply lacks the method.
When it is missing, the tap behaves **exactly as before this round**:
`Android.update(url)` hands off to DownloadManager, and the card shows the
original indeterminate stripe plus "check the notification shade, then open
the file". This is not a degraded mode to be improved later — it is the
correct, honest behaviour for a shell this page cannot ask for progress.

## Nothing may overlap anything (constraint 35)

The card sat at a FIXED `calc(topbar + 44px)` before this round — an
assumption that the status pill is always exactly one line and that the
window-offer chip is never showing at the same time. Neither is guaranteed
(a toast can wrap the pill to two lines; the chip stands for up to 30 s, see
[Window Offer](window-offer.md)'s `WINDOW_OFFER_MS`), so the card's own top
is now MEASURED: `syncUpdateBannerTop()` reads the real `getBoundingClientRect()`
of `#status` and `#window-offer` (whichever is visible and taller/lower) and
writes `--update-top`, exactly the same "measured, never a constant"
discipline `window-offer.js`'s own `syncToastShift()` already applies to the
status pill. A `ResizeObserver` on both elements — rather than a list of
call sites to keep in step — is what recomputes it on every real change
(new toast text, chip shown/hidden, rotation), because a call-site list is
exactly the class of bug this monorepo keeps meeting (a whitelist that never
learned the new field).

## The cube badge (constraint 16, and why it does NOT confuse the inventory)

`#update-banner-cube` reuses [Loading](loading.md)'s own `.cube-scene` /
`.cube` / `.cube-face` / `cf-*` markup and colours — the owner's logo is
drawn once — and is shrunk to badge size purely through CSS (`--cube-scale:
0.2` on the shared `cube-bob` keyframe, absolutely positioned and recentred
with a negative half-box margin, since the scene's own layout footprint
stays a fixed 110px regardless of how small the paint is scaled). Its motion
comes from its own `createCube()` handle (`cube.js`), independent of
`loading.js`'s `#lay-cube` instance. **This badge is not a third loading
kind.** It never calls `showLayLoading`, is not `#lay-loading`, and is
correctly invisible to `tests/test_loading_kind.py`'s sweep — see
[Loading](loading.md)'s own note on this, written the same round so a later
reader who greps for "the cube" in two files does not conclude the
two-kind classification broke.

## Grading round 2026-08-17 — the first photograph found five real defects

The card was staged in the phone audit for the first time and graded by
hand; the picture (`downloading`, `__updateProgress(100, 100)`) disagreed
with code that read correctly. Fixed, all in `client/`:

1. **The reload icon stayed visible beside the spinning cube — TWICE.**
   Round one added `#update-banner-icon[hidden]{display:none}` in
   `update-banner.css`, reasoning every OTHER toggled child already carried
   the same rule. It changed nothing, and the re-audit caught it doing
   nothing: `#update-banner-icon` is an inline `<svg>` — an SVGElement, not
   an HTMLElement — and `hidden` is an IDL property of HTMLElement only.
   `updateBannerIcon.hidden = spinning` therefore set a plain expando
   property on the JS object and never wrote the `hidden` ATTRIBUTE the
   `[hidden]` selector matches; the CSS rule was correct and had nothing to
   select. Fixed at the root with `setHiddenAttr(el, hidden)`
   (`update-banner.js`), which reaches the real attribute via
   `setAttribute`/`removeAttribute` regardless of which element interface
   owns the convenience property — used at both sites that touch this
   element (`setUpdateCardState` and the fallback tap handler). Swept the
   rest of `client/` for the same shape (every `.hidden =` assignment,
   traced back to its element's actual tag): `#lay-icon` (`layouts.js`) is a
   genuine `<img>`; every panel/bar/button this page toggles this way is a
   `<div>`, `<button>` or `<a>` — real HTMLElements where `.hidden` is
   correct. `#update-banner-icon` was the only inline `<svg>` with an `id`
   this page toggles visibility on at all.
2. **The fill disagreed with its own label for 200ms on every jump.**
   `__updateProgress(100, 100)` correctly showed "100%" while the CSS
   transition caught the fill mid-slide at roughly half the track — the
   same shape of bug constraint 35 already ruled on for the status pill's
   slide (INSTANT, never merely fast). `setDeterminateFill()`
   (`update-banner.js`) now decides PER TICK: a jump past
   `UPDATE_PCT_JUMP_THRESHOLD` (8 points), or the first tick of a fresh
   "downloading" (`updateLastPct === null`), gets a one-write
   `.no-transition` class that lands the width in the same frame as the
   number; an ordinary small real-download tick keeps the 200ms slide.
3. **The cube crowded the text and sat off the text's line — fixed in TWO
   passes, the first one wrong.** The badge wrapper grew 22px -> 30px (real
   air around the ~22px painted cube) with its own `margin-right` on top of
   the row's gap — that part held. The first pass ALSO hand-tuned the
   cube's centring offset down (`margin: -40px 0 0 -55px`, was `-55px 0 0
   -55px`) to compensate for the idle tilt (`rotateX(-28deg)`) reading as
   "sits above the text" — and a second photograph caught it badly
   overshot: ~43px of empty space above the cube, ~5px below, its bottom
   nearly riding the card's rounded border. The arithmetic behind the
   nudge was wrong (a margin change here moves the visual centre by the
   SAME number of real pixels, not that number divided by `--cube-scale` —
   scaling a box shrinks it around a FIXED point, it does not move that
   point), and the fix was the wrong KIND regardless: a constant tuned
   against "downloading"'s two-row content block cannot also fit
   "installing"'s one-row block, because the two states share no content
   height. Reverted to the mathematically exact box-centre (`-55px 0 0
   -55px` on both axes) and delegated the actual centring against the
   content block to `#update-banner`'s own `align-items: center` — it
   centres the 30px cube wrapper against whichever sibling is tallest
   (`#update-banner-body`) automatically, in BOTH states, with no constant
   to go stale when either state's content height changes. See the long
   comment on `#update-banner-cube .cube-scene` in `update-banner.css`,
   which exists specifically so nobody reintroduces the hand-tuned offset.
4. **The card wasted its own width.** `#update-banner-body` now grows
   (`flex:1 1 auto`) instead of shrink-wrapping, the bar takes the real
   remaining width (`flex:1 1 auto`, was a fixed 140px), and the percentage
   moved INTO a shared row with the bar (`#update-banner-progress`, new
   markup in `index.html`) instead of sitting as a separate flex child of
   the whole button, hanging far from the number it names.
5. **The audit's truncation tooth read the ellipsis as a cut string.**
   "Downloading the update…" is a complete sentence — `#update-banner-text`
   now carries `data-in-progress`, the same declaration `loading.js`'s own
   `#lay-loading` span already uses for the identical reason, present at
   all times (a standing declaration about what the element may show, inert
   during the states whose text carries no ellipsis).

**`client/update-banner.css` is new** — the card's rules split off
`style.css` the same round (THE STRUCTURE LAW: fixes 2–4 above pushed it
past 1,000 lines), following the `window-offer.js` + `window-offer.css`
pairing already in this codebase. Loaded after `layouts.css` (the cube
badge reuses its `.cube-scene`/`cube-bob` keyframe) and after `style.css`.

## Used by

- `client/connection.js` — calls `refreshUpdateBanner(msg.apk_version ||
  msg.app_version)` from the `config` message handler.
- `window.__updateProgress` / `window.__updateState` — called by the
  Android shell, not by any script on this page.
