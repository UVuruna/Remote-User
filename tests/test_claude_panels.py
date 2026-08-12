"""THE CLAUDE PANELS GATE — the three cards must not lie to him.

Owner ballot verdict 2026-08-11, tasks 190 / 191 / 208 / 219. Three reports,
one family of defect, and every one of them was a panel STATING SOMETHING IT
DID NOT KNOW:

  190 — the Model panel offered NINE options while the extension's own picker
        offers FIVE. The nine came out of CLI-transcript vocabulary an agent
        measured in its own session and verified against that same transcript;
        the authority nobody consulted was the menu HE looks at. A panel whose
        options do not exist is a list of taps that do nothing.
  191 — Thinking only RAISED a menu ("unazađena"): /effort takes a level, so
        the panel can finish the command itself.  # lang-ok: owner quote
  208 — the worst of the three, because it looked right. Thinking lit "Medium"
        while his PC ran on Max, and what was lit was this PHONE's memory of
        its own last tap wearing a live-state look. He believed the panel and
        reported the command as broken.

So the rules this gate holds are not cosmetic:

  1. THE FIVE ARE THE OFFICIAL FIVE, in HIS order (by strength, Default first),
     each carrying the literal PROVEN to commit with one Enter.
  2. THE STARS ARE DRAWN, never a font glyph — the ✥ move handle came out a
     blunt cross on his own phone (2026-08-05) and every mark this app draws
     has been an SVG path since.
  3. A CLAIM WE CANNOT MAKE IS "unknown", never a guess and never the other
     chip's value. `claude_state` is answered only by a new enough PC; the
     panels must be fully honest with NO answer at all, which is the state
     every check below starts from.
  4. A MEMORY MAY NOT WEAR A FACT'S CLOTHES (208, in one line).
  5. AN UNKNOWN MODE BUYS NO PRESSES. Shift+Tab steps a ring; guessing the
     start could land him in Accept edits, which edits his files without
     asking.
  6. SOMETHING CALLS IT. A pure module nobody runs is a feature that does not
     exist — the actions.json lesson of 2026-08-07, where a field shipped
     through four releases without ever reaching his own file.

The rules live in `client/claude-state.js`, kept PURE so this gate runs it
WHOLE in node (the grid-icons.js / view-anchor.js / voice.js precedent).

Run:  .venv\\Scripts\\python tests/test_claude_panels.py
Requires: node on PATH — a HARD requirement, fail-closed in setup/build.py.
Never skip it silently.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MODULE = PROJECT / "client" / "claude-state.js"
PANELS_JS = PROJECT / "client" / "claude-panels.js"
CONTROLS_JS = PROJECT / "client" / "controls.js"
CONNECTION_JS = PROJECT / "client" / "connection.js"
INDEX = PROJECT / "client" / "index.html"
LOAD_TEST = PROJECT / "client" / "load_test.js"
ACTIONS = PROJECT / "actions.json"

# ── HIS SHEET, held HERE rather than read from the module ───────────────────
# A catalogue that marks its own homework proves nothing. These five, in this
# order, with these stars, are the owner's verdict of 2026-08-11 written out;
# the literals are the picker aliases that commit with one Enter.
OFFICIAL_MODELS = [
    ("default", "Default (recommended)", 0),
    ("haiku", "Haiku", 1),
    ("sonnet", "Sonnet", 2),
    ("opus[1m]", "Opus (1M context)", 3),
    ("fable", "Fable", 4),
]
# /effort takes exactly these (task 191). "Extra high" is the word, `xhigh` is
# the argument — the two are deliberately different and both are checked.
OFFICIAL_EFFORTS = [
    ("low", "Low"), ("medium", "Medium"), ("high", "High"),
    ("xhigh", "Extra high"), ("max", "Max"),
]
# The Shift+Tab ring, in the order the key steps it.
MODE_RING = ["default", "acceptEdits", "plan"]

# Task 219: ONE group, five commands, DESCRIPTIVE labels because the official
# names "svima plivaju i ne ukazuju na to šta rade".  # lang-ok: owner quote
CLAUDE_TOOLS = {
    "review": ("Review", "/code-review"),
    "security": ("Security", "/security-review"),
    "simplify": ("Clean up", "/simplify"),
    "compact": ("Compact", "/compact"),
    "init": ("Init CLAUDE", "/init"),
}
CLAUDE_TOOLS_ACTIVE = ["review", "security", "simplify", "compact"]

# Characters that would draw a RANKING in someone else's font. None of them may
# appear anywhere in the client — the capability stars are paths.
#
# THE COLOUR EMOJI ⭐ IS DELIBERATELY NOT ON THIS LIST. It is the layout
# selector's parent mark (owner decision 2026-08-09, task 169), asked for BY
# NAME after the ✥ dingbat failed — a colour emoji from Android's own emoji
# font is exactly what that dingbat was not, and it is one mark rather than a
# scale of four. The rule this list holds is about a RANKING rendered by a
# monochrome text glyph, which is the thing that must be drawn.
STAR_GLYPHS = "★☆✭✪⚜"


# ═════════════════════════ running the real module ═════════════════════════
def node_run(body: str):
    """Evaluate an expression against the REAL client/claude-state.js."""
    node = shutil.which("node")
    if not node:
        raise AssertionError(
            "node is required for the Claude panels gate (it runs the REAL "
            "client/claude-state.js rules) — install Node.js. Never skip a "
            "gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_claude_gate_"))
    script = work / "run.js"
    script.write_text(
        f"const M = require({json.dumps(str(MODULE))});\n"
        "const {CLAUDE_MODELS, CLAUDE_EFFORTS, CLAUDE_MODES, CLAUDE_UNKNOWN,\n"
        "       claudeModePresses, claudeMode, claudeNowModel,\n"
        "       claudeSavedModel, claudeStarsSvg,\n"
        "       claudeEffortChips, claudeModelChips, claudeModeChips} = M;\n"
        f"console.log(JSON.stringify((() => {{ {body} }})()));\n",
        encoding="utf-8")
    try:
        out = subprocess.run([node, str(script)], capture_output=True,
                             text=True, timeout=60)
        if out.returncode != 0:
            raise AssertionError(f"node failed: {out.stderr.strip()}")
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def actions_data() -> dict:
    return json.loads(ACTIONS.read_text(encoding="utf-8"))


def app_set(name: str) -> dict:
    for s in actions_data().get("app_sets", []):
        if s.get("name") == name:
            return s
    raise AssertionError(f"actions.json has no app set named {name!r}")


# ══════════════ 1. THE OPTIONS ARE THE OFFICIAL ONES (task 190) ═════════════
def check_the_five_models_in_his_order() -> None:
    """PLANTED DEFECT: reorder the list, drop one, add `opusplan` back, or
    change a star count — every one of those is task 190 returning."""
    got = node_run("return CLAUDE_MODELS.map(m => [m.value, m.label, m.stars]);")
    want = [list(x) for x in OFFICIAL_MODELS]
    if got != want:
        raise AssertionError(
            "the Model panel is not the PC's own picker, by strength with "
            f"stars:\n  got  {got}\n  want {want}")


def check_every_model_value_is_a_proven_literal() -> None:
    """The ARGUMENT, separately from the row it sits on.

    PLANTED DEFECT: `opus[1m]` -> `opus1m` (or `opus-1m`). The row would still
    read correctly and every tap would type a command Claude Code refuses —
    exactly the shape of failure 174 shipped and 190 reported."""
    values = node_run("return CLAUDE_MODELS.map(m => m.value);")
    want = [v for v, _, _ in OFFICIAL_MODELS]
    if values != want:
        raise AssertionError(f"model arguments drifted: {values} != {want}")
    # And the command the panel actually builds is `/model <value>`.
    src = PANELS_JS.read_text(encoding="utf-8")
    if "`/model ${m.value}`" not in src:
        raise AssertionError(
            "claude-panels.js no longer sends `/model <value>` — the table can "
            "be perfect and the tap still type something else")


def check_the_five_effort_levels() -> None:
    """Task 191: Thinking CHOOSES. PLANTED DEFECT: drop `xhigh`, or spell the
    argument as its label ("Extra high") — the panel would look complete and
    type an argument /effort does not take."""
    got = node_run("return CLAUDE_EFFORTS.map(e => [e.value, e.label]);")
    want = [list(x) for x in OFFICIAL_EFFORTS]
    if got != want:
        raise AssertionError(f"the thinking levels drifted:\n  got  {got}\n"
                             f"  want {want}")
    src = PANELS_JS.read_text(encoding="utf-8")
    if "`/effort ${e.value}`" not in src:
        raise AssertionError(
            "claude-panels.js no longer sends `/effort <level>` — task 191 is "
            "the panel FINISHING the command, not raising a menu")


# ═══════════════ 2. THE STARS ARE DRAWN, NEVER TYPED ════════════════════════
def check_the_stars_are_svg_paths() -> None:
    """PLANTED DEFECT: `return "★".repeat(n)`. It renders on a desktop
    browser and gambles the whole ranking on the device's emoji font — the ✥
    lesson of 2026-08-05, on the one row that has to be read at a glance."""
    drawn = node_run("return [0,1,2,3,4].map(n => claudeStarsSvg(n));")
    if drawn[0] != "":
        raise AssertionError("Default carries no capability stars — it must "
                             f"draw nothing, drew {drawn[0]!r}")
    for n in (1, 2, 3, 4):
        svg = drawn[n]
        if not svg.startswith("<svg") or svg.count("<path") != n:
            raise AssertionError(
                f"{n} stars must be {n} drawn paths in one <svg>; got {svg!r}")
        if any(g in svg for g in STAR_GLYPHS):
            raise AssertionError(f"{n} stars fell back to a font glyph: {svg!r}")


def check_no_font_star_anywhere_in_the_client() -> None:
    """The same rule, across the product. PLANTED DEFECT: write a "★" into any
    client file — the drawing would be right and a stray glyph beside it would
    still be the thing his phone renders wrong."""
    offenders = []
    for path in sorted((PROJECT / "client").glob("*.*")):
        if path.suffix not in (".js", ".css", ".html"):
            continue
        text = path.read_text(encoding="utf-8")
        for glyph in STAR_GLYPHS:
            if glyph in text:
                offenders.append(f"{path.name}: {glyph!r}")
    if offenders:
        raise AssertionError(
            "a ranking star is drawn in this product, never typed "
            f"(client/icons.js house rule): {offenders}")


# ══════════ 3. NULLS ARE "unknown", NEVER A GUESS (task 208) ════════════════
def check_no_answer_says_unknown_everywhere() -> None:
    """The state an OLDER PC leaves the panels in, which is the state they must
    be honest in. PLANTED DEFECT: fall back to `saved` for the NOW chip — the
    panel then reports the saved default as the live conversation's state,
    which is 208 with the two facts swapped."""
    got = node_run(
        "return {model: claudeModelChips(null, {}),"
        " effort: claudeEffortChips(null, {}, ''),"
        " mode: claudeModeChips(null), unknown: CLAUDE_UNKNOWN};")
    unknown = got["unknown"]
    for panel, chips in (("model", got["model"]), ("effort", got["effort"]),
                         ("mode", got["mode"])):
        for chip in chips:
            if chip["text"] != unknown or chip["value"] is not None:
                raise AssertionError(
                    f"{panel} chip {chip['key']!r} invented a value with no "
                    f"answer from the PC: {chip}")


def check_saved_is_never_read_as_now() -> None:
    """The two facts are DIFFERENT facts, and 208 is what conflating them costs.
    PLANTED DEFECT: `claudeEffortChips` reading `saved.effort` into the `now`
    chip when the live answer is missing."""
    got = node_run(
        "return claudeEffortChips({effort: null}, {effort: 'medium'}, '');")
    by_key = {c["key"]: c for c in got}
    if by_key["saved"]["value"] != "medium":
        raise AssertionError("the SAVED chip must report the saved level")
    if by_key["now"]["value"] is not None:
        raise AssertionError(
            "the NOW chip claimed a value the PC never sent — this is exactly "
            f"the 208 report: {by_key['now']}")


def check_a_model_family_is_matched_not_guessed() -> None:
    """The PC answers with a FAMILY ("opus"); the row asks for an alias
    ("opus[1m]"). PLANTED DEFECT: compare `state.model` to `m.value` directly —
    nothing would ever be marked and the whole 208(a) fix silently disappears.
    Second defect: let Default match anything, and the panel claims a row the
    account, not the phone, decides."""
    got = node_run(
        "return [claudeNowModel({model:'opus'}), claudeNowModel({model:'fable'}),"
        " claudeNowModel({model:'haiku'}), claudeNowModel(null),"
        " claudeNowModel({model:'something-new'})];")
    if got[:3] != ["opus[1m]", "fable", "haiku"]:
        raise AssertionError(f"a live family no longer marks its row: {got}")
    if got[3] is not None or got[4] is not None:
        raise AssertionError(
            "an unknown or absent family must mark NOTHING — Default is not a "
            f"catch-all: {got}")


def check_the_saved_id_is_matched_by_family_too() -> None:
    """THE SAVED HALF OF THE SAME RULE (grader 2026-08-11).

    The live half above was matched by family from the day it shipped; the
    saved half was compared RAW — and the owner's own settings.json holds
    `claude-fable-5[1m]`, which is none of the five aliases this list offers.
    On his PC the "saved" mark could therefore never light a row and the chip
    printed the id back at him, on a card whose only job is to say which model
    is chosen.

    PLANTED DEFECT: have `claudeSavedModel` read `saved.model` (the raw id)
    instead of `saved.model_family` — the first branch then answers null for
    the very file he has.

    The second half is the honest limit, and it is deliberate: an older server
    sends no `model_family` at all, and a `default` alias names no family on
    purpose. Both must mark NOTHING and print what the PC actually said,
    exactly as an unknown live family does above."""
    got = node_run(
        "return {rows: ["
        "  claudeSavedModel({model:'claude-fable-5[1m]', model_family:'fable'}),"
        "  claudeSavedModel({model:'claude-opus-5[1m]', model_family:'opus'}),"
        "  claudeSavedModel({model:'claude-sonnet-4-5', model_family:'sonnet'}),"
        "  claudeSavedModel({model:'default'}),"
        "  claudeSavedModel({}), claudeSavedModel(null)],"
        " chip: claudeModelChips(null,"
        "   {model:'claude-fable-5[1m]', model_family:'fable'})[0],"
        " legacy: claudeModelChips(null, {model:'claude-fable-5[1m]'})[0]};")
    if got["rows"][:3] != ["fable", "opus[1m]", "sonnet"]:
        raise AssertionError(
            f"a saved family no longer marks its row: {got['rows']}")
    if any(r is not None for r in got["rows"][3:]):
        raise AssertionError(
            "an alias that names no family, and a server that sends none, must "
            f"mark NOTHING rather than guess a near row: {got['rows']}")
    if got["chip"]["text"] != "Fable":
        raise AssertionError(
            "the SAVED chip must SPELL the family the PC saved, not print the "
            f"raw id at him: {got['chip']}")
    if got["legacy"]["text"] != "claude-fable-5[1m]":
        raise AssertionError(
            "with no family from the PC the chip must print exactly what the "
            f"PC does hold — never a blank and never a guess: {got['legacy']}")


# ═════ 4. A MEMORY MAY NOT WEAR A FACT'S CLOTHES (task 208, in one line) ════
def check_last_sent_is_marked_as_a_memory() -> None:
    """PLANTED DEFECT: give the `sent` chip kind "fact". The card would then
    show the phone's own last tap in the same clothes as the PC's live state —
    which is the bug he reported, restored in one word."""
    chips = node_run("return claudeEffortChips({effort:'max'},"
                     " {effort:'medium'}, 'medium');")
    by_key = {c["key"]: c for c in chips}
    if by_key["sent"]["kind"] != "memory":
        raise AssertionError(
            "the LAST SENT chip must be a memory, not a fact: "
            f"{by_key['sent']}")
    if by_key["now"]["kind"] != "fact" or by_key["saved"]["kind"] != "fact":
        raise AssertionError("SAVED and NOW are read off the PC — both facts")
    # And the look must differ by more than a word. Colour alone cannot carry
    # it: three of the eight looks paint no colour on a control at all.
    # INSIDE THE RULE, not anywhere in the file. `border-style: dashed` also
    # dresses the quality panel's out-of-reach steps, so a file-wide search
    # stayed green when `.cl-memory` lost its own dashed edge (found by
    # planting, 2026-08-11 — a check that reads the wrong scope proves the
    # wrong thing).
    css = (PROJECT / "client" / "panels.css").read_text(encoding="utf-8")
    rule = re.search(r"\.cl-memory\s*\{([^}]*)\}", css)
    if not rule:
        raise AssertionError("panels.css has no `.cl-memory` rule at all")
    if "dashed" not in rule.group(1):
        raise AssertionError(
            "the memory chip is no longer distinguished BY SHAPE — a "
            "difference carried by colour alone vanishes in the plain looks: "
            f".cl-memory {{{rule.group(1)}}}")


def check_only_the_live_answer_lights_a_thinking_row() -> None:
    """His screenshot's exact defect. PLANTED DEFECT: mark the row matching
    `claudeLastEffort()` or `claudeSaved.effort` — "Medium" lights under a PC
    running Max, which is the report verbatim."""
    src = PANELS_JS.read_text(encoding="utf-8")
    start = src.index("function renderClaudeEffortPanel")
    body = src[start:src.index("// ── MODE", start)]
    if "claudeState && claudeState.effort" not in body:
        raise AssertionError("the Thinking rows no longer read the LIVE state")
    for banned in ("claudeLastEffort()", "claudeSaved.effort"):
        if banned in body.split("const list")[1]:
            raise AssertionError(
                f"a Thinking ROW is lit from {banned} — that is a memory or a "
                "saved default wearing a live-state look (task 208)")


# ══════════ 5. AN UNKNOWN MODE BUYS NO PRESSES (verdict item 4) ═════════════
def check_the_mode_ring_is_the_key_s_own_order() -> None:
    """PLANTED DEFECT: reorder the ring. Every press count is then wrong in a
    way nothing on screen reveals — he lands in Accept edits asking for Plan."""
    got = node_run("return CLAUDE_MODES.map(m => m.value);")
    if got != MODE_RING:
        raise AssertionError(f"the Shift+Tab ring drifted: {got} != {MODE_RING}")


def check_presses_walk_the_ring_forwards_only() -> None:
    """Shift+Tab only goes one way and WRAPS. PLANTED DEFECT: use an absolute
    difference (`Math.abs(to - at)`) — plan→default becomes 2 presses instead
    of 1 and lands him one mode short, every time, silently."""
    pairs = [(a, b) for a in MODE_RING for b in MODE_RING]
    got = node_run(
        f"const p = {json.dumps(pairs)};"
        "return p.map(([a,b]) => claudeModePresses(a,b));")
    want = [(MODE_RING.index(b) - MODE_RING.index(a)) % len(MODE_RING)
            for a, b in pairs]
    if got != want:
        raise AssertionError(
            "the press counts do not walk the ring forwards:\n"
            + "\n".join(f"  {a} -> {b}: got {g}, want {w}"
                        for (a, b), g, w in zip(pairs, got, want) if g != w))


def check_an_unknown_mode_yields_null() -> None:
    """PLANTED DEFECT: return 1 (or 0) when the current mode is unknown. The
    button would then claim to REACH a mode it only stepped toward — and a
    wrong guess can land on Accept edits, which edits his files without asking.
    The honest act is one step, said as one step."""
    got = node_run(
        "return [claudeModePresses(null,'plan'), claudeModePresses('','plan'),"
        " claudeModePresses('bogus','plan'), claudeModePresses('plan','bogus')];")
    if got != [None, None, None, None]:
        raise AssertionError(
            f"an unknown mode must buy NO computed presses: {got}")
    src = PANELS_JS.read_text(encoding="utf-8")
    if "presses === null" not in src or 'chord: "shift+tab"' not in src:
        raise AssertionError(
            "claude-panels.js no longer handles the unknown-mode case with a "
            "single honest step")


def check_the_mode_presses_ride_the_guarded_chord_path() -> None:
    """WHY THIS BUTTON COULD SHIP WITHOUT A NEW FOCUS CONTRACT: `chord` is in
    the server's TYPING_KINDS, so every press passes through
    `focus_guard.typist()` exactly like /usage and /compact beside it
    (constraint 11). PLANTED DEFECT: send the presses as `key_special` or any
    kind outside TYPING_KINDS — the focus fence would stop covering them and
    the mode could be typed into whatever window stole the foreground."""
    web = (PROJECT / "server" / "web.py").read_text(encoding="utf-8")
    block = web[web.index("TYPING_KINDS"):web.index("RETARGET_KINDS")]
    if '"chord"' not in block:
        raise AssertionError(
            "`chord` left the server's TYPING_KINDS — the Mode button's "
            "presses are no longer covered by the focus guard")


# ═══════════════ 6. SOMETHING CALLS IT (the 2026-08-07 lesson) ══════════════
def check_the_buttons_open_these_panels() -> None:
    """PLANTED DEFECT: drop the `panel` field from one of the three buttons in
    actions.json, or the `btn.panel` branch from controls.js. The module would
    be perfect and unreachable — the exact shape of the `agent` field that
    shipped through four releases without reaching his own file."""
    claude = app_set("Claude")
    by_id = {b.get("id"): b for b in claude["buttons"]}
    want = {"model": "claude-model", "effort": "claude-effort",
            "mode": "claude-mode"}
    for bid, panel in want.items():
        if bid not in by_id:
            raise AssertionError(f"the Claude set lost its {bid!r} button")
        if by_id[bid].get("panel") != panel:
            raise AssertionError(
                f"{bid!r} does not open {panel!r}: {by_id[bid]}")
        if "options" in by_id[bid]:
            raise AssertionError(
                f"{bid!r} still carries the generic `options` list — two "
                "chooser paths for one button is one of them going stale")
    # The BRANCH, not merely the words. Planting `btn.panel && false` left both
    # names in the file and this check green until 2026-08-11 — a grep for a
    # token proves the token was typed, never that it decides anything.
    controls = CONTROLS_JS.read_text(encoding="utf-8")
    if not re.search(r"\}\s*else if \(btn\.panel\)\s*\{", controls):
        raise AssertionError(
            "controls.js has no live `btn.panel` branch — every Claude panel "
            "button is a dead tap")
    if not re.search(r"^\s*el = makeClaudePanelButton\(btn\);", controls, re.M):
        raise AssertionError(
            "the `panel` branch no longer builds the card's button")
    if not re.search(r"^\s*keepFocus\(el, \(\) => openClaudePanel\(btn\)\);",
                     panels_src := PANELS_JS.read_text(encoding="utf-8"), re.M):
        raise AssertionError(
            "the button no longer opens the card on a tap")
    del panels_src
    panels = PANELS_JS.read_text(encoding="utf-8")
    for panel in want.values():
        if f'"{panel}"' not in panels:
            raise AssertionError(f"claude-panels.js renders nothing for {panel!r}")


def check_the_phone_asks_and_the_page_listens() -> None:
    """The `claude_state` contract, both directions. PLANTED DEFECT: delete the
    `claude_state` branch from connection.js — every chip would sit on
    "unknown" forever while the PC answered faithfully, and nothing would say
    so."""
    panels = PANELS_JS.read_text(encoding="utf-8")
    if 'type: "claude_state"' not in panels:
        raise AssertionError("nothing asks the PC for the live state")
    if "requestClaudeState()" not in panels:
        raise AssertionError("the panels never call the request")
    # LIVE CODE, not a mention. Commenting the call out left the name in the
    # file and this check green until 2026-08-11.
    conn = CONNECTION_JS.read_text(encoding="utf-8")
    if 'msg.type === "claude_state"' not in conn:
        raise AssertionError(
            "connection.js does not recognise the server's `claude_state`")
    if not re.search(r"^\s*onClaudeState\(msg\);\s*$", conn, re.M):
        raise AssertionError(
            "connection.js recognises `claude_state` and does nothing with it "
            "— every chip would sit on \"unknown\" while the PC answered")


def check_every_claude_command_asks_for_the_prompt() -> None:
    """TASK 200's OTHER HALF, and the reason it needed one.

    `server/claude_api.py` + `web.py` gained `paste_text {focus: "claude"}` —
    put the caret in Claude's own prompt before typing — and on the day it
    landed NOTHING on the phone sent the field. That is a feature that does not
    exist (the actions.json lesson of 2026-08-07, where `agent` shipped through
    four releases without reaching his file), and its own gate,
    `tests/test_claude_focus.py`, could not see it: it proves the SERVER wires
    the field, which was true and useless.

    PLANTED DEFECT (data): remove `"focus": "claude"` from a Claude command in
    actions.json — that command types wherever focus happens to be, which for
    the editor pane means into a source file.
    PLANTED DEFECT (code): drop the pass-through from controls.js — every
    button loses it at once, silently, and the shipped file still looks right.
    """
    for name in ("Claude", "Claude Tools"):
        for b in app_set(name)["buttons"]:
            if "text" not in b:
                continue
            if b.get("focus") != "claude":
                raise AssertionError(
                    f"{name} / {b.get('label')!r} types into whatever box has "
                    "focus — it must ask for the Claude prompt first (task 200)")
    controls = CONTROLS_JS.read_text(encoding="utf-8")
    if "btn.focus ? { focus: btn.focus }" not in controls:
        raise AssertionError(
            "controls.js drops the button's `focus` field — the server's own "
            "field becomes unreachable and nothing says so")
    panels = PANELS_JS.read_text(encoding="utf-8")
    if 'focus: "claude"' not in panels:
        raise AssertionError(
            "the Model/Thinking panels send their command without asking for "
            "the prompt — the one place a wrong box costs a whole command")


def check_the_page_loads_both_halves() -> None:
    """PLANTED DEFECT: drop a script tag. The page dies at the first tap with a
    ReferenceError nobody sees on a phone."""
    html = INDEX.read_text(encoding="utf-8")
    for name in ("claude-state.js", "claude-panels.js", "phone-panel.js"):
        if f"/static/{name}" not in html:
            raise AssertionError(f"index.html does not load {name}")
    if '<div id="claude-panel"' not in html or '<div id="phone-panel"' not in html:
        raise AssertionError("index.html is missing a panel's own element")
    load = LOAD_TEST.read_text(encoding="utf-8")
    for name in ("claude-state.js", "claude-panels.js", "phone-panel.js"):
        if f'"{name}"' not in load:
            raise AssertionError(
                f"client/load_test.js does not list {name} — its own header "
                "says the list must match index.html exactly, and the drift "
                "always hides the file being worked on")


def check_the_module_stays_pure() -> None:
    """PLANTED DEFECT: touch `document` or `window` in claude-state.js. The gate
    could then no longer run the rules at all, which is how a rule about
    revisions once shipped proven by a single call."""
    src = MODULE.read_text(encoding="utf-8")
    for banned in ("document.", "window.", "localStorage", "prefGet", "send("):
        if banned in src:
            raise AssertionError(
                f"claude-state.js touches {banned!r} — it must stay pure so "
                "this gate can run it whole")


# ═══════════════ 7. THE CLAUDE TOOLS GROUP (task 219) ═══════════════════════
def check_the_claude_tools_group() -> None:
    """PLANTED DEFECT: rename a label back to its official name ("Simplify"),
    drop a command, or forget `enter`. His whole reason for the group is that
    the official names "svima plivaju i ne ukazuju na to šta rade".
    # lang-ok: owner quote"""
    s = app_set("Claude Tools")
    if s.get("agent") != "claude" or s.get("process") != "code":
        raise AssertionError(
            "Claude Tools must ride beside the Claude set on the SAME "
            f"detection — the PC answers, nobody ticks: {s}")
    got = {b.get("id"): (b.get("label"), b.get("text")) for b in s["buttons"]}
    if got != CLAUDE_TOOLS:
        raise AssertionError(f"the group's commands drifted:\n  got  {got}\n"
                             f"  want {CLAUDE_TOOLS}")
    for b in s["buttons"]:
        if b.get("enter") is not True:
            raise AssertionError(f"{b.get('id')!r} must run, not just type it")
    if s.get("active") != CLAUDE_TOOLS_ACTIVE:
        raise AssertionError(
            f"the four that ride the D-pad drifted: {s.get('active')} != "
            f"{CLAUDE_TOOLS_ACTIVE} (Init waits in the pool — it is a "
            "once-per-project act)")


def check_compact_moved_and_did_not_multiply() -> None:
    """His correction to the ballot: Compact JOINS this group instead of the
    base Claude set — "on je izdvojen ... ustvari neka budu svi u 1 grupi".
    # lang-ok: owner quote
    PLANTED DEFECT: leave /compact in the Claude set too. Two buttons, one
    command, and the day one of them changes they disagree."""
    base = app_set("Claude")
    stragglers = [b for b in base["buttons"] if b.get("text") == "/compact"]
    if stragglers:
        raise AssertionError(
            "/compact is still in the base Claude set as well as in Claude "
            f"Tools: {stragglers}")


def check_the_wheel_cost_is_stated_honestly() -> None:
    """THE PICKER MUST NOT LIE (the cap is a LAW over the stored state, owner
    2026-08-06). Three sets share the `code` process, so the app-shortcut
    reserve is THREE — and the shipped file must not tick past the cap on a
    fresh install.

    THE CAP IS THE FILE'S OWN (fixed 2026-08-12, owner report "drop-out mode
    refuses more than 8, it must be 10"). This check hardcoded 8 and never
    read `wheel_mode`, while every load site in the product defaults to
    drop-out — `server/actions_api.py` twice, `controls_data.OWNER_TOP_KEYS`,
    `client/sets.js` `wheelCap()`. So the ONE place that disagreed with the
    product was the guard, and because a guard is what a shipped default has
    to satisfy, it is what kept the shipped defaults pre-capped at 8 and
    Claude Tools switched off. A gate that states a number the code does not
    hold is not protecting the owner from the code — it is protecting the
    code from the owner's own decision.

    PLANTED DEFECT: tick a fourth optional basic. Required 3 + four optional +
    a reserve of 3 is 11, and the very first connection would greet him by
    switching one of them off with a toast."""
    data = actions_data()
    # Same arithmetic as `server/gui/controls_editor.py` `_save` and
    # `client/sets.js` `wheelCap()`: absent means drop-out, and drop-out is 10.
    cap = 8 if data.get("wheel_mode") == "fixed" else 10
    required = sum(1 for c in data["categories"] if c.get("required"))
    optional_on = sum(1 for c in data["categories"]
                      if not c.get("required") and c.get("enabled") is not False)
    per_process: dict[str, int] = {}
    for s in data["app_sets"]:
        if s.get("enabled") is False:
            continue
        key = str(s.get("process", "")).lower()
        per_process[key] = per_process.get(key, 0) + 1
    reserve = max(per_process.values()) if per_process else 0
    total = required + optional_on + reserve
    if total > cap:
        raise AssertionError(
            f"the shipped file ticks {total} of {cap} wheel slots "
            f"({required} required + {optional_on} optional + {reserve} held "
            "for app shortcuts) — a fresh install would drop one on the first "
            "connection")


# ═══════════════ 8. THE PHONE CARD (tasks 161 / 218a) ═══════════════════════
def check_the_phone_card_gathered_the_switches() -> None:
    """PLANTED DEFECT: leave the D-pad shape rows in the sets picker, or the
    bar chips on the layout list. A switch with two doors is two states to keep
    in step, and his report was about the WRONG door, not a missing one."""
    settings = None
    for c in actions_data()["categories"]:
        if c.get("name") == "Settings":
            settings = c
    if settings is None:
        raise AssertionError("actions.json lost its Settings set")
    ids = [b.get("action") for b in settings["buttons"]]
    if "phone" not in ids:
        raise AssertionError("the Settings pool has no Phone button")
    if "phone" not in (settings.get("active") or []):
        raise AssertionError(
            "the Phone button does not ride the D-pad — a pool entry nobody "
            "sees is not a delivered card")
    # THE DOOR IS TWO HALVES, and both are checked (2026-08-12). controls.js
    # still owns the BUILT-IN — the button's label, icon and kind — but the
    # kind→opener wiring moved into panels.js's `PANEL_KINDS` when Settings →
    # Voice needed a seventh entry and controls.js stood two lines under THE
    # STRUCTURE LAW's ceiling. panels.js is the module that owns the overlay
    # cards, so that is where it belongs; what must not change is that a
    # `phone` built-in really reaches `openPhonePanel`.
    controls = CONTROLS_JS.read_text(encoding="utf-8")
    if "phone:" not in controls or 'kind: "phone"' not in controls:
        raise AssertionError("controls.js has no built-in for the Phone card")
    panels = (PROJECT / "client" / "panels.js").read_text(encoding="utf-8")
    if "openPhonePanel()" not in panels or "PANEL_KINDS" not in panels:
        raise AssertionError(
            "nothing wires the `phone` built-in to openPhonePanel — the "
            "button would be drawn and do nothing")
    phone = (PROJECT / "client" / "phone-panel.js").read_text(encoding="utf-8")
    for needed in ("layBarPos()", "hideMode()", "padShapeRow("):
        if needed not in phone:
            raise AssertionError(f"the Phone card does not carry {needed}")
    old_home = (PROJECT / "client" / "panels.js").read_text(encoding="utf-8")
    if "shape.appendChild(padShapeRow(" in old_home:
        raise AssertionError(
            "the D-pad shape rows are STILL in the sets picker — moved means "
            "moved (task 218a)")
    layouts = (PROJECT / "client" / "layouts.js").read_text(encoding="utf-8")
    if "LAY_BAR_POSITIONS.forEach" in layouts:
        raise AssertionError(
            "the layout bar's Top/Bottom chips are still on the layout list — "
            "task 160's own comment promised they would move when 161 landed")


def check_every_overlay_panel_is_registered_in_the_stylesheet() -> None:
    """A panel outside panels.css's selector lists is INVISIBLE, not ugly.

    THIS HAS NOW HAPPENED THREE TIMES — `#set-editor-panel`, then
    `#notify-voice-panel`, then `#appearance-panel` on 2026-08-12, which shipped
    as an element sitting in normal document flow at the bottom of <body> with
    no `position: fixed`, no scrim and no centring: the audit's screenshot of it
    was BARE WORKING SCREEN. The container is declared in index.html and the
    opener works perfectly; only the stylesheet never heard of it, and a
    hand-maintained list of ids in a CSS file has no way to notice that.
    Three times is a mechanism, not bad luck, so the list is checked instead of
    trusted: every overlay container index.html declares must appear in BOTH
    the positioning list and the `[hidden]` list.
    """
    html = (PROJECT / "client" / "index.html").read_text(encoding="utf-8")
    # EVERY client stylesheet, not just panels.css. A panel may legitimately be
    # positioned by the sheet that owns its feature — `#layout-panel` lives in
    # layouts.css and `#region-panel` in style.css — and a check that knew only
    # one file would demand they move, which is a rule about filing rather than
    # about the defect. What matters is that SOME sheet positions it and SOME
    # sheet hides it; where is the feature owner's business.
    css = "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted((PROJECT / "client").glob("*.css")))
    ids = re.findall(r'<div\s+id="([a-z0-9-]*panel)"[^>]*\bhidden\b', html)
    if len(ids) < 5:
        raise AssertionError(
            f"only {len(ids)} overlay panels found in index.html — the pattern "
            "this check reads has changed and the check has gone blind")
    for pid in ids:
        listed = f"#{pid}," in css or f"#{pid} {{" in css
        if not listed:
            raise AssertionError(
                f"#{pid} is declared in index.html but never positioned in "
                "panels.css — it would render in document flow, invisible")
        if f"#{pid}[hidden]" not in css:
            raise AssertionError(
                f"#{pid} has no [hidden] rule in panels.css — it would be "
                "drawn even while closed")


CHECKS = [
    ("every overlay panel is registered in the stylesheet",
     check_every_overlay_panel_is_registered_in_the_stylesheet),
    ("the Model panel is the PC's own five, by strength, with stars",
     check_the_five_models_in_his_order),
    ("every model argument is a literal proven to commit",
     check_every_model_value_is_a_proven_literal),
    ("Thinking chooses a level, and the five are the real ones",
     check_the_five_effort_levels),
    ("the capability stars are drawn paths, never a font glyph",
     check_the_stars_are_svg_paths),
    ("no ranking star is typed anywhere in the client",
     check_no_font_star_anywhere_in_the_client),
    ("with no answer from the PC, every chip says unknown",
     check_no_answer_says_unknown_everywhere),
    ("the saved default is never reported as the live state",
     check_saved_is_never_read_as_now),
    ("a live model family marks its row, and nothing else does",
     check_a_model_family_is_matched_not_guessed),
    ("a saved model id marks its row by FAMILY, on his own settings file",
     check_the_saved_id_is_matched_by_family_too),
    ("this phone's last tap is a memory, and looks like one",
     check_last_sent_is_marked_as_a_memory),
    ("only the live answer lights a Thinking row",
     check_only_the_live_answer_lights_a_thinking_row),
    ("the mode ring is the order Shift+Tab really steps",
     check_the_mode_ring_is_the_key_s_own_order),
    ("the press count walks the ring forwards and wraps",
     check_presses_walk_the_ring_forwards_only),
    ("an unknown mode buys no computed presses",
     check_an_unknown_mode_yields_null),
    ("the mode presses ride the focus-guarded chord path",
     check_the_mode_presses_ride_the_guarded_chord_path),
    ("the three buttons really open these three panels",
     check_the_buttons_open_these_panels),
    ("the phone asks for claude_state and the page listens",
     check_the_phone_asks_and_the_page_listens),
    ("every Claude command asks for the prompt before it types",
     check_every_claude_command_asks_for_the_prompt),
    ("the page loads both halves and both new panels",
     check_the_page_loads_both_halves),
    ("the rules module stays pure, so this gate runs it whole",
     check_the_module_stays_pure),
    ("the Claude Tools group is his five, named for what they do",
     check_the_claude_tools_group),
    ("Compact moved into the group and did not multiply",
     check_compact_moved_and_did_not_multiply),
    ("the shipped wheel does not tick past its own mode's cap",
     check_the_wheel_cost_is_stated_honestly),
    ("the Phone card gathered the switches, and their old homes let go",
     check_the_phone_card_gathered_the_switches),
]


def main() -> int:
    print("\n=== CLAUDE PANELS GATE ===")
    if shutil.which("node") is None:
        print("CLAUDE PANELS GATE FAILED — node is required (it runs the REAL "
              "client/claude-state.js rules) and is not on PATH. Never skip a "
              "gate silently.")
        return 1
    failed = 0
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nCLAUDE PANELS GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nCLAUDE PANELS GATE PASSED — the panels offer what the PC really "
          "has, and claim only what it really told them.")
    return 0


def test_claude_panels():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
