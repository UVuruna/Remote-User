"""Gate for setup/release_hygiene.py — closer (d) of task 187.

Proves `assert_clear_to_release` really refuses when update.json says a
handover is genuinely in flight, and really clears every other state: no
file, an unreadable file, a finished/failed record (state != "handover"),
and a record so old it can only be a crash left behind, not a live update.

Each check is proven by planting the exact opposite of what it claims —
see `check_a_stale_record_never_bricks_a_release` and
`check_only_state_handover_blocks`, which assert the function's behaviour
changes when the ONE fact it is supposed to key off changes and nothing
else does.

Run:  .venv\\Scripts\\python tests/test_release_hygiene.py
"""

import json
import sys
import tempfile
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "setup"))

import release_hygiene  # noqa: E402


def _write(dir_: Path, **fields) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / "update.json"
    path.write_text(json.dumps(fields), encoding="utf-8")
    return path


def check_no_file_is_clear() -> bool:
    d = Path(tempfile.mkdtemp(prefix="ru_hygiene_"))
    in_flight, reason = release_hygiene.update_in_flight(d)
    return in_flight is False and "no update record" in reason


def check_a_live_handover_is_refused() -> bool:
    """THE CASE THIS EXISTS FOR: a fresh "state": "handover" record, just
    now armed — exactly what his machine looked like mid-102->103."""
    d = Path(tempfile.mkdtemp(prefix="ru_hygiene_"))
    _write(d, state="handover", to="0.0.104", at=time.time())
    in_flight, reason = release_hygiene.update_in_flight(d)
    ok = in_flight is True and "0.0.104" in reason
    try:
        release_hygiene.assert_clear_to_release(d)
        raised = False
    except SystemExit as e:
        raised = e.code == 1
    return ok and raised


def check_a_finished_record_is_clear() -> bool:
    """announce() always consumes the record and either never rewrites it
    (success) or leaves nothing with state="handover" behind — this proves
    the hygiene check reads the SAME state field, not a stale guess."""
    d = Path(tempfile.mkdtemp(prefix="ru_hygiene_"))
    _write(d, state="finished", to="0.0.104", at=time.time())
    in_flight, reason = release_hygiene.update_in_flight(d)
    return in_flight is False and "finished" in reason


def check_only_state_handover_blocks() -> bool:
    """Planted-defect proof by construction: the SAME record, differing in
    exactly one field (state), must flip the verdict — proving the check
    keys off that field and nothing else (not merely "a file exists")."""
    d = Path(tempfile.mkdtemp(prefix="ru_hygiene_"))
    fresh = time.time()
    _write(d, state="handover", to="0.0.104", at=fresh)
    blocked, _ = release_hygiene.update_in_flight(d)
    _write(d, state="failed", to="0.0.104", at=fresh)
    cleared, _ = release_hygiene.update_in_flight(d)
    return blocked is True and cleared is False


def check_an_unreadable_record_is_clear_not_a_brick() -> bool:
    """Garbage on disk must never permanently refuse every future release —
    the same "never brick" rule update_handover.py's own lock reclaim
    follows for exactly the same reason."""
    d = Path(tempfile.mkdtemp(prefix="ru_hygiene_"))
    d.mkdir(parents=True, exist_ok=True)
    (d / "update.json").write_text("{not json", encoding="utf-8")
    in_flight, reason = release_hygiene.update_in_flight(d)
    return in_flight is False and "unreadable" in reason


def check_a_stale_record_never_bricks_a_release() -> bool:
    """Planted-defect proof: a record from 20 minutes ago (past
    STALE_AFTER_S = 15 min) must clear even though state is still
    "handover" — proving the age check is really consulted and is not
    dead code shadowed by the state check above it."""
    d = Path(tempfile.mkdtemp(prefix="ru_hygiene_"))
    stale_at = time.time() - release_hygiene.STALE_AFTER_S - 60
    _write(d, state="handover", to="0.0.104", at=stale_at)
    in_flight, reason = release_hygiene.update_in_flight(d)
    return in_flight is False and "min old" in reason


def check_a_fresh_record_one_second_old_still_blocks() -> bool:
    """The boundary case beside the one above it: fresh must still block,
    proving STALE_AFTER_S is a real threshold and not an always-clear no-op
    disguised as a feature."""
    d = Path(tempfile.mkdtemp(prefix="ru_hygiene_"))
    _write(d, state="handover", to="0.0.104", at=time.time() - 1)
    in_flight, _ = release_hygiene.update_in_flight(d)
    return in_flight is True


def check_missing_localappdata_is_a_loud_error_not_a_silent_clear() -> bool:
    """When called with no explicit dir (the real release-time call shape)
    and LOCALAPPDATA is unset, this must raise rather than silently answer
    "clear" — a check that can fail open on a broken environment is worse
    than a build that refuses to run at all."""
    import os
    had = "LOCALAPPDATA" in os.environ
    saved = os.environ.pop("LOCALAPPDATA", None)
    try:
        release_hygiene.update_record_path()
        return False  # should have raised
    except RuntimeError:
        return True
    finally:
        if had:
            os.environ["LOCALAPPDATA"] = saved


def main() -> int:
    results = {
        "no update.json at all is clear": check_no_file_is_clear(),
        "a live handover record is REFUSED (the task 187 case)":
            check_a_live_handover_is_refused(),
        "a finished record is clear": check_a_finished_record_is_clear(),
        "only state==handover blocks (planted-defect: flip one field)":
            check_only_state_handover_blocks(),
        "an unreadable record clears, never bricks a release":
            check_an_unreadable_record_is_clear_not_a_brick(),
        "a stale (>15 min) handover record never bricks a release "
        "(planted-defect: age past the threshold)":
            check_a_stale_record_never_bricks_a_release(),
        "a fresh (<15 min) handover record still blocks (the threshold "
        "boundary, proven both ways)":
            check_a_fresh_record_one_second_old_still_blocks(),
        "a missing LOCALAPPDATA is a loud error, never a silent clear":
            check_missing_localappdata_is_a_loud_error_not_a_silent_clear(),
    }
    print("\n=== RELEASE HYGIENE GATE (task 187d) ===")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok in results.items() if not ok]
    if failed:
        print(f"\nRELEASE HYGIENE GATE FAILED — {len(failed)} check(s).",
              file=sys.stderr)
        return 1
    print("\nRELEASE HYGIENE GATE PASSED.")
    return 0


def test_release_hygiene():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
