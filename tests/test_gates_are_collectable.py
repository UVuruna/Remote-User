"""Gate: every `tests/test_*.py` file pytest can see must yield at least one
collected item.

Thirty of this project's gate files carried `main()`/`check_*()` logic and
an `if __name__ == "__main__":` entry but no `def test_*` at all — pytest
imported them, found nothing to run, and reported them as neither passed nor
failed. Every "N/N green" evidence line silently excluded them, and a
refactor broke three of them unnoticed (see `docs/DECISIONS.md`, 2026-08-19
entry, and commit 560379d). This guard is the regression fence: it cannot
name WHICH check is wrong inside a file, only that the file went dark.

Runs pytest's own collector as a subprocess (never re-imports this project's
modules into the guard's own process — a collected item can have import-time
side effects, e.g. building a QApplication) and cross-checks its file list
against every `tests/test_*.py` name on disk.
"""

import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent


def _own_test_files() -> list[str]:
    """Every gate file pytest is expected to collect from — top-level
    `tests/test_*.py` only; `tests/manual/` is driven by hand, never by
    pytest or `setup/gates.py`."""
    return sorted(p.name for p in TESTS_DIR.glob("test_*.py"))


def _collected_files() -> set[str]:
    """The file part of every `tests/test_x.py::test_y` item pytest's own
    collector reports for this directory, one real subprocess call."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", str(TESTS_DIR)],
        cwd=PROJECT_ROOT, capture_output=True, text=True)
    names: set[str] = set()
    for line in proc.stdout.splitlines():
        if "::" not in line:
            continue
        rel = line.split("::", 1)[0]
        names.add(Path(rel).name)
    return names


def check_no_test_file_collects_zero_items() -> None:
    collected = _collected_files()
    missing = [name for name in _own_test_files() if name not in collected]
    assert not missing, (
        "pytest collects NOTHING from: " + ", ".join(missing) +
        " — add a `def test_*` that calls the existing check(s), keeping "
        "the `if __name__ == \"__main__\":` entry `setup/gates.py` needs "
        "(see tests/___tests.md, and commit 560379d for the shape of the "
        "failure this guards against)")


def test_gates_are_collectable() -> None:
    check_no_test_file_collects_zero_items()


def main() -> int:
    try:
        check_no_test_file_collects_zero_items()
    except AssertionError as e:
        print(f"GATES ARE COLLECTABLE — FAILED: {e}")
        return 1
    print("GATES ARE COLLECTABLE — every tests/test_*.py yields a pytest item")
    return 0


if __name__ == "__main__":
    sys.exit(main())
