# Updates

**Script:** [Updates (script)](updates.py)

## Purpose
Update discovery for the DESKTOP app via GitHub Releases (`SETTINGS.update_repo`, public repo — unauthenticated API). `check()` compares the latest release tag against the running version (`config.app_version()`) and returns an `Update(version, installer_url, page_url)` when a newer release exists, else `None`.

The phone is deliberately NOT served from here: its update source is the PC itself — `config.app_version` over the WebSocket plus `/app.apk` on the same server (see [Web Layer](web.md)). One internet check per ecosystem; everything downstream updates from the PC.

`None` is the documented result for: up to date, `update_check` disabled, a dev checkout (version "dev"), a repo with no releases yet, or any network failure — those log at info and never raise (the desktop must start fine offline).

## Pseudocode

```
check():
    IF update_check disabled OR running version has no numbers → None
    GET api.github.com/repos/<update_repo>/releases/latest (10 s timeout)
    ON any failure → log info, None
    latest = numbers from tag_name ("v0.0.37" → 0,0,37)
    IF latest <= current → None
    installer_url = first release asset ending in .exe (or None)
    RETURN Update(latest, installer_url, release page URL)
```

## Connections

### Uses
- [Config](config.md) — `update_repo`, `update_check`, `app_version()`

### Used by
- [Main Window](gui/main_window.md) — startup check → in-window Update button (download installer → launch → quit)
