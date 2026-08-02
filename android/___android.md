# android/

The Android app — a **native shell around the existing web client** (ROADMAP
Phase D). The page carries ALL product UI and guidance; the shell adds only
what a browser tab cannot. One wizard, one client, two containers.

Kotlin, two activities, two dependencies (AppCompat + the embedded ZXing
scanner). Package `com.uvuruna.remoteuser`, min Android 8 (API 26).

## Files

| File | Tier | One line |
|------|------|----------|
| `MainActivity.kt` | Algorithmic | WebView shell — dual-address resolve/failover state machine, self-healing error card, network callbacks, JS bridge, immersive UI — [about](__about/MainActivity.md) · [flow](__flow/MainActivity.md) |
| `OnboardingActivity.kt` | Standard | first-run pairing screen — automatic funnel handoff + manual QR-scan/paste fallback — [about](__about/OnboardingActivity.md) |
| `Prefs.kt` | Trivial | `SharedPreferences` wrapper for the two stored addresses (LAN URL from pairing, Tailscale URL learned from the page) |

**Other files in this folder (not source-tier — resources and build config):**
- `app/src/main/res/` — dark brand theme (same slate/cyan palette as the
  client and desktop), layouts (`activity_main.xml`: WebView + loading/error
  overlays; `activity_onboarding.xml`: logo + pairing card), `strings.xml`
  (all user-facing copy — onboarding card, connecting screen, error card,
  the foreign-Wi-Fi toast), launcher icons generated from `assets/logo.svg`
- `AndroidManifest.xml` — `OnboardingActivity` is `singleTask` (exported,
  `MAIN`/`LAUNCHER` + the `remoteuser://pair` `VIEW` intent filter);
  `MainActivity` is not exported, declares
  `configChanges="orientation|screenSize|…"` so rotation never recreates the
  WebView, and `usesCleartextTraffic="true"` (the server speaks plain HTTP on
  the LAN/Tailscale private network)
- `build.gradle.kts` / `settings.gradle.kts` — AGP 8.7, Kotlin 2.0, SDK 35;
  version comes from `setup/app_info.json` via build properties; release
  signing from environment variables (never committed)

## Building

```
.venv\Scripts\python setup/build_apk.py      → dist/RemoteUser.apk
```

Toolchain: Android Studio's bundled JDK + the SDK in `%LOCALAPPDATA%`;
Gradle vendored into `setup/vendor/` (wrapper generated on first run).
The keystore is generated ONCE into gitignored `android/keystore/` —
**back it up**: losing it means phone upgrades require uninstall/reinstall.

## Distribution

`dist/RemoteUser.apk` is served by the server at **`/app.apk`**. Any Android
browser hitting the server (the QR link) gets the full-screen **install
funnel** instead of the client: Open the app (pairs itself via `intent://`)
first and primary, Install (downloads the APK) below it. The desktop build
bundles the APK next to the exe, so the installed PC app distributes the
phone app too. No file shuffling, ever.

## Connections

### Uses
- [Client (folder)](../client/___client.md) — the entire product UI, loaded
  into the WebView (`client/index.html`); the `Android` JS bridge
  (`rescan`/`setTailscaleUrl`/`appVersion`/`update`/`lockOrientation`) and the `config`
  WebSocket message are the two-way contact points between the shell and the
  page's own [Connection](../client/__about/connection.md) script (the JS bridge calls and `config` handling both live there)
- [Server (folder)](../server/___server.md) — conceptually the HTTP/WS peer
  this shell talks to over the network (`GET /ping` reachability probe,
  `GET /app.apk`, the page's own `/ws` connection via
  [Web Layer](../server/__about/web.md)). This is **not a code dependency** — the
  shell never imports server code, it only speaks HTTP/WebSocket to whatever
  process answers at the resolved address

### Used by
- Nothing internal — this is the end-user-facing app, a terminal node with
  no in-repo caller
- Built by [Setup (folder)](../setup/___setup.md)'s `build_apk.py` into
  `dist/RemoteUser.apk`, run BEFORE `build.py` so the desktop installer
  bundles the APK and the server can serve it at `/app.apk`
- The owner's phone (v1: sideloaded APK; a Play Store listing is a later
  distribution decision)

## Design Decisions

The shell adds only what a browser tab cannot — everything below is WHY,
not just what:

- **Pairing is one tap**: the install funnel page (what an Android browser
  sees on the QR link) launches the app via `remoteuser://pair?url=…` with
  the tokened URL — `OnboardingActivity` stores it and connects; nothing is
  typed or scanned. Being singleTask, the handover is handled in BOTH
  `onCreate` and `onNewIntent` (an instance is often already alive — the
  "Open" button on the package installer starts one). The manual card
  (*scan the QR / paste the link*) remains as the fallback and for
  re-pairing; re-pair (`EXTRA_FORCE`) does NOT wipe the stored addresses —
  they survive until a NEW pairing succeeds, so a mis-tap away from home
  can never strand the phone. `openClient` uses `CLEAR_TASK`, so a re-pair
  replaces any old `MainActivity` instance instead of stacking WebViews. That
  LAN URL plus the learned Tailscale URL are the only stored state
  (`Prefs`).
- **The WebView identifies itself**: `RemoteUserApp` is appended to the
  User-Agent — that is how the server knows to serve the app the real client
  while plain Android browsers get the funnel.
- **Two addresses, probed on every start**: the QR gives the LAN address; the
  page hands over the Tailscale address on every `config` via
  `Android.setTailscaleUrl()`. `MainActivity.resolveAndLoad()` probes `/ping`
  on both in parallel (3 s timeout) and loads whichever answers — LAN
  preferred, Tailscale the mobile-data fallback. A single stored URL was the
  live failure: the LAN address on mobile data meant minutes of
  `ERR_CONNECTION_TIMED_OUT` before any card showed.
- **The probe accepts ONLY the exact, redirect-free 204** (2026-07-27 foreign-
  Wi-Fi failure): captive portals on foreign/public Wi-Fi answer ANY request
  with their login page (a 2xx or a redirect to one), so the old `2xx = alive`
  check chose a dead LAN address and loaded garbage. Every probe also sends
  `Connection: close` — pooled keep-alive sockets go stale across network
  changes and fail probes a freshly started process would pass. The 204
  contract is pinned fail-closed in the build gate (`tests/`).
- **The error card is a state, not a dead end** (root cause of "Try again
  does nothing, only an app restart helps", 2026-07-27): the old card ran ONE
  probe round per tap, which on flaky foreign Wi-Fi always fired mid-flap —
  a restart "worked" only because it took long enough for the network/tunnel
  to settle. While the card shows, the resolver now re-runs by itself every
  4 s (silently — no loader flash) AND immediately on every default-network
  change (`registerDefaultNetworkCallback`; needs the auto-granted
  `ACCESS_NETWORK_STATE`). Try again stays as the instant manual kick. An
  epoch counter voids stale resolver threads and timers, so retries never
  stack and never reload a live page. See
  [Main Activity (flow)](__flow/MainActivity.md) for the exact state machine.
- **A LIVE page is never reloaded by recovery** (audit finding 2026-07-29 —
  the unlock race): at screen unlock Wi-Fi takes 1–3 s to reassociate, so the
  onResume ping fails on a perfectly healthy session; the silent resolver
  then found an answering address and `loadUrl`-ed it — tearing down a
  session whose own JS had already reconnected. Now the shell tracks document
  health (`pageAlive`: set on `onPageFinished` without a main-frame error,
  cleared on error/load-start) and the silent path, when the loaded page is
  alive AND its own address answered the probe, only hides the card — the
  page's JS does the WebSocket reconnect. `loadUrl` happens only when the
  document is dead or its address stopped answering (the location-change
  case the resolver exists for).
- **Unfamiliar-Wi-Fi heads-up** (owner request 2026-07-27): when the home LAN
  probe fails but the tunnel answers while the default network is Wi-Fi, the
  session is running over someone else's Wi-Fi — a one-per-stay toast says it
  is protected by the encrypted tunnel but warns about public networks.
  Detecting "open/public" specifically would need the location permission
  just to read the SSID/security type — deliberately skipped; the transport
  bit comes from the network callback (a VPN's capabilities include its
  underlying transports).
- **External links open as real apps**: the in-page "anywhere" wizard's
  Google Play button opens the actual Play Store — the same guided Tailscale
  flow works identically in browser and app (no duplicated wizard, Rule #5
  at product level).
- **File chooser**: the page's phone→PC image upload gets the native
  gallery/camera picker.
- **Native "Connecting…" screen** while the address is probed and the page
  loads (a slow connect over mobile data must read as working, not frozen);
  hidden on first page load, replaced by the error card on failure.
- **Native error card** when no stored address answers the probe (Try again
  re-probes NOW; the card keeps re-probing by itself regardless — see above;
  Scan a new QR re-pairs but KEEPS the stored addresses until a new pairing
  succeeds).
- **QR scanner follows the phone orientation** (portrait when upright) — the
  ZXing default forced landscape.
- **`Android.rescan()` JS bridge**: on a rejected token the page shows
  "tap to scan the new QR" and the shell reopens the scanner.
- **In-app updates from the PC**: the page compares `config.app_version`
  with `Android.appVersion()` and, when the PC is newer, shows an update
  banner; `Android.update(url)` opens `/app.apk` (same PC) in the system
  browser — download, install over, done. The phone never checks the
  internet; the desktop app is the one that watches GitHub Releases.
- **Immersive — system bars hidden** (2026-07-26): `targetSdk 35` draws the
  WebView edge-to-edge, so the navigation bar sat ON TOP of the page's bottom
  controls and the system stole touches near the edges ("no button works").
  `MainActivity.hideSystemBars()` hides status + nav bars
  (`BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE` — an edge swipe shows them
  briefly), re-applied on every window-focus gain because the system restores
  them after dialogs, app switches and the keyboard.
- **Session behavior**: screen stays on; rotation never recreates the WebView
  (the stream survives); leaving the app pauses the page, whose visibility
  rule closes the stream (owner security decision). On resume the shell pings
  the loaded address — the app often survives in RAM across a location change
  (home Wi-Fi → mobile data) and the page would retry a dead address forever;
  if it stopped answering, the resolver runs again and the other address
  takes over.
