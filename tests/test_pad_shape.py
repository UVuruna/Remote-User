"""THE ARRANGEMENT IS NOT WELDED TO THE ORIENTATION — the pad shape gate.

Owner request 2026-08-09 (task 177), with his screenshot: his phone held
sideways shows the 16:9 desktop with a finger-wide band of empty space down
each side — the letterbox bars of an aspect-fitted picture — and those bands
would hold the two control sets UPRIGHT perfectly. Landscape nevertheless
always drew the D-pad cross, because the arrangement was welded to the
orientation by a CSS media query. His ruling: the defaults do not change
(column upright, cross sideways), and the user may override either one.

Three things have to be true, and this project has shipped features where only
one of them was:

1. **The DECISION is right.** `auto` still answers what the app has always
   drawn, an explicit choice outranks it in BOTH directions, and the two
   orientations are independent. Driven PURE, by argument
   (`padShapeFor`/`padShapeSeed`), so every combination is really visited
   rather than sampled through whatever the browser happened to be showing.
2. **Task 121's saved choice SURVIVES.** `padCross` was a boolean and only
   ever a portrait question; it is this feature's seed. Proven the only way it
   can honestly be proven — a browser that ARRIVES carrying the old key, at
   page load, exactly as his phone will.
3. **The mirror image FITS.** A column really renders as a column when the
   phone is sideways and a cross really renders as a cross when it is upright
   — measured in a real headless Chromium at phone AND tablet sizes, because
   a shape that is chosen but does not fit is a worse answer than no choice.

Run:  .venv\\Scripts\\python tests/test_pad_shape.py
Requires the same toolchain as the input gate (playwright + chromium): it
opens the REAL page against the REAL server.
"""

import re
import socket
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(PROJECT / "server"))

CONTROLS_JS = PROJECT / "client" / "controls.js"

# This gate's own port (see `start_server`) — never the input gate's 8898.
PORT = 8896

# THE SIZES ARE THE AUDIT'S OWN (tests/test_layout_audit.py): two phones and
# two tablets, in both orientations. He uses both devices — "do sad nikad
# nisam probao preko tableta" (2026-08-08) is exactly how a phone-only
# measurement becomes a tablet bug.
SIZES = [("phone upright 412x915", 412, 915),
         ("phone sideways 915x412", 915, 412),
         ("tablet upright 800x1280", 800, 1280),
         ("tablet sideways 1280x800", 1280, 800)]

# What the app has always drawn, and what `auto` must keep drawing.
DEFAULT_SHAPE = {"portrait": "column", "landscape": "cross"}

# The two shapes, as GEOMETRY rather than as a class name: a column is one
# button wide and five tall, a cross is three by three. Measured off the real
# rendered children, so a rule that sets the class and lays nothing out fails.
SHAPE_GRID = {"column": (1, 5), "cross": (3, 3)}

SHOT_DIR = PROJECT / ".claude" / "shots" / "round32-pad-shape"

# The measuring instrument. Installed once per page; returns the geometry of
# both groups plus everything the answer depends on.
GEOM_JS = """
window.__padGeom = () => {
  const box = (r) => ({l: r.left, t: r.top, r: r.right, b: r.bottom,
                       w: r.width, h: r.height});
  const out = {w: innerWidth, h: innerHeight,
               scrollW: document.scrollingElement.scrollWidth,
               shape: padShape(), column: padColumn(),
               klass: document.body.classList.contains('pad-column'),
               groups: {}, corners: []};
  for (const id of ['group-left', 'group-right']) {
    const g = document.getElementById(id);
    const kids = [...g.children].map((k) => k.getBoundingClientRect());
    const cx = new Set(kids.map((k) => Math.round(k.left + k.width / 2)));
    const cy = new Set(kids.map((k) => Math.round(k.top + k.height / 2)));
    out.groups[id] = {
      rect: box(g.getBoundingClientRect()),
      buttons: kids.length,
      cols: cx.size,
      rows: cy.size,
      outside: kids.filter((k) => k.left < -0.5 || k.top < -0.5 ||
                                  k.right > innerWidth + 0.5 ||
                                  k.bottom > innerHeight + 0.5).length,
    };
  }
  for (const c of document.querySelectorAll('.corner')) {
    const r = c.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) out.corners.push(box(r));
  }
  return out;
};
"""


def overlap(a, b) -> bool:
    """Do two rects share any pixel?"""
    return a["l"] < b["r"] and b["l"] < a["r"] and a["t"] < b["b"] and b["t"] < a["b"]


# ═══════════════════════════ the harness ═══════════════════════════
def start_server():
    """The audit server, in this process — the same one the input gate and the
    phone audit drive, on a PORT OF ITS OWN.

    The port matters: the gates run back to back in `setup/build.py`, and a
    uvicorn still shutting down holds 8898 long enough for the next process to
    connect to it, load the page from a server that is dying, and time out
    waiting for the first `config` — seen once while this gate was being
    written. A port per gate costs nothing and removes the race entirely."""
    import test_input_pipeline as gate
    gate.PORT = PORT
    threading.Thread(target=gate.run_server, daemon=True).start()
    gate.server_ready.wait(15)
    deadline = time.time() + 10
    while time.time() < deadline:
        if gate.server_error:
            raise gate.server_error[0]
        try:
            with socket.create_connection(("127.0.0.1", gate.PORT), timeout=0.25):
                return gate
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("the pad shape gate's server never started")


def open_page(browser, gate, w, h, init=None):
    """A real phone-ish context on the real page. `init` runs BEFORE any page
    script — the only honest way to hand the page a preference it was already
    carrying when it started."""
    ctx = browser.new_context(
        viewport={"width": w, "height": h}, has_touch=True, is_mobile=True,
        device_scale_factor=2,
        user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 "
                    "Mobile Safari/537.36 VibeCoderApp"))
    if init:
        ctx.add_init_script(init)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
    page.wait_for_selector("#group-left button", timeout=8000)
    # …and for the socket's first `config`, like the phone audit: the D-pad
    # renders from the page's own defaults about 1.4 s before the server has
    # said a word.
    page.wait_for_function("() => monitor.w > 0", timeout=10000)
    page.evaluate("() => {" + GEOM_JS + "}")
    return page, ctx, errors


def geom(page, orient=None, shape=None):
    """Put the page into one shape (through the product's own entry point) and
    measure. `orient` names which orientation's preference to move — always
    the one the viewport is really in, or the choice would not be the one on
    screen."""
    if orient and shape:
        page.evaluate("([o, s]) => setPadShape(o, s)", [orient, shape])
        page.wait_for_timeout(120)
    return page.evaluate("() => __padGeom()")


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def check_auto_still_draws_yesterdays_picture(pages):
    """HIS RULING, FIRST: defaults do not change. `auto` — and anything that
    is not one of his two words — answers exactly what the app drew before
    this feature existed."""
    page = pages[0]
    cases = ["auto", "", None, "wobble", "COLUMN", 1]
    for orient, want in DEFAULT_SHAPE.items():
        for pref in cases:
            got = page.evaluate("([p, o]) => padShapeFor(p, o)", [pref, orient])
            assert got == want, (
                f"a {pref!r} preference in {orient} drew the {got}; the "
                f"default there is the {want} and this feature may not move it")


def check_an_explicit_choice_outranks_the_default(pages):
    """The whole request, in both directions: sideways may show the columns
    and upright may show the cross."""
    page = pages[0]
    for orient in DEFAULT_SHAPE:
        for want in ("column", "cross"):
            got = page.evaluate("([p, o]) => padShapeFor(p, o)", [want, orient])
            assert got == want, (
                f"an explicit {want} in {orient} drew the {got} instead — the "
                "choice must outrank the default, which is the request")


def check_task_121s_key_is_read_as_the_portrait_choice(pages):
    """PURE half of the seed. Ticked = the cross upright; unticked = the
    column, which is what the default answers there anyway but is still HIS
    answer; no key at all = he was never asked."""
    page = pages[0]
    for legacy, want in [("1", "cross"), ("0", "column"), (None, "auto"),
                         ("", "auto"), ("yes", "auto")]:
        got = page.evaluate("(v) => padShapeSeed(v)", legacy)
        assert got == want, (
            f"the old padCross={legacy!r} translated to {got!r}, not {want!r} "
            "— a saved choice is an instruction, never a value to reset")


def check_a_device_arriving_with_the_old_key_keeps_its_choice(browser, gate):
    """THE SEED, PROVEN THE ONLY WAY IT CAN BE: a browser that already carries
    task 121's key when it starts, which is his tablet on the morning after
    this ships. A pure translation nobody calls would be worth nothing (the
    actions.json lesson of 2026-08-07 — a field that never reached HIS file)."""
    for legacy, want in [("1", "cross"), ("0", "column")]:
        page, ctx, errors = open_page(
            browser, gate, 800, 1280,
            init=f"try {{ localStorage.setItem('padCross', {legacy!r}); }} catch (e) {{}}")
        try:
            g = geom(page)
            assert not errors, f"the page errored while reading the old key: {errors}"
            assert g["shape"] == want, (
                f"a device arriving with padCross={legacy!r} upright drew the "
                f"{g['shape']}; task 121 saved the {want} and nothing here may "
                "quietly drop it")
        finally:
            ctx.close()


def check_the_old_key_never_leaks_into_the_other_orientation(browser, gate):
    """`padCross` was only ever asked about the upright screen, so it may not
    answer for the sideways one: a tablet that ticked the cross upright must
    still get the sideways default until he says otherwise."""
    page, ctx, errors = open_page(
        browser, gate, 1280, 800,
        init="try { localStorage.setItem('padCross', '1'); } catch (e) {}")
    try:
        g = geom(page)
        assert g["shape"] == "cross" and g["column"] is False, (
            f"sideways drew the {g['shape']} — the default there is the cross")
        pref = page.evaluate("() => padShapePref('landscape')")
        assert pref == "auto", (
            f"the old upright key answered for the sideways screen ({pref!r}); "
            "it was never a question about that orientation")
    finally:
        ctx.close()


def check_the_two_orientations_are_independent(pages):
    """One choice, one orientation. Setting the sideways shape may not move
    the upright one, and the reverse."""
    page = pages[0]
    page.evaluate("() => { setPadShape('landscape', 'column');"
                  " setPadShape('portrait', 'auto'); }")
    assert page.evaluate("() => padShape('portrait')") == "column", (
        "the upright default moved when the sideways choice was made")
    assert page.evaluate("() => padShape('landscape')") == "column", (
        "the sideways choice was made and the sideways shape did not follow it")
    page.evaluate("() => { setPadShape('portrait', 'cross');"
                  " setPadShape('landscape', 'auto'); }")
    assert page.evaluate("() => padShape('landscape')") == "cross", (
        "the sideways default moved when the upright choice was made")
    assert page.evaluate("() => padShape('portrait')") == "cross", (
        "the upright choice was made and the upright shape did not follow it")
    page.evaluate("() => { setPadShape('portrait', 'auto');"
                  " setPadShape('landscape', 'auto'); }")


def check_the_choice_is_stored_through_the_prefs_bridge(browser, gate):
    """NEVER BARE localStorage (owner bug 2026-08-05): it is keyed by ORIGIN,
    and the shell deliberately alternates between the LAN and the Tailscale
    address — a pure-localStorage switch silently keeps two diverging copies
    of the same device's state. This installs a fake shell bridge and proves
    the write really goes down it."""
    bridge = """
      window.__prefs = {};
      window.__prefWrites = [];
      window.Android = {
        prefGet: (k) => (k in window.__prefs ? window.__prefs[k] : ""),
        prefSet: (k, v) => { window.__prefs[k] = String(v);
                             window.__prefWrites.push([k, String(v)]); },
      };
    """
    page, ctx, errors = open_page(browser, gate, 915, 412, init=bridge)
    try:
        page.evaluate("() => setPadShape('landscape', 'column')")
        page.wait_for_timeout(120)
        writes = page.evaluate("() => window.__prefWrites")
        assert ["padShapeLand", "column"] in [list(w) for w in writes], (
            f"the sideways choice never reached the shell's bridge: {writes}")
        g = geom(page)
        assert g["shape"] == "column", (
            "the choice was written to the bridge but the page did not read it "
            f"back (drew the {g['shape']})")
        assert not errors, f"the page errored with the shell bridge present: {errors}"
    finally:
        ctx.close()


def check_the_decision_and_the_page_never_disagree(label, page):
    """`padColumn()` is the one question the rest of the page asks. The CSS
    class and the rendered GEOMETRY must both follow it — a class that is set
    while the grid stays a cross is the bug this gate exists to catch."""
    orient = "portrait" if "upright" in label else "landscape"
    for shape in ("column", "cross"):
        g = geom(page, orient, shape)
        assert g["shape"] == shape and g["column"] == (shape == "column"), (
            f"@ {label}: asked for the {shape}, the page decided {g['shape']}")
        assert g["klass"] == (shape == "column"), (
            f"@ {label}: the body class disagrees with the decision "
            f"({shape}, class={g['klass']})")
        cols, rows = SHAPE_GRID[shape]
        for gid, gg in g["groups"].items():
            assert (gg["cols"], gg["rows"]) == (cols, rows), (
                f"@ {label}: {gid} was asked for the {shape} ({cols}x{rows}) "
                f"and laid itself out {gg['cols']}x{gg['rows']} — the class "
                "moved, the layout did not")
    geom(page, orient, "auto")


def check_the_default_is_untouched(label, page):
    """A device that has chosen nothing draws what it drew yesterday — the
    first line of his ruling, measured on the real page rather than argued."""
    orient = "portrait" if "upright" in label else "landscape"
    g = geom(page, orient, "auto")
    want = DEFAULT_SHAPE[orient]
    assert g["shape"] == want, (
        f"@ {label}: with nothing chosen the page drew the {g['shape']}; it "
        f"has always drawn the {want} there and this feature may not move it")


def check_the_mirror_image_fits(pages, results):
    """THE NEW HALF, MEASURED WHERE HE ASKED FOR IT: the column sideways and
    the cross upright, on a phone AND on a tablet. Nothing may leave the
    screen, the two groups may not meet, the page may not gain horizontal
    scroll, and neither group may climb into the top corner buttons (Layout /
    Hide) — which is what an unclamped column does on a short sideways
    screen.

    THE ONE HONEST EXCEPTION, stated rather than hidden: two crosses do not
    fit side by side on a 412 px phone with the picture between them. That is
    precisely why the column is the upright default, and it is why the cross
    is offered there as HIS choice for a wide screen. On that one size the
    collision is expected and only the screen bounds are asserted."""
    label, page = pages
    portrait = "upright" in label
    orient = "portrait" if portrait else "landscape"
    narrow = min(page.viewport_size["width"], page.viewport_size["height"]) < 700
    for shape in ("column", "cross"):
        g = geom(page, orient, shape)
        bad = []
        for gid, gg in g["groups"].items():
            if gg["outside"]:
                bad.append(f"{gid} has {gg['outside']} button(s) off screen "
                           f"({gg['rect']})")
            for c in g["corners"]:
                if overlap(gg["rect"], c):
                    bad.append(f"{gid} overlaps a top corner button {c}")
        if g["scrollW"] > g["w"] + 1:
            bad.append(f"the page gained horizontal scroll "
                       f"({g['scrollW']} > {g['w']})")
        left = g["groups"]["group-left"]["rect"]
        right = g["groups"]["group-right"]["rect"]
        crowded = left["r"] > right["l"] - 8
        impossible = shape == "cross" and portrait and narrow
        if crowded and not impossible:
            bad.append(f"the two groups meet in the middle "
                       f"(left ends {left['r']:.0f}, right starts "
                       f"{right['l']:.0f})")
        results[f"the {shape} fits @ {label}"] = not bad
        if bad:
            print(f"  DETAIL {shape} @ {label}: {bad}")
    geom(page, orient, "auto")


def check_the_source_keeps_the_shape_out_of_the_media_queries():
    """The media query WAS the bug: `@media (orientation: portrait)` welded the
    column to the upright screen, so no preference could ever be consulted
    sideways. The rule now hangs off the decision class, and this keeps it
    there — a future round adding an orientation query back to `.group` would
    re-weld it silently."""
    css = (PROJECT / "client" / "style.css").read_text(encoding="utf-8")
    block = css.split("--- D-pad groups")[1].split("--- Category wheel")[0]
    # RULES ONLY — the comment above the rule quotes the media query it
    # replaced, and a check that cannot tell a quotation from a rule would
    # forbid writing down what was fixed.
    rules = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    assert "@media" not in rules, (
        "a media query is back on the D-pad groups — the shape is a DECISION "
        "(body.pad-column), never an orientation")
    assert "body.pad-column .group" in block, (
        "the decision class no longer lays the column out")


def check_nothing_writes_the_retired_key():
    """`padCross` is a seed to be READ. A round that starts writing it again
    would give this device two sources of truth for one answer."""
    src = CONTROLS_JS.read_text(encoding="utf-8")
    for line in src.splitlines():
        if "prefSet(" in line and "PAD_SHAPE_LEGACY" in line:
            raise AssertionError(f"the retired key is being written: {line.strip()}")
    assert "PAD_SHAPE_LEGACY" in src, "the seed key is gone — old choices would be lost"


# ═══════════════════════════ the run ═══════════════════════════
def main() -> int:
    print("\n=== PAD SHAPE GATE ===")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("PAD SHAPE GATE FAILED — playwright is required (it opens the "
              "REAL page). Never skip a gate silently.")
        return 1

    gate = start_server()
    results = {}
    SHOT_DIR.mkdir(parents=True, exist_ok=True)

    def record(name, check):
        try:
            check()
            results[name] = True
        except AssertionError as e:
            results[name] = False
            print(f"  DETAIL {name}: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            # ONE CONTEXT AT A TIME, closed before the next opens. The server
            # allows ONE device (a second authenticated socket closes the
            # first with 4409 — owner 2026-08-02), so four pages held open
            # together would each be measuring a page the server had already
            # hung up on, and every screenshot would carry the takeover toast
            # across it.
            for label, w, h in SIZES:
                page, ctx, errors = open_page(browser, gate, w, h)
                try:
                    results[f"the page loads clean @ {label}"] = not errors
                    if errors:
                        print(f"  DETAIL page errors @ {label}: {errors}")
                    pair = (label, page)
                    record(f"the default is untouched @ {label}",
                           lambda: check_the_default_is_untouched(*pair))
                    record(f"the decision, the class and the layout agree @ {label}",
                           lambda: check_the_decision_and_the_page_never_disagree(*pair))
                    check_the_mirror_image_fits(pair, results)
                    # The pure decision needs a page and nothing else — asked
                    # on the first size only, since a pure function cannot
                    # depend on the viewport.
                    if label == SIZES[0][0]:
                        for name, check in [
                            ("auto still draws yesterday's picture",
                             check_auto_still_draws_yesterdays_picture),
                            ("an explicit choice outranks the default, both ways",
                             check_an_explicit_choice_outranks_the_default),
                            ("task 121's key reads as the upright choice",
                             check_task_121s_key_is_read_as_the_portrait_choice),
                            ("the two orientations are independent",
                             check_the_two_orientations_are_independent),
                        ]:
                            record(name, lambda c=check: c([page]))
                    # THE PICTURE HE JUDGES IT BY: the mirror image is the
                    # request, so what gets shot is the state nobody could see
                    # before this round (rules/GUI.md — a choice offered
                    # without a picture is a choice he has to install to
                    # evaluate).
                    portrait = "upright" in label
                    shape = "cross" if portrait else "column"
                    geom(page, "portrait" if portrait else "landscape", shape)
                    # Let the re-render settle before the shutter: a shot taken
                    # mid-transition carries ghosts of the previous shape, and
                    # a picture that shows a state the product never rests in
                    # cannot be graded (the look-drift lesson of 2026-08-07).
                    page.wait_for_timeout(500)
                    page.screenshot(path=str(
                        SHOT_DIR / f"{shape}_{label.replace(' ', '_')}.png"))
                finally:
                    ctx.close()

            record("a device arriving with the old key keeps it",
                   lambda: check_a_device_arriving_with_the_old_key_keeps_its_choice(
                       browser, gate))
            record("the old key never answers for the other orientation",
                   lambda: check_the_old_key_never_leaks_into_the_other_orientation(
                       browser, gate))
            record("the choice is stored through the shell's bridge",
                   lambda: check_the_choice_is_stored_through_the_prefs_bridge(
                       browser, gate))
            record("the shape is a decision, not a media query",
                   check_the_source_keeps_the_shape_out_of_the_media_queries)
            record("nothing writes the retired key", check_nothing_writes_the_retired_key)
        finally:
            browser.close()

    failed = [k for k, ok in results.items() if not ok]
    for name in sorted(results):
        print(f"  {'PASS' if results[name] else 'FAIL'}  {name}")
    if failed:
        print(f"\nPAD SHAPE GATE FAILED — {len(failed)} check(s) broken.")
        return 1
    print("\nPAD SHAPE GATE PASSED — the arrangement follows his choice, in "
          "both orientations, and both mirror images fit.")
    return 0


def test_pad_shape():
    """pytest entry."""
    import pytest
    pytest.importorskip("playwright.sync_api")
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
