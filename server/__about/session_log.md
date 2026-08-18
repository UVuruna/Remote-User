# Session Log

**Script:** [Session Log (script)](../session_log.py)

## Purpose

A background use record, for two readers who are both US and never the user
(owner request 2026-08-16, and he named both purposes himself): (1) EVIDENCE
for a future bug — what the PC was, which encoder, what failed and how it
recovered; (2) BEHAVIOUR — what he actually uses the app for, so scenarios can
be adapted. Nothing in here is a feature anybody taps, and the user never
reads it — in the shipping default he never even keeps it, since the (still
being written) sibling `log_shipper.py` moves the file off his disk and
deletes it.

## Why JSONL and not CSV

`traffic.csv` next door is a CSV and copying its shape was the obvious first
move — rejected by the owner on being shown that design. A traffic row is one
fixed shape sampled once a second, which is exactly what CSV is good at. A use
event is the opposite: a notice, a capture fault and "he opened a layout"
carry different fields, so a CSV of them is a table of mostly-empty columns
whose schema change reaches BACKWARDS over every row already written. One JSON
object per line costs the same append, lets a new event kind touch no old
row, and is the shape that uploads with no conversion the day the destination
stops being a folder.

## What the cut is

The first design ended the file when the phone disconnected — wrong for how
this app actually runs (owner's own correction 2026-08-16): it sits in the
tray all day, and a phone that leaves and comes back in twenty seconds (an
excursion, a locked screen — see [Presence](presence.md)) is not the end of
anything. That design would have cut fifty files an evening. The real cut is
the PROCESS: a file lives as long as the server does, rolled at the local day
boundary (`_day_end` — the next local midnight at the default 24 h, so a PC
booted at 03:41 still rolls at a boundary he can reason about) so a PC left
running for a week does not grow one enormous file.

## Why the header describes only the process, never the phone

That correction moved the header too. When a file was one phone connection,
the header could name THE PHONE. A file that spans a whole day spans many
connections, several devices and several sets of settings, so a header
claiming "the phone" would be a fact that quietly stops being true an hour
later — the same class of defect as `Layout.arranged_ratio` (project
`docs/DECISIONS.md` constraint 13), a note of what was once true, read forever after
as if it still were. So the header written by `_open()`/`start()` carries only
what is stable for the process — this app, this PC, this install — and every
phone connection is expected to write its own `session.connect` event
carrying the device, the link and the settings that were live for it.

## What survives a kill

Every record is flushed as it is written (`_write` — `fh.write` then
`fh.flush`), so a power cut or a Task Manager kill loses at most the line
being written and never the file. What it does lose is the footer, and a file
with no footer is exactly how the NEXT start recognises a run that ended
without us: `is_unclosed()` reads the file's tail and asks whether the last
JSON line is a footer; `repair_unclosed()` appends an honest footer saying the
end is UNKNOWN rather than inventing a time, and hands the file to the
shipper. That is the same shape `window_manager.repair_stranded()` uses for
the topmost ledger (constraint 10), and for the same reason: the two ways a
process can end are "we get to run code" and "we do not," and only the first
can tidy up after itself.

## Responsibility split

This module knows nothing about WHERE a finished file goes — it writes lines
and rolls files. `log_shipper.py` (in flight, not yet documented) moves,
verifies, deletes and prunes them, and knows nothing about what is inside a
file. Splitting the two that way is what lets the destination become an HTTP
endpoint later without this file changing at all.

## Classes

### `SessionLog`
One open JSONL file, plus the rules for when it must become the next one.
Every public method takes `self._lock`, is safe to call from any thread, and
is a silent no-op when `config.session_log_enabled` is off — the whole
feature is background, and a use log that can break the app it observes is
worse than no use log.

- `start(**facts)` — opens the file and writes its header; a no-op if a file
  is already open.
- `record(kind, **fields)` — writes one event (`kind` is `group.what`),
  UNCONDITIONALLY, every call; rolls the current file FIRST when the day
  boundary or `session_log_max_bytes` is due, so a record is never split
  across the boundary it caused.
- `state(kind, **fields)` — writes `state.<kind>` (group `state`), but ONLY
  when `fields` differs from the last value recorded for that kind. This is
  the mechanism for the owner's 2026-08-16 ruling (see this doc's own
  "Why the header describes only the process" section, and the module
  docstring's "STATE VS RECORD"): a fact that is true UNTIL IT CHANGES —
  which monitors are on, at what resolution and scale, what quality mode is
  live — gets `state()`, never `record()`. The dedupe compares the whole
  `fields` dict against `self._last_state[kind]`; the first call for a kind
  in a file always writes (nothing to compare against yet), and a kind that
  never changes for the file's whole life writes exactly once. Deliberately
  a SEPARATE method from `record()` rather than a keyword flag on it, so a
  call site can never silently skip the dedupe by leaving an argument at a
  wrong default.
- `close(reason="stop")` — writes the footer, closes, and hands the path to
  the shipper if one was given; returns the closed path so a synchronous
  teardown caller (and a test) can act on it without reaching into the
  object. The footer now also carries `state`: the LAST value of every
  `state()` kind the file ever held — carried forward from the same dict
  `state()` built all along, never a second computation, and purely
  informational (a human tailing the file reads the final status without
  reading it backwards). Turning the file's `state.*` records into SPANS
  ("2 monitors 3h28m, 1 monitor 2h22m") is `log_summary.py`'s job, not this
  one — see [Log Summary](log_summary.md).
- `path` — the file currently open, or `None`.

### Module functions
- `is_unclosed(path)` — reads only the file's tail; true when the last JSON
  line is not a footer.
- `repair_unclosed(settings, shipper, skip=None)` — at start, footers every
  file the previous run could not close and offers each to the shipper;
  `skip` excludes the file the new run is about to open itself.

### `LOG`
The one live instance. Nothing is opened until the server calls `start()` —
importing this module never touches disk.

## Connections

### Uses
- `config.SETTINGS` — `session_log_enabled`, `session_log_dir`,
  `session_log_roll_hours`, `session_log_max_bytes`

### Used by
- none (entry point / not yet wired) — the calling side (`server_core.py`
  opening/closing `LOG`, and the per-event `record()`/`state()` call sites
  across the server, incl. `display_watch.py`'s planned `state("pc", …)`
  monitor facts) is not written yet, and `log_shipper.py`, which `close()`
  and `repair_unclosed()` hand finished files to, is a sibling module still
  being written by another session
- `log_summary.py` reads the files this module writes (never the reverse —
  this module knows nothing of spans or summaries)

## Honest limits

- Rolling by day boundary or by size can still split one meaningful episode
  (a long recovery ladder, a long dictation session) across two files —
  accepted, since the alternative is an unbounded file.
- A kill inside `_write`'s own `fh.write`/`fh.flush` can still lose the one
  line being written; only the file as a whole is protected, never that one
  record.
- `repair_unclosed()` only proves an abrupt end from the FOOTER's absence — it
  cannot say when the process actually died, only that its last known moment
  is the file's own last record.
- The footer's `state` field is a convenience snapshot, not a second source
  of truth: a reader computing SPANS still has to walk the file's `state.*`
  records from the start — the footer only tells you where each one ended
  up, never how long it had been that way.
