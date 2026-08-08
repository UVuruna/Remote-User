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
- `gui/main_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — the check on a worker thread (at start and every 15 min) → in-window Update button → download
- [Update Handover](update_handover.md) — takes it from there: `Update.size` is what `verify()` compares the download against, and `numbers()` is how it answers "is the version now running the one we installed?"

## Functions
- `check()`: compares the latest GitHub release tag against the running version — see below
- `numbers(version)`: `"v0.0.37"` / `"0.0.037"` → `(0, 0, 37)`; empty tuple when nothing numeric (a dev checkout). Public because the two spellings never match as strings — a tag renders back as `0.0.93` while `app_info.json` says `0.0.093`.

`check()` in order: bail to `None` if `update_check` is off or the running version has no digits (dev checkout); `GET` the repo's latest release (10 s timeout) and bail to `None` on any failure (offline, rate-limited, or a 404 from a repo with no releases yet); parse `tag_name` into numbers and bail to `None` if it is not strictly newer than the running version; otherwise return an `Update` built from the first release asset ending in `.exe` (or `None`) and the release page URL as fallback.

## Classes
### Update
Frozen dataclass: `version`, `installer_url` (`None` when the release has no `.exe` asset), `page_url` (the release page — the fallback UX when there is no asset), `size` (the asset's byte count as GitHub reports it, `None` when there is no asset).

`size` exists for one reason: a download cut short by a dropped Wi-Fi is an ordinary event, and running a truncated installer is the ONE failure that can leave the owner with a PC he cannot reach until he is standing in front of it ([Update Handover](update_handover.md) → `verify`).
