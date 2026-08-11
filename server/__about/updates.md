# Updates

**Script:** [Updates (script)](../updates.py)

## Purpose
Update discovery for the DESKTOP app via GitHub Releases (`SETTINGS.update_repo`, a public repo, unauthenticated API). `check()` compares the latest release tag against the running version (`config.app_version()`) and returns an `Update(version, installer_url, page_url)` when a newer release exists, else `None`.

The phone is deliberately NOT served from here: its update source is the PC itself — `config.app_version` over the WebSocket plus `/app.apk` on the same server (see [Web Layer](web.md)). One internet check per ecosystem; everything downstream updates from the PC (the Self-Update rule, rules/SHIP.md).

`None` is the documented result for: up to date, `update_check` disabled, a dev checkout (version `"dev"`, no digits to compare), a repo with no releases yet, or any network failure — all of those log at info and never raise, so the desktop app must start fine offline.

## Connections

### Uses
- [Config](config.md) — `update_repo`, `update_check`, `app_version()`

### Used by
- `gui/main_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — the check on a worker thread (at start and every 15 min) → in-window Update button → `download()` on a worker thread, reporting into `_update_progress` for the progress bar
- [Update Handover](update_handover.md) — takes it from there: `Update.size` is what `verify()` compares the download against, and `numbers()` is how it answers "is the version now running the one we installed?"

## Functions
- `check()`: compares the latest GitHub release tag against the running version — see below
- `numbers(version)`: `"v0.0.37"` / `"0.0.037"` → `(0, 0, 37)`; empty tuple when nothing numeric (a dev checkout). Public because the two spellings never match as strings — a tag renders back as `0.0.93` while `app_info.json` says `0.0.093`.
- `download(url, dest, on_progress=None, timeout=30)`: streams `url` to `dest` in `DOWNLOAD_CHUNK_BYTES`-sized chunks, calling `on_progress(received, total)` once before the first chunk and once after every chunk after (task 207, owner decree 2026-08-10 — "ne znam da li je blokirao ili radi", the frozen "Downloading…" ellipsis). `total` is the response's own `Content-Length` as an `int`, or `None` when the response gave none — that `None` is deliberate: `download()` never fabricates a size from anything else, because a caller showing a percentage against an invented total would be lying just as much as a frozen ellipsis was. The caller decides what `None` means on screen — `gui/main_window.py` reads it as "show the indeterminate bar". Raises whatever `urllib` raises on a network failure; the caller decides what a failed download means for its own state.

`check()` in order: bail to `None` if `update_check` is off or the running version has no digits (dev checkout); `GET` the repo's latest release (10 s timeout) and bail to `None` on any failure (offline, rate-limited, or a 404 from a repo with no releases yet); parse `tag_name` into numbers and bail to `None` if it is not strictly newer than the running version; otherwise return an `Update` built from the first release asset ending in `.exe` (or `None`) and the release page URL as fallback.

The "strictly newer, compared as NUMBERS" line is a fork guard in its own right (verified 2026-08-09, the 20-install fork): every handover the fork armed was fed from here, so a compare that let a release equal to — or a string compare that let `"0.0.9"` beat — the running version would hand a freshly installed app a reason to arm the installer again. Pinned by the version-compare check in `tests/test_update_handover.py`, fail-closed in `build.py` (0i/6).

## Classes
### Update
Frozen dataclass: `version`, `installer_url` (`None` when the release has no `.exe` asset), `page_url` (the release page — the fallback UX when there is no asset), `size` (the asset's byte count as GitHub reports it, `None` when there is no asset).

`size` exists for one reason: a download cut short by a dropped Wi-Fi is an ordinary event, and running a truncated installer is the ONE failure that can leave the owner with a PC he cannot reach until he is standing in front of it ([Update Handover](update_handover.md) → `verify`).
