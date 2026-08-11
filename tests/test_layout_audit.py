"""Layout audit for the GUI surfaces this project ships on the PHONE — the
overlay panels (Sets picker, Quality panel, Aspect panel + Move handle).
Proof source for .claude/layout-proof.md (THE SPACE & LEGIBILITY LAW,
rules/GUI.md): the REAL page is opened in a REAL headless Chromium at phone
sizes, each panel is opened, and geometry is checked — nothing clipped, no
horizontal overflow anywhere, every panel card fully inside the viewport.

Also audits the server-side region placement math (`_fit_rect` with the
2026-08-05 `pos` fraction): the placed rect must stay inside its box for
every position, or the phone would frame pixels outside the monitor.

Run:  .venv\\Scripts\\python tests/test_layout_audit.py
Requires the same toolchain as the input gate (playwright + chromium).
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

# The measuring instruments this audit injects into the live page — how a
# truth about PIXELS is computed (compositing, luminance, WCAG floors). Split
# out on 2026-08-08 (THE STRUCTURE LAW); what is opened and what is asserted
# stays here. See tests/_audit_js.py.
from _audit_js import CONTRAST_JS, LIVE_CLOCK_BLANK_JS, LIVE_CLOCK_DRIFT_JS, PANEL_FIT_JS  # noqa: E402
from _audit_frame import RADIUS_KIN_JS  # noqa: E402

# The panel CATALOGUE — WHICH overlay is opened and in WHAT state. Split out on
# 2026-08-09 (THE STRUCTURE LAW), when the dictation card's listen control
# pushed this file past 1,000 lines. See tests/_audit_panels.py.
from _audit_panels import (  # noqa: E402
    CLOSE_WARN_STAGE_JS, COLOUR_SHOTS, CREATION_CLOSE_JS,
    CREATION_LIST_STAGE_JS, DICT_STAGE_JS, LANDSCAPE_SHOTS,
    LAYOUT_LIST_CLOSE_JS, LAYOUT_LIST_STAGE_JS, LAYOUT_SETTINGS_STAGE_JS,
    PANELS, SHOT_SUBJECTS, UA_MODEL,
)

# THE TABLET WAS NEVER MEASURED (owner report 2026-08-08: "do sad nikad nisam
# probao preko tableta, sad sam probao … naišao sam na taj bag da Touch ne radi
# preko tableta"). Every size in this list was a PHONE, so every geometry
# claim this audit has ever made was a claim about a phone — and he uses both.
# 800x1280 / 1280x800 is a common 10" Android tablet in CSS pixels.
SIZES = [("portrait 412x915", 412, 915), ("landscape 915x412", 915, 412),
         ("tablet portrait 800x1280", 800, 1280),
         ("tablet landscape 1280x800", 1280, 800)]

# EVERY LOOK THE PRODUCT SHIPS — THREE INDEPENDENT AXES (build round R3,
# 2026-08-07; CORRECTED 2026-08-08 to match the owner's own model: "teme
# postoje samo dve, svetla i tamna … a ove komande … on može da bude obojen,
# neobojen, i može da bude transparentan ili pun"). theme (dark/light) x
# colored (True/False) x fill (transparent/full) = eight real renderings of
# every panel — and the CONTRAST check below is the only thing standing
# between a coloured look and a set whose own name is unreadable on its own
# colour. A look audited in one combination is not audited.
#
# `colored` is not a fourth THEME (the 2026-08-07 model this replaces): it is
# its own axis, orthogonal to `theme`. A coloured look on `light` is a
# DIFFERENT page wearing the SAME palette as a coloured look on `dark`
# (server/config.py ships ONE table since 2026-08-08), which makes this sweep
# MORE necessary rather than less: one set of hexes now has to hold up on both
# surfaces, and the whole reason the sweep exists is that a colour which reads
# on one surface can be invisible on the other — restructuring the axes changes NOTHING about that
# fact, only how it is spelled.
#
# The full panel sweep runs in every combination at PORTRAIT (where the cards
# are narrowest and a row starves first); landscape keeps the default look,
# because what landscape tests is GEOMETRY and geometry does not change with
# a colour. Both sizes get the contrast check in every combination.
#
# Each entry is (theme, colored, fill).
LOOKS = [("dark", False, "transparent"), ("dark", False, "full"),
         ("dark", True, "transparent"), ("dark", True, "full"),
         ("light", False, "transparent"), ("light", False, "full"),
         ("light", True, "transparent"), ("light", True, "full")]
DEFAULT_LOOK = LOOKS[0]


def _look_word(colored: bool) -> str:
    return "colored" if colored else "plain"


def _grid_audit() -> bool:
    """Every grid of the owner's sheet tiles its region EXACTLY: no gap, no
    overlap, no sliver. Pure numbers, so it is checked here rather than by
    looking at a screenshot of two windows."""
    from grids import GRID_CELLS, _cells
    region = (0, 0, 1200, 800)
    for grid, count in GRID_CELLS.items():
        for orient in ("landscape", "portrait"):
            cells = _cells(region, grid, orient)
            if len(cells) != count:
                return False
            area = sum(w * h for _, _, w, h in cells)
            if area != region[2] * region[3]:
                return False          # a gap or an overlap
            for x, y, w, h in cells:
                if w < 100 or h < 100:
                    return False      # a sliver nobody could use
                if x < 0 or y < 0 or x + w > region[2] or y + h > region[3]:
                    return False      # outside the region
    return True


def _fit_rect_audit() -> bool:
    """Pure-math check: the region never leaves its box and sits CENTRED, at
    any aspect. `pos` left this function on 2026-08-09 (owner decree — the
    Move handle anchors the letterboxed picture ON THE PHONE; the phone-side
    geometry has its own gate, tests/test_view_anchor.py)."""
    from grids import _fit_rect   # the geometry moved out of window_manager (2026-08-07)
    box = (100, 50, 1000, 600)
    for aspect in (0.4, 1.0, 16 / 9, 3.2):
        x, y, w, h = _fit_rect(box, aspect)
        if not (box[0] <= x and box[1] <= y and
                x + w <= box[0] + box[2] and y + h <= box[1] + box[3]):
            return False
        if w <= 0 or h <= 0:
            return False
        # Centred: the slack splits evenly (integer floor may differ by 1).
        if abs((x - box[0]) - ((box[0] + box[2]) - (x + w))) > 1:
            return False
        if abs((y - box[1]) - ((box[1] + box[3]) - (y + h))) > 1:
            return False
    return True


# WHERE THE PICTURES GO (rules/GUI.md -> Zubi v2, GATE of 2026-08-08).
# Every screenshot lives in a TOPIC subfolder named after what was being worked
# on, so the owner opens ONE folder and sees ONE story instead of a dump of a
# hundred and eighty cryptic names in a single directory. The topic is the
# ROUND's subject and it is set on this one line; `RU_SHOT_TOPIC` overrides it
# for a one-off sweep that is not the round's own proof (the colour VARIANTS of
# 2026-08-08 were rendered into their own folder that way, because alternatives
# offered for a decision are not candidate designs of ours to pass or fail).
SHOT_TOPIC = os.environ.get("RU_SHOT_TOPIC", "round17-caret-claude-set-colours")
SHOT_DIR = PROJECT / ".claude" / "shots" / SHOT_TOPIC

def shot_path(name: str):
    """`<round topic>/<subject>/<name>.png`, with the subject folder made on
    demand. The longest matching prefix wins, so `Controls_and_wheel` never
    falls into `controls`."""
    subject = "other"
    best = 0
    for prefix, folder in SHOT_SUBJECTS:
        if name.startswith(prefix) and len(prefix) > best:
            subject, best = folder, len(prefix)
    out = SHOT_DIR / subject
    out.mkdir(parents=True, exist_ok=True)
    return out / f"{name}.png"


def _shot_name(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_") + ".png"


def _shot_label(name: str, look, portrait: bool = True, always: bool = False) -> str:
    """A panel's name, plus the look it was shot in and the orientation — but
    ONLY when either is not the default (or `always` says otherwise — the
    eight axis-named "Controls and wheel" pictures the owner grades by hand
    want every combination spelled out, default included), so every OTHER
    shot the existing proof lines already point at keeps its filename.

    LANDSCAPE IS NOT A DEFAULT (independent grader, 2026-08-07): every phone
    screenshot on disk was 824x1830 portrait, so nothing about the other
    orientation had ever been LOOKED at, only measured. The app runs in both.

    THREE AXES SPELLED WITH TWO SPACES BETWEEN THEM (owner correction
    2026-08-08): a panel name may itself contain spaces ("Controls and
    wheel"), and `_shot_name` below turns every non-alnum run into
    underscores one-for-one — so a double space between the panel name and
    the axes, and between each axis, is what turns into the double
    underscores the owner asked filenames to carry
    ("Controls_and_wheel__dark__colored__full.png")."""
    theme, colored, fill = look
    if always or look != DEFAULT_LOOK:
        name = f"{name}  {theme}  {_look_word(colored)}  {fill}"
    return name if portrait else f"{name} landscape"


def _apply_look(page, theme, colored, fill):
    """Put the page into one of the eight looks the desktop can choose.

    Through `applyUi`, the app's OWN entry point — the same function the
    `config` frame calls — so the audit can never be measuring a state the
    product cannot actually reach.

    AND THROUGH THE DESKTOP, which is the only place a look is really chosen
    (client/__about/theme.md). This audit runs the real server in THIS process,
    so `config.apply` moves the same `SETTINGS.phone_theme` / `phone_colored` /
    `phone_fill` the Appearance card writes, and every `config` frame the
    server sends from now on carries the look this sweep asked for. Without it
    the audit was fighting its own server: the page's readiness gate
    (`#group-left button`) goes green about 1.4 s before the socket's first
    `config` lands, so the first look applied inside that window was silently
    dragged back to the shipped default — one wrong picture per browser
    context, which is exactly the two of twelve a third independent grader
    found by sampling page colours (2026-08-07). In-memory only;
    `save_user_settings` is the only writer of the owner's file and is never
    called here.

    AND THE PALETTE COMES WITH IT. The colours are no longer a parameter this
    file carries around: WHICH of the two shipped tables a THEME wears
    (independent of whether `colored` is even on) is a decision, and it
    belongs to the one place that makes it for the real phone —
    `config.ui_config()`. An audit that chose the palette itself could paint
    the light page with the dark table and report a green sweep of colours no
    phone will ever show."""
    import config as server_config
    server_config.apply(phone_theme=theme, phone_colored=colored, phone_fill=fill)
    ui = server_config.ui_config()
    page.evaluate("(ui) => applyUi(ui)", ui)
    return ui


def _shoot(page, label, look, results):
    """Write a look-named screenshot — after PROVING the page is still wearing
    that look.

    THE ASSERTION THIS FILE WAS MISSING, and the reason three rounds of
    independent graders were handed pictures of the wrong look while every
    check printed PASS (2026-08-07). Nothing here compared what `_apply_look`
    ASKED for against what `<body>` was actually showing when the shutter
    fired, so a `config` frame arriving in between — the product bug this round
    also fixes, and any future variant of it — renamed the look and nobody
    noticed. `Controls_dark_full.png` was byte-identical to `Controls.png` over
    the whole control surface; `Controls_light_transparent_landscape.png`
    rendered the dark palette. Both were labelled `audit: PASS`.

    It FAILS the audit rather than warning, because a warning on a picture is
    worth nothing: the picture is the deliverable, and a mislabelled one costs a
    whole grading round. The shot is still written — the grader has to be able
    to SEE what was measured — but the run goes red and names both looks.

    ALL THREE AXES, since the 2026-08-08 correction — a drifted `data-colored`
    is exactly as wrong a picture as a drifted `data-theme` or `data-fill`."""
    theme, colored, fill = look
    got = page.evaluate(
        "() => [document.body.dataset.theme, document.body.dataset.colored,"
        " document.body.dataset.fill]")
    ok = (got[0], got[1] == "true", got[2]) == (theme, colored, fill)
    results[f"the shot shows the look it is named for: {label}"] = ok
    if not ok:
        print(f"  DETAIL look drift @ {label}: asked for "
              f"{theme}/{_look_word(colored)}/{fill}, the page was showing "
              f"{got[0]}/{_look_word(got[1] == 'true')}/{got[2]} at the shutter")
    page.screenshot(path=str(shot_path(_shot_name(label)[:-4])))


_GROUPS_JS = ("__contrast(document.getElementById('group-left'))"
              ".concat(__contrast(document.getElementById('group-right')))")


def _check_auto_hide(page) -> dict:
    """THE CONTROLS GET OUT OF THE WAY, AND ONLY WHERE HE SAID THEY MAY
    (owner 2026-08-08, task 120).

    Driven by moving `lastWake` back rather than by sleeping three real
    seconds per case: the RULE is what is under test, and the tick re-decides
    it every 250 ms. Sleeping would add half a minute to every audit run and
    prove nothing extra.
    """
    out = {}

    def idle_one_tick():
        page.evaluate("lastWake = performance.now() - AUTO_HIDE_MS - 500")
        page.wait_for_timeout(400)          # one tick, comfortably

    def hidden():
        return page.evaluate(
            "document.body.classList.contains('hidden-controls')")

    page.evaluate("closeWheel(); closeLayoutPanel(); creating = null;"
                  " layoutArm = false; setControlsHidden(false)")
    idle_one_tick()
    out["the controls hide themselves on the bare working screen"] = hidden()

    # …and ANY contact brings them straight back.
    page.evaluate("wakeControls()")
    out["any contact brings the controls back"] = not hidden()

    # THE FENCE. Each of these is something he is looking at, and none of them
    # may take the controls away under his thumb.
    for label, open_js, shut_js in (
        ("the category wheel", "openWheel('left')", "closeWheel()"),
        ("a panel he is reading", "openSetsPanel()", "closeSetsPanel()"),
        ("a layout being built", "creating = newCreation('list')",
         "creating = null"),
        ("an armed window pick", "layoutArm = true", "layoutArm = false"),
    ):
        page.evaluate(open_js)
        idle_one_tick()
        out[f"nothing hides while {label} is open"] = not hidden()
        page.evaluate(shut_js)

    # A BLOCKER THAT OPENS WITH NO TOUCH BRINGS THEM BACK. The notices card
    # offers itself on connect and the dictation card opens itself on the
    # first Mic tap — neither is a pointerdown, and a one-shot timer armed at
    # load had already hidden the controls by then. This case is why the rule
    # is a tick.
    page.evaluate("setControlsHidden(false)")
    idle_one_tick()
    page.evaluate("openSetsPanel()")
    page.wait_for_timeout(400)
    out["a panel opening with no touch brings the controls back"] = not hidden()
    page.evaluate("closeSetsPanel(); setControlsHidden(false); wakeControls()")

    # The Hide button must still work IN BOTH DIRECTIONS. Its own press must
    # not wake the controls, or the one button that always worked would become
    # the one that never unhides.
    # Driven through the WINDOW's own capture listener and then the button's
    # own activator, in that order, because that IS the race: `wakeControls`
    # runs on pointerdown and the toggle runs on pointerup, so a toggle
    # reading "current state" instead of the state the finger LANDED on would
    # unhide and immediately re-hide. Playwright's `.tap()` proved too soft to
    # show it — it never reached the capture listener — and a check that
    # cannot fail is not a check (this one was rewritten after its own planted
    # defect walked straight through it).
    press = ("const btn = document.getElementById('btn-hide');"
             " wakeControls({target: btn});"
             " buttonPress(btn, true); buttonPress(btn, false);")

    page.evaluate("setControlsHidden(true)")
    page.evaluate(press)
    page.wait_for_timeout(60)
    out["a tap on Hide while hidden UNhides"] = not hidden()
    page.evaluate(press)
    page.wait_for_timeout(60)
    out["a tap on Hide while showing hides at once"] = hidden()
    page.evaluate("setControlsHidden(false); wakeControls()")
    return out


def _check_controls(page):
    """The D-pad groups and the category wheel — the surfaces the `colored`
    theme actually paints, and the ones no panel check has ever looked at.

    A set's colour is its BUTTON's ink in the outlined fill and its BACKGROUND
    in the filled one, so this is where an unreadable colour would land first.

    BOTH STATES (2026-08-07). The D-pad is measured with the wheel SHUT — the
    state the owner's thumb actually lives in — and again with it OPEN, which
    is the state the graded screenshot shows and the state whose veil used to
    hide a 2.66:1 label from this very check. The wheel itself is measured
    while open for its own sake: it is the one place every set's colour is on
    screen at once. It is left open on purpose — the caller shoots it."""
    bad = page.evaluate("() => " + _GROUPS_JS)
    page.evaluate("openWheel('left')")
    page.wait_for_selector("#wheel.open .wheel-item", state="visible", timeout=4000)
    return bad + page.evaluate(
        "() => __contrast(document.getElementById('wheel')).concat(" + _GROUPS_JS + ")")


def _check_panel(page, name, open_js, close_js, card_sel, shot=False,
                 look=None, results=None):
    """Opens one overlay panel and verifies: the card sits fully inside the
    viewport, the page gained no horizontal overflow, no element inside the
    card is clipped horizontally, and every leaf of text in it can be read."""
    page.evaluate(open_js)
    page.wait_for_selector(card_sel, state="visible", timeout=4000)
    ok = page.evaluate(
        PANEL_FIT_JS,
        card_sel,
    )
    if shot:
        # The layout gate grades a PICTURE, and a picture of the phone's own
        # panels is the only thing that can carry a colour verdict — the very
        # thing the owner had to report by eye on 2026-08-06. Written by the
        # audit itself, so it can never be of a different build than the one
        # just measured — and, since 2026-08-07, never of a different LOOK
        # than the one in its own filename (`_shoot`).
        _shoot(page, name, look, results)
    page.evaluate(close_js)
    passed = (ok["inView"] and ok["noPageScroll"] and ok["noClip"]
              and ok["noScrollWithSlack"] and not ok["contrast"]
              and not ok["truncated"])
    return passed, ok


def main() -> int:
    import test_input_pipeline as gate
    # The shipped set NAMES, from the tables that define them
    # (server/config.py). The colours themselves are fetched per look inside
    # `_apply_look` — a theme picks its own palette there — but the names are
    # the same thirteen in both, and they are what the sweep iterates.
    from config import set_colors
    SET_NAMES = list(set_colors("dark"))

    threading.Thread(target=gate.run_server, daemon=True).start()
    gate.server_ready.wait(15)
    deadline = time.time() + 10
    import socket
    while time.time() < deadline:
        if gate.server_error:
            raise gate.server_error[0]
        try:
            with socket.create_connection(("127.0.0.1", gate.PORT), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("audit server never started")

    from playwright.sync_api import sync_playwright

    results = {"region math: _fit_rect stays inside its box, centred": _fit_rect_audit(),
               "grid math: every shape tiles its region exactly": _grid_audit(),
               "live-clock wiring: render.js runs the module (task 151)": all(f"{fn}(" in (PROJECT / "client" / "render.js").read_text(encoding="utf-8") for fn in ("liveAction", "liveRegulate", "liveSeekTarget"))}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for label, w, h in SIZES:
            ctx = browser.new_context(
                viewport={"width": w, "height": h}, has_touch=True, is_mobile=True,
                # 2x, so the written shots are a real phone's pixels (824x1830,
                # not 412x915). The proof is GRADED BY EYE against DESIGN.md —
                # THE VISUAL PROOF (rules/GUI.md) will not accept an image
                # under 700 px on its short side, and it is right not to: a
                # 412 px thumbnail cannot show whether text is crowded.
                device_scale_factor=2,
                user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 "
                            "Mobile Safari/537.36 VibeCoderApp"),
            )
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
            page.wait_for_selector("#group-left button", timeout=8000)
            # …AND for the socket's first `config` to have landed. The D-pad
            # renders from the page's own defaults, so the selector above goes
            # green about 1.4 s before the server has said a word — measured,
            # 2026-08-07 — and everything the audit did in that window was
            # overwritten by the config frame when it finally arrived. `monitor`
            # stays 0x0 until that frame, so it is the honest readiness signal.
            page.wait_for_function("() => monitor.w > 0", timeout=10000)
            # The REAL app sets, from the shipped actions.json — the panels
            # that list them must be measured with the names the owner will
            # actually see, not with invented short ones.
            page.evaluate("(sets) => { window.APP_SETS = sets; }",
                          json.loads((PROJECT / "actions.json")
                                     .read_text(encoding="utf-8"))["app_sets"])

            # Wrapped in a no-argument function: Playwright treats any string
            # that LOOKS like a function as one to call, and the bare
            # assignment below contains an arrow — it was being invoked with
            # no root instead of installed.
            page.evaluate("() => {" + CONTRAST_JS + RADIUS_KIN_JS + "}")  # + the FRAME LAW instrument (task 156, _audit_js.py)
            # MEASURED, not read off the label. It was `label.startswith
            # ("portrait")` until 2026-08-08, which was true while every size
            # in this file was a phone — and became a silent lie the moment
            # "tablet portrait 800x1280" joined them: an upright tablet was
            # treated as landscape, so its shots would have been written with
            # a `_landscape` suffix. A picture whose NAME lies is exactly what
            # the look-assertion tooth exists to stop, and this is the same
            # class of defect one layer up.
            portrait = h > w

            # ON MUST BE VISIBLE IN THIS LOOK (owner 2026-08-09, screenshot
            # of the Mic switched on in the coloured look: "uopšte ti nije
            # jasno, meni kao korisniku, da li i šta je uključeno").
            # Colour alone is not enough — a saturated set fill swallows an
            # accent halo. So the check is that an ACTIVE button differs from
            # its own inactive sibling by something a camera would see, and by
            # something that is NOT only a hue.
            on = page.evaluate('''() => {
              const g = document.getElementById('group-left');
              const btns = [...g.querySelectorAll('button.ctl:not(.cat)')];
              if (btns.length < 2) return ['fewer than two buttons to compare'];
              btns[0].classList.add('active');
              const a = getComputedStyle(btns[0]);
              const b = getComputedStyle(btns[1]);
              const bad = [];
              if (a.borderTopWidth === b.borderTopWidth) {
                bad.push('the active button has the same border width');
              }
              if (a.borderTopStyle !== 'solid') {
                bad.push('the active ring is ' + a.borderTopStyle + ', not solid');
              }
              if (a.backgroundImage === b.backgroundImage) {
                bad.push('the active button carries no extra fill');
              }
              btns[0].classList.remove('active');
              return bad;
            }''')
            results[f"an ON button is unmistakable @ {label}"] = not on
            if on:
                print(f"  DETAIL active state @ {label}: {on}")
            results[f"a gap in the stream never blanks the screen @ {label}"] = not page.evaluate(LIVE_CLOCK_BLANK_JS)
            results[f"a starved player is caught, not only a late one @ {label}"] = not page.evaluate(LIVE_CLOCK_DRIFT_JS)
            results[f"a catch-up lands with headroom, not on the edge @ {label}"] = page.evaluate("LIVE_TARGET_BEHIND_S") >= 0.3
            # AUTO-HIDE — once per SIZE, not per look: it is a behaviour, and
            # a colour cannot change it. Run before the look sweep so the
            # controls are in a known state for everything that follows.
            for name, ok in _check_auto_hide(page).items():
                results[f"{name} @ {label}"] = ok

            # THE D-PAD SHAPE IS A CHOICE IN PORTRAIT TOO (owner 2026-08-08,
            # task 121). On a TABLET held upright this is the whole point of
            # the feature, and the tablet sizes had never been measured at all
            # until this round — so the cross is checked for fit exactly where
            # he asked for it, not only where it already lived.
            # `setPadCross(true)` until 2026-08-09, when the D-pad shape became
            # a per-orientation CHOICE (`setPadShape(orient, value)` in
            # controls.js) instead of one portrait boolean. Translated rather
            # than dropped, and asked of the orientation actually on screen —
            # the check is "the cross fits HERE", so forcing portrait's shape
            # while measuring a landscape page would have measured nothing.
            page.evaluate("setPadShape(padOrientation(), 'cross')")
            page.wait_for_timeout(150)
            fit = page.evaluate("""() => {
              const bad = [];
              for (const id of ['group-left', 'group-right']) {
                const g = document.getElementById(id);
                const r = g.getBoundingClientRect();
                if (r.left < 0 || r.top < 0 ||
                    r.right > innerWidth + 1 || r.bottom > innerHeight + 1) {
                  bad.push(id + ' leaves the screen: ' + JSON.stringify(
                    {l: Math.round(r.left), t: Math.round(r.top),
                     r: Math.round(r.right), b: Math.round(r.bottom),
                     w: innerWidth, h: innerHeight}));
                }
              }
              // …and the two crosses must not meet in the middle, which is
              // the whole reason the column exists on a narrow phone.
              const a = document.getElementById('group-left').getBoundingClientRect();
              const b = document.getElementById('group-right').getBoundingClientRect();
              if (a.right > b.left - 8) bad.push('the two crosses overlap');
              if (document.scrollingElement.scrollWidth > innerWidth + 1) {
                bad.push('the page gained horizontal scroll');
              }
              return bad;
            }""")
            wide = w >= 700
            # A NARROW phone genuinely cannot hold two crosses — that is why
            # the column is the default. What must hold is that the choice is
            # SAFE where he asked for it: a tablet held upright.
            if wide or not portrait:
                results[f"the D-pad cross fits upright @ {label}"] = not fit
                if fit:
                    print(f"  DETAIL pad cross @ {label}: {fit}")
                # …and he SEES it, because a choice offered without a
                # picture is a choice he has to install to evaluate.
                if portrait:
                    page.screenshot(path=str(shot_path("Pad_cross_upright")))
            page.evaluate("setPadShape(padOrientation(), 'auto')")
            page.wait_for_timeout(120)

            for look in LOOKS:
                theme, colored, fill = look
                look_name = f"{theme}/{_look_word(colored)}/{fill}"
                _apply_look(page, theme, colored, fill)

                # The D-pad and the wheel FIRST — they are the surfaces a
                # `colored` look actually paints, and no panel check has ever
                # looked at them. Both sizes, every look.
                bad = _check_controls(page)
                results[f"controls contrast @ {label} @ {look_name}"] = not bad
                if bad:
                    print(f"  DETAIL controls @ {label} @ {look_name}: {bad}")
                # THE STATUS PILL — every toast this app shows, and the one
                # element `__contrast` structurally could not see: its fill is
                # a linear-gradient, so its `backgroundColor` is transparent
                # and the walk scored the ink against the page behind it. It
                # shipped at 1.97:1 through four visual rounds because of that
                # (grader, 2026-08-07). Measured on the gradient's STOPS,
                # which bound every pixel between them, read live from the
                # page's own tokens so a palette retune fails here.
                bad = page.evaluate("() => __pillContrast()")
                results[f"toast pill contrast @ {label} @ {look_name}"] = not bad
                if bad:
                    print(f"  DETAIL toast pill @ {label} @ {look_name}: {bad}")
                # ALWAYS axis-named (owner request 2026-08-08): eight pictures
                # of the controls + open wheel, one per combination, graded by
                # the owner himself — unlike every other shot in this sweep,
                # even the DEFAULT look gets its axes spelled out in the name.
                _shoot(page, _shot_label("Controls and wheel", look, portrait,
                                        always=True),
                       look, results)
                page.evaluate("closeWheel()")
                # …and the working screen WITHOUT the wheel. Both orientations,
                # every look: a phone that runs in landscape and has never been
                # photographed there has been measured, not looked at.
                _shoot(page, _shot_label("Controls", look, portrait),
                       look, results)

                # EVERY colour of the desktop's table, on both surfaces — not
                # only the three the pinned fixture puts on screen.
                bad = page.evaluate("(names) => __sweepSetColours(names)",
                                    SET_NAMES)
                results[f"every set colour @ {label} @ {look_name}"] = not bad
                if bad:
                    print(f"  DETAIL set colours @ {label} @ {look_name}: {bad}")

                # The panels: every look at portrait (narrowest cards, where a
                # row starves first); at landscape only the default, because
                # what landscape tests is GEOMETRY and geometry does not
                # change with a colour.
                if not portrait and look != DEFAULT_LOOK:
                    continue
                for name, open_js, close_js, sel in PANELS:
                    shot = ((look == DEFAULT_LOOK or name in COLOUR_SHOTS)
                            if portrait else
                            (look == DEFAULT_LOOK and name in LANDSCAPE_SHOTS))
                    passed, detail = _check_panel(
                        page, _shot_label(name, look, portrait),
                        open_js, close_js, sel, shot=shot,
                        look=look, results=results)
                    results[f"{name} @ {label} @ {look_name}"] = passed
                    if not passed:
                        print(f"  DETAIL {name} @ {label} @ {look_name}: {detail}")

            # Everything below is geometry, and it is measured in the look the
            # product ships by default.
            _apply_look(page, *DEFAULT_LOOK)

            # THE NOTIFY TOAST MUST NEVER BECOME A CIRCLE (owner screenshot,
            # v0.0.107: a huge filled amber circle over the streamed VS Code,
            # bold notification text clipped mid-word by its own curved edges).
            # The toast reuses #status (client/chrome.js showToast()), which
            # was `width: auto` shrink-to-fit until this round: a notify
            # sentence long enough to wrap but not long enough to fill the
            # viewport landed on a near-SQUARE box, and --radius-pill's own
            # `border-radius: 999px` — correct CSS, clamped by the browser to
            # half the SHORTER side on every box — turned that square into a
            # circle. ALG-6's own instrument (__radiusAndKin, below) would
            # have convicted this shape on sight; it never saw it because
            # every OTHER call site in this file points it at a staged PANEL
            # ROOT (the dictation card, the layout list, the member chooser…)
            # and a toast that lives outside every panel was never once
            # handed to it — the law and the tooth were both correct, and the
            # coverage gap is the bug. A realistic long notify sentence (the
            # exact shape that produced the report: too long for one line,
            # too short to fill the phone's width) is staged here so this
            # gate proves the toast itself, not a synthetic square div.
            page.evaluate(
                "() => showToast('Claude Code (Vibe Coder) needs you — "
                "razmisljam o resenju problema sa iscekivanjem konekcije i "
                "treba mi tvoja odluka pre nego sto nastavim dalje')")
            page.wait_for_selector("#status.connecting", state="visible",
                                   timeout=2000)
            toast = page.evaluate(
                "() => __radiusAndKin(document.body).filter("
                "(m) => m.includes(' connecting '))")
            results[f"the notify toast never clips into a circle "
                    f"@ {label}"] = not toast
            if toast:
                print(f"  DETAIL notify toast radius @ {label}: {toast}")
            page.evaluate("() => setStatus('connected', 'Connected')")

            # THE DICTATION CARD SAYS WHOSE LANGUAGES THESE ARE, AND WHICH OF
            # THEM HE CAN HEAR (owner 2026-08-09, task 127 — a screenshot of
            # this card and: "koristim dva uredjaja … treba da kaze OVAJ
            # UREDJAJ ima te i te jezike" plus "treba da mogu da CUJEM da bih
            # odabrao"). The panel sweep above already measures the card's fit
            # and contrast in all eight looks; what it cannot say is whether
            # the three ROW STATES are on it at all — and a row state nobody
            # stages is exactly where this project's bugs keep arriving.
            #
            # The device name is measured, never merely present: the fallback
            # wording ("this device") renders perfectly while the real path is
            # broken, so the card must contain the model THIS context's own
            # User-Agent carries.
            page.evaluate(DICT_STAGE_JS)
            page.wait_for_selector("#dictation-panel .sets-card", state="visible",
                                   timeout=4000)
            dictation = page.evaluate(
                """(model) => {
                  const bad = [];
                  const card = document.querySelector('#dictation-panel .sets-card');
                  const cr = card.getBoundingClientRect();
                  const who = card.querySelector('.dict-device');
                  const said = who ? who.textContent.trim() : '';
                  if (!said) bad.push('the card does not say which device it describes');
                  else if (said.indexOf(model) < 0) {
                    bad.push('the device line does not name this device: "' + said + '"');
                  }
                  const rows = [...card.querySelectorAll('.dict-row')];
                  const play = rows.filter((r) => r.querySelector('.dict-listen'));
                  const noted = rows.filter((r) => r.querySelector('.dict-note'));
                  if (play.length < 2) bad.push('no row offers a listen button');
                  if (!noted.length) bad.push('no row states the honest limit');
                  // The two limits are DIFFERENT facts and each has to be on
                  // screen: no voice for this language, and a voice with no
                  // sample sentence written for it.
                  const said2 = noted.map((r) => r.querySelector('.dict-note').textContent);
                  if (!said2.some((t) => /preview voice/.test(t))) {
                    bad.push('the "no voice on this device" row is not staged');
                  }
                  if (!said2.some((t) => /sample sentence/.test(t))) {
                    bad.push('the "no sample sentence" row is not staged');
                  }
                  for (const b of card.querySelectorAll('.dict-listen')) {
                    const r = b.getBoundingClientRect();
                    if (r.width < 40 || r.height < 40) {
                      bad.push('a listen button is ' + Math.round(r.width) + 'x' +
                               Math.round(r.height) + ' — not a finger target');
                    }
                    if (r.left < cr.left - 1 || r.right > cr.right + 1 ||
                        r.top < cr.top - 1 || r.bottom > cr.bottom + 1) {
                      bad.push('a listen button leaves the card');
                    }
                    // …and it never lands ON the row's own text.
                    const name = b.closest('.dict-row').querySelector('.dict-name');
                    const nr = name.getBoundingClientRect();
                    if (nr.right > r.left + 1) {
                      bad.push('the language name runs under its listen button');
                    }
                  }
                  return bad;
                }""",
                UA_MODEL)
            results[f"the dictation card names the device and stages both "
                    f"preview states @ {label}"] = not dictation
            if dictation:
                print(f"  DETAIL dictation card @ {label}: {dictation}")
            page.evaluate("closeDictationPanel()")

            # KIN ROWS ARE THE SAME SIZE — A ROW IS ONE LINE, LIKE A BUTTON
            # (owner 2026-08-09, task 163, with his screenshot: one layout row
            # wrapped to FOUR lines beside a two-line sibling). The panel sweep
            # above cannot see this: every measurement up there judges a SINGLE
            # element, and four wrapped lines are legible, unclipped and inside
            # the card — the defect is a RELATION between siblings, which needs
            # siblings, and this panel was staged with ONE layout until today.
            # The measuring itself is `__kinRows` in tests/_audit_js.py.
            page.evaluate(LAYOUT_LIST_STAGE_JS)
            page.wait_for_selector("#layout-panel .lay-card", state="visible",
                                   timeout=4000)
            kin = page.evaluate(
                "() => { const c = document.querySelector('#layout-panel"
                " .lay-card'); return __kinRows(c).concat(__radiusAndKin(c)); }")
            results[f"the layout list's rows are one line, all the same "
                    f"height @ {label}"] = not kin
            if kin:
                print(f"  DETAIL layout list kin rows @ {label}: {kin}")

            # …AND THE NAME IS NOT THE LAST IN LINE FOR THE ROW'S WIDTH
            # (independent grader, 2026-08-09, task 172). The kin check above
            # is about the row as GEOMETRY and the shipped row passed it while
            # showing "Claude Cod…" — every sibling the same height, nothing
            # wrapped, nothing off the card, and a name too short to tell two
            # Claude layouts apart. `__nameRoom` in tests/_audit_js.py measures
            # the thing that check cannot see: what the row spends its width
            # ON. Same staging, same four viewports — the defect was present at
            # all of them.
            room = page.evaluate(
                "() => __nameRoom(document.querySelector('#layout-panel"
                " .lay-card'))")
            results[f"a layout row spends more width on its NAME than on any "
                    f"one button @ {label}"] = not room
            if room:
                print(f"  DETAIL layout name room @ {label}: {room}")

            # ⭐ ON THE TRUNK AND ON NOTHING ELSE (owner decision 2026-08-09,
            # task 169). A star that appears on the wrong row is worse than no
            # star, and the two things that could go wrong here are invisible
            # to every other instrument: it lands on the wrong row (a fact
            # about which layout, not about pixels), or a colour emoji's own
            # metrics lift the row it sits in above its siblings — which is
            # task 163's defect arriving through a new door, so the kin
            # measurement above runs on the SAME staging, with the star on it.
            # Expected from the staged `layouts` themselves, never from a row
            # number, so this can never drift from what is staged.
            star = page.evaluate("(lays) => __layoutStars(lays)",
                                 page.evaluate("() => layouts"))
            results[f"the ⭐ marks the trunk row and nothing else "
                    f"@ {label}"] = not star
            if star:
                print(f"  DETAIL layout list star @ {label}: {star}")
            page.evaluate(LAYOUT_LIST_CLOSE_JS)

            # ONE WINDOW OUT OF A GRID (owner request 2026-08-09, task 165).
            # Its rows are kin too — same card, same primitives, so the same
            # law — and the one claim only the live page can settle is that
            # every row really lights a DIFFERENT cell: the whole panel rests
            # on "he picks the window by its position", and four VS Code
            # windows have four nearly identical titles.
            # THE ⚙ SHEET OFFERS EXACTLY WHAT THIS LAYOUT CAN TAKE (owner
            # 2026-08-09, task 175). Both shapes: a THREE is the fullest the
            # sheet gets, a SOLO has neither a member to throw out nor an
            # arrangement to choose. Rule: `__settingsSheet` in _audit_js.py.
            for members, grid in ((3, "3-top"), (1, None)):
                page.evaluate(LAYOUT_SETTINGS_STAGE_JS,
                              {"name": "Claude Code - Vibe Coder - Visual "
                                       "Studio Code [Administrator]",
                               "grid": grid, "members": members,
                               "titles": ["Claude Code", "prompt.txt", "Notes"]})
                page.wait_for_selector("#layout-panel .lay-card",
                                       state="visible", timeout=4000)
                sheet = page.evaluate("(n) => __settingsSheet(n)", members)
                results[f"the ⚙ sheet offers exactly a {members}-window "
                        f"layout's acts @ {label}"] = not sheet
                if sheet:
                    print(f"  DETAIL settings sheet ({members}) @ {label}: {sheet}")
                page.evaluate(LAYOUT_LIST_CLOSE_JS)

            # WHAT ELSE DIES WITH THESE WINDOWS (owner 2026-08-09, task 171).
            # Which OPTION carries the warning is meaning, not pixels
            # (`__closeWarning` in _audit_js.py), and the expectation is the
            # page's own staged list, so it cannot drift from the card.
            page.evaluate(CLOSE_WARN_STAGE_JS)
            page.wait_for_selector("#layout-panel .lay-source", state="visible",
                                   timeout=4000)
            warn = page.evaluate("(d) => __closeWarning(d)",
                                 page.evaluate("() => layouts[0].dependents"))
            results[f"the ✕ chooser names the layouts a close would destroy "
                    f"@ {label}"] = not warn
            if warn:
                print(f"  DETAIL close warning @ {label}: {warn}")
            page.evaluate(LAYOUT_LIST_CLOSE_JS)

            page.evaluate(LAYOUT_LIST_STAGE_JS + "; openMemberPanel(2)")
            page.wait_for_selector("#layout-panel .lay-card", state="visible",
                                   timeout=4000)
            mem = page.evaluate(
                "() => { const c = document.querySelector('#layout-panel"
                " .lay-card'); return __kinRows(c).concat(__memberCells(c))"
                ".concat(__radiusAndKin(c)); }")
            results[f"the member chooser's rows are one line and each lights "
                    f"its own cell @ {label}"] = not mem
            if mem:
                print(f"  DETAIL member chooser @ {label}: {mem}")
            page.evaluate(LAYOUT_LIST_CLOSE_JS)

            # THE CREATION LIST IS GOVERNED BY THE SAME LAW (owner 2026-08-09,
            # tasks 163 + 168). Its rows became `.lay-item` rows this round, so
            # they fall under the kin rule the moment they are measured — and
            # they carry the one case no other panel has: an INDENTED child,
            # which is deliberately NOT in its parent's group. `__kinRows`
            # groups by indent for exactly that reason; without the grouping
            # this staging would be either illegal or unmeasured.
            page.evaluate(CREATION_LIST_STAGE_JS)
            page.wait_for_selector("#layout-panel .lay-card", state="visible",
                                   timeout=4000)
            # …AND ITS LIST IS NOT A SCROLLER INSIDE A FRAGMENTAINER (found
            # 2026-08-09 by photographing this panel at 915x412): the fourth of
            # six rows came out sliced through the middle, ten pixels above the
            # "Shape:" block in the same column, with rows five and six
            # nowhere. `__scrollInColumns` in _audit_js.py carries the finding.
            crea = page.evaluate(
                "() => { const c = document.querySelector('#layout-panel"
                " .lay-card'); return __kinRows(c).concat("
                "__scrollInColumns(c)).concat(__radiusAndKin(c)); }")
            results[f"the creation list's rows are one line, equal within "
                    f"their own indent, and reachable @ {label}"] = not crea
            if crea:
                print(f"  DETAIL creation list rows @ {label}: {crea}")
            page.evaluate(CREATION_CLOSE_JS)

            # D-pad labels: a set's POOL may hold reserve commands with longer
            # names than the shipped four ("Copy path", "Go to file"), and the
            # law forbids eliding them — they wrap instead (owner 2026-08-05).
            # The wrapped label must still stay INSIDE its 58 px button.
            page.evaluate(
                "categories.push({name:'Audit', icon:'grid', required:true,"
                " buttons:[{label:'Copy path', chord:'ctrl+shift+c'},"
                "          {label:'Go to file', chord:'ctrl+p'},"
                "          {label:'Paste plain', chord:'ctrl+shift+v'},"
                "          {label:'Find next', chord:'f3'}]});"
                "groups.left = allCats().length - 1; renderGroup('left');")
            results[f"D-pad labels inside their buttons @ {label}"] = page.evaluate(
                """() => {
                  const btns = document.querySelectorAll('#group-left .ctl');
                  let ok = btns.length > 0;
                  for (const b of btns) {
                    const l = b.querySelector('.lbl');
                    if (!l) continue;
                    const br = b.getBoundingClientRect();
                    const lr = l.getBoundingClientRect();
                    if (lr.top < br.top - 1 || lr.bottom > br.bottom + 1 ||
                        lr.left < br.left - 1 || lr.right > br.right + 1) ok = false;
                    if (l.scrollWidth > l.clientWidth + 1) ok = false;  // no cut
                  }
                  return ok;
                }""")
            page.evaluate("categories.pop(); groups.left = 0; refreshCategories();")

            # The Move handle must be visible and inside the panel card.
            page.evaluate(
                "layouts = [{name:'Audit', process:'x', orient:'portrait',"
                " icon:null, ratio:[600,1000], pos:0.5}]; openAspectPanel(0)")
            page.wait_for_selector(".asp-move", state="visible", timeout=4000)
            results[f"Move handle visible inside the card @ {label}"] = page.evaluate(
                """() => {
                  const m = document.querySelector('.asp-move').getBoundingClientRect();
                  const c = document.querySelector('.lay-card').getBoundingClientRect();
                  return m.width >= 40 && m.left >= c.left && m.right <= c.right &&
                         m.top >= c.top && m.bottom <= c.bottom;
                }""")
            # A SECOND TOUCH IS NOT A DOUBLE TAP (owner 2026-08-07: he shrank
            # a layout, pulled the Move handle down, "ali on je i dalje na
            # sredini"). The handle treated ANY contact within 350 ms of the
            # previous one as the double-tap that re-centres — including the
            # press that begins a drag right after a first touch. That press
            # then returned without capturing the pointer, so the drag was
            # dead AND the region had just been put back in the middle: his
            # exact words. A double tap is two SHORT taps; this drives the
            # real handlers and asserts the region actually moved.
            # A ROW'S BADGE IS A BADGE (owner's law, found 2026-08-07 by
            # OPENING this panel's own screenshot). `.lay-item-main img` sized
            # the app icon; the Desktop row draws an inline <svg>, which the
            # rule never named — so it had no size, took the whole flex line,
            # and squeezed "Desktop" into "Deskt/op" beside a monitor the
            # height of the card. Every geometric check stayed green: nothing
            # was clipped, it was merely unreadable. So the icon is measured.
            page.evaluate(
                "layouts = [{name:'Audit', process:'x', orient:'portrait',"
                " icon:null, ratio:null, pos:0.5}]; openLayoutPicker()")
            page.wait_for_selector("#layout-panel .lay-card", state="visible", timeout=4000)
            results[f"a layout row's icon stays a badge @ {label}"] = page.evaluate(
                """() => [...document.querySelectorAll('.lay-item-main img, .lay-item-main svg')]
                     .every((el) => {
                       const r = el.getBoundingClientRect();
                       return r.width <= 40 && r.height <= 40;
                     })""")
            page.evaluate("closeLayoutPanel()")
            page.evaluate(
                "layouts = [{name:'Audit', process:'x', orient:'portrait',"
                " icon:null, ratio:[600,1000], pos:0.5}]; openAspectPanel(0)")
            page.wait_for_selector(".asp-move", state="visible", timeout=4000)
            results[f"a press after a tap is not a re-centre @ {label}"] = page.evaluate(
                """() => {
                  const h = document.querySelector('.asp-move');
                  const r = document.querySelector('.asp-screen').getBoundingClientRect();
                  const put = (t) => h.dispatchEvent(new PointerEvent(t, {
                    pointerId: 7, bubbles: true, cancelable: true,
                    clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 }));
                  // A synthetic pointer id owns no real capture — stubbing
                  // keeps the DOM from throwing; nothing below depends on it.
                  h.setPointerCapture = () => {};
                  h.hasPointerCapture = () => false;
                  aspecting.pos = 0.9; updateAspectPreview();
                  put('pointerdown'); put('pointerup');   // one tap
                  put('pointerdown');                     // …then a real press
                  return aspecting.pos === 0.9;
                }""")
            page.evaluate("closeLayoutPanel()")

            # THE REGION FRAME IS BORN WHERE NOTHING OF OURS IS (independent
            # grader, 2026-08-07 — his picture read "Layou" where the corner
            # button says "Layout"). `#region-panel` draws at z-index 55, above
            # every control, so a frame, a 44 px handle or the hint bar sitting
            # on a control paints straight across its label — and the law's
            # subject is content the user must read. The default rect used to
            # be two percentages that knew nothing about the chrome; it is now
            # placed in the band the chrome leaves free, and this is the tooth
            # that keeps it there when the chrome next changes size.
            #
            # The BAR is measured with it, because the ladder fix that gave the
            # hint its width (bounded both sides instead of `left: 50%`) is
            # exactly the kind of change that could push it under the D-pad.
            page.evaluate("rgBox = null; openRegionPanel()")
            page.wait_for_selector("#region-panel .rg-box", state="visible",
                                   timeout=4000)
            results[f"the Region frame opens clear of every control @ {label}"] = (
                page.evaluate(
                    """() => {
                      const mine = [...document.querySelectorAll(
                        '.rg-box, .rg-h, .rg-bar')].map((e) => e.getBoundingClientRect());
                      const theirs = [...document.querySelectorAll(
                        '.corner, #layout-bar, .group')]
                        .map((e) => e.getBoundingClientRect())
                        .filter((r) => r.width > 0 && r.height > 0);
                      const hits = (a, b) => a.left < b.right && b.left < a.right &&
                                             a.top < b.bottom && b.top < a.bottom;
                      return mine.length > 0 && theirs.length > 0 &&
                             theirs.every((t) => mine.every((m) => !hits(m, t)));
                    }"""))
            page.evaluate("closeRegionPanel()")

            results[f"no page errors @ {label}"] = not errors
            ctx.close()
        browser.close()

    print("\n=== LAYOUT AUDIT ===")
    failed = 0
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    if failed:
        print(f"LAYOUT AUDIT FAILED — {failed} check(s).")
        return 1
    print("LAYOUT AUDIT PASSED — panels fit, nothing clipped, region math bounded.")
    return 0


def test_layout_audit():
    """pytest entry — skipped where the browser toolchain is absent."""
    import pytest
    pytest.importorskip("playwright.sync_api")
    pytest.importorskip("uvicorn")
    assert main() == 0

if __name__ == "__main__":
    sys.exit(main())
