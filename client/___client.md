# client/

The phone side of Vibe Coder — a plain web page served by the PC server, loaded inside the Android app's WebView. NO **browser** ever sees it (owner rule, hardened 2026-08-02 — tablet Chrome carries a desktop User-Agent, so "detect Android" routing leaked the client): the server serves the client only to the `VibeCoderApp` WebView marker and routes every other User-Agent to the install funnel (`install.html`). No framework, no build step.

## Files

| File | Tier | One line |
|------|------|----------|
| `index.html` | Standard | page shell — canvas, corner buttons, D-pad groups, wheel, keyboard capture — [about](__about/index.md) |
| `install.html` | Standard | install funnel (Open the app → Install) — the only page ANY browser ever sees — [about](__about/install.md) |
| `theme.css` | Algorithmic | EVERY colour, in four themes (dark / light / colored / colored-light) and two fills (outlined / filled) — loaded FIRST, documented with `theme.js` in [about](__about/theme.md) · [flow](__flow/theme.md) |
| `style.css` | Algorithmic | every component's visual rules — shape and position only; it reads theme.css's tokens and names no colour of its own — [about](__about/style.md) · [flow](__flow/style.md) |
| `panels.css` | Standard | the OVERLAY CARDS — the Sets picker, Quality panel, dictation card, notices card and command chooser, plus the `.sets-card` / `.sets-row` vocabulary they share; split off style.css 2026-08-09 (the dictation card's listen control crossed 1,000 lines) — documented with `panels.js` in [about](__about/panels.md) |
| `clipboard.js` | Standard | the phone's half of the shared clipboard — `clipboard {text}` frames land in the device clipboard via `Android.setClipboard`, browser fallback silently swallowed (task 182) — [about](__about/clipboard.md) |
| `set-editor.css` | Standard | the set editor's own two surfaces — the arrangement preview (the live D-pad's own grid areas) and the edit door on a picker row; everything else is `panels.css`'s `.sets-*` vocabulary — [about](__about/set-editor.md) |
| `layouts.css` | Algorithmic | the layout feature's own styling (bar, list, aspect panel, creation, loading cube), split off style.css 2026-08-05 — documented with `layouts.js` in [about](__about/layouts.md) · [flow](__flow/layouts.md) |
| `layout-create.css` | Algorithmic | the CREATION panel's rows — a tab drawn INDENTED under its window in both lists, the dim an unavailable control wears, `touch-action` put back so the list still scrolls (owner 2026-08-09, task 168); loads after `layouts.css` and reuses its `.lay-item` rows — documented with `layout-create.js` in [about](__about/layout-create.md) · [flow](__flow/layout-create.md) |
| `load_test.js` | Standard | dev harness — concatenates and executes every client script below, in load order, against a stubbed DOM to catch load-time errors — [about](__about/load_test.md) |
| `state.js` | Standard | tunables + shared state + `setStatus`/`toCanvasPx`/`send` — loads 1st — [about](__about/state.md) |
| `render.js` | Algorithmic | canvas drawing, view transform, dual-mode (H.264 MSE / JPEG) frame decode — loads 2nd — [about](__about/render.md) · [flow](__flow/render.md) |
| `input-geometry.js` | Algorithmic | finger→PC coordinate mapping (pointer under the finger since 2026-08-02), scroll inertia — loads 3rd — [about](__about/input-geometry.md) · [flow](__flow/input-geometry.md) |
| `icons.js` | Standard | the icon set both the phone and the desktop Controls editor draw from — loads 4th — [about](__about/icons.md) |
| `grid-icons.js` | Standard | WHAT SHAPE a layout is — the drawn silhouette per (member count, arrangement, orientation), his sheet exactly: 6 grids + solo, 14 with the orientations (owner request 2026-08-09 — a row of the list said nothing about its shape). PURE, so its gate runs it whole and compares every partition to `server/grids.py`; loads before `grids.js`, which delegates to it — [about](__about/grid-icons.md) |
| `grids.js` | Algorithmic | the grid catalogue as the phone OFFERS it — which shapes exist, and the panel that asks which of a three's four arrangements to use; the drawings themselves moved to `grid-icons.js` on 2026-08-09 (split from layouts.js 2026-08-07) — [about](__about/grids.md) · [flow](__flow/grids.md) |
| `settle-motion.js` | Standard | the settle watcher's MOTION metric — fraction of pixels changed vs. a threshold, not a whole-frame mean (owner report 2026-08-11, task 194: "traje predugo ... radi kontra uslugu" — the old mean let his agents' ongoing typing hold the overlay up for the whole watch window). PURE, so its gate runs it whole; loads before `loading.js`, which uses it — [about](__about/settle-motion.md) |
| `loading.js` | Algorithmic | the loading cube and the SETTLE watcher — the animation lasts as long as the WORK does, never until the server merely answers (split from layouts.js 2026-08-07; its motion metric moved to `settle-motion.js` 2026-08-11) — [about](__about/loading.md) · [flow](__flow/loading.md) |
| `sets.js` | Algorithmic | which sets ride the wheel: per-device prefs, app-aware matching by the owner's per-layout ticks, THE CAP OF 8 (split from controls.js 2026-08-06) — loads 5th — [about](__about/sets.md) · [flow](__flow/sets.md) |
| `voice.js` | Algorithmic | the dictation TEXT rules: type as he speaks (the settle rule) + never type a re-heard tail twice (the round-boundary trim); PURE, so its gate runs it whole (split from controls.js 2026-08-08) — loads 6th — [about](__about/voice.md) · [flow](__flow/voice.md) |
| `caret.js` | Algorithmic | HOW FAR the picture rises for the soft keyboard — only if the typing caret would be covered, and only by the shortfall; only the PICTURE moves, never the letterbox filler (owner 2026-08-07). PURE, so its gate runs it whole — [about](__about/caret.md) · [flow](__flow/caret.md) |
| `cursor-shapes.js` | Standard | WHAT the PC's cursor looks like — the drawn silhouette per name the server sends (owner request 2026-08-09: a resize cursor at a window edge is how he knows the edge is grabbable). PURE, so its gate runs it whole; loads before `render.js`, which draws it — [about](__about/cursor-shapes.md) |
| `hold-gesture.js` | Standard | WHEN a press is a hold, a drag or a tap — the layout list's row drag arms on a finger that STAYED PUT, not one that never moved a pixel (owner report 2026-08-09, task 162: a resting finger on a digitizer wanders, so the old zero-tolerance test never let a hold arm). PURE, so its gate drives it with a real jitter sequence; loads before `layouts.js` — [about](__about/hold-gesture.md) |
| `view-anchor.js` | Standard | WHERE the letterboxed picture sits — the fit-and-anchor math the layout's `pos` drives (owner decree 2026-08-09: the position lives on the PHONE, the server always centres the windows). PURE, so its gate runs it whole; loads before `render.js`, which runs it — [about](__about/view-anchor.md) |
| `decode-caps.js` | Standard | WHAT this device's decoder can drink — the H.264 level table, smooth-fps ceiling and cap rules that keep the phone from requesting a stream it cannot decode (owner report 2026-08-12: 4K@60 drowned the tablet and read as "no picture"). PURE, so its gate runs it whole; loads before `quality.js`, which wires it — [about](__about/decode-caps.md) |
| `live-clock.js` | Algorithmic | the live-edge truth table + slow-before-flush playbackRate regulator that recovers a starved H.264 player without ever flushing the decoder more than once per 4s (task 151, 2026-08-10 — "the picture never goes blank, and when it stops it starts again by itself"), plus `liveHoldFrame` — the never-blank guard's own truth table (2026-08-11, his blue flashes while dictating: a catch-up seek raises `seeking` while readyState still claims a frame, so the old readyState-only guard cleared the canvas and drew nothing). PURE, so its gate drives it whole against a realistic drift ramp; loads before `render.js`, which runs it — [about](__about/live-clock.md) · [flow](__flow/live-clock.md) |
| `controls.js` | Algorithmic | on-screen chrome: keyboard capture, anywhere wizard, upload, D-pad groups, wheel, corner buttons, toast — loads 7th — [about](__about/controls.md) · [flow](__flow/controls.md) |
| `update-banner.js` | Standard | the in-app APK update offer — version compare, show/hide, and the tap that swaps the banner into an honest INDETERMINATE bar (owner decree 2026-08-10, task 207: "ne znam da li je blokirao ili radi" — the download runs in Android's own DownloadManager, so this page can never see real bytes); split off `controls.js` the round it crossed 1,000 lines — loads right after it — [about](__about/update-banner.md) |
| `window-offer.js` + `window-offer.css` | Standard | the two-button chip that asks where a window which just opened on the PC should go — **Show in layout** / **Leave on desktop** — and POSTs his answer back to `/window_offer`; ignoring it is an answer, and the answer is the desktop (owner amendment to task 202, 2026-08-11) — [about](__about/window-offer.md) |
| `chrome.js` | Algorithmic | our own FURNITURE — the Hide button, the auto-hide rule (3 s, only on the bare working screen) and the toast; split off `controls.js` 2026-08-08 — nothing here drives the PC — [about](__about/chrome.md) · [flow](__flow/chrome.md) |
| `wheel.js` | Standard | the CATEGORY WHEEL — the ring a group's dashed centre button opens, its pick, and the layout that follows the screen through a rotation; split off `controls.js` 2026-08-13 — [about](__about/wheel.md) |
| `theme.js` | Algorithmic | which theme/fill are in force (the DESKTOP decides — no menu on the phone), the colour each set wears, and the ink COMPUTED from that colour's luminance — loads 8th — [about](__about/theme.md) · [flow](__flow/theme.md) |
| `panels.js` | Standard | Settings overlays: Sets picker + dictation setup card (split from controls.js 2026-08-05) — loads 9th — [about](__about/panels.md) |
| `quality.js` | Standard | stream quality: this device's overrides of the PC's settings — prefs + panel, hierarchy-aware (split 2026-08-05) — loads 10th — [about](__about/quality.md) |
| `claude-state.js` | Algorithmic | what the phone may CLAIM about the PC's Claude Code — the official five models with their capability stars, the five `/effort` levels, the Shift+Tab mode ring, and the rule that a SAVED fact, a LIVE fact and this phone's own MEMORY never wear each other's clothes (owner ballot verdict 2026-08-11, tasks 190/191/208 — he read a "Medium" chip as the PC's live state while it ran on Max). PURE, so its gate runs it whole; loads early, read by `claude-panels.js` — [about](__about/claude-state.md) · [flow](__flow/claude-state.md) |
| `claude-panels.js` | Standard | the three cards those rules dress — Model, Thinking and Mode — each asking the PC for `claude_state` on open and each fully honest without an answer (an older PC never sends one); Mode's presses ride the ordinary `chord` path, which the server's focus guard already fences — loads after `quality.js` — [about](__about/claude-panels.md) |
| `phone-panel.js` | Standard | Settings → Phone: the per-device switches gathered into the card they belong to — layout bar Top/Bottom, what Hide means, the D-pad shape per orientation (owner tasks 161 + 218a, 2026-08-11; each MOVED out of a card named for another subject, never copied) — [about](__about/phone-panel.md) |
| `set-editor.js` | Standard | Settings → Wheel sets → ONE set: which pool commands ride the controls and in which slot — the same job the desktop Controls editor does, saved through the PC (`actions_update`) into the SAME actions.json (owner 2026-08-04, task 218b) — loads after `phone-panel.js` — [about](__about/set-editor.md) |
| `region.js` | Standard | the Region grab: a free frame the finger sizes, captured and pasted on the PC — loads 11th — [about](__about/region.md) |
| `notify.js` | Standard | the PC's notices: Android notification + speech + toast, named per agent — loads 12th — [about](__about/notify.md) |
| `layouts.js` | Algorithmic | LIVING with the layouts that exist — bar, list (+ its drag), the ✕ chooser, the member chooser — loads 13th — [about](__about/layouts.md) · [flow](__flow/layouts.md) |
| `layout-settings.js` | Standard | CHANGING one — the per-layout ⚙ sheet and the panels behind it (rename, aspect ratio + Move handle, orientation, arrangement); split off `layouts.js` 2026-08-09 (owner task 175: one common settings icon instead of one icon per act, and a portrait list graded 6/10 for the crowding) — loads 14th, reading `HOLD_DRAG_SLOP` at load — [about](__about/layout-settings.md) |
| `layout-create.js` | Algorithmic | MAKING one — source chooser, armed tap, slot panel; split off `layouts.js` 2026-08-08 (task 116 crossed 1,000 lines) — loads 15th — [about](__about/layout-create.md) · [flow](__flow/layout-create.md) |
| `gamepad.js` | Algorithmic | the Bluetooth game controller mapped onto the controls that already exist — every pad press goes through the FINGER's activator (`buttonPress`), plus the stick curve and the held-and-pointed wheel — loads 14th — [about](__about/gamepad.md) · [flow](__flow/gamepad.md) |
| `gestures.js` | Algorithmic | canvas pointer-event dispatch: pinch-zoom + font-zoom staircase + the single-finger touchMode gestures — loads 15th — [about](__about/gestures.md) · [flow](__flow/gestures.md) |
| `connection.js` | Algorithmic | WebSocket lifecycle, protocol message handlers, visibility-gated session — loads 16th (starts the page) — [about](__about/connection.md) · [flow](__flow/connection.md) |

## Connections

### Uses
- [Server (folder)](../server/___server.md) — WebSocket endpoint `/ws` (frames in, input out), `/upload` (phone → PC images), `/ping` (anywhere-wizard reachability probe)

### Used by
- [Web Layer](../server/__about/web.md) — serves `index.html` or `install.html` at `/` by User-Agent, and every file here at `/static/*` (`StaticFiles` mount)
- [Tests (folder)](../tests/___tests.md) — `test_input_pipeline.py` drives `index.html` end-to-end in real headless Chromium
- [Android (folder)](../android/___android.md) — the APK's WebView loads `index.html` (its User-Agent carries the `VibeCoderApp` marker, so it never gets the install funnel)

## Design Decisions

- **No framework, no build step** — plain HTML/CSS/JS the WebView loads
  directly; `load_test.js` is the only tooling, and it is run manually
  (`node client/load_test.js`), never a bundler step.
- **Browsers get funneled, never the client** (owner rule — no half-working
  browser sessions, hardened 2026-08-02 to ALL browsers after tablet Chrome's
  desktop User-Agent leaked the client): the server routes every User-Agent
  without the APK WebView's `VibeCoderApp` marker to
  [Install Funnel](__about/install.md); only the WebView reaches
  [Page Shell](__about/index.md). Dev exception: with no APK built the funnel
  has nothing to offer, so a dev checkout still serves the client. See
  [Web Layer](../server/__about/web.md) for the routing logic.
- **`install.html` is self-contained on purpose** — its own inline
  `<style>`/`<script>`, no dependency on `style.css` or any of the client
  scripts: the one page an app-less phone can reach must never break because
  of a mismatch elsewhere in the client.
- **File-specific behavior is documented with its file, not duplicated here**
  — the gesture model (finger steers, buttons act), the cursor's fixed
  handedness diagonal, letterbox-aware coordinate mapping, the pointerup +
  pointercancel button rescue (locked in by [Tests (folder)](../tests/___tests.md)),
  ghost-pointer self-heal, H.264/JPEG rendering, virtual-cursor drawing,
  region streaming, the visibility-gated session, and the guided "anywhere
  access" wizard were all one `app.js` file (1,174 lines) — split (god-file
  refactor, THE STRUCTURE LAW) into the `state.js`/`render.js`/
  `input-geometry.js`/`controls.js`/`gestures.js`/`connection.js` files above,
  each documented individually; `layouts.js` split off `controls.js` the same
  way on 2026-08-03 when the layout feature (bar, list, aspect panel,
  creation, loading cube) pushed it past 1,000 lines. Visual-only decisions (see-through buttons,
  the `--kb`/`--vtop` viewport variables) are in [Style](__about/style.md).
- **The 7 client scripts share ONE global scope, on purpose** — classic
  (non-module) `<script>` tags loaded in the exact order `index.html` lists
  them, which is semantically identical to one concatenated file. This
  preserves `app.js`'s original behavior with zero change while splitting it
  into cohesive, independently readable modules; the order is load-bearing
  (`controls.js` calls `keepFocus` before its own definition, relying on
  function hoisting scoped to that one file — see
  [Controls](__about/controls.md)). `load_test.js` must be kept in sync with
  `index.html`'s script order — both list the same 7 files.
- **One CSS inconsistency noticed while documenting, flagged not fixed:**
  `body.hidden-controls` hides most of the chrome in one grouped block at the
  end of `style.css`, but `#update-banner`'s own `body.hidden-controls`
  rule is declared next to its component block instead — see
  [Style (flow)](__flow/style.md) for exactly where. Harmless today (both
  rules fire), but a future edit to the grouped block alone would miss it.
