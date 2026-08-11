"""Update discovery via GitHub Releases (the project's GIT RELEASE artifacts).

`check()` compares the latest release tag of SETTINGS.update_repo against the
running version and returns an Update when a newer one exists, else None.
`download()` is the streaming fetch that button's worker thread runs — it
reports (received, total) bytes after every chunk so the GUI can show a real
progress bar, `total` being None whenever the response gave no Content-Length
(task 207, owner decree 2026-08-10). Callers own the UX: the desktop GUI shows
an in-window Update button (which downloads and launches the installer); the
phone is NOT served from here — its update comes from the PC server itself
(`config.app_version` + /app.apk).

A repo with no releases yet and plain network failures are normal outcomes
(documented: check() returns None then) — logged at info, never raised.
"""

import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from config import SETTINGS, app_version

logger = logging.getLogger(__name__)

TIMEOUT_S = 10
DOWNLOAD_CHUNK_BYTES = 256 * 1024


@dataclass(frozen=True)
class Update:
    version: str            # e.g. "0.0.037"
    installer_url: str | None  # direct Setup.exe asset, if the release has one
    page_url: str           # the release page — fallback when there is no asset
    # What GitHub says the asset weighs. The handover compares it with what
    # actually landed on disk before it hands the PC over to that file: a
    # download cut short by a Wi-Fi drop is a perfectly ordinary event, and
    # running a truncated installer is the one failure that could leave the
    # owner with no way back in (server/update_handover.py -> verify).
    size: int | None = None


def numbers(version: str) -> tuple[int, ...]:
    """'v0.0.37' / '0.0.037' → (0, 0, 37); () when nothing numeric (dev).

    Public because the handover has to answer a question of its own after the
    installer ran — "is the version now running the one we installed?" — and
    the two spellings never match as strings: a tag renders back as '0.0.93'
    while `app_info.json` says '0.0.093'.
    """
    return tuple(int(p) for p in re.findall(r"\d+", version)[:3])


def check(force: bool = False) -> Update | None:
    """None = up to date, disabled, dev run, no releases yet, or unreachable.

    `force` is the owner ASKING, right now (2026-08-09: "trebao bi da imam
    opciju i tu na licu mesta da proverim novu verziju, neki button, a ne da
    moram restart aplikacije"). The setting below governs the automatic check
    at START; it must never gag a check he pressed a button for — a switch
    that silently swallows a deliberate action is the worst kind.
    """
    if not force and not SETTINGS.update_check:
        return None
    current = numbers(app_version())
    if not current:
        return None  # dev checkout — nothing meaningful to compare
    url = f"https://api.github.com/repos/{SETTINGS.update_repo}/releases/latest"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
            data = json.loads(response.read())
    except Exception as e:  # offline / rate-limited / no releases yet (404)
        logger.info("Update check skipped: %s", e)
        return None
    latest = numbers(data.get("tag_name") or "")
    if not latest or latest <= current:
        return None
    asset = next(
        (a for a in data.get("assets", []) if a.get("name", "").endswith(".exe")),
        None,
    )
    version = ".".join(str(n) for n in latest)
    logger.info("Update available: v%s (running v%s)", version, app_version())
    return Update(version,
                  asset.get("browser_download_url") if asset else None,
                  data.get("html_url") or
                  f"https://github.com/{SETTINGS.update_repo}/releases",
                  asset.get("size") if asset else None)


def download(url: str, dest: Path,
             on_progress: Callable[[int, int | None], None] | None = None,
             timeout: int = 30) -> None:
    """Stream `url` to `dest`, reporting bytes as they land.

    `on_progress(received, total)` is called once before the first chunk and
    once after every chunk that follows. `total` is the response's own
    Content-Length as an int, or None when it did not send one — that None is
    the whole point of this function's shape (owner decree 2026-08-10, task
    207: "ne znam da li je blokirao ili radi" — a frozen "Downloading…" told
    him nothing about whether the app had hung). The CALLER decides what None
    means on screen (an indeterminate bar); this function only reports what
    the response actually said, honestly, never guessing a size it was not
    given.

    Chunked with a socket timeout — `urllib.request.urlretrieve` has none,
    and a mid-transfer stall (Wi-Fi drop, CDN hang) would otherwise hang this
    call forever with no way for the caller to notice and retry. Raises
    whatever `urllib` raises on a network failure; the caller decides what a
    failed download means for its own UI state.
    """
    with urllib.request.urlopen(url, timeout=timeout) as response, \
            open(dest, "wb") as out:
        length = response.headers.get("Content-Length")
        total = int(length) if length and length.isdigit() else None
        received = 0
        if on_progress:
            on_progress(received, total)
        while chunk := response.read(DOWNLOAD_CHUNK_BYTES):
            out.write(chunk)
            received += len(chunk)
            if on_progress:
                on_progress(received, total)
