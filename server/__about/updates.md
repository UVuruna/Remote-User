# Updates

**Script:** [Updates (script)](../updates.py)

## Purpose
Update discovery for the DESKTOP app via GitHub Releases (`SETTINGS.update_repo`, a public repo, unauthenticated API). `check()` compares the latest release tag against the running version (`config.app_version()`) and returns an `Update(version, installer_url, page_url)` when a newer release exists, else `None`.

The phone is deliberately NOT served from here: its update source is the PC itself — `config.app_version` over the WebSocket plus `/app.apk` on the same server (see [Web Layer](web.md)). One internet check per ecosystem; everything downstream updates from the PC (root Rule #23).

`None` is the documented result for: up to date, `update_check` disabled, a dev checkout (version `"dev"`, no digits to compare), a repo with no releases yet, or any network failure — all of those log at info and never raise, so the desktop app must start fine offline.

## Connections

### Uses
- [Config](config.md) — `update_repo`, `update_check`, `app_version()`

### Used by
- `gui/main_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — startup check on a worker thread → in-window Update button (download installer → launch → quit)

## Functions
- `check()`: compares the latest GitHub release tag against the running version — see below
- `_numbers(version)`: `"v0.0.37"` / `"0.0.037"` → `(0, 0, 37)`; empty tuple when nothing numeric (a dev checkout)

`check()` in order: bail to `None` if `update_check` is off or the running version has no digits (dev checkout); `GET` the repo's latest release (10 s timeout) and bail to `None` on any failure (offline, rate-limited, or a 404 from a repo with no releases yet); parse `tag_name` into numbers and bail to `None` if it is not strictly newer than the running version; otherwise return an `Update` with the first release asset ending in `.exe` (or `None`) and the release page URL as fallback.

## Classes
### Update
Frozen dataclass: `version`, `installer_url` (`None` when the release has no `.exe` asset), `page_url` (the release page — the fallback UX when there is no asset).
