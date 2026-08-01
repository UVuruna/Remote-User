# Onboarding Activity

**Script:** [Onboarding Activity (script)](../app/src/main/java/com/uvuruna/remoteuser/OnboardingActivity.kt)

## Purpose

First-run pairing screen — binds this phone to a PC, and doubles as the
re-pair screen later. Two independent entry points converge on the same
logic:

- **Automatic (normal path):** the install funnel page (what an Android
  browser sees when it opens the QR link) launches this activity via
  `remoteuser://pair?url=…` carrying the tokened LAN URL — one tap, no
  typing, no scanning. The activity is `singleTask` (see the manifest), so
  this launch can land in `onCreate` (fresh instance) OR `onNewIntent` (an
  instance is already alive — e.g. the user tapped "Open" on the package
  installer first); both call `handlePairIntent`.
- **Manual (fallback / re-pair):** the visible card lets the user scan the
  QR themselves (ZXing `ScanContract`, orientation unlocked so it follows
  the phone instead of forcing landscape) or paste the link into a text
  field.

Either path funnels into `tryConnect`, which validates the link
(`http…` + contains `token=`), stores it as the LAN address, and hands off
to `MainActivity`. Every step after pairing — including the Tailscale
"use from anywhere" wizard — is guided by the loaded page itself, so the
guidance text exists exactly once (in the client, not duplicated here).

Re-pairing (`EXTRA_FORCE`) intentionally does **not** wipe the previously
stored addresses — they survive until a *new* pairing actually succeeds
(`tryConnect` overwrites them). A stray tap on "Scan a new QR" while away
from home must never strand the phone with nothing left to connect to.

## Connections

### Uses
- [Prefs (script)](../app/src/main/java/com/uvuruna/remoteuser/Prefs.kt) — `setLanUrl` stores the freshly paired LAN
  address; `setTsUrl(null)` clears the previously learned Tailscale address
  (it may belong to a different PC/token now — it is relearned on first
  connect via the JS bridge)
- [Main Activity](MainActivity.md) — `openClient()` starts it with
  `NEW_TASK | CLEAR_TASK` once a link is accepted, so a re-pair replaces any
  old WebView instance instead of stacking a new one on top

### Used by
- [Main Activity](MainActivity.md) — `repair()` relaunches this activity
  (`EXTRA_FORCE = true`) whenever no stored LAN address exists at startup, or
  the user taps "Scan a new QR" on the error card
- The Android launcher (`MAIN`/`LAUNCHER` intent filter) — first cold start
- The install funnel page (`client/install.html`, served by the PC, not part
  of this app) — its "Open the app" button targets the
  `remoteuser://pair?url=…` intent filter; see
  [Client (folder)](../../client/___client.md)

## Classes

### OnboardingActivity
The pairing screen (`AppCompatActivity`).

**Attributes**
- `scanner`: `ActivityResultLauncher<ScanOptions>` — ZXing embedded scanner,
  registered via `registerForActivityResult(ScanContract())`

**Methods**
- `onCreate()`: tries `handlePairIntent` first; if not a funnel launch and an
  LAN URL is already stored (and re-pair wasn't forced), skips the UI
  entirely and calls `openClient()`; otherwise inflates the manual card and
  wires the Scan/Connect buttons
- `onNewIntent(intent)`: the `singleTask` re-entry path — required because
  without overriding it, a funnel launch arriving while an instance is
  already alive is silently dropped and the empty pairing card comes forward
  instead of connecting
- `handlePairIntent(intent)`: validates a `remoteuser://pair?url=…` intent
  (scheme + `token=` present) and calls `tryConnect`; returns whether it
  acted, so `onCreate` knows whether to fall through to the stored-URL
  shortcut
- `tryConnect(url)`: link validation (`http` + `token=`, else a toast),
  stores the LAN URL, clears the stale Tailscale URL, calls `openClient()`
- `openClient()`: starts `MainActivity` with `NEW_TASK | CLEAR_TASK` and
  finishes this activity

**Companion object**
- `EXTRA_FORCE`: intent extra — skips the already-paired shortcut in
  `onCreate` WITHOUT wiping the stored addresses, so the manual card shows
  even though a LAN URL is already on file
