"""Guard: THE STRUCTURE LAW (root CLAUDE.md -> The Laws, Priority S / rules/CODE.md
-> Enforcement). No source file may exceed ~1,000 lines unless it is in the
RATCHET allowlist below. Each allowlist entry documents WHY the file stays
whole and which session owes the split. The allowlist may only SHRINK —
adding an entry requires the owner's explicit approval in that same session.

Counts .py, .js, .ts, .kt, .html and .css sources — not Python only. This
project's one historical violation was client/app.js (a JS file).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _guards_common import PROJECT_ROOT, iter_source_files  # noqa: E402

THRESHOLD = 1000

# RATCHET allowlist — empty. The one historical violation, client/app.js
# (1,174 lines: WebSocket connection, rendering, gestures, controls all in
# one file), was split by responsibility into 6 cohesive modules — state.js,
# render.js, input-geometry.js, controls.js, gestures.js, connection.js —
# during the 2026-08-01 docs-migration + god-file session (see
# client/___client.md Design Decisions). Nothing else in the project has
# ever crossed the threshold.
RATCHET: dict[str, str] = {}


def test_no_file_exceeds_structure_law_threshold():
    violations = []
    for path in iter_source_files():
        with path.open(encoding="utf-8", errors="replace") as f:
            line_count = sum(1 for _ in f)
        if line_count <= THRESHOLD:
            continue
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel in RATCHET:
            continue
        violations.append(f"{rel}: {line_count} lines (> {THRESHOLD}, no RATCHET entry)")
    assert not violations, "THE STRUCTURE LAW violated:\n" + "\n".join(violations)


def test_ratchet_entries_reference_existing_files():
    # A ratchet entry for a file that no longer exists (renamed/split/deleted)
    # is dead weight that should be cleaned up, not silently carried forward.
    missing = [rel for rel in RATCHET if not (PROJECT_ROOT / rel).exists()]
    assert not missing, f"RATCHET entries for files that no longer exist: {missing}"


def test_no_log_file_lands_in_the_project_root():
    """Owner ruling 2026-08-16: a log may NEVER end up in the project root,
    and `.gitignore` is deliberately NOT the answer.

    WHAT HAPPENED, measured rather than assumed. Twelve files (`out.log`,
    `out2-4`, `outP`, `outR1-3`, `err.log`, `err2-4`) sat in the root, all
    written between 02:00 and 02:06 on 2026-08-16. Nothing in this repo writes
    them — the app's own `log_dir` is `USER_DIR` when frozen and `logs/` in a
    checkout, never the root. Their CONTENT names their author: the headings
    `=== a. file-backed span, no zoom ===` and `=== d. during/after a pan ===`
    are exactly the four states the T110 reproduction agent measured that
    night, and the run counts match its own record. An agent wrote a throwaway
    probe and captured it with a shell redirect from the project directory.

    WHY A GUARD AND NOT AN IGNORE RULE, which is the owner's point and the
    better one: `*.log` in `.gitignore` would have made these invisible
    instead of absent. They would still be written, still accumulate, and the
    next person to look would find a root full of files git had been told to
    pretend were not there. The rule he actually wants is that they must not
    be CREATED here, so the check fails the build and names the file — the
    only thing an ignore rule cannot do.

    Scoped to the ROOT on purpose: `logs/` is where a dev run is supposed to
    write, and a test that captures output into its own temp directory is
    fine. It is the root that must stay clean.
    """
    strays = sorted(p.name for p in PROJECT_ROOT.glob("*.log"))
    assert not strays, (
        "Log file(s) in the project root: " + ", ".join(strays) + "\n"
        "Nothing here may write a log to the project root. The app writes to "
        "USER_DIR (frozen) or logs/ (checkout); a probe or a harness must "
        "capture its output into its own temp directory. Delete these and "
        "redirect the writer — do NOT add them to .gitignore (owner ruling "
        "2026-08-16: an ignored log is hidden, not prevented)."
    )


if __name__ == "__main__":
    test_no_file_exceeds_structure_law_threshold()
    test_ratchet_entries_reference_existing_files()
    test_no_log_file_lands_in_the_project_root()
    print("PASS — test_structure_law")
