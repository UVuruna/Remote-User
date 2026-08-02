# Main Activity

**Script:** [Main Activity (script)](../app/src/main/java/com/uvuruna/remoteuser/MainActivity.kt) ·
**Flow:** [diagram](../__flow/MainActivity.md)

## Purpose

The client shell: a full-screen `WebView` on whichever stored address
answers, plus everything a browser tab cannot do by itself. The page
(`client/index.html`, loaded inside the `WebView`) carries ALL product UI
and guidance; this class only adds:

- **Dual-address resolution with failover** — the LAN address (from
  pairing) and the Tailscale address (learned from the page on every
  `config`, via the JS bridge) are probed on every start and the reachable
  one is loaded, LAN preferred. A single stored URL was the original live
  failure: the LAN address on mobile data meant minutes of
  `ERR_CONNECTION_TIMED_OUT` before anything showed.
- **A self-healing error card** — while shown, it re-probes itself on a 4 s
  timer AND immediately on every default-network change, instead of the old
  one-shot "Try again" that always fired mid-flap on flaky Wi-Fi.
- **Document-health tracking (`pageAlive`)** so recovery never reloads a
  session that is actually fine — the classic case is screen unlock, where
  Wi-Fi takes 1–3 s to reassociate and a single ping fails on a perfectly
  healthy page whose own JS has already reconnected the WebSocket.
- **A foreign-Wi-Fi heads-up toast**, the `Android` JS bridge
  (`rescan` / `setTailscaleUrl` / `appVersion` / `update`), the native file
  chooser for phone→PC image upload, immersive system bars, and the
  keep-awake / rotation-survives-the-session / pause-on-background behavior.

See [Main Activity (flow)](../__flow/MainActivity.md) for the resolve/retry
state machine as a diagram — the logic below is dense enough that the prose
alone undersells it.

## Connections

### Uses
- [Prefs (script)](../app/src/main/java/com/uvuruna/remoteuser/Prefs.kt) — reads both stored URLs every
  `resolveAndLoad`; writes the Tailscale URL from the JS bridge; read by
  `Client.shouldOverrideUrlLoading` to recognize "our server" by port
- [Onboarding Activity](OnboardingActivity.md) — `repair()` launches it
  (`EXTRA_FORCE`) when no LAN address is stored, or the user taps "Scan a
  new QR" on the error card
- [Client (folder)](../../client/___client.md) — the entire product UI,
  loaded into the `WebView`; the `Android` bridge and the `config` message
  are the two-way contact points with the client's [Connection](../../client/__about/connection.md) script (the JS bridge calls and `config` handling both live there)
- The PC's HTTP/WebSocket server, conceptually (not a code dependency — this
  class talks to it only over the network): `GET /ping` for the reachability
  probe, `GET /app.apk` opened by the update bridge, and the page's own
  WebSocket to `/ws`. See [Web Layer](../../server/__about/web.md) and
  [Server (folder)](../../server/___server.md).

### Used by
- [Onboarding Activity](OnboardingActivity.md) — `openClient()` starts it
  once a pairing link is accepted
- The Android task/Recents system on resume (no other internal caller — this
  is the app's terminal screen)

## Classes

### MainActivity
The activity itself (`AppCompatActivity`) — owns the `WebView`, the loading/
error overlay views, the network callback, and the resolve/retry state
(`resolveEpoch`, `pageAlive`, `lastLoadFailed`, `onWifi`,
`warnedForeignWifi`). Key methods: `resolveAndLoad(silent)` (the probe/
failover core — see the flow doc), `scheduleRetry(epoch)`, `pingOk(url)`
(the strict-204 `/ping` probe), `warnIfForeignWifi()`, `hideSystemBars()`,
`repair()` (hands off to `OnboardingActivity`), `onResume()` /
`onPause()` / `onDestroy()` lifecycle wiring.

### netCallback (`ConnectivityManager.NetworkCallback`, anonymous, field)
Registered via `registerDefaultNetworkCallback` in `onCreate`, unregistered
in `onDestroy`. `onAvailable` kicks a silent `resolveAndLoad` when the error
card is showing; `onCapabilitiesChanged` tracks whether the default network
carries a Wi-Fi transport (`onWifi`) and re-arms the foreign-Wi-Fi toast the
next time Wi-Fi drops.

### Bridge (inner class, `@JavascriptInterface`, exposed as `Android`)
The page's only way to reach the shell.
- `rescan()`: reopens `OnboardingActivity` (called when the page's own token
  gets rejected server-side)
- `setTailscaleUrl(url)`: persists the works-anywhere address handed over on
  every `config`; blank means the PC currently has no Tailscale address
- `appVersion()`: this shell's `versionName`, compared by the page against
  the server's `config.app_version` to decide whether to show the in-app
  update banner
- `update(url)`: opens `/app.apk` (same PC) in the system browser — the
  WebView itself has no download pipeline, so the browser is only the
  download UI; Android installs over this app on the same signature
- `lockOrientation(mode)`: layout focus locks the phone's rotation to the
  layout's chosen orientation (`"portrait"` / `"wide"`), `""` unlocks — the
  full-desktop view rotates freely (owner 2026-08-02)
- `transport()`: `"cellular"` / `"wifi"` / `""` — the page's auto quality
  mode reduces the stream only on mobile data (owner spec 2026-08-02)

### Client (inner class, `WebViewClient`)
- `shouldOverrideUrlLoading`: keeps navigation to the paired server's own
  host:port inside the `WebView`; every other link (Google Play, tailscale.com)
  opens as a real external app via `ACTION_VIEW`
- `onReceivedError` (main frame only): marks `pageAlive = false`, swaps the
  loader for the error card, schedules a retry — a failed page load
  self-heals through the same machinery as a failed probe
- `onPageStarted` / `onPageFinished`: track `pageAlive` (`onPageFinished`
  fires even after `onReceivedError`, so a failed load must not read as a
  live document)

### Chrome (inner class, `WebChromeClient`)
`onShowFileChooser`: routes the page's phone→PC image-upload picker to the
native gallery/camera chooser (`filePicker`, `GetContent("image/*")`).

### Companion object
`PING_TIMEOUT_MS` (3000), `RETRY_INTERVAL_MS` (4000) — the two tunables
behind the probe timeout and the self-healing error-card cadence.

`update(url)` falls back to an Intent chooser when no direct ACTION_VIEW
handler resolves ("no app can open this" — owner report 2026-08-02).
