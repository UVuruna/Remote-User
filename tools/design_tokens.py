"""THE ENGINE — where each design value lives, and how it is read and written.

The catalogue moved to `tools/design_groups.py` on 2026-08-19 (owner round 2):
that file says WHICH knobs exist, in which group, and what each one is for;
this one says where the value is on disk and how to change it without touching
anything around it. Two questions, two files, and the vocabulary is now free to
grow — a sentence and a diagram per row — without pushing the engine towards
the structure wall.

WHY A REGISTRY AND NOT A JSON FILE OF VALUES. The values already have a home:
client/theme.css (colour, per theme), client/style.css (shape), client/theme.js
(the two shadow colours, which are a rule in code) and server/config.py (the
set palette). A tuner that kept its own copy would be a second source of truth,
and the second one goes stale — this project has the scars. So nothing here
holds a value. Every read parses the real file, every save rewrites the real
declaration in place, and the prose around it — the owner's verdicts, the
graders' findings, the dates — is never touched.

WHAT MAY BE WRITTEN. Exactly the declarations the catalogue names, and only
inside the block they are declared in. The writer matches `--name: <value>;` by
name; a rule, a selector, a comment or an unknown token is not something it can
reach even if the page asks. That is the whole safety story of this tool.

PINNED VALUES ARE STILL OFFERED. Some of these numbers are the owner's own,
settled on a ballot and guarded by a test that names the date. They are shown
with the gate that pins them and saved like any other — the gate then fails,
loudly, which is exactly right: re-opening his verdict is his to do, and the
failing gate is the reminder that docs/DECISIONS.md is updated in the same
round. A tool that silently refused would just send him back to the editor.
"""

from __future__ import annotations

import re
from pathlib import Path

from design_groups import GROUPS, PINNED, SET_PIN

PROJECT = Path(__file__).resolve().parent.parent

__all__ = ["GROUPS", "PINNED", "SET_PIN", "SOURCES", "JS_ALPHAS", "THEME_JS",
           "read_source", "read_js_alpha", "alpha_of", "with_alpha",
           "snapshot", "write_source", "write_js_alpha", "pins_touched"]


# ═══════════════════════════ THE SOURCES ═══════════════════════════
# Every tunable lives in one of five places.
#   "css"   — a rule whose body is `--name: value;` declarations
#   "dict"  — one Python dict of name -> "#hex"
#   "const" — top-level `const NAME = "value";` in a JS file. Not a block: the
#             two shadow COLOURS are a rule the page applies per element, so
#             they were never CSS and could never be a theme token.
SOURCES = {
    "dark": {"file": "client/theme.css", "open": ":root {", "kind": "css"},
    "light": {"file": "client/theme.css", "open": 'body[data-theme="light"] {',
              "kind": "css"},
    "shape": {"file": "client/style.css", "open": ":root {", "kind": "css"},
    "sets": {"file": "server/config.py", "open": "SET_COLORS = {", "kind": "dict"},
    "js": {"file": "client/theme.js", "open": None, "kind": "const"},
}

# The JS twins of two CSS alphas. client/theme.js computes the COLOURED looks'
# shadows in code, so the strength the owner tunes has to land in both places
# or the plain and the coloured looks drift apart by a value nobody edited.
JS_ALPHAS = {
    "--ink-shadow": "INK_SHADOW_ALPHA",
    "--lbl-shadow": "LBL_SHADOW_ALPHA",
}
THEME_JS = "client/theme.js"

# An `rgb()` triple as client/theme.js spells it — `0 0 0`, `255 255 255`.
# The value is interpolated straight into a CSS colour by `shadowFor`, so this
# is not tidiness: it is the check that stops a page bug from becoming a
# stylesheet that silently draws nothing.
_TRIPLE = re.compile(r"^\d{1,3} \d{1,3} \d{1,3}$")


# ═══════════════════════════ READING ═══════════════════════════
_DECL = re.compile(r"^\s*(--[\w-]+)\s*:\s*(.+?);", re.M)
_ENTRY = re.compile(r'^\s*"([^"]+)"\s*:\s*"([^"]+)"\s*,', re.M)


def _block(source_id: str, text: str) -> tuple[int, int]:
    """The span of one source's body — from its opener to the line that closes
    it. A brace in the FIRST column is the close: every declaration inside is
    indented, so nothing nested can end the block early."""
    src = SOURCES[source_id]
    start = text.index(src["open"]) + len(src["open"])
    end = text.index("\n}", start)
    return start, end


def _const_names() -> list:
    """The JS constants the catalogue offers — the only names a `const` source
    is ever asked about, so a file full of other constants is not something
    this tool can wander into."""
    return [row["token"] for group in GROUPS for row in group["rows"]
            if row["kind"] == "jscolor"]


def read_source(source_id: str) -> dict:
    text = (PROJECT / SOURCES[source_id]["file"]).read_text(encoding="utf-8")
    kind = SOURCES[source_id]["kind"]
    if kind == "const":
        found = {}
        for name in _const_names():
            match = re.search("^const " + re.escape(name) + r' = "([^"]*)";',
                              text, re.M)
            if match:
                found[name] = match.group(1)
        return found
    start, end = _block(source_id, text)
    body = text[start:end]
    pattern = _ENTRY if kind == "dict" else _DECL
    return {m.group(1): m.group(2).strip() for m in pattern.finditer(body)}


def read_js_alpha(const: str):
    text = (PROJECT / THEME_JS).read_text(encoding="utf-8")
    match = re.search(r"^const " + const + r" = ([\d.]+);", text, re.M)
    return float(match.group(1)) if match else None


def alpha_of(css_color: str) -> float:
    """The strength slot of `rgb(r g b / a)`. A colour with no slot is opaque —
    said here once rather than at each call site."""
    match = re.search(r"/\s*([\d.]+)\s*\)", css_color)
    return float(match.group(1)) if match else 1.0


def with_alpha(css_color: str, alpha: float) -> str:
    """The same colour at a new strength. The HUE is untouched on purpose: a
    shadow's colour is a rule (the ink's opposite), and this tool tunes how
    strong it is, never what it is."""
    text = ("%g" % float(alpha))
    # UNCHANGED MEANS UNTOUCHED. `0.80` and `0.8` are the same strength and a
    # different line: a save that reformatted every alpha it merely READ would
    # bury the one value he actually moved, and tests/test_ink_shadow.py reads
    # the file's own spelling of his 2026-08-15 answer.
    if alpha_of(css_color) == float(alpha):
        return css_color
    if re.search(r"/\s*[\d.]+\s*\)", css_color):
        return re.sub(r"/\s*[\d.]+\s*\)", "/ " + text + ")", css_color)
    match = re.fullmatch(r"rgb\(([^/)]+)\)", css_color.strip())
    if match:
        return "rgb(" + match.group(1).strip() + " / " + text + ")"
    return css_color


def snapshot() -> dict:
    """Everything the page needs to draw itself: the groups, the values as
    they are on disk right now, and which gate has an opinion about what."""
    return {
        "groups": GROUPS,
        "values": {sid: read_source(sid) for sid in SOURCES},
        "pinned": PINNED,
        "setPin": SET_PIN,
        "files": {sid: SOURCES[sid]["file"] for sid in SOURCES},
        "jsAlphas": {token: read_js_alpha(const)
                     for token, const in JS_ALPHAS.items()},
    }


# ═══════════════════════════ WRITING ═══════════════════════════
def _known(source_id: str) -> set:
    """The tokens this source is ALLOWED to have written. Derived rows are left
    out — the file computes them, and a tuner that pinned a computed value
    would be turning a rule back into a constant."""
    names = set()
    for group in GROUPS:
        for row in group["rows"]:
            if row["kind"] in ("derived", "sets"):
                continue
            if row["kind"] == "shape" and source_id == "shape":
                names.add(row["token"])
            elif row["kind"] == "jscolor" and source_id == "js":
                names.add(row["token"])
            elif row["kind"] in ("theme", "shadow") and source_id in ("dark", "light"):
                names.add(row["token"])
    return names


def write_source(source_id: str, changes: dict) -> list:
    """Rewrite `--name: value;` (or `"Name": "#hex",`, or `const NAME = "…";`)
    in place, by name, inside this source's own block. Returns the lines that
    really changed.

    Everything this tool is trusted with is in the three refusals below: an
    unknown token, a value with a `;` or a newline in it, and a name the block
    does not already declare. Nothing is inserted, nothing is deleted, and no
    rule, selector or comment is ever part of the match — which is why the
    owner's verdicts written around these values survive every save."""
    if not changes:
        return []
    allowed = set(read_source("sets")) if source_id == "sets" else _known(source_id)
    path = PROJECT / SOURCES[source_id]["file"]
    text = path.read_text(encoding="utf-8")
    kind = SOURCES[source_id]["kind"]
    is_dict = kind == "dict"
    is_const = kind == "const"
    # A `const` source is not a block — the whole file is the search space, and
    # the anchored `^const NAME = "` is what keeps it to the one line.
    start, end = (0, len(text)) if is_const else _block(source_id, text)
    body, changed = text[start:end], []

    for name, value in changes.items():
        if name not in allowed:
            raise ValueError(source_id + ": " + name + " is not a tunable of this source")
        value = str(value).strip()
        if ";" in value or "\n" in value or ((is_dict or is_const) and '"' in value):
            raise ValueError(source_id + ": " + name + " — refused, that is not a value")
        if is_const and not _TRIPLE.match(value):
            raise ValueError(source_id + ": " + name + " — refused, a shadow "
                             "colour is an `r g b` triple such as `255 255 255`")
        if is_dict:
            pattern = re.compile('(^[ \t]*"' + re.escape(name) + r'"\s*:\s*")([^"]+)(")', re.M)
        elif is_const:
            pattern = re.compile("(^const " + re.escape(name) + r' = ")([^"]*)(";)', re.M)
        else:
            pattern = re.compile("(^[ \t]*" + re.escape(name) + r"\s*:\s*)([^;]+)(;)", re.M)
        match = pattern.search(body)
        if not match:
            raise ValueError(source_id + ": " + name + " is not declared here")
        if match.group(2).strip() == value:
            continue
        changed.append(SOURCES[source_id]["file"] + "  " + name + ": "
                       + match.group(2).strip() + " -> " + value)
        body = body[:match.start(2)] + value + body[match.end(2):]

    if changed:
        path.write_text(text[:start] + body + text[end:], encoding="utf-8")
    return changed


def write_js_alpha(const: str, alpha: float) -> list:
    """The JS twin of a shadow alpha, kept in step with the CSS token in the
    SAME save — two places holding one number is how the plain and the coloured
    looks drift apart without anyone editing either."""
    path = PROJECT / THEME_JS
    text = path.read_text(encoding="utf-8")
    pattern = re.compile("^(const " + const + r" = )([\d.]+)(;)", re.M)
    match = pattern.search(text)
    if not match:
        raise ValueError(THEME_JS + ": " + const + " is gone")
    value = ("%g" % float(alpha))
    if match.group(2) == value:
        return []
    path.write_text(text[:match.start(2)] + value + text[match.end(2):],
                    encoding="utf-8")
    return [THEME_JS + "  " + const + ": " + match.group(2) + " -> " + value]


def pins_touched(changes: dict) -> list:
    """Which of the saved values a test has an opinion about — reported after
    the write, never used to refuse one."""
    notes = []
    for source_id, values in changes.items():
        for name in values:
            if source_id == "sets":
                notes.append('set "' + name + '" — ' + SET_PIN)
            elif name in PINNED:
                notes.append(name + " — " + PINNED[name])
    return sorted(set(notes))
