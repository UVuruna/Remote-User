"""Fast guard runner — THE STRUCTURE LAW, THE CONFIG SECTION LAW, docs
coverage, and doc-links, wired into Claude Code hooks (.claude/settings.json).

Exit 2 on any guard failure (what makes a PostToolUse/Stop hook BLOCKING);
exit 0 when every guard is green. Never runs the project's own app/test
suite (tests/test_input_pipeline.py) — guards only, kept fast and
deterministic per rules/CODE.md -> Enforcement.

Usage:
    python tests/run_guards.py           # all four guards
    python tests/run_guards.py --fast    # structure + config-sections only
                                          # (the PostToolUse hook's speed budget)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_structure_law as structure_law  # noqa: E402
import test_config_sections as config_sections  # noqa: E402
import test_docs_coverage as docs_coverage  # noqa: E402
import test_doc_links as doc_links  # noqa: E402
import test_layout_law as layout_law  # noqa: E402

FAST_CHECKS = [
    ("structure law", structure_law.test_no_file_exceeds_structure_law_threshold),
    ("structure law (ratchet)", structure_law.test_ratchet_entries_reference_existing_files),
    ("config sections", config_sections.test_config_sections_law),
    # The static half of the layout law is a grep — it costs nothing and
    # belongs where the damage is done (rules/GUI.md → Law — Space &
    # Legibility; MIGRATE-LAYOUT.md step 5).
    ("layout law (static)", layout_law.test_no_banned_layout_patterns),
    ("layout law (ratchet)", layout_law.test_ratchet_entries_still_exist),
]

def _control_sets() -> None:
    """Imported lazily for the same reason as the Qt audit below: it builds
    the real Controls dialog offscreen. Guards the owner's actions.json
    against being silently rewritten (both failures of 2026-08-05)."""
    import test_controls_sets
    for _, check in test_controls_sets.CHECKS:
        check()


def _layout_audit_qt() -> None:
    """Imported lazily: it pulls in PySide6 and builds an offscreen
    QApplication, which the --fast path must never pay for."""
    import test_layout_audit_qt
    test_layout_audit_qt.test_layout_audit()


FULL_ONLY_CHECKS = [
    ("docs coverage (classified)", docs_coverage.test_every_source_file_is_classified),
    ("docs coverage (required docs)", docs_coverage.test_standard_and_algorithmic_files_have_required_docs),
    ("docs coverage (no stray docs)", docs_coverage.test_trivial_and_tests_tier_files_have_no_stray_doc),
    ("docs coverage (folder docs)", docs_coverage.test_every_code_folder_has_a_folder_doc),
    ("doc links (no broken links)", doc_links.test_every_relative_link_resolves_to_a_real_file),
    ("doc links (reachable from README)", doc_links.test_every_doc_reachable_from_readme),
    # The runtime half: opens every Qt window offscreen and measures it.
    # Full run only — it builds a QApplication (~1 s), too slow for the
    # PostToolUse budget.
    ("control sets (never silently rewritten)", _control_sets),
    ("layout audit (Qt windows)", _layout_audit_qt),
]


def main() -> int:
    fast_only = "--fast" in sys.argv
    checks = FAST_CHECKS if fast_only else FAST_CHECKS + FULL_ONLY_CHECKS

    failures = []
    for name, check in checks:
        try:
            check()
        except AssertionError as e:
            failures.append(f"[{name}] {e}")

    if failures:
        print("GUARDS FAILED:\n", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
            print(file=sys.stderr)
        return 2

    scope = "fast (structure + config-sections)" if fast_only else "full (all guards)"
    print(f"GUARDS PASSED — {scope}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
