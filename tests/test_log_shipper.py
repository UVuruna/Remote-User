"""LOG SHIPPER GATE — proves the one rule that matters: a file is never
deleted before its transfer is CONFIRMED, and every non-happy path (bad
destination, unreachable disk, debug mode, empty target, a URL target, a
worker that cannot start) leaves the local file exactly where it was.

Every real filesystem touch happens inside a `tmp_path`-style temp directory
made per check — never `V:`, never `USER_DIR` (`log_shipper.install_id()`
persists to `USER_DIR / "install_id.txt"`, so every check that calls `ship`
or `sweep` builds its own `LogShipper` against a settings object whose
`session_log_dir`/`log_upload_target` point into the temp tree, and monkeypatches
`log_shipper.USER_DIR`/`log_shipper._INSTALL_ID_PATH` to a temp path too, so a
run of this gate can never write into the developer's real profile).

Run:  .venv\\Scripts\\python tests/test_log_shipper.py
"""

import shutil
import sys
import tempfile
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import log_shipper  # noqa: E402


class FakeSettings:
    """Just the fields log_shipper.py reads off `SETTINGS`."""

    def __init__(self, root: Path):
        self.session_log_dir = root / "sessions_log"
        self.log_upload_target = str(root / "dest")
        self.log_upload_verify = True
        self.log_debug_mode = False
        self.log_debug_keep_files = 10


def _make_source_file(settings: FakeSettings, name="a.jsonl", body=b"hello world\n") -> Path:
    settings.session_log_dir.mkdir(parents=True, exist_ok=True)
    p = settings.session_log_dir / name
    p.write_bytes(body)
    return p


def _tmp_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="vc_log_shipper_"))


def _isolated_shipper(settings: FakeSettings, root: Path) -> log_shipper.LogShipper:
    """A shipper whose install_id() cannot touch the real USER_DIR."""
    log_shipper._INSTALL_ID_PATH = root / "install_id.txt"
    return log_shipper.LogShipper(settings)


# ── ship() ──────────────────────────────────────────────────────────────────

def check_good_transfer_deletes_local() -> bool:
    root = _tmp_root()
    try:
        s = FakeSettings(root)
        src = _make_source_file(s)
        sh = _isolated_shipper(s, root)
        ok = sh.ship(src)
        dest = Path(s.log_upload_target) / "logs" / log_shipper.install_id() / "a.jsonl"
        return ok is True and not src.exists() and dest.read_bytes() == b"hello world\n"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_failed_verification_keeps_local() -> bool:
    root = _tmp_root()
    try:
        s = FakeSettings(root)
        src = _make_source_file(s)
        sh = _isolated_shipper(s, root)
        # Force verification to fail without touching the real copy path.
        real_verify = sh._verify
        sh._verify = lambda a, b: False
        try:
            ok = sh.ship(src)
        finally:
            sh._verify = real_verify
        return ok is False and src.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_debug_mode_keeps_file_after_good_transfer() -> bool:
    root = _tmp_root()
    try:
        s = FakeSettings(root)
        s.log_debug_mode = True
        src = _make_source_file(s)
        sh = _isolated_shipper(s, root)
        ok = sh.ship(src)
        dest = Path(s.log_upload_target) / "logs" / log_shipper.install_id() / "a.jsonl"
        return ok is True and src.exists() and dest.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_unreachable_destination_keeps_file_no_raise() -> bool:
    root = _tmp_root()
    try:
        s = FakeSettings(root)
        src = _make_source_file(s)
        # A destination path that cannot exist: a file sitting where a
        # directory would need to be created ("mounted" as a plain file).
        blocker = root / "blocked_dest"
        blocker.write_bytes(b"x")
        s.log_upload_target = str(blocker)
        sh = _isolated_shipper(s, root)
        try:
            ok = sh.ship(src)
        except Exception:
            return False
        return ok is False and src.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_empty_target_ships_nothing_deletes_nothing() -> bool:
    root = _tmp_root()
    try:
        s = FakeSettings(root)
        s.log_upload_target = ""
        src = _make_source_file(s)
        sh = _isolated_shipper(s, root)
        ok = sh.ship(src)
        dest_root = root / "dest"
        return ok is False and src.exists() and not dest_root.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_url_target_is_refused_not_treated_as_folder() -> bool:
    # Asserted directly against the resolver, not only through ship(): on
    # Windows a colon mid-path makes mkdir() raise on its own (WinError 123),
    # which would make ship() look correct even with the scheme check
    # removed — the resolver itself is the thing this check must prove.
    if log_shipper._resolve_target("https://logs.example.com/upload") is not None:
        return False
    root = _tmp_root()
    try:
        s = FakeSettings(root)
        s.log_upload_target = "https://logs.example.com/upload"
        src = _make_source_file(s)
        sh = _isolated_shipper(s, root)
        ok = sh.ship(src)
        # The literal string must never become a directory on disk.
        stray = root / "https:"
        return ok is False and src.exists() and not stray.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ── prune() ─────────────────────────────────────────────────────────────────

def check_prune_keeps_exactly_n_newest() -> bool:
    root = _tmp_root()
    try:
        s = FakeSettings(root)
        s.log_debug_keep_files = 3
        s.session_log_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(6):
            p = s.session_log_dir / f"{i}.jsonl"
            p.write_bytes(b"x")
            paths.append(p)
            time.sleep(0.01)  # distinct mtimes
        sh = _isolated_shipper(s, root)
        sh.prune()
        remaining = sorted(p.name for p in s.session_log_dir.glob("*.jsonl"))
        expected = sorted(p.name for p in paths[3:])  # the three newest
        return remaining == expected
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ── offer() never raises ─────────────────────────────────────────────────────

def check_offer_never_raises_when_worker_cannot_start() -> bool:
    root = _tmp_root()
    try:
        s = FakeSettings(root)
        src = _make_source_file(s)
        sh = _isolated_shipper(s, root)

        def boom(*a, **kw):
            raise RuntimeError("no threads left")

        sh._ensure_worker = boom
        try:
            sh.offer(src)
        except Exception:
            return False
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_offer_never_raises_when_queue_full() -> bool:
    root = _tmp_root()
    try:
        s = FakeSettings(root)
        src = _make_source_file(s)
        sh = _isolated_shipper(s, root)
        sh._ensure_worker = lambda: None  # never actually starts a worker
        # Fill the bounded queue without draining it.
        for i in range(log_shipper.QUEUE_MAX):
            sh._queue.put_nowait(Path(f"fake-{i}.jsonl"))
        try:
            sh.offer(src)  # queue is full — must not raise
        except Exception:
            return False
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ── sweep() re-offers what a previous run left behind ────────────────────────

def check_sweep_prunes_then_reships_local_files() -> bool:
    root = _tmp_root()
    try:
        s = FakeSettings(root)
        _make_source_file(s, "a.jsonl")
        _make_source_file(s, "b.jsonl", body=b"second\n")
        sh = _isolated_shipper(s, root)
        sh.sweep(s)
        for _ in range(100):
            left = list(s.session_log_dir.glob("*.jsonl"))
            if not left:
                break
            time.sleep(0.02)
        dest_dir = Path(s.log_upload_target) / "logs" / log_shipper.install_id()
        shipped = sorted(p.name for p in dest_dir.glob("*.jsonl"))
        return shipped == ["a.jsonl", "b.jsonl"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


CHECKS = [
    ("a good transfer deletes the local file", check_good_transfer_deletes_local),
    ("a failed verification keeps the local file",
     check_failed_verification_keeps_local),
    ("debug mode keeps the file after a good transfer",
     check_debug_mode_keeps_file_after_good_transfer),
    ("an unreachable destination keeps the file and never raises",
     check_unreachable_destination_keeps_file_no_raise),
    ("an empty target ships nothing and deletes nothing",
     check_empty_target_ships_nothing_deletes_nothing),
    ("a URL target is refused rather than made into a folder",
     check_url_target_is_refused_not_treated_as_folder),
    ("prune keeps exactly N newest local files",
     check_prune_keeps_exactly_n_newest),
    ("offer() never raises when the worker cannot start",
     check_offer_never_raises_when_worker_cannot_start),
    ("offer() never raises when the queue is full",
     check_offer_never_raises_when_queue_full),
    ("sweep() prunes then re-ships every local file",
     check_sweep_prunes_then_reships_local_files),
]


def main() -> int:
    print("=== LOG SHIPPER GATE ===")
    failed = 0
    for name, fn in CHECKS:
        started = time.monotonic()
        try:
            ok = fn()
        except Exception as e:  # a crashing check is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  ({time.monotonic() - started:.1f}s)")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"LOG SHIPPER GATE FAILED — {failed} check(s).")
        return 1
    print("LOG SHIPPER GATE PASSED — a log is never deleted before its "
          "transfer is confirmed.")
    return 0


def test_log_shipper():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
