# android/

The Android app — a **native shell around the existing web client** (ROADMAP
Phase D). The page carries ALL product UI and guidance; the shell adds only
what a browser tab cannot. One wizard, one client, two containers.

Kotlin, two activities, two dependencies (AppCompat + the embedded ZXing
scanner). Package `com.uvuruna.remoteuser`, min Android 8 (API 26).

## What the shell does (and nothing more)

- **Pairing is one tap**: the install funnel page (what an Android browser
  sees on the QR link) launches the app via `remoteuser://pair?url=…` with
  the tokened URL — `OnboardingActivity` stores it and connects; nothing is
  typed or scanned. The manual card (*scan the QR / paste the link*) remains
  as the fallback and for re-pairing. That LAN URL plus the learned
  Tailscale URL are the only stored state.
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
- **External links open as real apps**: the in-page "anywhere" wizard's
  Google Play button opens the actual Play Store — the same guided Tailscale
  flow works identically in browser and app (no duplicated wizard, Rule #5
  at product level).
- **File chooser**: the page's phone→PC image upload gets the native
  gallery/camera picker.
- **Native error card** when no stored address answers the probe (Try again
  re-probes / Scan a new QR re-pairs and clears both addresses).
- **`Android.rescan()` JS bridge**: on a rejected token the page shows
  "tap to scan the new QR" and the shell reopens the scanner.
- **In-app updates from the PC**: the page compares `config.app_version`
  with `Android.appVersion()` and, when the PC is newer, shows an update
  banner; `Android.update(url)` opens `/app.apk` (same PC) in the system
  browser — download, install over, done. The phone never checks the
  internet; the desktop app is the one that watches GitHub Releases.
- **Session behavior**: screen stays on; rotation never recreates the WebView
  (the stream survives); leaving the app pauses the page, whose visibility
  rule closes the stream (owner security decision). On resume the shell pings
  the loaded address — the app often survives in RAM across a location change
  (home Wi-Fi → mobile data) and the page would retry a dead address forever;
  if it stopped answering, the resolver runs again and the other address
  takes over.

## Files

- `app/src/main/java/com/uvuruna/remoteuser/` — `OnboardingActivity` (QR
  scan/paste → store the LAN URL), `MainActivity` (WebView + the resolver
  and bridges above), `Prefs` (the two stored addresses)
- `app/src/main/res/` — dark brand theme (same slate/cyan palette as the
  client and desktop), layouts, launcher icons generated from `assets/logo.svg`
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
funnel** instead of the client: Install (downloads the APK) → Open the app
(pairs itself via `intent://`). The desktop build bundles the APK next to
the exe, so the installed PC app distributes the phone app too. No file
shuffling, ever.

## Connections

### Uses
- [Client (folder)](../client/___client.md) — the entire UI, loaded in the WebView
- [Web Layer](../server/web.md) — `/app.apk`, `/ping`, and the WebSocket it serves

### Used by
- The owner's phone (v1: APK; Play Store is a later distribution decision)
