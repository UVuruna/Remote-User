# android/

The Android app — a **native shell around the existing web client** (ROADMAP
Phase D). The page carries ALL product UI and guidance; the shell adds only
what a browser tab cannot. One wizard, one client, two containers.

Kotlin, two activities, two dependencies (AppCompat + the embedded ZXing
scanner). Package `com.uvuruna.remoteuser`, min Android 8 (API 26).

## What the shell does (and nothing more)

- **Pairing**: first run shows one card — *scan the QR on the PC* (or paste
  the link). The URL (with token) is the only stored state.
- **External links open as real apps**: the in-page "anywhere" wizard's
  Google Play button opens the actual Play Store — the same guided Tailscale
  flow works identically in browser and app (no duplicated wizard, Rule #5
  at product level).
- **File chooser**: the page's phone→PC image upload gets the native
  gallery/camera picker.
- **Native error card** when the PC is unreachable (Try again / Scan a new QR).
- **`Android.rescan()` JS bridge**: on a rejected token the page shows
  "tap to scan the new QR" and the shell reopens the scanner.
- **Session behavior**: screen stays on; rotation never recreates the WebView
  (the stream survives); leaving the app pauses the page, whose visibility
  rule closes the stream (owner security decision).
- **URL follows the wizard**: whatever tokened URL the page navigates to
  (the works-anywhere link) is persisted as the new home.

## Files

- `app/src/main/java/com/uvuruna/remoteuser/` — `OnboardingActivity` (QR
  scan/paste → store URL), `MainActivity` (WebView + the bridges above),
  `Prefs` (the one stored value)
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

`dist/RemoteUser.apk` is served by the server at **`/app.apk`** — the phone
page shows a "Get the app" pill (Android browsers, outside the app, only when
the APK exists). The desktop build bundles the APK next to the exe, so the
installed PC app distributes the phone app too. No file shuffling, ever.

## Connections

### Uses
- [Client (folder)](../client/___client.md) — the entire UI, loaded in the WebView
- [Web Layer](../server/web.md) — `/app.apk`, `/ping`, and the WebSocket it serves

### Used by
- The owner's phone (v1: APK; Play Store is a later distribution decision)
