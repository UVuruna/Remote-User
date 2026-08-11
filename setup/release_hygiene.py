"""Closer (d) of task 187: never publish a GIT RELEASE while HIS machine is
mid-update.

Task 187's second half (owner, unwritten but standing rule): v0.0.104 was
published while his 102->103 handover was still in flight, so the fresh
app that came up out of that handover immediately found a NEWER release
waiting and offered to update again -- on top of a storm the fork had
already caused. "Check his installed state first" is a rule this project
already carries (`decisions-are-dated-quotes` / `owner-runs-stale-build`
memory) and it was not followed here.

This module answers exactly one question, honestly, from local disk state
alone: **does %LOCALAPPDATA%/RemoteUser/update.json say a handover is
genuinely still in flight right now?** It does not, and cannot, ask
GitHub, and it does not reach into any other machine -- it reads
`update.json` on WHATEVER MACHINE THIS RUNS ON, which is only useful when
run on (or against a copy of) the machine that matters. See the module
docstring's "HONEST LIMITS" section below before wiring this in.

Not imported by setup/build.py (file-ownership boundary for this task) --
see the wiring note at the bottom of this file and the task 187 report for
the two call sites the coordinator should add.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Mirrors server/update_handover.py's RECORD_STATE and update_handover's own
# staleness rule (LOCK_STALE_S) -- duplicated as small literals rather than
# imported: this script must run from setup/, standalone, before or without a
# `server` on sys.path (e.g. from a CI box that never pip-installed the app),
# and importing update_handover for two constants is not worth coupling a
# release-time check to the app's own import graph. See HONEST LIMITS below.
HANDOVER_STATE = "handover"

# Same number as update_handover.LOCK_STALE_S: far past anything a genuine
# handover can honestly take (30s exit wait + silent install + 40s start
# wait + antivirus slack). A record older than this is not "in flight" --
# it is a crashed or forgotten one, and refusing a release over it forever
# would be a worse bug than the one this closer exists to prevent.
STALE_AFTER_S = 15 * 60


def update_record_path(user_dir: Path | None = None) -> Path:
    """Where update.json lives. `user_dir` is for tests and for pointing
    this at a machine OTHER than the one running the check (e.g. a copy of
    the owner's %LOCALAPPDATA%\\RemoteUser pulled down for inspection);
    default is THIS machine's own %LOCALAPPDATA%\\RemoteUser, which is the
    right answer only when this script runs where the release matters —
    see HONEST LIMITS.
    """
    if user_dir is not None:
        return user_dir / "update.json"
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError(
            "LOCALAPPDATA is not set — cannot locate update.json on this "
            "machine (not Windows, or a stripped environment)")
    return Path(local) / "RemoteUser" / "update.json"


def update_in_flight(user_dir: Path | None = None) -> tuple[bool, str]:
    """(True, reason) when update.json says a handover is genuinely live;
    (False, reason) otherwise — missing file, unreadable file, a finished/
    failed record already consumed by `announce()`, or a record so old it
    can only be a crash. `reason` is always a full sentence: this is what a
    release script prints when it refuses, and a bare boolean tells nobody
    why the release did not happen.
    """
    path = update_record_path(user_dir)
    if not path.exists():
        return False, f"no update record at {path} — nothing in flight"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        # An unreadable record answers exactly like update_handover.py's own
        # _read_record() does elsewhere in this project: treat it as nothing
        # rather than block a release on a file we cannot even parse.
        return False, f"update record at {path} is unreadable ({e}) — treating as clear"
    if record.get("state") != HANDOVER_STATE:
        return False, f"update record state is {record.get('state')!r}, not in flight"
    at = record.get("at")
    age = time.time() - float(at) if isinstance(at, (int, float)) else None
    if age is not None and age > STALE_AFTER_S:
        return False, (
            f"update record is {age / 60:.0f} min old (> {STALE_AFTER_S // 60} min) "
            "— a stale handover, not a live one")
    target = record.get("to", "?")
    age_text = f"{age:.0f}s ago" if age is not None else "at an unknown time"
    return True, (
        f"an update to v{target} was armed {age_text} and update.json still "
        f"says \"state\": \"{HANDOVER_STATE}\" — his machine may still be "
        "mid-handover; publishing now risks exactly task 187's second bug "
        "(a new release landing while an old one is still installing)")


def assert_clear_to_release(user_dir: Path | None = None) -> None:
    """Raise SystemExit(1) with the reason printed, when a release must not
    happen right now. Returns normally (nothing printed) when it is clear —
    silence-on-success matches every other build.py step in this project.
    """
    in_flight, reason = update_in_flight(user_dir)
    if in_flight:
        print(f"RELEASE REFUSED — {reason}", file=sys.stderr)
        raise SystemExit(1)


# ═══════════════════════════ HONEST LIMITS ═══════════════════════════
# 1. This reads update.json on the machine it RUNS ON. If the release is
#    built and published from a machine that is not the owner's own PC —
#    a CI runner, a different dev box — this check is answering a question
#    about the WRONG machine and will always say "clear" whether or not he
#    is really mid-update. As of this task there is no telemetry channel
#    that reports his update.json to a build machine that is not his own;
#    the honest fix, if releases ever move off his own PC, is a check
#    wired through `notify`'s existing phone-reachable channel or a small
#    server endpoint — out of scope for a file-ownership-bounded task.
# 2. It answers "was a handover armed and not yet resolved", never "is his
#    phone currently reachable" or "is a human at the keyboard" — a
#    handover that crashed silently past STALE_AFTER_S reads as clear, by
#    design (see update_handover.py's own LOCK_STALE_S reasoning: a check
#    that can never be reclaimed is worse than the bug it guards against).
# 3. It is a REFUSAL, not a wait-and-retry: a release attempted while an
#    update is genuinely in flight must be re-run by a human after the
#    handover settles, not looped on automatically — build.py already runs
#    under the owner's own supervision for every release, so a silent
#    retry loop would be one more thing that "just works" until it does
#    not.
#
# ═══════════════════════════ WIRING (for the coordinator; build.py is out
#                              of this task's file ownership) ═══════════
#   from release_hygiene import assert_clear_to_release
#   assert_clear_to_release()   # call near the TOP of build.main(), before
#                                # any build step — a release that fails
#                                # this must cost nothing, so it has to run
#                                # before PyInstaller, not after.
# Import path: setup/ is already on sys.path for anything build.py itself
# runs from (same directory) — `from release_hygiene import ...` next to
# the existing `from setup.X import Y` style already in build.py.


def main() -> int:
    in_flight, reason = update_in_flight()
    if in_flight:
        print(f"RELEASE REFUSED — {reason}", file=sys.stderr)
        return 1
    print(f"Clear to release — {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
