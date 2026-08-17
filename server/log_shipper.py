"""Moves a FINISHED use-log file off the local disk, and only off the local
disk once the copy is PROVEN to have arrived.

WHY THIS EXISTS AT ALL: `session_log.py` writes evidence for a bug that has
not happened yet, so it must survive the machine it was written on outliving
its own disk, its own crash, and — in the shipping default — the file never
being kept locally at all (`log_debug_mode` is the owner's own carve-out,
config.py). None of that is this module's business to decide; it only knows
how to move a file and prove it moved.

THE ONE RULE THAT MATTERS: delete-before-confirm must be IMPOSSIBLE. A copy
to another disk can land short — that is the entire reason `ship()` re-reads
the ARRIVED bytes and hashes them rather than trusting the copy call's return
value. The local file is deleted only after that check passes, and never at
all in debug mode, however good the transfer was.

DESTINATION KIND IS DECIDED IN ONE PLACE (`_resolve_target`), because
`log_upload_target` is a setting that is a folder path TODAY and is meant to
become an HTTP URL later (config.py's own comment). A URL landing here before
that code exists must be REFUSED with a clear reason, never silently treated
as a folder name — a stray `https://` would otherwise become a directory
called "https:" next to the real ones. An EMPTY target is the honest default
for a stranger's fresh install: nothing is shipped, nothing is deleted, one
INFO line, never an error.

THE CALLER MUST NEVER BLOCK OR RAISE. `offer()` is called from the server's
teardown path and from a phone connection's own thread — a full disk, a
missing drive, or a worker thread that failed to start must never turn into a
hung shutdown or a broken connection. One worker thread drains a bounded
queue; anything that cannot be queued (queue full, worker never started) is
logged and dropped rather than raised.

A DESTINATION THAT IS UNREACHABLE (the disk unplugged) is not an error, it is
Tuesday: the file stays local and `sweep()` — run once at start — offers it
again. Nothing is ever lost to a missing drive; it just waits.

WHAT THIS MODULE DOES NOT KNOW: what is inside the file. `session_log.py`
writes lines and rolls files; this one moves, verifies, deletes and prunes
them by name and mtime alone.
"""

import hashlib
import logging
import queue
import shutil
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

from config import SETTINGS, USER_DIR

logger = logging.getLogger(__name__)

# How many finished files can wait for the worker before `offer()` starts
# dropping them. Bounded on purpose: a shipper that is stuck (destination
# gone, worker dead) must not let the queue itself become the unbounded disk
# fill this module exists to prevent.
QUEUE_MAX = 200

_INSTALL_ID_PATH = USER_DIR / "install_id.txt"


def install_id() -> str:
    """A random per-install identifier, created on first use and read back
    after. Deliberately NOT hardware-derived (root CLAUDE.md — no capacity for
    fingerprinting a stranger's machine, and a swapped disk or a reinstall
    would silently change a hardware id anyway, which would look like a
    second installation in the destination's folder layout for no reason)."""
    try:
        existing = _INSTALL_ID_PATH.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass
    new_id = uuid.uuid4().hex
    try:
        _INSTALL_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
        _INSTALL_ID_PATH.write_text(new_id, encoding="utf-8")
    except OSError as e:
        # Can't persist it — still hand back a value so shipping isn't
        # blocked by a read-only USER_DIR; it just won't survive a restart.
        logger.warning("Log shipper: cannot persist install id (%s)", e)
    return new_id


def _sha256(path: Path) -> str | None:
    """Streamed so a multi-megabyte log never sits in memory twice."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _resolve_target(target: str) -> Path | None:
    """The ONE place that decides what kind of destination `log_upload_target`
    is. Returns a directory Path for a filesystem target, or None for an
    empty/unimplemented target — the caller tells those apart by the log line
    already written here, not by re-inspecting the string itself."""
    target = (target or "").strip()
    if not target:
        return None
    scheme = urlparse(target).scheme
    if scheme in ("http", "https"):
        logger.info("Log shipper: log_upload_target=%r is a URL — HTTP "
                    "upload is not implemented yet, keeping files local",
                    target)
        return None
    return Path(target)


class LogShipper:
    """Owns one background worker draining a bounded queue of finished log
    files. Safe to construct with logging disabled or no destination
    configured — it simply never moves anything."""

    def __init__(self, settings=SETTINGS):
        self._s = settings
        self._queue: queue.Queue[Path] = queue.Queue(maxsize=QUEUE_MAX)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ---- the public interface session_log.py uses -----------------------

    def offer(self, path: Path) -> None:
        """Queue a finished file for shipping. Never raises, never blocks:
        the caller is server teardown and a phone connection's own thread,
        neither of which may hang or die because a disk is unplugged."""
        try:
            self._ensure_worker()
            self._queue.put_nowait(Path(path))
        except Exception as e:  # queue full, worker failed, anything at all
            logger.warning("Log shipper: could not queue %s (%s)", path, e)

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            try:
                t = threading.Thread(target=self._run, daemon=True,
                                     name="log-shipper")
                t.start()
            except Exception as e:
                # A thread that never started leaves files queued forever —
                # log it once; offer() has already returned without raising.
                logger.warning("Log shipper: worker thread failed to start "
                               "(%s) — files will ship on the next sweep()", e)
                return
            self._thread = t

    def _run(self) -> None:
        while True:
            path = self._queue.get()
            try:
                self.ship(path)
            except Exception as e:  # the worker must never die mid-queue
                logger.warning("Log shipper: unexpected failure on %s (%s)",
                               path, e)

    # ---- the actual transfer ---------------------------------------------

    def ship(self, path: Path) -> bool:
        """Copy one file to the configured destination, verify it, and
        delete the local copy only when verification passed and debug mode
        is off. Returns whether the transfer was CONFIRMED (a no-op — empty
        target, missing source — is not a confirmed transfer)."""
        path = Path(path)
        if not path.is_file():
            return False  # already shipped, or never existed

        target_dir = _resolve_target(self._s.log_upload_target)
        if target_dir is None:
            return False  # covered by _resolve_target's own log line

        dest_dir = target_dir / "logs" / install_id()
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # The drive is probably unplugged. Not an error — a wait.
            logger.info("Log shipper: destination unreachable (%s) — "
                        "keeping %s local for the next try", e, path.name)
            return False

        dest_path = dest_dir / path.name
        try:
            shutil.copy2(path, dest_path)
        except OSError as e:
            logger.info("Log shipper: copy of %s failed (%s) — keeping it "
                        "local for the next try", path.name, e)
            return False

        confirmed = self._verify(path, dest_path)
        if not confirmed:
            logger.warning("Log shipper: %s did not verify after copying — "
                           "keeping the local file", path.name)
            return False

        logger.info("Log shipper: %s shipped to %s", path.name, dest_dir)
        if self._s.log_debug_mode:
            return True  # owner's carve-out: keep the local copy anyway
        try:
            path.unlink()
        except OSError as e:
            # Shipped and verified but couldn't delete — not a failure of
            # the transfer itself; prune() will catch up on it later.
            logger.warning("Log shipper: could not delete shipped %s (%s)",
                           path.name, e)
        return True

    def _verify(self, src: Path, dest: Path) -> bool:
        """Re-reads the ARRIVED bytes — never trusts `shutil.copy2`'s return
        value, which says nothing about what actually landed on the other
        disk. Size first (cheap, catches a short copy immediately), then a
        full hash when `log_upload_verify` asks for it."""
        try:
            src_size = src.stat().st_size
            dest_size = dest.stat().st_size
        except OSError:
            return False
        if src_size != dest_size:
            return False
        if not self._s.log_upload_verify:
            return True
        return _sha256(src) == _sha256(dest)

    # ---- retention ---------------------------------------------------------

    def prune(self) -> None:
        """Keep at most `log_debug_keep_files` local *.jsonl files, newest
        first, regardless of why they are still here. Runs whether debug mode
        is on or off — a failed transfer can leave files behind even when the
        normal outcome is zero, so this is a defensive bound, not a feature
        of debug mode."""
        d = Path(self._s.session_log_dir)
        if not d.is_dir():
            return
        keep = max(0, int(self._s.log_debug_keep_files))
        files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime,
                       reverse=True)
        for stale in files[keep:]:
            try:
                stale.unlink()
            except OSError as e:
                logger.warning("Log shipper: could not prune %s (%s)",
                               stale.name, e)

    # ---- start-of-run catch-up ---------------------------------------------

    def sweep(self, settings=None) -> None:
        """Called once at start: prune, then re-offer every local file that
        still exists — the ones a previous run's transfer never confirmed,
        or that arrived while the destination was unreachable."""
        s = settings or self._s
        d = Path(s.session_log_dir)
        self.prune()
        if not d.is_dir():
            return
        for path in sorted(d.glob("*.jsonl")):
            self.offer(path)


# The one live shipper. Constructing it touches no disk beyond reading
# settings — nothing is queued or shipped until something calls offer/sweep.
SHIPPER = LogShipper()
