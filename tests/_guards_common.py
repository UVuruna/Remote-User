"""Shared helpers for the project's guard tests (test_structure_law,
test_config_sections, test_docs_coverage, test_doc_links). Not a test module
itself — no `test_` prefix, pytest will not collect it.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories never scanned by any guard: vendored/generated/build output,
# the Python venv, VCS internals, and the owner's gitignored UV/ inbox.
# PRUNED during the walk (never descended into) — .venv alone holds tens of
# thousands of files; filtering them out AFTER an os.walk/rglob would blow
# the guard runner's <~2s speed budget (rules/CODE.md -> Enforcement).
EXCLUDE_DIR_NAMES = {
    ".venv", "venv", "node_modules", "build", "dist", ".git", "__pycache__",
    "vendor", ".gradle", ".kotlin", "cert", "UV", ".pytest_cache",
}

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".kt", ".html", ".css"}


def _walk_files(suffixes: set[str]):
    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for name in filenames:
            if Path(name).suffix in suffixes:
                yield Path(dirpath) / name


def iter_source_files(extensions=SOURCE_EXTENSIONS):
    """Yields every project source file with one of `extensions`, skipping
    vendored/build/venv directories (pruned, not just filtered). Covers
    every source language in this project (Python server, JS client, Kotlin
    android) — THE STRUCTURE LAW is not Python-only."""
    yield from _walk_files(extensions)


def iter_doc_files():
    """Yields every project .md file, skipping vendored/build/venv dirs and
    the owner's gitignored UV/ inbox."""
    yield from _walk_files({".md"})
