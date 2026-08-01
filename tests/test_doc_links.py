"""Guard: the navigation chain (DOCS.md -> Navigation & the Living Docs Rule).
Every project `.md` file must be reachable from `README.md` by following
relative `.md` links (`___folder.md` -> `__about/`, `__flow/`, sibling folder
docs...), and every relative link in every `.md` file (including the
"(script)" links to source files) must resolve to a real file on disk.

Link syntax matched: markdown `[text](path)` and `[text](path#anchor)`.
External links (http/https/mailto) and pure same-page anchors (`#foo`) are
ignored — they are not part of the on-disk navigation chain.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _guards_common import PROJECT_ROOT, iter_doc_files  # noqa: E402

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
EXTERNAL_RE = re.compile(r"^(https?://|mailto:)", re.IGNORECASE)


def _extract_relative_targets(md_file: Path) -> list[str]:
    """Every non-external, non-pure-anchor link target in this file, with any
    `#anchor` suffix stripped."""
    text = md_file.read_text(encoding="utf-8", errors="replace")
    targets = []
    for raw in LINK_RE.findall(text):
        raw = raw.strip()
        if not raw or raw.startswith("#") or EXTERNAL_RE.match(raw):
            continue
        targets.append(raw.split("#", 1)[0])
    return targets


def _resolve(md_file: Path, target: str) -> Path:
    return (md_file.parent / target).resolve()


def test_every_relative_link_resolves_to_a_real_file():
    broken = []
    for md_file in iter_doc_files():
        for target in _extract_relative_targets(md_file):
            resolved = _resolve(md_file, target)
            if not resolved.exists():
                rel = md_file.relative_to(PROJECT_ROOT).as_posix()
                broken.append(f"{rel} -> {target} (resolves to missing {resolved})")
    assert not broken, "Broken relative links:\n" + "\n".join(broken)


def test_every_doc_reachable_from_readme():
    readme = PROJECT_ROOT / "README.md"
    assert readme.exists(), "README.md is missing — the whole nav chain starts there"

    all_docs = {p.resolve() for p in iter_doc_files()}

    visited: set[Path] = set()
    frontier = [readme.resolve()]
    while frontier:
        current = frontier.pop()
        if current in visited or current.suffix != ".md" or not current.exists():
            continue
        visited.add(current)
        for target in _extract_relative_targets(current):
            if not target.lower().endswith(".md"):
                continue  # script/asset links don't extend the doc-navigation graph
            resolved = _resolve(current, target)
            if resolved not in visited:
                frontier.append(resolved)

    unreachable = sorted(
        p.relative_to(PROJECT_ROOT).as_posix() for p in (all_docs - visited)
    )
    assert not unreachable, (
        "Docs unreachable from README.md (broken navigation chain):\n"
        + "\n".join(unreachable)
    )


if __name__ == "__main__":
    test_every_relative_link_resolves_to_a_real_file()
    test_every_doc_reachable_from_readme()
    print("PASS — test_doc_links")
