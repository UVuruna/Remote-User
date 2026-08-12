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
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from config import SETTINGS, app_version

logger = logging.getLogger(__name__)

TIMEOUT_S = 10
DOWNLOAD_CHUNK_BYTES = 256 * 1024
# THE APP DOES ITS OWN RETRYING (owner report 2026-08-12, with his screenshot
# of the button reading "Update download failed — retry": *"ovo mi se u zadnje
# vreme dešava pa treba par puta da se klikne button"* — lang-ok: owner quote).
# Four attempts with a short backoff, and the backoff RESETS whenever an
# attempt actually moved bytes — a transfer that stalled at 80 MB is a
# different animal from a link that never opened, and treating them the same
# either gives up on the first or hammers a dead host.
DOWNLOAD_ATTEMPTS = 4
DOWNLOAD_BACKOFF_S = (1.0, 3.0, 6.0)


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
    last: Exception | None = None
    for attempt in range(DOWNLOAD_ATTEMPTS):
        have = dest.stat().st_size if dest.exists() else 0
        try:
            _download_once(url, dest, have, on_progress, timeout)
            return
        except _AlreadyComplete:
            # The file on disk is the whole asset: a previous attempt finished
            # and only the caller's bookkeeping was lost. The server answers
            # 416 to a Range that starts at the end, and treating that as a
            # failure would make a COMPLETE download look broken forever.
            if on_progress:
                size = dest.stat().st_size
                on_progress(size, size)
            return
        except Exception as e:  # noqa: BLE001 — every network failure retries
            last = e
            moved = (dest.stat().st_size if dest.exists() else 0) > have
            logger.warning("Update download attempt %d/%d failed after %s: %s",
                           attempt + 1, DOWNLOAD_ATTEMPTS,
                           "progress" if moved else "no progress", e)
            if attempt == DOWNLOAD_ATTEMPTS - 1:
                break
            # A stall that still moved bytes gets the shortest pause: the link
            # is alive and the next attempt resumes where this one stopped.
            delay = DOWNLOAD_BACKOFF_S[0] if moved else DOWNLOAD_BACKOFF_S[
                min(attempt, len(DOWNLOAD_BACKOFF_S) - 1)]
            time.sleep(delay)
    raise last if last is not None else RuntimeError("download failed")


class _AlreadyComplete(Exception):
    """The bytes on disk ARE the asset — a 416 to our own resume request."""


def _download_once(url: str, dest: Path, have: int,
                   on_progress: Callable[[int, int | None], None] | None,
                   timeout: int) -> None:
    """One attempt, RESUMING from `have` bytes already on disk.

    Resuming is the half of this that the owner actually feels. The installer
    is ~113 MB; before this, one hiccup at 90% discarded all of it and his
    next click started from zero — which is exactly why several clicks were
    needed and why each one took as long as the first.
    """
    request = urllib.request.Request(url)
    if have:
        request.add_header("Range", f"bytes={have}-")
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as e:
        if have and e.code == 416:
            raise _AlreadyComplete from e
        raise
    with response, open(dest, "ab" if _is_partial(response, have) else "wb") as out:
        if not _is_partial(response, have):
            # The server IGNORED the Range (200, not 206) — it is sending the
            # whole file, so the bytes on disk are about to be replaced and
            # nothing may be counted twice.
            have = 0
        length = response.headers.get("Content-Length")
        remaining = int(length) if length and length.isdigit() else None
        total = have + remaining if remaining is not None else None
        received = have
        if on_progress:
            on_progress(received, total)
        while chunk := response.read(DOWNLOAD_CHUNK_BYTES):
            out.write(chunk)
            received += len(chunk)
            if on_progress:
                on_progress(received, total)
    # A STREAM THAT ENDS EARLY ENDS CLEANLY (found by this function's own gate,
    # 2026-08-12). A CDN that drops the connection mid-transfer does not raise:
    # `read` simply returns b"" and the loop exits, so a truncated file would
    # be reported as a finished download and the button would go to "ready".
    # The response told us how much it was sending; short of that is a failure,
    # and raising here is what lets the retry above resume the rest. The
    # handover's own size check would eventually refuse the file — but only
    # after telling him it was ready, which is the wrong place to find out.
    if total is not None and received < total:
        raise IncompleteDownload(
            f"the stream ended at {received} of {total} bytes")


class IncompleteDownload(OSError):
    """The response ended before it delivered the length it announced."""


def _is_partial(response, have: int) -> bool:
    return bool(have) and getattr(response, "status", None) == 206


# Human-readable failure names for the desktop Update button. Kept HERE and
# not in the GUI: this module owns the transfer, so it owns what its own
# failures mean; the window only puts the sentence on the button. Every arm
# ends in "retry" because the button IS the retry, and a reason with no next
# step is just bad news (owner 2026-08-12 — the generic message told him
# nothing, and by the time he sees it the app has already tried four times).
_REASONS = (
    (urllib.error.HTTPError, "GitHub refused the download — retry"),
    (urllib.error.URLError, "No connection to GitHub — retry"),
    (TimeoutError, "The download timed out — retry"),
    (OSError, "Could not write the installer to disk — retry"),
)


def failure_reason(error: Exception) -> str:
    """One short sentence naming WHY, for the button."""
    if isinstance(error, urllib.error.HTTPError):
        return f"GitHub refused the download ({error.code}) — retry"
    for kind, text in _REASONS:
        if isinstance(error, kind):
            return text
    return "Update download failed — retry"
