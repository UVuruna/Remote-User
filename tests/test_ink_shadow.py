"""THE INK-SHADOW GATE — a shadow is never the colour of its own ink.

Owner report 2026-08-17, his picture 5. Attach and Claude Tools drew BLACK
icons and labels with a BLACK shadow under them, and his sentence is the whole
rule: "kada je senka iste boje kao i slova to izgleda lose i mutno" — a shadow
the same colour as the ink reads as blur, because there is nothing for the eye
to separate. <!-- lang-ok: owner quote, transliterated -->

WHY IT SURVIVED A WHOLE ROUND ON HIS SCREEN, and why this file exists rather
than one more check in an existing one. On 2026-08-15 he reported the same
defect in its other direction — white shadow under white ink — and the fix
written then was a CONSTANT: the shadow is always black, on both themes. That
sentence is true of exactly one of the two inks this page draws, and the page
had never been asked which one it was using. Nothing in this repo could catch
it either: the phone audit measures the contrast of INK against SURFACE, which
was correct in every one of the eight looks all along; a shadow is neither of
those two things, so no measurement it makes has an opinion about it.

What is held here, each proven by planting its own defect:

  1. `shadowFor` picks the OPPOSITE of the ink, both ways round. The rule, as a
     function, over the whole luminance range.
  2. Every SHIPPED set colour, in both fills, produces a shadow that differs
     from the ink it sits under — the sweep his picture is one frame of. It
     reads the colours from `server/config.py`, so a palette the owner retunes
     tomorrow is swept as it really is and not as this file remembers it.
  3. The two coloured fills write DIFFERENT shadow variables. Filled ink is
     black-or-white against the fill, outlined ink is the set's own lifted
     colour — one shadow for both is one of them wrong.
  4. The CSS really re-points `--ink-shadow` / `--lbl-shadow` for the coloured
     looks. `shadowFor` is arithmetic; a value nothing reads is not a feature
     (this project's own actions.json lesson).
  5. The LIGHT theme's tokens are light and the DARK theme's are dark, because
     that is where the ink is `--text-primary` and nothing computes it per
     element.
  6. The GEOMETRY and the two ALPHAS are the owner's, settled on his 2026-08-15
     ballot, and this round changed only the COLOUR. A "fix" that also moved
     the blur would be re-opening a question he has already answered.

Requires: node on PATH — it runs the REAL `client/theme.js`, whole, exactly as
tests/test_appearance_device.py does. A gate that re-implements the arithmetic
it is checking proves only that two copies agree.

Run:  .venv\\Scripts\\python tests/test_ink_shadow.py
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402

from _focus_fakes import run_checks  # noqa: E402

THEME_JS = PROJECT / "client" / "theme.js"
THEME_CSS = PROJECT / "client" / "theme.css"
STYLE_CSS = PROJECT / "client" / "style.css"

# The two shadows the page may ever draw. Written here as the ANSWERS, so a
# check can name which one it expected — never as a copy of the rule that picks
# between them, which is the thing under test.
DARK = "0 0 0"
LIGHT = "255 255 255"


# ═══════════════════════════ THE HARNESS ═══════════════════════════
# `theme.js` run whole in node, with just enough of a page around it to let
# `paintSet` write onto a fake element. The element records every custom
# property, which is exactly what the browser would hand the CSS.
HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const input = JSON.parse(process.argv[3]);

function element() {
  const props = {};
  return {
    props,
    style: {
      setProperty: (k, v) => { props[k] = v; },
      removeProperty: (k) => { delete props[k]; },
    },
  };
}

const dataset = {};
const sandbox = {
  console,
  performance: { now: () => 0 },
  prefGet: () => null,
  prefSet: () => {},
  document: { body: { dataset, style: {} } },
  getComputedStyle: () => ({
    backgroundColor: input.page,
    getPropertyValue: (name) => input.surfaces[name] || "",
  }),
  setCanvasBackdrop: () => {},
  categories: [], customSets: [], appSets: [],
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), sandbox,
                { filename: "theme.js" });
sandbox.applyUi({ theme: input.theme, colored: true, fill: "full",
                  colors: input.colors });

const out = { sets: {}, rule: [] };
for (const name of Object.keys(input.colors)) {
  const el = element();
  sandbox.paintSet(el, name, "--glass-fill");
  out.sets[name] = el.props;
}
// The rule itself, swept across the whole range rather than sampled: an ink
// this page can produce is any grey between the two extremes.
for (let v = 0; v <= 255; v += 5) {
  out.rule.push([v, sandbox.shadowFor([v, v, v], 1)]);
}
console.log(JSON.stringify(out));
"""


def run_theme(theme: str, colors: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "harness.js"
        script.write_text(HARNESS, encoding="utf-8")
        payload = {
            "theme": theme,
            "colors": colors,
            # The page and the button tint the page really wears in that theme.
            # Read as literals rather than parsed out of the CSS: what this
            # gate is about is the INK against its shadow, and a surface it got
            # slightly wrong would still exercise every rule under test.
            "page": "rgb(15 23 42)" if theme == "dark" else "rgb(241 245 249)",
            "surfaces": {"--glass-fill": "rgb(30 41 59 / 0.20)"
                         if theme == "dark" else "rgb(255 255 255)"},
        }
        out = subprocess.run(
            ["node", str(script), str(THEME_JS), json.dumps(payload)],
            capture_output=True, text=True, check=False)
        assert out.returncode == 0, f"node failed:\n{out.stderr}"
        return json.loads(out.stdout)


def shipped_colors() -> dict:
    """The real palette, from the one table that owns it (server/config.py →
    `SET_COLORS`). Never a copy: the owner retunes these, and a gate sweeping
    last month's hexes proves nothing about the ones on his phone."""
    return dict(config.SET_COLORS)


def family(css_color: str) -> str:
    """Which of the two shadows this is — `rgb(R G B / A)` reduced to its
    colour. The alpha is a separate question and check 6 asks it."""
    inner = css_color[css_color.index("(") + 1:css_color.rindex(")")]
    return inner.split("/")[0].strip()


def ink_family(value: str) -> str:
    """The same reduction for an INK, which arrives either as a hex (the
    filled look's black-or-white) or as `rgb(...)` (the outlined look's lifted
    colour). Answered by luminance against the same 0.179 crossover the page
    itself uses, so "is the shadow the ink's own colour" is asked in the terms
    the eye asks it: a near-black ink under a black shadow is the defect
    whether the ink is #0b1220 or a very dark navy."""
    if value.startswith("#"):
        rgb = [int(value[i:i + 2], 16) for i in (1, 3, 5)]
    else:
        nums = re.findall(r"[\d.]+", value)
        rgb = [float(n) for n in nums[:3]]
    lin = [(c / 255) / 12.92 if c / 255 <= 0.03928
           else (((c / 255) + 0.055) / 1.055) ** 2.4 for c in rgb]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return DARK if lum <= 0.179 else LIGHT


# ═══════════════════════════ 1. THE RULE ═══════════════════════════
def check_the_shadow_is_the_ink_s_opposite() -> bool:
    """Both directions, across the whole range. A rule that only ever answers
    one of the two colours is the constant this round replaced."""
    swept = run_theme("dark", shipped_colors())["rule"]
    if len({family(s) for _, s in swept}) != 2:
        return False          # a constant, whichever one it is
    for value, shadow in swept:
        if family(shadow) != ink_family(f"#{value:02x}{value:02x}{value:02x}"):
            continue
        return False          # the shadow agreed with its own ink
    return True


# ═══════════════════════════ 2. HIS PICTURE ═══════════════════════════
def _sweep(theme: str) -> list[tuple[str, str, str, str]]:
    """(set, look, ink, shadow) for every shipped colour in both fills."""
    painted = run_theme(theme, shipped_colors())["sets"]
    rows = []
    for name, props in painted.items():
        rows.append((name, "full", props["--set-ink"],
                     props["--set-ink-shadow"]))
        rows.append((name, "outlined", props["--set-line"],
                     props["--set-line-shadow"]))
    return rows


def check_no_shipped_set_draws_its_shadow_in_its_own_ink() -> bool:
    """HIS PICTURE 5, as a sweep. Attach and Claude Tools are light fills, so
    `inkOn` hands them BLACK ink — on the DARK theme, which is why no
    theme-level token could ever have covered them."""
    for theme in ("dark", "light"):
        rows = _sweep(theme)
        if not rows:
            return False
        for name, look, ink, shadow in rows:
            if family(shadow) == ink_family(ink):
                return False
    return True


def check_a_light_fill_really_is_in_the_palette() -> bool:
    """The sweep above proves nothing if every shipped colour happens to take
    white ink — the defect he photographed needs a set whose ink is BLACK to
    exist at all. This asserts the case is really in the palette, so check 2 is
    known to be asking his question and not an easier one."""
    return any(ink_family(ink) == DARK
               for _, look, ink, _ in _sweep("dark") if look == "full")


# ═══════════════════════════ 3. TWO INKS, TWO SHADOWS ═══════════════
def check_the_two_fills_get_their_own_shadows() -> bool:
    """A filled button's ink is black-or-white against the fill; an outlined
    one's is the set's own lifted colour. They are different inks, so one
    shared shadow variable would be wrong for one of the two looks — and it
    would be wrong invisibly, since only one look is on screen at a time."""
    painted = run_theme("dark", shipped_colors())["sets"]
    wanted = {"--set-ink-shadow", "--set-ink-lbl-shadow",
              "--set-line-shadow", "--set-line-lbl-shadow"}
    disagreed = False
    for props in painted.values():
        if not wanted <= set(props):
            return False
        if family(props["--set-ink-shadow"]) != family(props["--set-line-shadow"]):
            disagreed = True
    # At least one shipped set must actually need two different answers, or
    # "they are computed separately" is a claim nothing on his phone tests.
    return disagreed


def check_a_set_with_no_colour_leaves_no_shadow_behind() -> bool:
    """`paintSet` clears every property it can write when the set has no colour
    — a stale shadow from a set that has gone is the same class of bug as a
    stale ink, and this project has met it before."""
    src = THEME_JS.read_text(encoding="utf-8")
    body = src[src.index("function paintSet"):src.index("function writeLook")]
    written = set(re.findall(r'setProperty\("(--set-[\w-]+)"', body))
    cleared = set(re.findall(r'removeProperty\("(--set-[\w-]+)"', body))
    return written and written <= cleared


# ═══════════════════════════ 4-5. THE CSS READS IT ═══════════════════
def check_the_coloured_looks_repoint_the_shadow_tokens() -> bool:
    """The arithmetic must reach the two variables the icon and the label
    really draw with. This is the actions.json lesson in its smallest form: a
    computed value nothing consumes is a feature that does not exist."""
    css = THEME_CSS.read_text(encoding="utf-8")
    outlined = re.search(
        r'body\[data-colored="true"\][^{}]*\{[^}]*?--ink-shadow:\s*'
        r'var\(--set-line-shadow[^}]*?--lbl-shadow:\s*var\(--set-line-lbl-shadow',
        css, re.S)
    filled = re.search(
        r'body\[data-colored="true"\]\[data-fill="full"\][^{}]*\{[^}]*?'
        r'--ink-shadow:\s*var\(--set-ink-shadow[^}]*?'
        r'--lbl-shadow:\s*var\(--set-ink-lbl-shadow', css, re.S)
    # …and the icon and the label must still be the ONLY things drawing them,
    # from the one place they have always been drawn.
    style = STYLE_CSS.read_text(encoding="utf-8")
    drawn = ("drop-shadow(0 1px 1px var(--ink-shadow))" in style
             and "text-shadow: 0 1px 1px var(--lbl-shadow)" in style)
    return bool(outlined) and bool(filled) and drawn


def _theme_tokens(selector: str) -> dict:
    css = THEME_CSS.read_text(encoding="utf-8")
    start = css.index(selector)
    block = css[start:css.index("\n}", start)]
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r"(--(?:ink|lbl)-shadow):\s*([^;]+);", block)}


def check_the_plain_themes_carry_the_ink_s_opposite() -> bool:
    """Where the ink is `--text-primary` nothing computes per element, so the
    token IS the decision: white ink on the dark page keeps his black shadow,
    dark ink on the light page takes a white one. The dark block's value is his
    from 2026-08-15 and is asserted unchanged — this round narrowed that
    verdict, it did not overturn it."""
    dark = _theme_tokens(":root {")
    light = _theme_tokens('body[data-theme="light"] {')
    return (family(dark.get("--ink-shadow", "")) == DARK
            and family(dark.get("--lbl-shadow", "")) == DARK
            and family(light.get("--ink-shadow", "")) == LIGHT
            and family(light.get("--lbl-shadow", "")) == LIGHT)


# ═══════════════════════════ 6. HIS NUMBERS ═══════════════════════════
def check_the_geometry_and_the_alphas_are_untouched() -> bool:
    """0 / 1 px, 1 px blur, and the two alphas — settled by the owner on his
    own ballot's sliders (2026-08-15). This round is about WHICH of two colours
    is drawn and about nothing else; a shadow that also grew a 2 px blur would
    be re-opening a question he has answered, and it was a 2 px blur that made
    the original report."""
    style = STYLE_CSS.read_text(encoding="utf-8")
    if ("drop-shadow(0 1px 1px var(--ink-shadow))" not in style
            or "text-shadow: 0 1px 1px var(--lbl-shadow)" not in style):
        return False
    dark = _theme_tokens(":root {")
    light = _theme_tokens('body[data-theme="light"] {')
    alphas = [v.split("/")[1].strip(" )") for v in
              (*dark.values(), *light.values())]
    if sorted(set(alphas)) != ["0.80", "1"]:
        return False
    src = THEME_JS.read_text(encoding="utf-8")
    return ("const INK_SHADOW_ALPHA = 0.8" in src
            and "const LBL_SHADOW_ALPHA = 1" in src)


CHECKS = [
    ("the shadow is the ink's opposite, over the whole range",
     check_the_shadow_is_the_ink_s_opposite),
    ("no shipped set draws its shadow in its own ink",
     check_no_shipped_set_draws_its_shadow_in_its_own_ink),
    ("a light fill — his own case — really is in the palette",
     check_a_light_fill_really_is_in_the_palette),
    ("the filled and outlined looks get their own shadows",
     check_the_two_fills_get_their_own_shadows),
    ("a set with no colour leaves no shadow behind",
     check_a_set_with_no_colour_leaves_no_shadow_behind),
    ("the coloured looks really re-point the shadow tokens",
     check_the_coloured_looks_repoint_the_shadow_tokens),
    ("the plain themes carry the ink's opposite",
     check_the_plain_themes_carry_the_ink_s_opposite),
    ("the geometry and the alphas are untouched",
     check_the_geometry_and_the_alphas_are_untouched),
]


def main() -> int:
    if shutil.which("node") is None:
        print("INK SHADOW GATE FAILED — node is required (it runs the REAL "
              "client/theme.js; a re-implementation would prove only that two "
              "copies agree)")
        return 1
    return run_checks(
        "INK SHADOW GATE", CHECKS,
        "a shadow is never the colour of its own ink")


def test_ink_shadow():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
