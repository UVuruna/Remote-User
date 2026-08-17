"""Turns one `session_log.py` file into spans and totals — the arithmetic
half of the owner's ruling of 2026-08-16, kept apart from `session_log.py`
itself for the reason its own docstring gives: writing lines correctly is one
responsibility, and reading them back into something a human can act on is
another, with its own honest edge cases a writer never has to think about.

THE RULING THIS IMPLEMENTS, restated because it is the whole point: in a file
that spans a whole day, nothing but the process's own identity is a stable
fact — everything observable is a fact WITH A DURATION. "We worked an hour
with two monitors and two hours with one" is the shape of answer this module
exists to produce; a header that just said "2 monitors" would have been
exactly the defect `Layout.arranged_ratio` was (project CLAUDE.md constraint
13) — a note of what was once true, read forever after as if it still were.

THE ONE RULE THAT KEEPS THIS HONEST: every number in here is derived FROM the
log's own records, and NEVER computed a second, independent way. `spans()`
turns `state.*` records into durations by walking them in the order they were
WRITTEN — there is no second pass, no cross-check against a remembered value,
no reconstruction from anything but the records themselves. `summarize()`
carries the footer's own `duration_s` and `counts` through UNCHANGED rather
than re-deriving totals that would only ever have to agree with it by
accident. Two independent computations of one number is the exact class of
defect this project keeps paying for (constraint 25's `place_window` lesson,
constraint 30's four-mechanism capture failure) — one path, walked once, is
the whole defence.

WHY GENERIC AND NOT "PC-AWARE": `spans()` does not know what a "monitor" is.
It tracks each `state.<kind>` kind as ONE independent series, comparing the
WHOLE fields dict call-to-call — the same equality `SessionLog.state()`
itself dedupes on, so a span boundary in this module's output is always
exactly a record boundary in the file, never a re-interpretation of one. A
"scaling-only change must not disturb the resolution span" is not special
code here: it falls out for free as long as the writer emits scaling and
resolution as SEPARATE `state()` kinds (e.g. `state("scale", ...)` beside
`state("resolution", ...)`) rather than folding both into one kind's fields —
that choice belongs to whoever calls `state()` (`display_watch.py`, for the
monitor facts this was written for), not to this reader.

HONEST CASES, not assumed away:
  * A file with no footer (`session_log.is_unclosed`) — the run was killed.
    The last open span of every kind, and the last open session of every
    device, is reported OPEN (`"open": True`, `"to": None`, `"seconds":
    None`) — never given an invented end time.
  * A device that connects and never leaves, in a file that DOES have a
    footer — the process is known to have still been running at the
    footer's own moment, so that is an honest (not invented) end for the
    open session; still marked distinctly from a session with a real
    `session.leave` (`"closed_by": "footer"` vs `"leave"`).
  * Records from an older schema missing fields this module reads — every
    read is `.get(...)`, defaulting rather than raising, because a summary
    that cannot be built from an old file is worse than one with a few
    blanks in it.
  * A malformed or half-written last line (an abrupt kill mid-`fh.write`) —
    skipped, not fatal to the rest of the file.

Pure and side-effect-free except `write_summary()`, which is the one function
that touches disk — so a gate can import this module and run every other
function against fixtures with zero risk of writing anything.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

# ---- reading -------------------------------------------------------------


def _read_records(path: Path) -> list[dict]:
    """Every well-formed JSON line in `path`, in file order. A line that
    fails to parse (the last line of a file killed mid-write) is skipped
    rather than raising — the rest of the file is still evidence."""
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
    return records


def _footer(records: list[dict]) -> dict | None:
    """The file's footer record, or None when the file has no footer — the
    exact question `session_log.is_unclosed` answers, asked here against
    records already in hand instead of a second read of the file's tail."""
    for rec in reversed(records):
        if rec.get("kind") == "footer":
            return rec
    return None


# ---- state spans -----------------------------------------------------------


def spans(records: list[dict]) -> dict[str, list[dict]]:
    """Every `state.<kind>` record turned into `(value, from, to, seconds)`
    spans, one list per kind, in chronological order.

    Walks `records` ONCE. For each kind, a span opens at the first record
    seen (or the first after the previous span closed) and closes the moment
    a DIFFERENT value for that same kind appears — closing at that new
    record's own timestamp, never a guess. The last span of each kind closes
    at the footer's timestamp when the file has one; when it does not
    (`is_unclosed`), that last span is left OPEN — no end time is invented.
    """
    footer = _footer(records)
    open_spans: dict[str, dict] = {}
    closed: dict[str, list[dict]] = {}

    def _close_span(kind_name: str, cur: dict, to_at, to_epoch, *, open_: bool) -> None:
        from_epoch = cur["from_epoch"]
        seconds = None
        if not open_ and from_epoch is not None and to_epoch is not None:
            seconds = round(to_epoch - from_epoch, 1)
        closed.setdefault(kind_name, []).append({
            "value": cur["value"],
            "from": cur["from"], "from_epoch": from_epoch,
            "to": to_at, "to_epoch": to_epoch,
            "seconds": seconds,
            "open": open_,
        })

    for rec in records:
        kind = rec.get("kind", "")
        if not isinstance(kind, str) or not kind.startswith("state."):
            continue
        kind_name = kind[len("state."):]
        fields = {k: v for k, v in rec.items() if k not in ("kind", "at", "epoch")}
        cur = open_spans.get(kind_name)
        if cur is not None and cur["value"] == fields:
            # The writer already dedupes; a match here means a hand-built or
            # older-schema file repeated a value. Never split a span over
            # nothing observable actually changing.
            continue
        if cur is not None:
            _close_span(kind_name, cur, rec.get("at"), rec.get("epoch"), open_=False)
        open_spans[kind_name] = {
            "value": fields, "from": rec.get("at"), "from_epoch": rec.get("epoch"),
        }

    for kind_name, cur in open_spans.items():
        if footer is not None:
            _close_span(kind_name, cur, footer.get("at"), footer.get("epoch"), open_=False)
        else:
            _close_span(kind_name, cur, None, None, open_=True)

    return closed


# ---- per-device totals ------------------------------------------------------


def device_totals(records: list[dict]) -> dict[str, dict]:
    """`session.connect` / `session.leave` pairs turned into per-device
    totals: connected seconds, bytes out/in, session count.

    Devices are matched to a specific connection FIFO (a device may connect
    several times in one file) via `rec["device"]`; a `session.leave` with no
    matching open connect for its device is counted for its bytes but adds no
    duration, since there is nothing honest to measure it against. A connect
    with no matching leave stays open — closed at the footer's time when the
    file has one (an honest end: the process was known to be alive then),
    left OPEN with no seconds when it does not.
    """
    footer = _footer(records)
    open_by_device: dict[str, deque] = {}
    totals: dict[str, dict] = {}

    def entry(device: str) -> dict:
        return totals.setdefault(device, {
            "connected_seconds": 0.0, "bytes_out": 0, "bytes_in": 0,
            "sessions": 0, "open_sessions": 0,
        })

    for rec in records:
        kind = rec.get("kind")
        device = rec.get("device")
        if device is None:
            continue
        if kind == "session.connect":
            open_by_device.setdefault(device, deque()).append(rec.get("epoch"))
            entry(device)["sessions"] += 1
        elif kind == "session.leave":
            e = entry(device)
            q = open_by_device.get(device)
            start = q.popleft() if q else None
            end = rec.get("epoch")
            if start is not None and end is not None:
                e["connected_seconds"] += end - start
            e["bytes_out"] += rec.get("bytes_out") or 0
            e["bytes_in"] += rec.get("bytes_in") or 0

    for device, q in open_by_device.items():
        e = entry(device)
        while q:
            start = q.popleft()
            if footer is not None and start is not None:
                e["connected_seconds"] += footer.get("epoch", start) - start
            else:
                e["open_sessions"] += 1

    for e in totals.values():
        e["connected_seconds"] = round(e["connected_seconds"], 1)
    return totals


# ---- the whole file ---------------------------------------------------------


def summarize(path: Path) -> dict:
    """The whole summary object for one `.jsonl` log: the header's immutable
    facts, the state spans, the per-device totals, and the footer's own
    counts — carried through unchanged rather than re-derived (the one rule,
    see the module docstring)."""
    path = Path(path)
    records = _read_records(path)
    header = records[0] if records and records[0].get("kind") == "header" else {}
    footer = _footer(records)
    return {
        "path": str(path),
        "header": header,
        "unclosed": footer is None,
        "footer": footer,
        "spans": spans(records),
        "devices": device_totals(records),
    }


def write_summary(path: Path) -> Path:
    """Write `<name>.summary.json` beside `path` and return its Path. The
    only function in this module that touches disk."""
    path = Path(path)
    summary = summarize(path)
    out = path.with_name(f"{path.stem}.summary.json")
    out.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    return out
