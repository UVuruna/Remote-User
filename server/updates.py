"""Update discovery via GitHub Releases (the project's GIT RELEASE artifacts).

`check()` compares the latest release tag of SETTINGS.update_repo against the
running version and returns an Update when a newer one exists, else None.
Callers own the UX: the desktop GUI shows an in-window Update button (which
downloads and launches the installer); the phone is NOT served from here —
its update comes from the PC server itself (`config.app_version` + /app.apk).

A repo with no releases yet and plain network failures are normal outcomes
(documented: check() returns None then) — logged at info, never raised.
"""

import json
import logging
import re
import urllib.request
from dataclasses import dataclass

from config import SETTINGS, app_version

logger = logging.getLogger(__name__)

TIMEOUT_S = 10


@dataclass(frozen=True)
class Update:
    version: str            # e.g. "0.0.037"
    installer_url: str | None  # direct Setup.exe asset, if the release has one
    page_url: str           # the release page — fallback when there is no asset


def _numbers(version: str) -> tuple[int, ...]:
    """'v0.0.37' / '0.0.037' → (0, 0, 37); () when nothing numeric (dev)."""
    return tuple(int(p) for p in re.findall(r"\d+", version)[:3])


def check() -> Update | None:
    """None = up to date, disabled, dev run, no releases yet, or unreachable."""
    if not SETTINGS.update_check:
        return None
    current = _numbers(app_version())
    if not current:
        return None  # dev checkout — nothing meaningful to compare
    url = f"https://api.github.com/repos/{SETTINGS.update_repo}/releases/latest"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
            data = json.loads(response.read())
    except Exception as e:  # offline / rate-limited / no releases yet (404)
        logger.info("Update check skipped: %s", e)
        return None
    latest = _numbers(data.get("tag_name") or "")
    if not latest or latest <= current:
        return None
    installer = next(
        (a.get("browser_download_url") for a in data.get("assets", [])
         if a.get("name", "").endswith(".exe")),
        None,
    )
    version = ".".join(str(n) for n in latest)
    logger.info("Update available: v%s (running v%s)", version, app_version())
    return Update(version, installer, data.get("html_url") or
                  f"https://github.com/{SETTINGS.update_repo}/releases")
