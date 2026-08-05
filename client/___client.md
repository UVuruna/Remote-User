# client/

The phone side of Remote User — a plain web page served by the PC server, loaded inside the Android app's WebView. NO **browser** ever sees it (owner rule, hardened 2026-08-02 — tablet Chrome carries a desktop User-Agent, so "detect Android" routing leaked the client): the server serves the client only to the `RemoteUserApp` WebView marker and routes every other User-Agent to the install funnel (`install.html`). No framework, no build step.

## Files

| File | Tier | One line |
|------|------|----------|
| `index.html` | Standard | page shell — canvas, corner buttons, D-pad groups, wheel, keyboard capture — [about](__about/index.md) |
| `install.html` | Standard | install funnel (Open the app → Install) — the only page ANY browser ever sees — [about](__about/install.md) |
| `style.css` | Algorithmic | design tokens + every component's visual rules — [about](__about/style.md) · [flow](__flow/style.md) |
| `layouts.css` | Algorithmic | the layout feature's own styling (bar, list, aspect panel, creation, loading cube), split off style.css 2026-08-05 — documented with `layouts.js` in [about](__about/layouts.md) · [flow](__flow/layouts.md) |
| `load_test.js` | Standard | dev harness — concatenates and executes the 11 client scripts below, in load order, against a stubbed DOM to catch load-time errors — [about](__about/load_test.md) |
| `state.js` | Standard | tunables + shared state + `setStatus`/`toCanvasPx`/`send` — loads 1st — [about](__about/state.md) |
| `render.js` | Algorithmic | canvas drawing, view transform, dual-mode (H.264 MSE / JPEG) frame decode — loads 2nd — [about](__about/render.md) · [flow](__flow/render.md) |
| `input-geometry.js` | Algorithmic | finger→PC coordinate mapping (pointer under the finger since 2026-08-02), scroll inertia — loads 3rd — [about](__about/input-geometry.md) · [flow](__flow/input-geometry.md) |
| `icons.js` | Standard | the icon set both the phone and the desktop Controls editor draw from — loads 4th — [about](__about/icons.md) |
| `controls.js` | Algorithmic | on-screen chrome: keyboard capture, anywhere wizard, update banner, upload, D-pad groups, wheel, corner buttons, toast — loads 5th — [about](__about/controls.md) · [flow](__flow/controls.md) |
| `panels.js` | Standard | Settings overlays: Sets picker + dictation setup card (split from controls.js 2026-08-05) — loads 6th — [about](__about/panels.md) |
| `quality.js` | Standard | stream quality: this device's overrides of the PC's settings — prefs + panel, hierarchy-aware (split 2026-08-05) — loads 7th — [about](__about/quality.md) |
| `region.js` | Standard | the Region grab: a free frame the finger sizes, captured and pasted on the PC — loads 8th — [about](__about/region.md) |
| `layouts.js` | Algorithmic | layout bar, layout list, aspect-ratio panel (+ Move handle), creation flow, loading cube — loads 9th — [about](__about/layouts.md) · [flow](__flow/layouts.md) |
| `gestures.js` | Algorithmic | canvas pointer-event dispatch: pinch-zoom + font-zoom staircase + the single-finger touchMode gestures — loads 10th — [about](__about/gestures.md) · [flow](__flow/gestures.md) |
| `connection.js` | Algorithmic | WebSocket lifecycle, protocol message handlers, visibility-gated session — loads 11th (starts the page) — [about](__about/connection.md) · [flow](__flow/connection.md) |

## Connections

### Uses
- [Server (folder)](../server/___server.md) — WebSocket endpoint `/ws` (frames in, input out), `/upload` (phone → PC images), `/ping` (anywhere-wizard reachability probe)

### Used by
- [Web Layer](../server/__about/web.md) — serves `index.html` or `install.html` at `/` by User-Agent, and every file here at `/static/*` (`StaticFiles` mount)
- [Tests (folder)](../tests/___tests.md) — `test_input_pipeline.py` drives `index.html` end-to-end in real headless Chromium
- [Android (folder)](../android/___android.md) — the APK's WebView loads `index.html` (its User-Agent carries the `RemoteUserApp` marker, so it never gets the install funnel)

## Design Decisions

- **No framework, no build step** — plain HTML/CSS/JS the WebView loads
  directly; `load_test.js` is the only tooling, and it is run manually
  (`node client/load_test.js`), never a bundler step.
- **Browsers get funneled, never the client** (owner rule — no half-working
  browser sessions, hardened 2026-08-02 to ALL browsers after tablet Chrome's
  desktop User-Agent leaked the client): the server routes every User-Agent
  without the APK WebView's `RemoteUserApp` marker to
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
