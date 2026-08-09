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
from _audit_js import CONTRAST_JS  # noqa: E402

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

# The panels SHOT in a non-default look. Shooting all eleven in all eight
# would be eighty-eight pictures nobody will open, and a picture nobody opened is not
# proof (rules/GUI.md). These three are the ones that carry colour: the sets
# list with its live badge, the quality panel's segmented rows, and the
# dictation card's status column.
COLOUR_SHOTS = {"Sets picker", "Quality panel", "Dictation card"}

# The panels SHOT IN LANDSCAPE (2026-08-07). Every phone panel is MEASURED in
# both orientations and always was; these two are also photographed there,
# because they are the ones whose content is orientation-dependent: the
# creation panel draws the grid catalogue on a LANDSCAPE outer box, and the
# arrangement row draws the four landscape three-window variants that no
# picture had ever shown. The controls and the wheel are shot in landscape in
# every look, separately, below.
# The Region grab joined them on 2026-08-07: its bar is the panel whose
# layout depends most on the width it is given, and landscape is where it
# gets three times as much of it.
# The ✕ chooser joined on 2026-08-08: it is two big side-by-side chips, which
# is exactly the shape landscape squeezes — 46% of a wide card each, with a
# consequence line that must still wrap rather than clip.
LANDSCAPE_SHOTS = {"Creation panel + Name field", "Grid arrangement choice",
                   "Sets picker", "Quality panel", "Dictation card",
                   "Layout list with rename", "Region grab",
                   "Layout close chooser"}


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
    """Pure-math check: the region never leaves its box, at any pos/aspect."""
    from grids import _fit_rect   # the geometry moved out of window_manager (2026-08-07)
    box = (100, 50, 1000, 600)
    for aspect in (0.4, 1.0, 16 / 9, 3.2):
        for pos in (0.0, 0.25, 0.5, 0.75, 1.0):
            x, y, w, h = _fit_rect(box, aspect, pos)
            if not (box[0] <= x and box[1] <= y and
                    x + w <= box[0] + box[2] and y + h <= box[1] + box[3]):
                return False
            if w <= 0 or h <= 0:
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

# ONE FOLDER, ONE SUBJECT (owner 2026-08-08, his second word on this): a topic
# folder per ROUND was still a dump — "necu da folderi budu ovako siroki, da
# otvorim folder koji ima 161 sliku; hocu da ih grupises u sub-foldere". So the
# round's folder now holds SUBJECT folders, and a subject is what the picture
# is OF, read from its own name. Anything unrecognised lands in `other`, which
# is a signal rather than a hiding place: an `other` that grows means a new
# screen exists and nobody named it.
SHOT_SUBJECTS = (
    ("Controls_and_wheel", "controls-and-wheel"),
    ("Controls", "controls"),
    ("ControlsEditor", "desktop-controls-editor"),
    ("Sets_picker", "sets-picker"),
    ("Quality_panel", "quality-panel"),
    ("Dictation_card", "dictation-card"),
    ("Region_grab", "region-grab"),
    ("Command_chooser", "command-chooser"),
    ("Notices_card", "notices-card"),
    ("Pad_cross_upright", "controls"),
    ("Layout_close_chooser", "layouts"),
    ("Layout_list", "layouts"),
    ("Rename_card", "layouts"),
    ("Aspect_panel", "layouts"),
    ("Creation_panel", "layouts"),
    ("Grid_arrangement", "layouts"),
    ("MainWindow", "desktop-windows"),
    ("SettingsWindow", "desktop-windows"),
    ("TrafficWindow", "desktop-traffic"),
    ("WheelOrderDialog", "desktop-windows"),
)


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
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
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
        """(sel) => {
          const card = document.querySelector(sel);
          const r = card.getBoundingClientRect();
          const inView = r.left >= 0 && r.top >= 0 &&
                         r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1;
          const noPageScroll =
            document.scrollingElement.scrollWidth <= innerWidth + 1;
          let noClip = card.scrollWidth <= card.clientWidth + 1;
          for (const el of card.querySelectorAll('button, .q-row, .sets-row, input')) {
            if (el.scrollWidth > el.clientWidth + 2) noClip = false;
          }
          // BUG A of THE SPACE & LEGIBILITY LAW, measured (2026-08-07): "a
          // visible scrollbar with unused space in the same window is a bug,
          // not a style choice". Not "the card never scrolls" — rung 4 is
          // legal once the screen is genuinely full — but "it never scrolls
          // while there is width standing idle beside it". That is exactly
          // what landscape did to seven of these ten panels: 420 px of card
          // in a 915 px screen, scrolling by up to 256 px.
          const hidden = card.scrollHeight - card.clientHeight;
          const freeW = innerWidth - r.width;
          const noScrollWithSlack = !(hidden > 1 && freeW > 24);
          return { inView, noPageScroll, noClip, noScrollWithSlack,
                   hiddenPx: hidden, freeWidthPx: Math.round(freeW),
                   contrast: __contrast(card),
                   // …and the cut this file could not see until 2026-08-07:
                   // a string JavaScript shortened before the DOM existed.
                   truncated: __truncated(card) };
        }""",
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


# Every overlay panel the phone shows, each opened in its FULLEST real
# state. Hoisted out of `main()` in build round R3 so the same list can be
# swept once per LOOK (three themes x two fills) instead of once per run.
PANELS = (
    # FULLEST state (owner 2026-08-05): the panel states the PC's
    # own settings and strikes out the fps steps that PC puts out
    # of reach. A base must therefore be set before opening —
    # without it the header is the short "Waiting for the PC's own
    # settings…" and the audit would measure the empty case. 4K +
    # a 10 fps PC is the longest header AND the most struck-out
    # steps this panel can show.
    ("Quality panel",
     "setStreamBase({fps:10, width:3840, height:2160,"
     " bitrate:'6M', bitrate_mid:'2400k', bitrate_low:'600k'});"
     "openQualityPanel()",
     "closeQualityPanel()", "#quality-panel .sets-card"),
    # FULLEST state (owner 2026-08-06): every app set listed AND
    # two of them wearing the live badge, which is the widest a
    # row in this card can get — checkbox + icon + the longest set
    # name + "ON THE WHEEL NOW". The badge exists because he asked
    # to SEE which app set is actually riding, so it is exactly
    # the thing that must not be cut off.
    ("Sets picker",
     "appSets = APP_SETS;"
     "layouts = [{name:'Claude', process:'code.exe',"
     " title:'Ispravka UI dizajna meni…', orient:'portrait',"
     " icon:null, app_sets:['VSCode','Claude'], ratio:null, pos:0.5}];"
     "layoutActive = 0; openSetsPanel()",
     "layoutActive = null; layouts = []; closeSetsPanel()",
     "#sets-panel .sets-card"),
    ("Dictation card",
     "window.Android = {"
     " voiceLangs: () => JSON.stringify(["
     "  {tag:'sr-RS', name:'Srpski (Srbija)', status:'download'},"
     "  {tag:'en-US', name:'English (United States)', status:'ready'},"
     "  {tag:'de-DE', name:'Deutsch (Deutschland)', status:'online'},"
     "  {tag:'pt-BR', name:'Português (Brasil)', status:'download', extra:true},"
     "  {tag:'ja-JP', name:'日本語 (日本)', status:'online', extra:true}]),"
     " voiceMuteBeeps: () => true, voiceSetMuteBeeps: () => {},"
     " voiceChosen: () => 'sr-RS', voiceSetLang: () => {},"
     " voiceState: () => '' };"
     "renderDictationCard()",
     "closeDictationPanel()", "#dictation-panel .sets-card"),
    # The Region grab (owner 2026-08-05). Its bar is the part that
    # can starve: hint + Send + ✕ above the keyboard inset, on a
    # 412 px phone.
    #
    # OPENED AS THE USER MEETS IT — `rgBox = null` — since 2026-08-07.
    # It used to be staged into the top-left corner "where a bar
    # overlap would show first", which was wrong twice: the bar is
    # pinned bottom-centre and never moves with the frame, so the
    # staging proved nothing about it, and the picture every grader
    # was handed showed a frame lying across the Layout button
    # (label read "Layou") in a position the product never opens in.
    # A staged state nobody can reach is not evidence; the frame's
    # real birthplace is now measured by its own check below.
    ("Region grab",
     "rgBox = null; openRegionPanel()",
     "closeRegionPanel()", "#region-panel .rg-bar"),
    # The command chooser (owner idea 2026-08-05): the longest
    # real case is the Claude Thinking button's six levels.
    ("Command chooser",
     "openChoicePanel({label:'Thinking', text:'/effort',"
     " options:['low','medium','high','xhigh','max','auto']})",
     "closeChoicePanel()", "#choice-panel .sets-card"),
    ("Aspect panel + Move handle",
     "layouts = [{name:'Audit', process:'x', orient:'portrait',"
     " icon:null, ratio:[600,1000], pos:0.5}]; openAspectPanel(0)",
     "closeLayoutPanel()", "#layout-panel .lay-card"),
    # THE NOTICES CARD — and the reason it is here is the finding, not the
    # card. The owner photographed a stark WHITE "Not now" pill on it from his
    # tablet (2026-08-08) and asked whether such things are being caught. They
    # were not: this card was written on 2026-08-07 and registered in NO sweep,
    # so it had never been measured, never been photographed and never been
    # asked about its contrast in any of the eight looks. A panel outside the
    # registry is a panel with no law over it.
    ("Notices card",
     "renderNoticeCard({battery: false, notifications: false})",
     "closeNoticeCard()", "#notice-panel .sets-card"),
    # The ✕ chooser (owner 2026-08-08, task 116). Staged at its
    # WORST: a 4-cell grid, so both chips carry a count, under a
    # layout name as long as one really gets. The second line is
    # the whole point of the card — it is the difference between
    # "the windows stay" and "the windows close" — so this shot
    # exists to prove that line is never the thing that gets cut.
    ("Layout close chooser",
     "layouts = [{name:'Claude Code - Remote User - Visual Studio "
     "Code [Administrator]', process:'code.exe', orient:'portrait',"
     " icon:null, members:4, ratio:null, pos:0.5}];"
     "layoutActive = 0; openCloseChooser(0)",
     "layoutActive = null; layouts = []; closeLayoutPanel()",
     "#layout-panel .lay-card"),
    # The layout list carries a rename button per row (owner
    # 2026-08-05) — a long window title must not push the row's
    # buttons off the card.
    ("Layout list with rename",
     "layouts = [{name:'Claude Code - Remote User - Visual Studio "
     "Code [Administrator]', process:'x', orient:'portrait',"
     " icon:null, ratio:[600,1000], pos:0.5}]; openLayoutPicker()",
     "closeLayoutPanel()", "#layout-panel .lay-card"),
    # The rename card also carries the per-layout app-shortcut
    # ticks (owner 2026-08-06) — the long title AND four chips.
    ("Rename card",
     "appSets = APP_SETS;"
     "layouts = [{name:'Claude Code - Remote User - Visual Studio "
     "Code [Administrator]', process:'code.exe', orient:'portrait',"
     " icon:null, app_sets:['VSCode','Claude'], ratio:null, pos:0.5}];"
     "openRenamePanel(0)",
     "closeLayoutPanel()", "#layout-panel .lay-card"),
    # Creation panel: the Name field is prefilled with the chosen
    # window's (long) title and must fit the card.
    # The grid catalogue he drew (owner 2026-08-07) — the THREE
    # state, where four arrangement SKETCHES sit under the count
    # chips. Its own case because it is the tallest the creation
    # panel ever gets, and because a drawing nobody looked at is
    # not a proof.
    ("Grid arrangement choice",
     "creating = newCreation('list');"
     "creating.slots = [{hwnd:1, title:'Chrome', process:'chrome.exe',"
     " icon:null, tab:null, x:0.5, y:0.5},"
     " {hwnd:2, title:'Explorer', process:'explorer.exe',"
     " icon:null, tab:null, x:0.5, y:0.5},"
     " {hwnd:3, title:'Claude Code - Remote User - Visual Studio"
     " Code [Administrator]', process:'code.exe', icon:null,"
     " tab:null, x:0.5, y:0.5}];"
     "creating.mode = 'grid'; creating.grid = '3-left';"
     "renderCreationPanel()",
     "cancelCreation(true)", "#layout-panel .lay-card"),
    ("Creation panel + Name field",
     "appSets = APP_SETS;"
     "creating = newCreation('tap');"
     "creating.slots = [{hwnd:1, title:'Claude Code - Remote User"
     " - Visual Studio Code [Administrator]', process:'code.exe',"
     " icon:null, tab:null, x:0.5, y:0.5}];"
     "renderCreationPanel()",
     "creating = null; closeLayoutPanel()",
     "#layout-panel .lay-card"),
)


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

    results = {"region math: _fit_rect stays inside its box for every pos":
               _fit_rect_audit(),
               "grid math: every shape tiles its region exactly": _grid_audit()}
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
                            "Mobile Safari/537.36 RemoteUserApp"),
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
            page.evaluate("() => {" + CONTRAST_JS + "}")
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
            page.evaluate("setPadCross(true)")
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
            page.evaluate("setPadCross(false)")
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
    print()
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
