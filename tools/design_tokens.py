"""THE REGISTRY — which design value is tunable, where it lives, and what kind
of thing it is. Read AND written through this one table (tools/design_lab.py
serves it, tools/design_lab.js draws it), so the page can never offer a knob
the writer cannot save, and the writer can never touch a value the page did
not offer.

WHY A REGISTRY AND NOT A JSON FILE OF VALUES. The values already have a home:
client/theme.css (colour, per theme), client/style.css (shape), and
server/config.py (the set palette). A tuner that kept its own copy would be a
second source of truth, and the second one goes stale — this project has the
scars. So nothing here holds a value. Every read parses the real file, every
save rewrites the real declaration in place, and the prose around it — the
owner's verdicts, the graders' findings, the dates — is never touched.

WHAT MAY BE WRITTEN. Exactly the declarations named below, and only inside the
block they are declared in. The writer matches `--name: <value>;` by name; a
rule, a selector, a comment or an unknown token is not something it can reach
even if the page asks. That is the whole safety story of this tool.

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

PROJECT = Path(__file__).resolve().parent.parent


# ═══════════════════════════ THE SOURCES ═══════════════════════════
# Every tunable lives in one of four places. A "css" source is a rule whose
# whole body is `--name: value;` declarations; a "dict" source is one Python
# dict of name -> "#hex".
SOURCES = {
    "dark": {"file": "client/theme.css", "open": ":root {", "kind": "css"},
    "light": {"file": "client/theme.css", "open": 'body[data-theme="light"] {',
              "kind": "css"},
    "shape": {"file": "client/style.css", "open": ":root {", "kind": "css"},
    "sets": {"file": "server/config.py", "open": "SET_COLORS = {", "kind": "dict"},
}

# The JS twins of two CSS alphas. client/theme.js computes the COLOURED looks'
# shadows in code, so the strength the owner tunes has to land in both places
# or the plain and the coloured looks drift apart by a value nobody edited.
JS_ALPHAS = {
    "--ink-shadow": "INK_SHADOW_ALPHA",
    "--lbl-shadow": "LBL_SHADOW_ALPHA",
}
THEME_JS = "client/theme.js"


# ═══════════════════════════ WHAT A GATE PINS ═══════════════════════════
# token -> the sentence shown beside it in the page, and again in the save
# report. Naming the gate is the point: he should know before he drags the
# slider that a test is going to have an opinion.
PINNED = {
    "--ink-shadow": "tests/test_ink_shadow.py — his ballot of 2026-08-15 (strength)",
    "--lbl-shadow": "tests/test_ink_shadow.py — his ballot of 2026-08-15 (strength)",
    "--ink-shadow-x": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--ink-shadow-y": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--ink-shadow-blur": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--lbl-shadow-x": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--lbl-shadow-y": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--lbl-shadow-blur": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--warning": "tests/test_layout_audit.py — 4.5:1 under the status pill's ink",
    "--error": "tests/test_layout_audit.py — #ef4444 measured 3.45:1 here (2026-08-08)",
    "--on-warning": "tests/test_layout_audit.py — the ink belongs to the fill",
    "--on-error": "tests/test_layout_audit.py — the ink belongs to the fill",
    "--ledger-yellow": "the 2026-08-17 grader — must not read as a shade of --warning",
    "--fill-solid": "his choice of 2026-08-08 — the fill axis must be VISIBLE",
}
# Every set colour answers to the same sweep, so the note is one sentence.
SET_PIN = ("tests/test_layout_audit.py — the contrast sweep, both themes, both "
           "fills · saturation <= 72%, lightness 26-54%")


# ═══════════════════════════ THE GROUPS ═══════════════════════════
# The order they appear in the page. A group is a JOB, not a file: what the
# page is made of, what the ink is, what a switched-on button does — so a
# question like "the ON ring is too tight" lands in one place, with the colour
# and the geometry of that ring side by side, however far apart the two live
# on disk.
#
# kinds:
#   theme   — one colour token, TWO values (dark + light), edited together
#   shape   — one number in client/style.css, with the range its slider spans
#   alpha   — the strength slot of a theme colour whose HUE is a rule, not a
#             choice (a shadow is the ink's opposite — client/theme.css)
#   derived — shown, never edited: the file computes it from another token
#   sets    — the whole set palette, one swatch per shipped set
GROUPS = [
    {
        "id": "surfaces",
        "title": "Surfaces",
        "note": "What the page is made of. Every one of these is a surface an "
                "ink is later measured against, so a move here moves contrast "
                "everywhere.",
        "rows": [
            {"kind": "theme", "token": "--surface-0", "label": "Page floor"},
            {"kind": "theme", "token": "--card", "label": "Panel card"},
            {"kind": "theme", "token": "--glass-fill", "label": "Control fill (outlined)"},
            {"kind": "theme", "token": "--glass-strong", "label": "Wheel circle fill"},
            {"kind": "theme", "token": "--fill-solid", "label": "Control fill (FULL axis)"},
            {"kind": "theme", "token": "--chip", "label": "Chip / input / list row"},
            {"kind": "theme", "token": "--chip-2", "label": "Chip, second"},
            {"kind": "theme", "token": "--bar", "label": "Floating bar / banner"},
            {"kind": "theme", "token": "--scrim", "label": "Modal backdrop"},
            {"kind": "theme", "token": "--scrim-soft", "label": "Wheel backdrop"},
            {"kind": "theme", "token": "--dim-out", "label": "Outside the region grab"},
            {"kind": "theme", "token": "--opaque", "label": "Loading overlay"},
            {"kind": "theme", "token": "--border", "label": "Edge"},
            {"kind": "theme", "token": "--wheel-border", "label": "Edge, wheel circle"},
        ],
    },
    {
        "id": "ink",
        "title": "Ink",
        "note": "Text. An `--on-*` token is the ink ON a fill, never a surface "
                "ink — amber wants dark letters on one theme and light on the "
                "other, which is why they are their own tokens.",
        "rows": [
            {"kind": "theme", "token": "--text-primary", "label": "Primary text"},
            {"kind": "theme", "token": "--text-secondary", "label": "Secondary text"},
            {"kind": "theme", "token": "--on-accent", "label": "Ink on accent"},
            {"kind": "theme", "token": "--on-warning", "label": "Ink on amber"},
            {"kind": "theme", "token": "--on-error", "label": "Ink on red"},
        ],
    },
    {
        "id": "accent",
        "title": "Accent",
        "note": "The one hue the page uses for itself — selection, focus, the "
                "current wheel circle, a pressed button.",
        "rows": [
            {"kind": "theme", "token": "--accent", "label": "Accent"},
            {"kind": "theme", "token": "--accent-2", "label": "Accent, gradient end"},
            {"kind": "theme", "token": "--accent-glow", "label": "Accent glow"},
            {"kind": "theme", "token": "--accent-wash", "label": "Accent wash"},
        ],
    },
    {
        "id": "status",
        "title": "Status colours",
        "note": "The pill and the ledger dot. Semantic colour carries a 4.5:1 "
                "floor (rules/DESIGN.md) because it is the only thing that "
                "ever tells him a layout was refused.",
        "rows": [
            {"kind": "theme", "token": "--success", "label": "Success"},
            {"kind": "theme", "token": "--success-dim", "label": "Success wash"},
            {"kind": "theme", "token": "--success-edge", "label": "Success edge"},
            {"kind": "theme", "token": "--warning", "label": "Warning"},
            {"kind": "theme", "token": "--warning-2", "label": "Warning, gradient end"},
            {"kind": "theme", "token": "--error", "label": "Error"},
            {"kind": "theme", "token": "--error-2", "label": "Error, gradient end"},
            {"kind": "theme", "token": "--ledger-yellow", "label": "Ledger [?] yellow"},
        ],
    },
    {
        "id": "on",
        "title": "ON state",
        "note": "A switched-on button is a LUMINANCE event, not a hue (his "
                "report of 2026-08-09): the face flips to the far end of the "
                "theme's range and the ring reads face / gap / ring. Colour "
                "and geometry of that ring, together.",
        "rows": [
            {"kind": "theme", "token": "--on-face", "label": "Flipped face"},
            {"kind": "theme", "token": "--on-face-ink", "label": "Ink on the face"},
            {"kind": "theme", "token": "--on-glow", "label": "Glow"},
            {"kind": "derived", "token": "--on-gap", "label": "Ring gap colour",
             "why": "always the page floor — the gap is what makes the ring "
                    "read over any picture the PC happens to be showing"},
            {"kind": "shape", "token": "--on-border", "label": "Border width",
             "min": 1, "max": 6, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--on-ring-gap", "label": "Ring: gap stop",
             "min": 0, "max": 8, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--on-ring-face", "label": "Ring: face stop",
             "min": 0, "max": 14, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--on-glow-blur", "label": "Glow blur",
             "min": 0, "max": 48, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--on-scale", "label": "Scale",
             "min": 0.9, "max": 1.3, "step": 0.01, "unit": ""},
        ],
    },
    {
        "id": "held",
        "title": "Pressed",
        "note": "A finger holding the button down — a hue and an inward "
                "scale. It must never be mistaken for the switched-on state, "
                "which is why it stays a hue while that one is a flip.",
        "rows": [
            {"kind": "shape", "token": "--held-ring", "label": "Ring",
             "min": 0, "max": 8, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--held-glow", "label": "Glow blur",
             "min": 0, "max": 48, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--held-scale", "label": "Scale",
             "min": 0.8, "max": 1.1, "step": 0.01, "unit": ""},
            {"kind": "shape", "token": "--held-on-scale", "label": "Scale, when also ON",
             "min": 0.8, "max": 1.1, "step": 0.01, "unit": ""},
        ],
    },
    {
        "id": "shadows",
        "title": "Shadows",
        "note": "Controls float over the PC's own screen, which can be any "
                "colour, so the icon and the label carry a shadow. ITS COLOUR "
                "IS NOT A CHOICE — it is the ink's opposite, computed per "
                "element (client/theme.js -> shadowFor), which is why only the "
                "strength and the geometry are offered here.",
        "rows": [
            {"kind": "alpha", "token": "--ink-shadow", "label": "Icon shadow strength",
             "min": 0, "max": 1, "step": 0.05},
            {"kind": "alpha", "token": "--lbl-shadow", "label": "Label shadow strength",
             "min": 0, "max": 1, "step": 0.05},
            {"kind": "shape", "token": "--ink-shadow-x", "label": "Icon shadow · x",
             "min": -4, "max": 4, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ink-shadow-y", "label": "Icon shadow · y",
             "min": -4, "max": 4, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ink-shadow-blur", "label": "Icon shadow · blur",
             "min": 0, "max": 12, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--lbl-shadow-x", "label": "Label shadow · x",
             "min": -4, "max": 4, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--lbl-shadow-y", "label": "Label shadow · y",
             "min": -4, "max": 4, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--lbl-shadow-blur", "label": "Label shadow · blur",
             "min": 0, "max": 12, "step": 1, "unit": "px"},
            {"kind": "theme", "token": "--card-shadow", "label": "Card elevation"},
        ],
    },
    {
        "id": "shape",
        "title": "Control shape",
        "note": "The face itself: how round, how big, how much of it the "
                "label may take. A label that wraps onto a second row is "
                "correct here — nothing readable is ever cut off.",
        "rows": [
            {"kind": "shape", "token": "--corner", "label": "Button size",
             "min": 36, "max": 96, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-radius", "label": "Corner radius",
             "min": 0, "max": 40, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-icon", "label": "Icon size",
             "min": 10, "max": 44, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-gap", "label": "Icon to label",
             "min": 0, "max": 12, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-label", "label": "Label size",
             "min": 6, "max": 18, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-label-max", "label": "Label width",
             "min": 30, "max": 120, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-label-text", "label": "Chord button label",
             "min": 8, "max": 24, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--cat-size", "label": "Set switcher size",
             "min": 24, "max": 72, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--cat-radius", "label": "Set switcher radius",
             "min": 0, "max": 36, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--cat-icon", "label": "Set switcher icon",
             "min": 8, "max": 32, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--cat-label", "label": "Set switcher label",
             "min": 6, "max": 16, "step": 1, "unit": "px"},
        ],
    },
    {
        "id": "wheel",
        "title": "Wheel",
        "note": "The ring of set circles. Its own diameter is measured live "
                "(a multi-word name grows every circle at once), so what is "
                "tunable here is what the circle is made of.",
        "rows": [
            {"kind": "shape", "token": "--wheel-icon", "label": "Icon size",
             "min": 10, "max": 40, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--wheel-gap", "label": "Icon to label",
             "min": 0, "max": 14, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--wheel-label", "label": "Label size",
             "min": 8, "max": 20, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--wheel-ring", "label": "Current: ring",
             "min": 0, "max": 8, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--wheel-glow", "label": "Current: glow blur",
             "min": 0, "max": 48, "step": 1, "unit": "px"},
        ],
    },
    {
        "id": "rhythm",
        "title": "Page rhythm",
        "note": "Spacing and the pill end. `--topbar` is computed from the "
                "first two and the button size, and is what every floating "
                "notice starts below.",
        "rows": [
            {"kind": "shape", "token": "--space-s", "label": "Small space",
             "min": 0, "max": 32, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--space-m", "label": "Medium space",
             "min": 0, "max": 48, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--radius-pill", "label": "Pill radius",
             "min": 0, "max": 999, "step": 1, "unit": "px"},
            {"kind": "derived", "token": "--topbar", "label": "Top bar floor",
             "why": "computed from the spaces and the button size — a notice "
                    "that started above it would sit on the layout arrows"},
        ],
    },
    {
        "id": "sets",
        "title": "Set palette",
        "note": "One colour per shipped set — the button OUTLINE when the "
                "controls are outlined, the FILL when they are full. ONE "
                "table for both themes (his decision of 2026-08-08): a set's "
                "colour is its identity, and an identity that changes with the "
                "sun/moon switch is not one. Every ink you see on these is "
                "computed from the surface it really lands on, never tabled, "
                "so no colour chosen here can make a label unreadable.",
        "rows": [{"kind": "sets"}],
    },
]


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


def read_source(source_id: str) -> dict:
    text = (PROJECT / SOURCES[source_id]["file"]).read_text(encoding="utf-8")
    start, end = _block(source_id, text)
    body = text[start:end]
    pattern = _ENTRY if SOURCES[source_id]["kind"] == "dict" else _DECL
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
            elif row["kind"] in ("theme", "alpha") and source_id in ("dark", "light"):
                names.add(row["token"])
    return names


def write_source(source_id: str, changes: dict) -> list:
    """Rewrite `--name: value;` (or `"Name": "#hex",`) in place, by name, inside
    this source's own block. Returns the lines that really changed.

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
    start, end = _block(source_id, text)
    body, changed = text[start:end], []
    is_dict = SOURCES[source_id]["kind"] == "dict"

    for name, value in changes.items():
        if name not in allowed:
            raise ValueError(source_id + ": " + name + " is not a tunable of this source")
        value = str(value).strip()
        if ";" in value or "\n" in value or (is_dict and '"' in value):
            raise ValueError(source_id + ": " + name + " — refused, that is not a value")
        if is_dict:
            pattern = re.compile('(^[ \t]*"' + re.escape(name) + r'"\s*:\s*")([^"]+)(")', re.M)
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
