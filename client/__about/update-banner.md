# Update Banner

**Script:** [Update Banner (script)](../update-banner.js) ·
**Folder:** [client](../___client.md)

## Purpose

The in-app offer to install the newer APK the PC server carries
(`config.apk_version` vs. `Android.appVersion()`) — a pill under the status
that shows only inside the app (`IN_APP`), never in any browser. Split off
[Controls](controls.md) on 2026-08-10 (task 207) to keep that file under THE
STRUCTURE LAW's line ceiling; loads right after `controls.js` and reads its
`IN_APP` global, plus `keepFocus`/`showToast` (`chrome.js`).

## Why it exists (owner decree 2026-08-10, task 207)

His report, translated: a frozen ellipsis told him nothing about whether the
app had hung — "downloading, three dots, no response at all ... I don't know
... whether it stalled or is working." # lang-ok: paraphrase of an owner quote
The same complaint covered the desktop's "Downloading…" button
([Main Window](../../server/gui/__about/main_window.md)) and this banner,
which used to swap a static toast for nothing further at all. The desktop can
watch real bytes land and show a real percentage; this page cannot — the
tapped `Android.update()` hands the URL to Android's OWN DownloadManager and
returns immediately, and no new bridge method exists to ask it for progress
(the shell is installed separately from this page, so a page that needed one
would go blank on an older shell). The honest answer is an INDETERMINATE
animated stripe plus a sentence naming where the download actually lives —
never a frozen number pretending to track a transfer this page cannot see.

## Key Functions

- `refreshUpdateBanner(apkVersion)` — called from `connection.js`'s `config`
  handler; shows/hides the banner by comparing `apkVersion` (what the PC
  SERVES) against `Android.appVersion()` (what this shell IS). Deliberately
  never compares against the desktop's own version — a release that changed
  only the desktop side offered a phantom phone update (owner bug
  2026-08-02).
- `isNewer(server, app)` / `versionNumbers(v)` — strict numeric compare
  (`0.0.9` must never beat `0.0.102`, which a string compare gets wrong).
- The `keepFocus(updateBanner, …)` tap handler — one-shot (`.downloading`
  guards a second tap), starts the download, and swaps the banner's icon for
  the bar plus the "check the notification shade" sentence.

## Design Decisions

- **One tap, ever.** `updateBanner.classList.contains("downloading")` refuses
  a second tap once the first has started — the banner cannot be told the
  download finished (no bridge for that either), so a repeat tap would only
  start a second, redundant DownloadManager job.
- **Indeterminate, not a fabricated percentage.** No polling, no fake
  progress ramp — `#update-banner-fill`'s CSS animation (`style.css`) is a
  plain looping sweep, the same honest shape the desktop bar falls back to
  when ITS response gives no `Content-Length`
  ([Main Window](../../server/gui/__about/main_window.md)).
- **The banner stays up rather than auto-hiding on a timer.** A vanishing
  banner mid-download would read exactly like the silent-disappearance bug
  this task exists to end; it is left showing the bar until the page's next
  `config` naturally refreshes it (a reconnect, or the update landing and
  `appVersion()` catching up).

## Used by

- `client/connection.js` — calls `refreshUpdateBanner(msg.apk_version ||
  msg.app_version)` from the `config` message handler.
