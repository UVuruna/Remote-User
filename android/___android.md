# android/

The Android app — a **native shell around the existing web client** (ROADMAP
Phase D). The page carries ALL product UI and guidance; the shell adds only
what a browser tab cannot. One wizard, one client, two containers.

Kotlin, two activities, two dependencies (AppCompat + the embedded ZXing
scanner). Package `com.uvuruna.vibecoder`, min Android 8 (API 26).

## Files

| File | Tier | One line |
|------|------|----------|
| `MainActivity.kt` | Algorithmic | WebView shell — dual-address resolve/failover state machine, self-healing error card, network callbacks, immersive UI — [about](__about/MainActivity.md) · [flow](__flow/MainActivity.md) |
| `ConnectivityWatcher.kt` | Standard | what network the phone is on and when it changes — the default-network callback that re-resolves the address on EVERY new network (not only behind the error card: that `if` is the 2026-08-07 report) and tracks the transport for auto-quality and the foreign-Wi-Fi notice; split off `MainActivity.kt` 2026-08-18 — [about](__about/ConnectivityWatcher.md) |
| `Insets.kt` | Standard | what the window's EDGES do — the immersive system bars, and the keyboard inset only the shell can measure (edge-to-edge broke `adjustResize`); split off `MainActivity.kt` 2026-08-09 — [about](__about/Insets.md) |
| `ScreenAwake.kt` | Standard | which layer is on screen (error card / loader / page) and whether `FLAG_KEEP_SCREEN_ON` may be held — one owner instead of the page alone, which could not clear it while the error card was up (T80a, 2026-08-14) — [about](__about/ScreenAwake.md) |
| `ConnectionError.kt` | Standard | why the PC can't be reached, and the one button that fixes it — the five-cause diagnosis and the error card's own actions; split off `MainActivity.kt` 2026-08-17 — [about](__about/ConnectionError.md) |
| `Bridge.kt` | Standard | `window.Android` — every name the PAGE calls; the shell's compatibility surface (split from MainActivity 2026-08-07) — [about](__about/Bridge.md) |
| `Updater.kt` | Algorithmic | the in-app update job — streams `/app.apk` straight into a `PackageInstaller` session with no file ever written to disk, throttled progress, automatic continuation once "install unknown apps" is granted — [about](__about/Updater.md) |
| `UpdateReturn.kt` | Standard | the way back IN after the app installs a new version of itself — a manifest receiver for `MY_PACKAGE_REPLACED` that tries to reopen the app (best effort; Android 10+ normally refuses a background activity start) and ALWAYS posts a one-tap "you are up to date" notice through `Notifier` (owner report 2026-08-18) — [about](__about/UpdateReturn.md) |
| `Gamepad.kt` | Standard | the Bluetooth game controller — keys and sticks captured before the WebView sees them and forwarded to the page, which owns the whole mapping (build round G1, 2026-08-07) — [about](__about/Gamepad.md) |
| `OnboardingActivity.kt` | Standard | first-run pairing screen — automatic funnel handoff + manual QR-scan/paste fallback — [about](__about/OnboardingActivity.md) |
| `VoiceInput.kt` | Standard | dictation subsystem — user-chosen language, engine choice, silent model download, silent diagnostics (split from MainActivity 2026-08-05) — [about](__about/VoiceInput.md) |
| `Notifier.kt` | Standard | notifications + speech for the PC's notices — one line per agent, TTS queued until the engine is ready (ROADMAP Phase H, 2026-08-05) — [about](__about/Notifier.md) |
| `NoticeService.kt` | Standard | the foreground service that lets a notice reach this phone with NO page — the permanent notification Android demands, the battery-optimisation ask, delivery (owner decree 2026-08-07) — [about](__about/NoticeService.md) |
| `NoticeLink.kt` | Algorithmic | the waiting state itself — one thread blocked on `GET /notices`, the PC's 60 s beat, connect/read/backoff (owner decree 2026-08-07) — [about](__about/NoticeLink.md) · [flow](__flow/NoticeLink.md) |
| `Prefs.kt` | Trivial | `SharedPreferences` wrapper for the two stored addresses (LAN URL from pairing, Tailscale URL learned from the page) plus the name of the page's own preference store |

## Two channels, and only one of them is a session

The streaming session dies the moment the page hides — the owner's security
rule, and what the presence protocol, the topmost ledger and the layout
defence all rest on. That is exactly why an agent's notice used to arrive only
when he opened the app (his report, 2026-08-07).

So the shell holds a **second, minimal** channel that carries notices and
nothing else: `NoticeService` + `NoticeLink`, one idle socket, the phone
sending nothing at all. The PC keeps the two apart structurally — `/notices`
never touches the one-device slot presence is built on — so a waiting phone is
never mistaken for a present one, and nothing it does can hold a window
always-on-top over the owner's desk. See
[Notify (server)](../server/__about/notify.md).

**Other files in this folder (not source-tier — resources and build config):**
- `app/src/main/res/` — dark brand theme (same slate/cyan palette as the
  client and desktop), layouts (`activity_main.xml`: WebView + loading/error
  overlays; `activity_onboarding.xml`: logo + pairing card), `strings.xml`
  (all user-facing copy — onboarding card, connecting screen, error card,
  the foreign-Wi-Fi toast), launcher icons generated from `assets/logo.svg`
- `AndroidManifest.xml` — `OnboardingActivity` is `singleTask` (exported,
  `MAIN`/`LAUNCHER` + the `vibecoder://pair` `VIEW` intent filter);
  a `<queries>` element declares `com.tailscale.ipn` so Android 11+ package
  visibility lets the error card tell "Tailscale not installed" from
  "installed but off"; `MainActivity` is not exported, declares
  `configChanges="orientation|screenSize|…"` so rotation never recreates the
  WebView, and `usesCleartextTraffic="true"` (the server speaks plain HTTP on
  the LAN/Tailscale private network). Since 2026-08-07 it also declares
  `NoticeService` with `foregroundServiceType="connectedDevice"` — the honest
  type, since the service exists to hold a network connection to ONE paired
  device, the owner's PC (`dataSync` is deprecated in Android 15 with a
  six-hour cap; `specialUse` is for things with no honest type) — plus
  `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_CONNECTED_DEVICE` and
  `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`; since 2026-08-17 also
  `REQUEST_INSTALL_PACKAGES` — a sideload-only permission Google Play
  forbids, accepted on purpose since this project ships its own APK by
  decision (see [Updater](__about/Updater.md)); since 2026-08-18 a
  `<receiver android:name=".UpdateReturn" android:exported="false">` filtering
  exactly `android.intent.action.MY_PACKAGE_REPLACED` — declared here and
  never registered at runtime, because at the moment that broadcast is sent
  our process is dead (the install killed it), and only a manifest entry can
  bring the package back from nothing (see
  [UpdateReturn](__about/UpdateReturn.md))
- `build.gradle.kts` / `settings.gradle.kts` — AGP 8.7, Kotlin 2.0, SDK 35;
  version comes from `setup/app_info.json` via build properties; release
  signing from environment variables (never committed)

## Building

```
.venv\Scripts\python setup/build_apk.py      → dist/VibeCoder.apk
```

Toolchain: Android Studio's bundled JDK + the SDK in `%LOCALAPPDATA%`;
Gradle vendored into `setup/vendor/` (wrapper generated on first run).
The keystore is generated ONCE into gitignored `android/keystore/` —
**back it up**: losing it means phone upgrades require uninstall/reinstall.

## Distribution

`dist/VibeCoder.apk` is served by the server at **`/app.apk`**. Any Android
browser hitting the server (the QR link) gets the full-screen **install
funnel** instead of the client: Open the app (pairs itself via `intent://`)
first and primary, Install (downloads the APK) below it. The desktop build
bundles the APK next to the exe, so the installed PC app distributes the
phone app too. No file shuffling, ever.

## Connections

### Uses
- [Client (folder)](../client/___client.md) — the entire product UI, loaded
  into the WebView (`client/index.html`); the `Android` JS bridge
  ([Bridge](__about/Bridge.md) — every name the page calls) and the `config`
  WebSocket message are the two-way contact points between the shell and the
  page's own [Connection](../client/__about/connection.md) script (the JS bridge calls and `config` handling both live there)
- [Server (folder)](../server/___server.md) — conceptually the HTTP/WS peer
  this shell talks to over the network (`GET /ping` reachability probe,
  `GET /app.apk`, `GET /notices` for the waiting channel, the page's own `/ws`
  connection via [Web Layer](../server/__about/web.md)). This is **not a code dependency** — the
  shell never imports server code, it only speaks HTTP/WebSocket to whatever
  process answers at the resolved address

### Used by
- Nothing internal — this is the end-user-facing app, a terminal node with
  no in-repo caller
- Built by [Setup (folder)](../setup/___setup.md)'s `build_apk.py` into
  `dist/VibeCoder.apk`, run BEFORE `build.py` so the desktop installer
  bundles the APK and the server can serve it at `/app.apk`
- The owner's phone (v1: sideloaded APK; a Play Store listing is a later
  distribution decision)

## Design Decisions

The shell adds only what a browser tab cannot — everything below is WHY,
not just what:

- **Pairing is one tap**: the install funnel page (what an Android browser
  sees on the QR link) launches the app via `vibecoder://pair?url=…` with
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
- **The WebView identifies itself**: `VibeCoderApp` is appended to the
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
  flow works identically in browser and app (no duplicated wizard, Priority C —
  Inheritance over duplication, root CLAUDE.md — at product level).
- **File chooser**: the page's phone→PC image upload gets the native
  gallery/camera picker.
- **Native "Connecting…" screen** while the address is probed and the page
  loads (a slow connect over mobile data must read as working, not frozen);
  hidden on first page load, replaced by the error card on failure.
- **Native error card** when no stored address answers the probe (the card
  keeps re-probing by itself regardless — see above; Scan a new QR re-pairs
  but KEEPS the stored addresses until a new pairing succeeds).
- **The card names the CAUSE and its button is the FIX** (owner request
  2026-08-04): one generic "Try again" served five different failures,
  including the everyday one — phone away from home with Tailscale switched
  off — where Try again can never work and the fix lives in another app.
  `classifyFailure()` reads three things, all without a new permission: is
  there a network at all, is Tailscale installed (needs the manifest
  `<queries>` entry on Android 11+), is a VPN tunnel up. That plus "did the
  PC ever report a Tailscale address" yields five states — no network / PC
  not on Tailscale / Tailscale missing / Tailscale off / PC down — each with
  its own text and primary button (Install Tailscale → Play Store, Turn
  Tailscale on → opens the app, or Try again). Android cannot flip another
  app's VPN switch, so the button opens Tailscale and the text names the one
  control to press; coming back needs no tap, since the network callback
  fires the moment the tunnel is up. Limits accepted on purpose: the platform
  exposes only "some VPN is up", not "Tailscale is connected", and telling
  the home Wi-Fi from a foreign one would cost the location permission just
  to read an SSID — so the "Tailscale is off" copy also covers "at home, PC
  asleep". Decision tree: [Main Activity (flow)](__flow/MainActivity.md).
- **QR scanner follows the phone orientation** (portrait when upright) — the
  ZXing default forced landscape.
- **`Android.rescan()` JS bridge**: on a rejected token the page shows
  "tap to scan the new QR" and the shell reopens the scanner.
- **In-app updates from the PC**: the page compares `config.app_version`
  with `Android.appVersion()` and, when the PC is newer, shows an update
  banner. Two paths now exist. `Android.update(url)` — the original,
  unchanged fallback — opens `/app.apk` (same PC) in the system browser:
  download, install over, done. `Android.updateInApp(url)` (2026-08-17,
  [Updater](__about/Updater.md)) streams the same `/app.apk` straight into a
  `PackageInstaller` session with no file ever touched on disk, reports
  progress and state back to the page (`__updateProgress`/`__updateState`),
  and — missing the one-time "install unknown apps" grant — remembers the
  request and finishes it BY ITSELF the moment the user grants it in
  Settings (`updateAllowInstall()` → `MainActivity.onResume()`), never a
  second tap. The phone never checks the internet either way; the desktop
  app is the one that watches GitHub Releases.
- **After the update, he is brought back** (2026-08-18,
  [UpdateReturn](__about/UpdateReturn.md)): a successful install replaces the
  process and the app vanishes off the screen, so a manifest receiver for
  `MY_PACKAGE_REPLACED` — the one action delivered to our OWN package —
  attempts to reopen the app and ALWAYS posts a "tap to open it again"
  notice. The attempt is best effort only (Android 10+ normally refuses a
  background activity start, and refuses it silently); the notice is the
  carrier that works, which is why it is never an `else`.
- **Immersive — system bars hidden** (2026-07-26): `targetSdk 35` draws the
  WebView edge-to-edge, so the navigation bar sat ON TOP of the page's bottom
  controls and the system stole touches near the edges ("no button works").
  `MainActivity.hideSystemBars()` hides status + nav bars
  (`BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE` — an edge swipe shows them
  briefly), re-applied on every window-focus gain because the system restores
  them after dialogs, app switches and the keyboard.
- **No platform focus highlight** (owner 2026-08-03): the page's keyboard
  capture field is deliberately invisible, so any focus rectangle drawn around
  it is a bright bar across the top of the stream — the owner reported it five
  times. The page kills the CSS focus ring and
  `web.defaultFocusHighlightEnabled = false` kills the framework's.
- **Session behavior**: screen stays on; rotation never recreates the WebView
  (the stream survives); leaving the app pauses the page, whose visibility
  rule closes the stream (owner security decision). On resume the shell pings
  the loaded address — the app often survives in RAM across a location change
  (home Wi-Fi → mobile data) and the page would retry a dead address forever;
  if it stopped answering, the resolver runs again and the other address
  takes over.
