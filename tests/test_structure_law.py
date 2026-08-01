"""Guard: THE STRUCTURE LAW (root CLAUDE.md Rule #20, Priority S / rules/CODE.md
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


if __name__ == "__main__":
    test_no_file_exceeds_structure_law_threshold()
    test_ratchet_entries_reference_existing_files()
    print("PASS — test_structure_law")
