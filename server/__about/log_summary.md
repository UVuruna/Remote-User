# Log Summary

**Script:** [Log Summary (script)](../log_summary.py)

## Purpose

Turns one `session_log.py` file into the two things a reader of a whole day's
log actually wants: SPANS ("2 monitors 3h28m, 1 monitor 2h22m") and per-device
totals (connected hours, bytes out/in, session count) — the arithmetic half of
the owner's ruling of 2026-08-16. Kept apart from `session_log.py` itself for
the reason that module's own docstring gives: writing lines correctly is one
responsibility, reading them back into something a human can act on is
another, with its own honest edge cases a writer never has to think about.

## The ruling this implements

In a file that spans a whole day, nothing but the process's own identity is a
stable fact — everything observable is a fact WITH A DURATION. A header that
just said "2 monitors" would have been exactly the defect `Layout
.arranged_ratio` was (`docs/DECISIONS.md` constraint 13) — a note of what was
once true, read forever after as if it still were. `session_log.SessionLog
.state()` writes the raw material (a `state.<kind>` record only when the
value changes); this module turns that material into the answer the owner
actually asked for.

## The one rule that keeps this honest

Every number here is derived FROM the log's own records, and never computed a
second, independent way. `spans()` turns `state.*` records into durations by
walking them in the order they were WRITTEN — one pass, no cross-check
against a remembered value, no reconstruction from anything but the records
themselves. `summarize()` carries the footer's own `duration_s` and `counts`
through UNCHANGED rather than re-deriving totals that would only ever have to
agree with it by accident. Two independent computations of one number is the
exact class of defect this project keeps paying for (constraint 25's
`place_window` lesson, constraint 30's four-mechanism capture failure) — one
path, walked once, is the whole defence.

## Why generic, not "PC-aware"

`spans()` does not know what a "monitor" is. It tracks each `state.<kind>`
kind as one independent series, comparing the WHOLE fields dict call-to-call —
the same equality `SessionLog.state()` itself dedupes on, so a span boundary
in this module's output is always exactly a record boundary in the file,
never a re-interpretation of one. "A scaling-only change must not disturb the
resolution span" is not special code here: it falls out for free as long as
the writer emits scaling and resolution as SEPARATE `state()` kinds (e.g.
`state("scale", …)` beside `state("resolution", …)`) rather than folding both
into one kind's fields — that choice belongs to whoever calls `state()`
(`display_watch.py`, for the monitor facts this was written for), not to this
reader.

## Honest cases, not assumed away

- A file with no footer (`session_log.is_unclosed`) — the run was killed. The
  last open span of every kind, and the last open session of every device, is
  reported OPEN (`"open": true`, `"to": null`, `"seconds": null`) — never
  given an invented end time.
- A device that connects and never leaves, in a file that DOES have a footer
  — the process is known to have still been running at the footer's own
  moment, so closing the session there is an honest (not invented) end.
- Records from an older schema missing fields this module reads — every read
  defaults rather than raising, because a summary that cannot be built from
  an old file is worse than one with a few blanks in it.
- A malformed or half-written last line (an abrupt kill mid-`fh.write`) —
  skipped, not fatal to the rest of the file.

## Functions

- `spans(records)` — every `state.<kind>` record turned into
  `{value, from, from_epoch, to, to_epoch, seconds, open}` spans, one list
  per kind, in chronological order. The last span of each kind closes at the
  footer's timestamp when the file has one; otherwise it is left `open`.
- `device_totals(records)` — `session.connect`/`session.leave` pairs (matched
  per device by a FIFO, since a device may connect several times in one file)
  turned into `{connected_seconds, bytes_out, bytes_in, sessions,
  open_sessions}` per device.
- `summarize(path)` — the whole summary object for one `.jsonl` file: the
  header's immutable facts, `unclosed`, the raw `footer` record, `spans(...)`
  and `device_totals(...)`.
- `write_summary(path)` — writes `<name>.summary.json` beside `path` and
  returns its `Path`. The ONLY function in this module that touches disk —
  every other function is pure, so a gate can import the module and run it
  whole with zero risk of writing anything.

## Connections

### Uses
- `session_log.py` — reads the `.jsonl` files it writes; never the reverse.
  No import of `session_log` itself (records are read as plain dicts off
  disk), so this module has no dependency on the writer's internals, only on
  the grammar it documents.

### Used by
- none yet — entry point for whatever eventually shows the owner "how the PC
  was used today" (a Traffic-window-style summary, or the shipper's own
  upload manifest); not wired to a caller in this round.

## Honest limits

- `spans()`/`device_totals()` trust the file's own ordering — a hand-edited
  or reordered `.jsonl` would produce spans in the wrong order. Real files are
  append-only, so this is not a concern for anything `session_log.py` itself
  produces.
- A `session.leave` with no matching open `session.connect` for its device
  (a leave with no prior connect, e.g. a truncated file that starts mid-
  session) is counted for its bytes but adds no connected time — there is
  nothing honest to measure it against.
- No timezone handling beyond what `session_log._stamp` already bakes into
  `at` — spans are measured on `epoch` (UTC Unix time), which is
  timezone-agnostic by construction.
