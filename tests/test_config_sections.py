"""Guard: THE CONFIG SECTION LAW (root CLAUDE.md Rule #20 addendum /
rules/CODE.md -> Enforcement). Every file listed in CONFIG_FILES must have
every top-level definition sitting under a `# ══...══` section banner, must
never post-definition-patch an earlier module-level table
(`TABLE[...] = ...` / `TABLE.update(...)` outside the table's own section),
and must never define a dict literal with duplicate keys.

Python-only (the law's post-definition-patch and duplicate-key checks are
AST-based; this project's config/data-table files are all Python).
"""

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _guards_common import PROJECT_ROOT  # noqa: E402

# Config/data-table files seeded from the 2026-08-01 docs migration + THE
# STRUCTURE LAW pass: server/config.py (the Settings dataclass — every
# tunable in the project) and server/gui/theme.py (TOKENS dict + QSS
# stylesheet). Add a file here the moment it becomes a config/data table
# per DOCS.md's tier rules — and give it section banners in the same commit.
CONFIG_FILES = [
    "server/config.py",
    "server/gui/theme.py",
]

BANNER_RE = re.compile(r"#.*═{5,}")


def _banner_lines(source: str) -> list[int]:
    return [i + 1 for i, line in enumerate(source.splitlines()) if BANNER_RE.search(line)]


def _top_level_table_names(tree: ast.Module) -> set[str]:
    """Names assigned at module level — candidate 'tables' a later statement
    could illegally patch."""
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _is_boilerplate(node: ast.stmt) -> bool:
    """Imports and the module docstring are prologue, not a 'definition'
    that needs its own section banner."""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return True
    if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
        return True
    return False


def _check_file(path: Path) -> list[str]:
    problems = []
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    banners = _banner_lines(source)
    table_names = _top_level_table_names(tree)
    rel = path.relative_to(PROJECT_ROOT).as_posix()

    for node in tree.body:
        if _is_boilerplate(node):
            continue
        if not any(b <= node.lineno for b in banners):
            problems.append(f"{rel}:{node.lineno}: top-level definition outside any section banner")

        # Post-definition patching: TABLE[...] = ... at module level.
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) \
                        and t.value.id in table_names:
                    problems.append(
                        f"{rel}:{node.lineno}: post-definition patch of "
                        f"{t.value.id!r} ({t.value.id}[...] = ... away from its section)"
                    )
        # Post-definition patching: TABLE.update(...) at module level.
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "update" \
                    and isinstance(call.func.value, ast.Name) \
                    and call.func.value.id in table_names:
                problems.append(
                    f"{rel}:{node.lineno}: post-definition patch of "
                    f"{call.func.value.id!r} (.update(...) away from its section)"
                )

    # Duplicate dict keys anywhere in the file (nested dicts included).
    for dict_node in ast.walk(tree):
        if not isinstance(dict_node, ast.Dict):
            continue
        seen = set()
        for key in dict_node.keys:
            if key is None or not isinstance(key, ast.Constant):
                continue  # **spread or a computed key — not statically checkable
            if key.value in seen:
                problems.append(f"{rel}:{dict_node.lineno}: duplicate dict key {key.value!r}")
            seen.add(key.value)

    return problems


def test_config_sections_law():
    all_problems = []
    for rel in CONFIG_FILES:
        path = PROJECT_ROOT / rel
        assert path.exists(), f"CONFIG_FILES entry does not exist: {rel}"
        all_problems.extend(_check_file(path))
    assert not all_problems, "THE CONFIG SECTION LAW violated:\n" + "\n".join(all_problems)


if __name__ == "__main__":
    test_config_sections_law()
    print("PASS — test_config_sections")
