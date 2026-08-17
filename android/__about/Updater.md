# Updater — the in-app update job

**Script:** [Updater.kt](../app/src/main/java/com/uvuruna/vibecoder/Updater.kt) ·
**Folder:** [Android](../___android.md)

## Purpose

Downloads `/app.apk` from the paired PC and installs it over this app, with
**no file ever written to this app's storage**. The response body is streamed
directly into a `PackageInstaller.Session`'s own `OutputStream` — the session
Android itself manages is the only place the bytes ever live outside the
network socket.

Started by `Bridge.updateInApp(url)`; the older `Bridge.update(url)` (open
`/app.apk` in the system browser) is untouched and stays the fallback for a
page served by a PC too old to know about this path.

## Why no file, no `FileProvider`, no `DownloadManager`

Every one of those would create something **shareable** — a path another app
could be handed a URI to — for the sole purpose of handing bytes to a system
service that already accepts them directly over a stream. An install carries
elevated trust by definition; a copy of the APK sitting in cache is one more
surface a wrong grant, a backup, or a stray `FileProvider` path could point
at, for no reason this feature needs. `PackageInstaller.Session.openWrite`
exists precisely so nothing has to touch disk outside the session.

## The contract, exactly as `Bridge.kt` exposes it

| Direction | Name | Notes |
|---|---|---|
| page → shell | `updateInApp(url): Boolean` | Starts the job. `true` = a job is now in flight; `false` = one already was, or the permission was missing (in which case `"permission"` fires through `onState` instead). |
| page → shell | `updateInstallAllowed(): Boolean` | `canRequestPackageInstalls()`, direct. |
| page → shell | `updateAllowInstall()` | Opens `ACTION_MANAGE_UNKNOWN_APP_SOURCES` scoped to this app's own package. |
| shell → page | `__updateProgress(received, total)` | `total <= 0` = unknown length (no `Content-Length`, chunked transfer). |
| shell → page | `__updateState(state, detail)` | `state` ∈ `"permission"` / `"downloading"` / `"installing"` / `"failed"`; `detail` is a plain-language sentence, only ever populated for `"failed"`. |

**There is no success state, on purpose.** A successful install replaces this
very process — there is no later moment in which a callback could still reach
a page that no longer has a process to run in. The page's own reload, once
the new version restarts it, is the only signal a success can ever produce.

## The URL is untrusted (2026-08-17)

`start(url)` accepts a url ONLY when `isPairedApkUrl()` says it names one of
this shell's own two stored, paired addresses (`Prefs.lanUrl`/`Prefs.tsUrl`
— the same pair `MainActivity` probes) at the exact path `/app.apk`, compared
by **parsed** scheme/host/port, never by a string prefix. The reason: this
shell loads its page over plain HTTP on the LAN, and every
`@JavascriptInterface` method is reachable from whatever script the WebView
currently holds — `update(url)` always had this exposure, but only ever
opened a browser download the user had to find and tap, while this path
raises the system install-confirm dialog directly. A refusal is logged with
the rejected url and reports `"failed"` with a plain sentence; it never
downloads anything.

## Redirects are followed OURSELVES, never by `HttpURLConnection` (2026-08-17)

Validating the url `start()` was ASKED for proves nothing about where the
bytes that come back actually CAME FROM: `instanceFollowRedirects = true`
would let whatever answered send back a 3xx pointing anywhere, silently, and
the threat model here is exactly a party who can answer on the LAN — so a
redirect is a trivial bypass of `isPairedApkUrl`, not an edge case.
`openValidated()` is the one place in this class allowed to follow a
redirect: `instanceFollowRedirects` is always `false`; on 301/302/303/307/308
it resolves `Location` against the current url (relative locations are
legal), re-validates the resolved url through the SAME `isPairedApkUrl`, and
only then follows it — bounded at `MAX_REDIRECTS` (3) so a chain cannot spin
forever. This app's own PC serves `/app.apk` as a plain static file and has
never actually needed a redirect, but that is precisely why this path is
exercised rarely — a reason to keep the explicit, checked handling rather
than trust the one-liner.

## The job, in order

1. `start(url)` — refuses if already `running`; refuses (logged) if the url
   is not a paired `/app.apk`; refuses (and remembers `url` as `pendingUrl`)
   if `canInstall()` is false, reporting `"permission"`.
2. A daemon thread opens the URL through `openValidated()`, reads
   `Content-Length` (may be `-1`,
   PackageInstaller's own "unknown" sentinel — passed straight through, never
   translated), and opens a `PackageInstaller` session
   (`MODE_FULL_INSTALL`).
3. `streamInto()` copies the body into the session's write stream, calling
   `fsync()` on the stream **before** it is closed — that ordering is
   PackageInstaller's own contract, which is why the close lives in a
   `finally` rather than a `use {}` block that would close first.
4. Progress is throttled to roughly every 1% AND every 100 ms — **both**
   gates, not either, so a known-size download reports rarely (the "whichever
   is rarer" rule); an unknown-size one falls back to the time gate alone,
   since there is no percentage to compute.
5. `session.commit(pendingIntent.intentSender)` — this THREAD's job ends
   here, but the job is not over: `commit()` is asynchronous, so `running`
   deliberately stays `true` (a `committed` flag guards the usual
   `finally`-clears-it path) until the system's confirm dialog is answered
   and `installReceiver` reaches a terminal state. Without this a second
   `start()` in that window would open a second download and a second
   session (defect found in review, fixed 2026-08-17) — the page's own state
   must not be what prevents that; the shell owes it structurally.

## `installReceiver` — registered at RUNTIME, never in the manifest

A private action string (`com.uvuruna.vibecoder.action.INSTALL_UPDATE`); on
API 33+, `Context.RECEIVER_NOT_EXPORTED` says structurally what the private
name only said by convention — nothing outside this process may ever trigger
it. `STATUS_PENDING_USER_ACTION` pulls `Intent.EXTRA_INTENT` and starts it
(`FLAG_ACTIVITY_NEW_TASK`, since the broadcast may land with no Activity
alive) and reports `"installing"`; any failure status is translated to one
short, plain-language sentence — never the constant's own name, never a
stack trace — via `readableFailure()`.

## `pendingUrl` and `onAppResumed()` — automatic continuation

If the permission is missing, `start()` remembers the URL and reports
`"permission"` instead of downloading. `updateAllowInstall()` opens Settings;
`MainActivity.onResume()` calls `updater.onAppResumed()` on every resume
(cheap when nothing is pending), which re-checks `canInstall()` and, if it is
now true, starts the remembered download **without another tap** — the
project's standing "guided IN the app, with automatic continuation" rule
(project `CLAUDE.md`), not a nicety.

## `cancel()` / `release()`

`cancel()` disconnects the socket, abandons the session (only meaningful
before commit — a committed session's confirm dialog is a fact by then that
cannot be recalled), and interrupts the thread. `release()` additionally
unregisters `installReceiver`; called once, from `MainActivity.onDestroy()`.

## Connections

### Uses
- `MainActivity` — `Updater.attach(host)` builds the instance against the
  Activity's own `evaluateJavascript` sink (same shape as `notifier`/`pad`);
  `appCtx` is `context.applicationContext`, held instead of the Activity
- `PackageInstaller` (platform) — the whole install mechanism
- [Bridge](Bridge.md) — `updateInApp`, `updateInstallAllowed`,
  `updateAllowInstall` are its only callers

### Used by
- The web client, indirectly — `__updateProgress` / `__updateState` are page
  globals this class calls through `MainActivity`'s callback wiring

## Honest limits

- Kotlin cannot be executed in this repo (no JVM test runner) — this file is
  correct by inspection and by matching the codebase's existing
  `PackageInstaller`-adjacent patterns; it has not been run on a device by
  this round.
- A `gradle` build was not run as part of this change (no Android SDK in
  this environment).
