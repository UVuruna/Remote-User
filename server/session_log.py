"""The use log: what this installation did, written for two readers who are
both US and never the user.

Owner request 2026-08-16, and he named both purposes himself: (1) EVIDENCE for
a future bug — "where and what went wrong, so we can establish why it came to
that"; (2) BEHAVIOUR — "what the user does and what he uses the application
for, so we can adapt scenarios in future". Nothing in here is a feature
anybody taps. The user never reads it, and in the shipping default he never
even keeps it (`log_shipper.py` moves it off his disk and deletes it).

WHY JSONL AND NOT CSV, since `traffic.csv` next door is a CSV and the obvious
move was to copy it. A traffic row is one fixed shape sampled once a second,
which is exactly what CSV is good at. An event log is the opposite: a notice,
a capture fault and "he opened a layout" carry different fields, so a CSV of
them is a table of mostly-empty columns whose schema change reaches backwards
over every row ever written. One JSON object per line costs the same append,
lets a new event kind touch no old row, and is the format that UPLOADS with no
conversion the day the destination stops being a folder. His correction,
2026-08-16, on being shown a CSV design.

WHAT THE CUT IS, and this is his correction of my own first design. I had the
file ending when the phone disconnected. That is wrong for the way this app
actually runs: it sits in the tray all day, and a phone that leaves and comes
back in twenty seconds (an excursion, a locked screen — see `presence`) is not
the end of anything. It would have cut fifty files an evening. His rule is the
PROCESS: a file lives as long as the server does, rolled at the local day
boundary so a PC left running for a week does not grow one enormous file.

THAT CORRECTION MOVED THE HEADER TOO, which is the part worth reading twice.
When a file was one phone connection, the header could describe THE PHONE. A
file that spans a whole day spans many connections, several devices and
several sets of settings, so a header claiming "the phone" would be a fact
that quietly stops being true an hour later — the same class of defect as
`Layout.arranged_ratio` (constraint 13), a note of what was true once, read
forever after as if it still were. So the HEADER describes only what is stable
for the process (this app, this PC, this install), and every phone connection
writes its own `session.connect` event carrying the device, the link and the
settings that were live for it.

WHAT SURVIVES A KILL. Every record is flushed as it is written, so a power cut
or a Task Manager kill loses at most the line being written and never the
file. What it does lose is the footer, and a file with no footer is exactly
how the NEXT start recognises a run that ended without us — `repair_unclosed()`
writes an honest footer saying the end is unknown rather than inventing a
time, and hands the file to the shipper. That is the same shape
`window_manager.repair_stranded()` uses for the topmost ledger (constraint 10),
and for the same reason: the two ways a process can end are "we get to run
code" and "we do not", and only the first can tidy up after itself.

WHAT THIS MODULE DOES NOT KNOW: where the file goes. It writes lines and rolls
files; `log_shipper.py` moves, verifies, deletes and prunes them, and knows
nothing about what is inside. Splitting them that way is what lets the
destination become an HTTP endpoint later without this file changing at all.

STATE VS RECORD, added 2026-08-16 for the SAME owner ruling that shaped the
header (above): "a header claiming the PC is X is exactly
`Layout.arranged_ratio` in a new place — a note of what was once true, read
forever as if it still were." His fix, generalised past the header: in a
file that spans a whole day, nothing but the process's own identity is a
stable fact — everything OBSERVABLE (which monitors are on, at what
resolution and scale, what quality mode is live, …) is a fact WITH A
DURATION, and a file that wrote it every time something merely asked would
make a later reader's spans meaningless and the file enormous. `state(kind,
**fields)` is that distinction made mechanical: it writes `state.<kind>` ONLY
when `fields` differs from the last value recorded for that kind — the
dedupe against `self._last_state` IS the whole feature, and it is
deliberately a SEPARATE entry point from `record()` rather than a flag on
it, so a call site can never forget to ask for the dedupe by leaving an
argument at its default. Turning a file of `state.*` changes into SPANS ("2
monitors 3h28m, 1 monitor 2h22m") is NOT this module's job — that arithmetic
lives in `log_summary.py`, kept out of here for the same reason capture and
injection stay out of `web.py`: this module's whole contract is writing
lines correctly, and a reader that walks records is a different
responsibility with its own honest edge cases (a file with no footer, a
value that never changed at all).
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from config import SETTINGS

logger = logging.getLogger(__name__)

# The grammar's version. It rides in every header so a file read months from
# now says which shape it is, instead of being guessed at by its field names.
SCHEMA = 1

# Event kinds are `group.what`, and the GROUP is what a later reader filters
# on. Kept here as the one list rather than spelled out at each call site,
# because a typo'd kind is invisible until somebody tries to read the file.
GROUP_SESSION = "session"   # a phone connected, left, came back
GROUP_NOTICE = "notice"     # an agent's notice and what became of it
GROUP_USE = "use"           # what he did: sets, buttons, layouts, voice, zoom
GROUP_FAULT = "fault"       # what went wrong and whether it recovered
GROUP_STATE = "state"       # an observable fact, true from this record until
                             # the next one of the same kind — see `state()`


def _now() -> float:
    return time.time()


def _stamp(t: float) -> str:
    """Local time, seconds, ISO-ish. Local and not UTC deliberately: every
    other timestamp he is ever shown beside this one — `server.log`, the
    Traffic window, his own clock when he reports a bug — is local, and a log
    read against a report is worth more than one that is technically tidier."""
    return datetime.fromtimestamp(t).isoformat(timespec="seconds")


def _day_end(t: float, roll_hours: float) -> float:
    """The moment this file must roll.

    At the default 24 h this is the next local MIDNIGHT, not `t + 24 h`: the
    boundary he thinks in is a working day, and a file that rolls at 03:41
    because that is when the PC booted is a cut nobody can reason about. Any
    other value is taken literally as an interval, which is what a shorter
    debugging roll wants.
    """
    if roll_hours >= 24.0:
        start = datetime.fromtimestamp(t)
        midnight = (start + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        return midnight.timestamp()
    return t + roll_hours * 3600.0


class SessionLog:
    """One open JSONL file, plus the rules for when it must become the next one.

    Every public method is safe to call from any thread and safe to call when
    logging is switched off — the whole feature is background, and a use log
    that can break the app it observes is worse than no use log.
    """

    def __init__(self, settings=SETTINGS, shipper=None):
        self._s = settings
        self._shipper = shipper
        self._lock = threading.Lock()
        self._fh = None
        self._path: Path | None = None
        self._opened_at = 0.0
        self._roll_at = 0.0
        self._counts: dict[str, int] = {}
        self._bytes = 0
        # The last value written for each `state()` kind, so a repeat asks
        # nothing of the file — reset on every `_open()`, since a NEW file
        # has seen nothing yet and must accept the first value of a run even
        # when it happens to equal whatever the previous file ended on.
        self._last_state: dict[str, dict] = {}

    # ---- the file itself ------------------------------------------------

    @property
    def path(self) -> Path | None:
        """The file currently being written, or None when nothing is open."""
        return self._path

    def start(self, **facts) -> None:
        """Open a file and write its header. `facts` is whatever the caller
        knows about this PC and this app — stable-for-the-process facts only,
        for the reason in this module's own docstring."""
        if not self._s.session_log_enabled:
            return
        with self._lock:
            if self._fh is not None:
                return
            self._open(_now(), facts)

    def _open(self, t: float, facts: dict) -> None:
        """Caller holds the lock."""
        d = Path(self._s.session_log_dir)
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("Use log: cannot create %s (%s) — logging off", d, e)
            return
        name = datetime.fromtimestamp(t).strftime("%Y-%m-%dT%H-%M-%S")
        path = d / f"{name}.jsonl"
        try:
            fh = open(path, "a", encoding="utf-8", newline="\n")
        except OSError as e:
            logger.warning("Use log: cannot open %s (%s) — logging off", path, e)
            return
        self._fh = fh
        self._path = path
        self._opened_at = t
        self._roll_at = _day_end(t, self._s.session_log_roll_hours)
        self._counts = {}
        self._bytes = 0
        self._last_state = {}
        self._write({"kind": "header", "at": _stamp(t), "epoch": round(t, 3),
                     "schema": SCHEMA, **facts})
        logger.info("Use log: %s opened (rolls at %s)",
                    path.name, _stamp(self._roll_at))

    def _write(self, obj: dict) -> None:
        """Caller holds the lock. One line, flushed. Never raises: a use log
        that can take the server down with it has no business existing."""
        if self._fh is None:
            return
        try:
            line = json.dumps(obj, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as e:
            logger.warning("Use log: undumpable record %r (%s)",
                           obj.get("kind"), e)
            return
        try:
            self._fh.write(line + "\n")
            self._fh.flush()
        except OSError as e:
            logger.warning("Use log: write failed (%s) — closing", e)
            self._drop()
            return
        self._bytes += len(line) + 1

    def _drop(self) -> None:
        """Caller holds the lock. Let the file go without pretending it ended
        properly — the missing footer is what tells the next start to repair
        it, which is exactly the right outcome for a disk that stopped
        answering."""
        try:
            if self._fh is not None:
                self._fh.close()
        except OSError:
            pass
        self._fh = None
        self._path = None

    # ---- writing ---------------------------------------------------------

    def record(self, kind: str, **fields) -> None:
        """Write one event, unconditionally. `kind` is `group.what`; `fields`
        is whatever that event carries. Rolls the file first when it is due,
        so a record is never split across the boundary it caused.

        For a fact that is true until it CHANGES rather than a thing that
        HAPPENED, use `state()` instead — this writes every call, every time,
        which is correct for an event and wrong for a status."""
        if not self._s.session_log_enabled:
            return
        with self._lock:
            if self._fh is None:
                return
            self._record_locked(kind, fields)

    def state(self, kind: str, **fields) -> None:
        """Write `state.<kind>` — but ONLY when `fields` differs from the
        last value recorded for this kind. This dedupe is the whole feature:
        a `state.pc` written every time something merely asks would make the
        spans `log_summary.py` computes from it meaningless, and the file
        enormous. The first call for a kind in a file always writes (there is
        no prior value to compare against), and a kind that never changes for
        the file's whole life writes exactly once, at open."""
        if not self._s.session_log_enabled:
            return
        with self._lock:
            if self._fh is None:
                return
            if self._last_state.get(kind) == fields:
                return
            # `_record_locked` may ROLL the file, which resets
            # `self._last_state` for the new file (a fresh file has seen
            # nothing yet) — so the new value is recorded AFTER, never
            # before, or a roll on this very call would erase the value this
            # call is in the middle of writing.
            self._record_locked(f"state.{kind}", fields)
            self._last_state[kind] = dict(fields)

    def _record_locked(self, kind: str, fields: dict) -> None:
        """Caller holds the lock. Rolls the file first when it is due, so a
        record is never split across the boundary it caused."""
        t = _now()
        if t >= self._roll_at or self._bytes >= self._s.session_log_max_bytes:
            why = "size" if self._bytes >= self._s.session_log_max_bytes else "day"
            facts = {"rolled_from": self._path.name if self._path else None}
            self._close(t, reason=f"roll:{why}")
            self._open(t, facts)
        group = kind.split(".", 1)[0]
        self._counts[kind] = self._counts.get(kind, 0) + 1
        self._counts[group] = self._counts.get(group, 0) + 1
        self._write({"kind": kind, "at": _stamp(t), "epoch": round(t, 3),
                     **fields})

    # ---- closing ---------------------------------------------------------

    def close(self, reason: str = "stop") -> Path | None:
        """Write the footer, close, and hand the file to the shipper.

        Returns the closed file's path so a caller that wants to ship
        synchronously (the teardown path) can, and so a test can assert on it
        without reaching into the object.
        """
        with self._lock:
            if self._fh is None:
                return None
            path = self._path
            self._close(_now(), reason)
        if path is not None and self._shipper is not None:
            self._shipper.offer(path)
        return path

    def _close(self, t: float, reason: str) -> None:
        """Caller holds the lock.

        `state` on the footer is the LAST value of every `state()` kind this
        file ever held — informational only, and never a second computation
        of anything: it is the same dict `state()` has been building all
        along, carried forward rather than recomputed. A reader turning the
        file into SPANS (`log_summary.py`) must still walk the `state.*`
        records themselves to get the open span's start; this field exists so
        a human tailing the file can see the file's final status without
        reading it backwards.
        """
        self._write({
            "kind": "footer", "at": _stamp(t), "epoch": round(t, 3),
            "reason": reason,
            "duration_s": round(t - self._opened_at, 1),
            "counts": dict(sorted(self._counts.items())),
            "state": dict(self._last_state),
        })
        name = self._path.name if self._path else "?"
        self._drop()
        logger.info("Use log: %s closed (%s)", name, reason)


# ---- what a kill leaves behind ------------------------------------------

def is_unclosed(path: Path) -> bool:
    """True when this file has no footer, i.e. the run that wrote it ended
    without us getting to run any code.

    Reads the TAIL rather than the file: these can be megabytes, this runs at
    every start, and the only question is what the last line says.
    """
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size == 0:
        return False
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, size - 4096))
            tail = fh.read().decode("utf-8", "replace")
    except OSError:
        return False
    for line in reversed(tail.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line).get("kind") != "footer"
        except ValueError:
            # A half-written last line is itself proof of an abrupt end.
            continue
    return True


def repair_unclosed(settings=SETTINGS, shipper=None,
                    skip: Path | None = None) -> list[Path]:
    """At start: footer every file the previous run could not close, and hand
    each to the shipper. Returns what was repaired.

    The footer says the end is UNKNOWN and does not invent a time. The file's
    own last record already carries the last moment we know about, and writing
    "ended at start-up o'clock" would put a number in the record that no
    reader could tell apart from a measured one.
    """
    d = Path(settings.session_log_dir)
    if not d.is_dir():
        return []
    done: list[Path] = []
    for path in sorted(d.glob("*.jsonl")):
        if skip is not None and path == skip:
            continue
        if not is_unclosed(path):
            continue
        t = _now()
        try:
            with open(path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps({
                    "kind": "footer", "at": _stamp(t), "epoch": round(t, 3),
                    "reason": "unclosed",
                    "note": "the run that wrote this ended without us — "
                            "no duration is claimed",
                }, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("Use log: cannot repair %s (%s)", path.name, e)
            continue
        logger.info("Use log: repaired %s (previous run ended abruptly)",
                    path.name)
        done.append(path)
        if shipper is not None:
            shipper.offer(path)
    return done


# The one live log. Nothing is opened until the server starts it, so importing
# this module never touches the disk.
LOG = SessionLog()
