# Log Shipper

**Script:** [Log Shipper (script)](../log_shipper.py)

## Purpose

A finished use-log file leaves the user's disk — the user is not our storage
(owner decree 2026-08-16). [Session Log](session_log.md) writes and rolls the
files; this module only moves, verifies, deletes and prunes them, and knows
nothing about what is inside one. That split is deliberate: it is what lets
the destination become an HTTP endpoint later without `session_log.py`
changing at all.

## The ordering rule — the module's whole point

Copy, then VERIFY the arrived bytes, and only THEN delete:

1. `shutil.copy2` to the destination.
2. `_verify` re-reads the bytes that actually landed — size first (cheap,
   catches a short copy immediately), then a full SHA-256 of both files when
   `log_upload_verify` asks for it.
3. Only a confirmed verification unlinks the local file.

`shutil.copy2` returning says nothing about what landed on the other disk — it
is a local call that can succeed while the far side is short, truncated or
never actually flushed. Deleting on that return value alone would lose
exactly the evidence the log exists for, silently, which is worse than never
shipping at all. A failed verification keeps the local file and logs a
warning; the next `sweep()` tries again.

## Why the destination is a SETTING, not a constant

`log_upload_target` (`config.py`) is a folder path today and is meant to
become an HTTP URL later — the comment beside it says so. `V:` is the owner's
own machine, and the root constitution forbids a product feature leaning on
it ("we build for OTHERS, never for the owner's machine"). Keeping it a
setting, resolved in exactly one place (`_resolve_target`), is what lets a
stranger's install run with nothing configured and lets the destination kind
change later without touching `ship()`.

## Three honest non-error cases

- **Empty target** — a stranger's fresh install. `_resolve_target` returns
  `None`, one INFO line is logged, nothing is shipped and nothing is deleted.
  Never an error.
- **Unreachable destination** — an unplugged drive. `mkdir`/`copy2` raise
  `OSError`, logged at INFO ("keeping it local for the next try"), and the
  file stays put. `sweep()`, run once at start, offers it again — nothing is
  ever lost to a missing drive, it just waits.
- **A URL target** — `log_upload_target` starting `http://`/`https://` is
  REFUSED with a clear log line, never silently treated as a folder name. A
  stray `https://` handed to `mkdir` would otherwise become a directory
  literally called `https:` next to the real ones.

## Debug mode — the owner's carve-out

With `log_debug_mode` on, a shipped file is kept locally instead of deleted
(`ship()` still copies and verifies — the transfer is still confirmed, only
the delete is skipped) so the last few days can be read on the machine that
made them. It is never unbounded: `prune()` keeps at most
`log_debug_keep_files` (10) local `*.jsonl` files, newest first, regardless of
why they are still there — a failed transfer can leave files behind even with
debug mode off, so pruning runs unconditionally, not only in debug mode.

## `install_id()`

A random per-install UUID (`uuid.uuid4().hex`), created on first use and
persisted at `USER_DIR/install_id.txt`, read back after. Deliberately NOT
hardware-derived: the root constitution gives no capacity for fingerprinting a
stranger's machine, and a swapped disk or a reinstall would silently change a
hardware id anyway — which would look like a second installation in the
destination's folder layout for no reason. If the id cannot be persisted
(read-only `USER_DIR`) a value is still handed back so shipping is not
blocked by it; it simply will not survive a restart.

## The caller must never block or raise

`offer()` is called from server teardown and from a phone connection's own
thread — a full disk, a missing drive or a worker that failed to start must
never turn into a hung shutdown or a broken connection. One background worker
drains a bounded queue (`QUEUE_MAX` = 200); anything that cannot be queued
(queue full, worker never started) is logged and dropped rather than raised.
The bound exists so a stuck shipper cannot let its own queue become the
unbounded disk fill this module exists to prevent.

## Classes and functions

### `LogShipper`
- `offer(path)` — queues a finished file; never raises, never blocks.
- `ship(path)` — the copy → verify → delete sequence for one file; returns
  whether the transfer was CONFIRMED (a no-op — empty target, missing source
  — is not a confirmed transfer).
- `prune()` — keeps at most `log_debug_keep_files` local files, newest first.
- `sweep(settings=None)` — called once at start: prune, then re-offer every
  local file still on disk (a previous run's unconfirmed transfer, or one
  that arrived while the destination was unreachable).

### Module functions
- `install_id()` — see above.
- `_resolve_target(target)` — the one place that decides what kind of
  destination `log_upload_target` is: a directory `Path`, or `None` for an
  empty or unimplemented (URL) target.

### `SHIPPER`
The one live shipper. Constructing it touches no disk beyond reading
settings — nothing is queued or shipped until something calls `offer()` or
`sweep()`.

## Connections

### Uses
- `config.SETTINGS` — `log_upload_target`, `log_upload_verify`,
  `log_debug_mode`, `log_debug_keep_files`, `session_log_dir`
- `config.USER_DIR` — where `install_id.txt` is persisted

### Used by
- [Session Log](session_log.md) — `close()` and `repair_unclosed()` hand
  finished files to `SHIPPER.offer()`

## Honest limits

- Verification only proves the bytes that arrived match the bytes that were
  read locally at copy time — a source file rewritten mid-copy (it should
  not be; `session_log.py` only hands off files it has already rolled past)
  is not this module's problem to detect.
- `log_upload_verify=False` skips the SHA-256 and trusts a size match alone —
  cheaper, and a false positive (same size, different bytes) is possible in
  principle though not in the failure modes this exists to catch (short
  copies, truncated writes).
- An HTTP destination is a refusal, not a feature — `log_upload_target` can
  only be a filesystem folder today.
