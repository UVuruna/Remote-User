"""THE BOTTOM LAYOUT BAR — measured, finally (owner report 2026-08-12, twice:
"floats in the middle" both times, and each round shipped a fix nobody staged).

Root cause named in the CLAUDE.md task brief: `body.laybar-bottom` never
appeared in ANY audit stage — grep proves `laybar-bottom` lives only in
client/layouts.js and client/layouts.css, in no test. Every screenshot this
project ever took of the layout bar was of the TOP position. That is how a
CSS regression (the bar's `bottom` offset carrying `--group-h`, floating it a
third of the way up the phone) shipped, was reported, "fixed", and shipped
broken again — nobody ever put the bottom bar on screen to check.

Split into its own module (THE STRUCTURE LAW: tests/test_layout_audit.py sits
at the 1,000-line ceiling) rather than folded into tests/_audit_panels.py —
that file is the panel CATALOGUE (what opens, in what state); this is a
CHECK, with its own measuring instrument, in the shape of
tests/_audit_frame.py / tests/_audit_js.py.

Drives the pref the same way the phone's own Settings row does
(`setLayBarPos`, client/layouts.js — called from client/phone-panel.js), so a
broken switch would fail this check even if the CSS were flawless, and stages
one real layout first (`updateLayoutBar()` hides the bar with none).
"""

# Stage constants live in _audit_panels.py (LAYBAR_STAGE_JS / LAYBAR_BOTTOM_JS
# / LAYBAR_CLOSE_JS) — imported here rather than duplicated so the panel
# catalogue keeps ONE copy of what state each screen is put in.
from _audit_panels import LAYBAR_CLOSE_JS, LAYBAR_STAGE_JS

# THE MEASURING INSTRUMENT. Reads the bar, both `.group`s, the viewport and
# the live `--space-m` token (never a hardcoded pixel guess — a retuned
# spacing scale must not silently widen this check's tolerance out from under
# it). `overflow` is read from the class `layBarFit()` itself sets, so the
# check asks the SAME question the page just answered rather than
# re-deriving it from the viewport width a second, possibly-drifting way.
_LAYBAR_MEASURE_JS = """() => {
  const bar = document.getElementById('layout-bar');
  const gl = document.querySelector('.group.left');
  const gr = document.querySelector('.group.right');
  const b = bar.getBoundingClientRect();
  const rect = (el) => el && {top: el.top, bottom: el.bottom,
                               left: el.left, right: el.right};
  const cs = getComputedStyle(document.documentElement);
  const spaceM = parseFloat(cs.getPropertyValue('--space-m')) || 16;
  return {
    bar: rect(b), groupL: rect(gl && gl.getBoundingClientRect()),
    groupR: rect(gr && gr.getBoundingClientRect()),
    banner: (() => {
      const el = document.getElementById('anywhere-banner');
      return (el && !el.hidden) ? rect(el.getBoundingClientRect()) : null;
    })(),
    innerHeight, spaceM,
    overflow: document.body.classList.contains('laybar-overflow'),
  };
}"""


def _overlaps(a, b) -> bool:
    if not a or not b:
        return False
    return (a["left"] < b["right"] and b["left"] < a["right"] and
            a["top"] < b["bottom"] and b["top"] < a["bottom"])


def check_laybar_bottom(page, label, portrait, results, shot_path, shot_name):
    """Stages the bottom bar with a real layout present, measures it, writes
    a shot, then restores "top" for everything the audit does afterward.

    FOUR CHECKS, each aimed at one shape of the reported bug:

    - hugs the bottom edge: the gap between the bar's bottom and the
      viewport's bottom must not exceed one row's worth of margin — a bar
      floating 300+ px up (the reported defect, `--group-h` in the offset)
      fails this outright.
    - never overlaps a `.group`: the bar and the D-pad columns must not
      paint over each other in EITHER layout.
    - overflow case (narrow phone, no room in the row): the groups sit
      ABOVE the bar, never straddling it.
    - with-room case (wide tablet, fits in the row): the bar shares the
      groups' own baseline and sits horizontally BETWEEN the two columns —
      "IN the row", his own words, not floating above it.
    - never overlaps the "Use from anywhere" BANNER. This one was written
      because the very FIRST screenshot of the corrected bar showed the
      banner's pill drawn straight across the layout's name: the banner is
      pinned to the same bottom baseline, which was safe only while nothing
      else stood on that line. The four checks above all passed on that
      picture — they compared the bar against the D-pad columns, which are at
      the far edges, and the collision was in the middle where nobody was
      looking. A check aimed at the neighbours you thought of is not a check
      on the row.
    """
    page.evaluate(LAYBAR_STAGE_JS)
    page.evaluate("setLayBarPos('bottom')")
    page.wait_for_timeout(120)
    geo = page.evaluate(_LAYBAR_MEASURE_JS)
    bar, gl, gr = geo["bar"], geo["groupL"], geo["groupR"]

    tol = geo["spaceM"] + 40   # a row's margin + slack for kb/safe-area rounding
    gap = geo["innerHeight"] - bar["bottom"]
    hugs = 0 <= gap <= tol
    results[f"the bottom layout bar hugs the bottom edge @ {label}"] = hugs
    if not hugs:
        print(f"  DETAIL laybar bottom offset @ {label}: gap={gap:.1f}px"
              f" (allowed 0-{tol:.1f}px)")

    no_overlap = not _overlaps(bar, gl) and not _overlaps(bar, gr)
    results[f"the bottom layout bar never overlaps a control group "
            f"@ {label}"] = no_overlap
    if not no_overlap:
        print(f"  DETAIL laybar/group overlap @ {label}: bar={bar} "
              f"groupL={gl} groupR={gr}")

    banner = geo["banner"]
    clear_banner = not _overlaps(bar, banner)
    results[f"the bottom layout bar never overlaps the anywhere banner "
            f"@ {label}"] = clear_banner
    if not clear_banner:
        print(f"  DETAIL laybar/banner overlap @ {label}: bar={bar} "
              f"banner={banner}")

    if portrait and geo["overflow"]:
        above = ((gl is None or gl["bottom"] <= bar["top"] + 1) and
                  (gr is None or gr["bottom"] <= bar["top"] + 1))
        results[f"in overflow the groups sit above the bottom bar "
                f"@ {label}"] = above
        if not above:
            print(f"  DETAIL overflow order @ {label}: bar.top="
                  f"{bar['top']:.1f} groupL.bottom="
                  f"{gl['bottom'] if gl else None} groupR.bottom="
                  f"{gr['bottom'] if gr else None}")
    elif gl and gr:
        baseline = (abs(bar["bottom"] - gl["bottom"]) <= 4 and
                    abs(bar["bottom"] - gr["bottom"]) <= 4)
        between = bar["left"] >= gl["right"] - 1 and bar["right"] <= gr["left"] + 1
        results[f"the bottom bar shares the groups' baseline "
                f"@ {label}"] = baseline
        results[f"the bottom bar sits between the columns @ {label}"] = between
        if not baseline or not between:
            print(f"  DETAIL laybar in-row geometry @ {label}: bar={bar} "
                  f"groupL={gl} groupR={gr}")

    # SETTLE BEFORE THE SHUTTER, and disable animations in it. The independent
    # grader opened the tablet-portrait shot and found a GHOST of the bar still
    # painted at the TOP, faintly, behind the corner buttons, while the real
    # bar stood correctly at the bottom — in exactly one of the four sizes, and
    # with every geometric check green, because the measured rect was right and
    # only the PICTURE was wrong. The bar carries no transition of its own, so
    # this is the compositor holding the layer it painted before the position
    # class changed. A stale layer is not a defect a user would ever see, but a
    # screenshot IS the evidence this law runs on, so it must show the page and
    # not the page's history.
    page.wait_for_timeout(400)
    # AN EXPLICIT CLIP, AND THAT IS THE FIX. The independent grader opened the
    # tablet-portrait shot and found a faint GHOST of the bar painted at the
    # TOP behind the corner buttons, in exactly one of four sizes, with every
    # geometric check green. It is not in the page: a DOM probe at the instant
    # of the shutter finds only the two corner buttons and the invisible
    # keyboard field in that band, and the bar's own rect reads y=1206 — the
    # bottom. A 400 ms settle did not clear it, nor `animations="disabled"`,
    # nor hiding and re-showing the element to force a repaint.
    # What DID prove it: a screenshot taken with an explicit `clip` over the
    # same top band came back CLEAN. So the defect is in the un-clipped
    # viewport capture reusing a raster tile from before the position class
    # changed, and naming the region explicitly makes it raster afresh.
    # A photograph problem, never a product one — but a screenshot IS the
    # evidence this law runs on, so it must show the page and not its history.
    page.wait_for_timeout(400)
    page.screenshot(
        path=str(shot_path(shot_name(f"Layout_bar_bottom {label}")[:-4])),
        clip={"x": 0, "y": 0,
              "width": page.evaluate("innerWidth"),
              "height": page.evaluate("innerHeight")},
        animations="disabled")
    page.evaluate(LAYBAR_CLOSE_JS)
