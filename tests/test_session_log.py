"""SESSION LOG GATE — proves `server/session_log.py`'s contract, the module
that had NO gate of its own even though `log_shipper.py`, `log_summary.py`
and `display_watch.py` beside it all did.

The header is written once, at open, and carries only what cannot change
while the process lives; `record()` writes one flushed JSON line per call
and counts it under both its full `kind` and its `group`; the file rolls at
the local day boundary (`session_log_roll_hours`) AND at the byte ceiling
(`session_log_max_bytes`), and the new file's header carries `rolled_from`;
`close()` writes exactly one footer and returns the closed path;
`is_unclosed()` reads only the file's TAIL and is true for a missing footer
or a half-written last line, false for a real one; `repair_unclosed()`
footers an abandoned file with `reason: "unclosed"`, invents no end time,
offers it to the shipper, and skips the file named by `skip`;
`session_log_enabled = False` makes every entry point a silent no-op; and a
write failure never raises into the caller.

Every check is proven against a PLANTED defect: the real module's source
text is read, one exact substitution is applied (each `old` string must
appear exactly once — a substitution that matches nothing, or matches more
than once, proves nothing), and the patched text is exec'd as a fresh module
under a scratch name — the real, already-imported `session_log` is never
touched. This is the `tests/test_session_ledger.py` technique, used here
because `session_log.py` is pure, importable Python with no ctypes/dxcam
seam to fake.

Every real filesystem touch happens inside a fresh `tempfile.mkdtemp()` tree
per check — never `USER_DIR`, never a real disk the owner cares about.

Run:  .venv\\Scripts\\python tests/test_session_log.py
"""

import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

PROJECT = Path(__file__).resolve().parent.parent
SERVER = PROJECT / "server"
sys.path.insert(0, str(SERVER))

import session_log  # noqa: E402

LOG_PY = SERVER / "session_log.py"

DEFECTS = {
    "header written once, at open, no duplicate on a second start()":
        "drop the `if self._fh is not None: return` guard in start() — a "
        "second start() call reopens and writes a second header",
    "record() counts a kind under BOTH its full kind and its group":
        "drop the `self._counts[group] = ...` line in _record_locked",
    "the file rolls at the BYTE ceiling, new header carries rolled_from":
        "drop the byte half of the roll condition in _record_locked",
    "the file rolls at the DAY boundary, new header carries rolled_from":
        "drop the day half of the roll condition in _record_locked",
    "close() writes exactly ONE footer and returns the closed path":
        "duplicate the footer _write() call in _close",
    "is_unclosed(): true for missing/half-written footer, false for a real one":
        "invert the `!= \"footer\"` comparison in is_unclosed",
    "is_unclosed() reads the TAIL, never the whole file":
        "change `fh.seek(max(0, size - 4096))` to `fh.seek(0)`",
    "repair_unclosed(): reason unclosed, no invented duration, offered, "
    "skip is honoured":
        "drop the `skip` guard in repair_unclosed — the file the caller is "
        "about to open itself would get footered too",
    "session_log_enabled = False: every entry point is a silent no-op":
        "make start() ignore the enabled flag",
    "a write failure closes the log instead of raising into the caller":
        "drop the try/except around fh.write/flush in _write",
}


def _load_patched(old: str, new: str, mod_name: str):
    """Read session_log.py, apply exactly one substitution, exec it as a
    fresh module under `mod_name`. The real, already-imported `session_log`
    module is never touched."""
    text = LOG_PY.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"plant text appears {count} times, want 1: {old!r}")
    text = text.replace(old, new, 1)
    spec = importlib.util.spec_from_file_location(mod_name, LOG_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    exec(compile(text, str(LOG_PY), "exec"), mod.__dict__)
    return mod


class FakeSettings:
    """Just the fields session_log.py reads off `SETTINGS`."""

    def __init__(self, root: Path, *, roll_hours=24.0, max_bytes=8_000_000,
                 enabled=True):
        self.session_log_dir = root / "sessions_log"
        self.session_log_roll_hours = roll_hours
        self.session_log_max_bytes = max_bytes
        self.session_log_enabled = enabled


class FakeShipper:
    def __init__(self):
        self.offered: list[Path] = []

    def offer(self, path: Path) -> None:
        self.offered.append(path)


class BadFile:
    """A file handle that always fails to write, exactly like a disk that
    stopped answering — but never fails to close."""

    def write(self, _data):
        raise OSError("simulated: disk is gone")

    def flush(self):
        raise OSError("simulated: disk is gone")

    def close(self):
        pass


def _tmp_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="vc_session_log_"))


def _lines(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    if not condition:
        FAILURES.append(f"{name}: {detail}")
    return condition


# ═══════════════════════════ THE CHECKS ═══════════════════════════

def check_header_once_no_duplicate() -> bool:
    root = _tmp_root()
    try:
        settings = FakeSettings(root)
        log = session_log.SessionLog(settings=settings)
        log.start(app_version="1.2.3")
        path = log.path
        recs = _lines(path)
        if not check("header: written", len(recs) == 1, f"got {len(recs)} lines"):
            return False
        header = recs[0]
        if not check("header: shape",
                     header.get("kind") == "header"
                     and header.get("schema") == session_log.SCHEMA
                     and header.get("app_version") == "1.2.3"
                     and "at" in header and "epoch" in header,
                     f"header={header}"):
            return False

        # A second start() while already open must be a no-op.
        log.start(app_version="9.9.9")
        recs2 = _lines(path)
        if not check("header: second start() writes nothing new",
                     len(recs2) == 1, f"got {len(recs2)} lines after 2nd start()"):
            return False

        # Prove the plant would break it.
        old = ("        with self._lock:\n"
               "            if self._fh is not None:\n"
               "                return\n"
               "            self._open(_now(), facts)")
        new = ("        with self._lock:\n"
               "            self._open(_now(), facts)")
        patched = _load_patched(old, new, "session_log_plant_header_once")
        proot = _tmp_root()
        try:
            psettings = FakeSettings(proot)
            plog = patched.SessionLog(settings=psettings)
            plog.start(app_version="1")
            plog.start(app_version="2")
            precs = _lines(plog.path)
            if not check("header: plant reopens on a second start()",
                         len(precs) == 2,
                         f"plant should have written 2 headers, got {len(precs)}"):
                return False
        finally:
            shutil.rmtree(proot, ignore_errors=True)
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_record_counts_kind_and_group() -> bool:
    root = _tmp_root()
    try:
        settings = FakeSettings(root)
        log = session_log.SessionLog(settings=settings)
        log.start(app_version="1")
        log.record("use.button", label="a")
        log.record("use.button", label="b")
        log.record("fault.capture", err="e")
        path = log.close("stop")
        footer = _lines(path)[-1]
        counts = footer["counts"]
        if not check("counts: full kind + group both present",
                     counts.get("use.button") == 2 and counts.get("use") == 2
                     and counts.get("fault.capture") == 1 and counts.get("fault") == 1,
                     f"counts={counts}"):
            return False

        old = "        self._counts[group] = self._counts.get(group, 0) + 1\n"
        new = ""
        patched = _load_patched(old, new, "session_log_plant_group_count")
        proot = _tmp_root()
        try:
            psettings = FakeSettings(proot)
            plog = patched.SessionLog(settings=psettings)
            plog.start(app_version="1")
            plog.record("use.button", label="a")
            pfooter = _lines(plog.close("stop"))[-1]
            if not check("counts: plant drops the group total",
                         "use" not in pfooter["counts"],
                         f"plant counts={pfooter['counts']}"):
                return False
        finally:
            shutil.rmtree(proot, ignore_errors=True)
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_rolls_at_byte_ceiling() -> bool:
    root = _tmp_root()
    try:
        settings = FakeSettings(root, roll_hours=24.0, max_bytes=200)
        log = session_log.SessionLog(settings=settings)
        log.start(app_version="1")
        first_name = log.path.name
        # File names carry whole-second precision — sleep past the second
        # boundary so the rolled file is not the SAME name as the original
        # (which would silently append instead of opening a second file).
        time.sleep(1.1)
        for i in range(20):
            log.record("use.button", label="x" * 20, i=i)
        files = sorted(root.glob("sessions_log/*.jsonl"))
        if not check("byte roll: a second file was opened",
                     len(files) == 2, f"got {len(files)} files: {files}"):
            return False
        new_header = _lines(log.path)[0]
        if not check("byte roll: new header carries rolled_from",
                     new_header.get("rolled_from") == first_name,
                     f"new_header={new_header}"):
            return False
        log.close("stop")

        old = ("        if t >= self._roll_at or self._bytes >= self._s.session_log_max_bytes:\n"
               "            why = \"size\" if self._bytes >= self._s.session_log_max_bytes else \"day\"")
        new = ("        if t >= self._roll_at:\n"
               "            why = \"day\"")
        patched = _load_patched(old, new, "session_log_plant_byte_roll")
        proot = _tmp_root()
        try:
            psettings = FakeSettings(proot, roll_hours=24.0, max_bytes=200)
            plog = patched.SessionLog(settings=psettings)
            plog.start(app_version="1")
            for i in range(20):
                plog.record("use.button", label="x" * 20, i=i)
            pfiles = sorted(proot.glob("sessions_log/*.jsonl"))
            if not check("byte roll: plant never rolls on size",
                         len(pfiles) == 1, f"plant produced {len(pfiles)} files"):
                return False
        finally:
            shutil.rmtree(proot, ignore_errors=True)
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_rolls_at_day_boundary() -> bool:
    root = _tmp_root()
    try:
        settings = FakeSettings(root, roll_hours=24.0, max_bytes=8_000_000)
        log = session_log.SessionLog(settings=settings)
        log.start(app_version="1")
        first_name = log.path.name
        time.sleep(1.1)  # see the byte-roll check's comment on file naming
        log._roll_at = time.time() - 1.0  # the boundary has already passed
        log.record("use.button", label="a")
        files = sorted(root.glob("sessions_log/*.jsonl"))
        if not check("day roll: a second file was opened",
                     len(files) == 2, f"got {len(files)} files: {files}"):
            return False
        new_header = _lines(log.path)[0]
        if not check("day roll: new header carries rolled_from",
                     new_header.get("rolled_from") == first_name,
                     f"new_header={new_header}"):
            return False
        log.close("stop")

        old = ("        if t >= self._roll_at or self._bytes >= self._s.session_log_max_bytes:\n"
               "            why = \"size\" if self._bytes >= self._s.session_log_max_bytes else \"day\"")
        new = ("        if self._bytes >= self._s.session_log_max_bytes:\n"
               "            why = \"size\"")
        patched = _load_patched(old, new, "session_log_plant_day_roll")
        proot = _tmp_root()
        try:
            psettings = FakeSettings(proot, roll_hours=24.0, max_bytes=8_000_000)
            plog = patched.SessionLog(settings=psettings)
            plog.start(app_version="1")
            plog._roll_at = time.time() - 1.0
            plog.record("use.button", label="a")
            pfiles = sorted(proot.glob("sessions_log/*.jsonl"))
            if not check("day roll: plant never rolls on the day boundary",
                         len(pfiles) == 1, f"plant produced {len(pfiles)} files"):
                return False
        finally:
            shutil.rmtree(proot, ignore_errors=True)
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_close_single_footer_returns_path() -> bool:
    root = _tmp_root()
    try:
        settings = FakeSettings(root)
        log = session_log.SessionLog(settings=settings)
        log.start(app_version="1")
        log.record("use.button", label="a")
        opened_path = log.path
        returned = log.close("stop")
        if not check("close: returns the closed path",
                     returned == opened_path, f"{returned} != {opened_path}"):
            return False
        if not check("close: log.path is None after close",
                     log.path is None, f"log.path={log.path}"):
            return False
        recs = _lines(returned)
        footers = [r for r in recs if r.get("kind") == "footer"]
        if not check("close: exactly one footer",
                     len(footers) == 1, f"got {len(footers)} footers"):
            return False
        footer = footers[0]
        if not check("close: footer carries duration and counts",
                     footer.get("reason") == "stop"
                     and "duration_s" in footer and "counts" in footer,
                     f"footer={footer}"):
            return False

        old = ("        self._write({\n"
               "            \"kind\": \"footer\", \"at\": _stamp(t), \"epoch\": round(t, 3),\n"
               "            \"reason\": reason,\n"
               "            \"duration_s\": round(t - self._opened_at, 1),\n"
               "            \"counts\": dict(sorted(self._counts.items())),\n"
               "            \"state\": dict(self._last_state),\n"
               "        })")
        new = old + "\n" + old
        patched = _load_patched(old, new, "session_log_plant_double_footer")
        proot = _tmp_root()
        try:
            psettings = FakeSettings(proot)
            plog = patched.SessionLog(settings=psettings)
            plog.start(app_version="1")
            ppath = plog.close("stop")
            pfooters = [r for r in _lines(ppath) if r.get("kind") == "footer"]
            if not check("close: plant writes two footers",
                         len(pfooters) == 2, f"plant produced {len(pfooters)} footers"):
                return False
        finally:
            shutil.rmtree(proot, ignore_errors=True)
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_is_unclosed_states() -> bool:
    root = _tmp_root()
    root.mkdir(parents=True, exist_ok=True)
    try:
        unclosed = root / "unclosed.jsonl"
        unclosed.write_text('{"kind": "header", "at": "x", "epoch": 1}\n',
                            encoding="utf-8")
        closed = root / "closed.jsonl"
        closed.write_text(
            '{"kind": "header", "at": "x", "epoch": 1}\n'
            '{"kind": "footer", "at": "y", "epoch": 2}\n', encoding="utf-8")
        half = root / "half.jsonl"
        half.write_text('{"kind": "header", "at": "x", "epoch": 1}\n'
                        '{"kind": "use.button", "at": "y", "epo', encoding="utf-8")
        empty = root / "empty.jsonl"
        empty.write_text("", encoding="utf-8")

        if not check("is_unclosed: header-only is True",
                     session_log.is_unclosed(unclosed) is True, ""):
            return False
        if not check("is_unclosed: header+footer is False",
                     session_log.is_unclosed(closed) is False, ""):
            return False
        if not check("is_unclosed: half-written last line is True",
                     session_log.is_unclosed(half) is True, ""):
            return False
        if not check("is_unclosed: empty file is False",
                     session_log.is_unclosed(empty) is False, ""):
            return False

        old = 'return json.loads(line).get("kind") != "footer"'
        new = 'return json.loads(line).get("kind") == "footer"'
        patched = _load_patched(old, new, "session_log_plant_unclosed_invert")
        if not check("is_unclosed: plant inverts header-only",
                     patched.is_unclosed(unclosed) is False, ""):
            return False
        if not check("is_unclosed: plant inverts header+footer",
                     patched.is_unclosed(closed) is True, ""):
            return False
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_is_unclosed_reads_tail() -> bool:
    root = _tmp_root()
    root.mkdir(parents=True, exist_ok=True)
    try:
        big = root / "big.jsonl"
        # >4096 bytes of body, footer at the very end.
        body = "".join(f'{{"kind": "use.button", "n": {i}}}\n' for i in range(400))
        body += '{"kind": "footer", "at": "y", "epoch": 2}\n'
        big.write_text(body, encoding="utf-8")
        size = big.stat().st_size
        if not check("is_unclosed tail: fixture really exceeds 4096 bytes",
                     size > 4096, f"size={size}"):
            return False

        seeks = []
        real_open = open

        def spy_open(path_, mode="r", *a, **kw):
            fh = real_open(path_, mode, *a, **kw)
            if "b" in mode:
                orig_seek = fh.seek

                def spy_seek(offset, whence=0):
                    seeks.append(offset)
                    return orig_seek(offset, whence)
                fh.seek = spy_seek
            return fh

        with mock.patch("builtins.open", side_effect=spy_open):
            result = session_log.is_unclosed(big)
        if not check("is_unclosed tail: correct result", result is False, ""):
            return False
        if not check("is_unclosed tail: real seek targets the tail, not byte 0",
                     seeks and seeks[0] == size - 4096,
                     f"seeks={seeks}, expected {size - 4096}"):
            return False

        old = "fh.seek(max(0, size - 4096))"
        new = "fh.seek(0)"
        patched = _load_patched(old, new, "session_log_plant_seek_zero")
        pseeks = []

        def pspy_open(path_, mode="r", *a, **kw):
            fh = real_open(path_, mode, *a, **kw)
            if "b" in mode:
                orig_seek = fh.seek

                def pspy_seek(offset, whence=0):
                    pseeks.append(offset)
                    return orig_seek(offset, whence)
                fh.seek = pspy_seek
            return fh

        with mock.patch("builtins.open", side_effect=pspy_open):
            patched.is_unclosed(big)
        if not check("is_unclosed tail: plant seeks byte 0 instead",
                     pseeks and pseeks[0] == 0, f"plant seeks={pseeks}"):
            return False
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_repair_unclosed() -> bool:
    root = _tmp_root()
    try:
        settings = FakeSettings(root)
        d = settings.session_log_dir
        d.mkdir(parents=True, exist_ok=True)
        unclosed = d / "a-unclosed.jsonl"
        unclosed.write_text('{"kind": "header", "at": "x", "epoch": 1}\n',
                            encoding="utf-8")
        closed = d / "b-closed.jsonl"
        closed.write_text(
            '{"kind": "header", "at": "x", "epoch": 1}\n'
            '{"kind": "footer", "at": "y", "epoch": 2}\n', encoding="utf-8")
        skipped = d / "c-skip-me.jsonl"
        skipped.write_text('{"kind": "header", "at": "x", "epoch": 1}\n',
                           encoding="utf-8")

        shipper = FakeShipper()
        done = session_log.repair_unclosed(settings, shipper=shipper, skip=skipped)

        if not check("repair: only the truly-unclosed, non-skipped file",
                     done == [unclosed], f"done={done}"):
            return False
        if not check("repair: offered to the shipper exactly that file",
                     shipper.offered == [unclosed], f"offered={shipper.offered}"):
            return False
        if not check("repair: the skipped file is untouched (still unclosed)",
                     session_log.is_unclosed(skipped) is True, ""):
            return False
        if not check("repair: the already-closed file is untouched",
                     len(_lines(closed)) == 2, f"lines={_lines(closed)}"):
            return False

        footer = _lines(unclosed)[-1]
        if not check("repair: reason is 'unclosed', no duration invented",
                     footer.get("kind") == "footer"
                     and footer.get("reason") == "unclosed"
                     and "duration_s" not in footer,
                     f"footer={footer}"):
            return False

        old = "        if skip is not None and path == skip:\n            continue\n"
        new = ""
        patched = _load_patched(old, new, "session_log_plant_repair_skip")
        proot = _tmp_root()
        try:
            psettings = FakeSettings(proot)
            pd = psettings.session_log_dir
            pd.mkdir(parents=True, exist_ok=True)
            pskip = pd / "skip-me.jsonl"
            pskip.write_text('{"kind": "header", "at": "x", "epoch": 1}\n',
                             encoding="utf-8")
            pshipper = FakeShipper()
            pdone = patched.repair_unclosed(psettings, shipper=pshipper, skip=pskip)
            if not check("repair: plant repairs the skipped file too",
                         pskip in pdone, f"plant done={pdone}"):
                return False
        finally:
            shutil.rmtree(proot, ignore_errors=True)
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_disabled_is_silent_noop() -> bool:
    root = _tmp_root()
    try:
        settings = FakeSettings(root, enabled=False)
        log = session_log.SessionLog(settings=settings)
        log.start(app_version="1")
        if not check("disabled: start() opens nothing",
                     log.path is None, f"log.path={log.path}"):
            return False
        if not check("disabled: not even the directory is created",
                     not settings.session_log_dir.exists(), ""):
            return False
        log.record("use.button", label="a")  # must not raise
        log.state("pc", monitors=1)  # must not raise
        returned = log.close("stop")  # must not raise
        if not check("disabled: close() returns None, nothing to close",
                     returned is None, f"returned={returned}"):
            return False

        old = ("    def start(self, **facts) -> None:\n"
               "        \"\"\"Open a file and write its header. `facts` is whatever the caller\n"
               "        knows about this PC and this app — stable-for-the-process facts only,\n"
               "        for the reason in this module's own docstring.\"\"\"\n"
               "        if not self._s.session_log_enabled:\n"
               "            return\n"
               "        with self._lock:")
        new = ("    def start(self, **facts) -> None:\n"
               "        \"\"\"Open a file and write its header. `facts` is whatever the caller\n"
               "        knows about this PC and this app — stable-for-the-process facts only,\n"
               "        for the reason in this module's own docstring.\"\"\"\n"
               "        with self._lock:")
        patched = _load_patched(old, new, "session_log_plant_enabled_ignored")
        proot = _tmp_root()
        try:
            psettings = FakeSettings(proot, enabled=False)
            plog = patched.SessionLog(settings=psettings)
            plog.start(app_version="1")
            if not check("disabled: plant opens a file despite enabled=False",
                         plog.path is not None, "plant should have opened a file"):
                return False
        finally:
            shutil.rmtree(proot, ignore_errors=True)
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_write_failure_closes_without_raising() -> bool:
    root = _tmp_root()
    try:
        settings = FakeSettings(root)
        log = session_log.SessionLog(settings=settings)
        log.start(app_version="1")
        log._fh = BadFile()  # simulate a disk that stopped answering
        try:
            log.record("use.button", label="a")
        except OSError:
            return check("write failure: record() must not raise", False,
                         "OSError escaped record()")
        if not check("write failure: the log dropped itself",
                     log._fh is None and log.path is None,
                     f"fh={log._fh} path={log.path}"):
            return False

        old = ("        try:\n"
               "            self._fh.write(line + \"\\n\")\n"
               "            self._fh.flush()\n"
               "        except OSError as e:\n"
               "            logger.warning(\"Use log: write failed (%s) — closing\", e)\n"
               "            self._drop()\n"
               "            return\n")
        new = ("        self._fh.write(line + \"\\n\")\n"
               "        self._fh.flush()\n")
        patched = _load_patched(old, new, "session_log_plant_write_raises")
        proot = _tmp_root()
        try:
            psettings = FakeSettings(proot)
            plog = patched.SessionLog(settings=psettings)
            plog.start(app_version="1")
            plog._fh = BadFile()
            raised = False
            try:
                plog.record("use.button", label="a")
            except OSError:
                raised = True
            if not check("write failure: plant lets OSError escape",
                         raised, "plant should have raised OSError"):
                return False
        finally:
            shutil.rmtree(proot, ignore_errors=True)
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


CHECKS = [
    ("header written once, at open, no duplicate on a second start()",
     check_header_once_no_duplicate),
    ("record() counts a kind under both its full kind and its group",
     check_record_counts_kind_and_group),
    ("the file rolls at the byte ceiling, new header carries rolled_from",
     check_rolls_at_byte_ceiling),
    ("the file rolls at the day boundary, new header carries rolled_from",
     check_rolls_at_day_boundary),
    ("close() writes exactly one footer and returns the closed path",
     check_close_single_footer_returns_path),
    ("is_unclosed(): true for missing/half-written footer, false for a real one",
     check_is_unclosed_states),
    ("is_unclosed() reads the tail, never the whole file",
     check_is_unclosed_reads_tail),
    ("repair_unclosed(): reason unclosed, no invented duration, offered, skip honoured",
     check_repair_unclosed),
    ("session_log_enabled = False: every entry point is a silent no-op",
     check_disabled_is_silent_noop),
    ("a write failure closes the log instead of raising into the caller",
     check_write_failure_closes_without_raising),
]


def main() -> int:
    print("=== SESSION LOG GATE ===")
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
    if FAILURES:
        print("Failure detail:")
        for f in FAILURES:
            print(f"  - {f}")
        print()
    if failed:
        print(f"SESSION LOG GATE FAILED — {failed} check(s).")
        return 1
    print("SESSION LOG GATE PASSED — the use log opens, writes, rolls, closes "
          "and repairs itself honestly, and never takes the app down with it.")
    return 0


def test_session_log():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
