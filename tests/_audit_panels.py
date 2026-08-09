"""WHICH phone screen the audit opens, and in WHAT state.

Split out of tests/test_layout_audit.py on 2026-08-09 (THE STRUCTURE LAW): the
listen control on the dictation card (task 127) pushed that file past 1,000
lines, and the boundary was already written in its own docstring — it "decides
WHICH screens are opened and what is asserted about them", while
tests/_audit_js.py owns HOW a truth about pixels is measured.

This file is the first half of that sentence and nothing else: a catalogue that
grows by one entry every time the product grows a panel. Each entry is
(name, open_js, close_js, card_selector), and each stages its panel in the
FULLEST, most crowded state it can really reach — a panel measured in its empty
state is a panel nobody measured.

It also holds, since 2026-08-09, the three tables that say WHICH PICTURE each
of those panels gets and where it lands — `COLOUR_SHOTS`, `LANDSCAPE_SHOTS`
and `SHOT_SUBJECTS`. They are the same responsibility read one step further
on: a row of the catalogue and the pictures that row is worth. They moved
here when the creation-list entry above took `tests/test_layout_audit.py` to
998 of its 1,000 allowed lines (THE STRUCTURE LAW) — two lines of headroom is
not a margin, and the boundary this split follows was already written in both
files' docstrings.

Nothing here imports anything: every value is a plain string or a plain table
of strings the audit hands to the live page or reads to name a file.
"""

# THE DICTATION CARD, STAGED IN EVERY STATE A ROW CAN BE IN (owner 2026-08-09,
# task 127 — the listen control). Its own constant because two things use it:
# the panel sweep below, and the audit's own dictation check, which asserts
# that the three row states are all really on screen.
#
# THE HONEST-LIMIT ROWS ARE THE POINT. A language he may dictate in can have
# no text-to-speech voice on this device, and a language with a voice can have
# no sample sentence in our table — this project's bugs keep arriving in the
# state nobody staged, so both are ON the card the audit photographs and
# measures, beside the two rows that do offer a preview:
#
#   sr-RS  voice + sample            -> the listen button (and the chosen row)
#   en-US  voice + sample            -> the listen button
#   de-DE  no voice for German       -> "no preview voice on this device"
#   is-IS  a voice, no sample yet    -> "no sample sentence for this language"
#
# Icelandic carries the third state ONLY because client/panels.js has no
# Icelandic sample. The moment one is written, this row goes green and the
# state stops being staged — swap in another language the table does not
# cover; the check below fails loudly rather than silently losing the case.
DICT_STAGE_JS = (
    "window.Android = {"
    " voiceLangs: () => JSON.stringify(["
    "  {tag:'sr-RS', name:'Srpski (Srbija)', status:'download'},"
    "  {tag:'en-US', name:'English (United States)', status:'ready'},"
    "  {tag:'de-DE', name:'Deutsch (Deutschland)', status:'online'},"
    "  {tag:'is-IS', name:'Íslenska (Ísland)', status:'online'},"
    "  {tag:'pt-BR', name:'Português (Brasil)', status:'download', extra:true},"
    "  {tag:'ja-JP', name:'日本語 (日本)', status:'online', extra:true}]),"
    # The same source the PC's own voice list comes from (`tts_info`), so the
    # card is measured against a REAL shape: Android reports `{name, label,
    # locale}` per voice and `name` is what `speakAs` takes back.
    " ttsVoices: () => JSON.stringify(["
    "  {name:'sr-rs-x-sfg#female_1', label:'Serbian female', locale:'sr-RS'},"
    "  {name:'en-us-x-tpf#male_1', label:'English male', locale:'en-US'},"
    "  {name:'is-is-x-isf#female_1', label:'Icelandic female', locale:'is-IS'}]),"
    " speakAs: () => {},"
    " voiceMuteBeeps: () => true, voiceSetMuteBeeps: () => {},"
    " voiceChosen: () => 'sr-RS', voiceSetLang: () => {},"
    " voiceState: () => '' };"
    "renderDictationCard()"
)

# THE LAYOUT LIST, STAGED WITH THREE LAYOUTS (owner 2026-08-09, tasks 162+163).
# Its own constant because three things use it: the panel sweep below, the
# mid-drag staging under it, and the audit's own kin-row check.
#
# ONE ROW WAS WHAT LET BOTH BUGS SHIP. This entry used to stage a single
# layout, and a list of one has neither of the two things this panel is now
# judged on: nothing to compare a row's HEIGHT against (he photographed a row
# wrapped to four lines beside a two-line sibling — task 163) and nothing to
# drag a row ONTO (the whole gesture of task 162). So the panel was measured
# for years in the one state where both features are invisible.
#
# The three rows are the three real shapes a list holds: a 63-character VS Code
# window title (the longest a title really gets, and the one he screenshotted),
# an ordinary short name, and a layout that is already FULL — four windows, so
# it is the row that greys out as a refused drop target while a drag is in
# flight. `ratio` differs across them on purpose: the trailing chip's label is
# "Screen" on one and "3:5" on another, and those chips are a kin group too.
#
# AND THEY ARE THREE DIFFERENT SHAPES since 2026-08-09 (task 164): a two, a
# solo and a four, so the row's new drawing is a different picture on every
# row instead of the same one three times — a staging that cannot tell the
# feature from a constant proves nothing about it. `member_titles` rides along
# because the member chooser (task 165) is staged from this same list, and one
# of its four is the long VS Code title, which is what makes its rows carry
# task 163's elision too. The FIRST row is `parent: true` — the ⭐ (owner
# 2026-08-09, task 169) lands on the hardest row there is: the long name, the
# elision and all three trailing buttons at once.
#
# AND EVERY ROW CARRIES ITS OWN APP ICON since 2026-08-09 (task 172). It staged
# `icon: null` on all three until then, which makes `layRow` fall back to the
# Desktop row's monitor drawing — so the picture showed FOUR IDENTICAL leading
# badges, and the independent grader read the row's leading glyph as a constant
# that could be deleted to make room for the name. It is not: the server sends
# a real per-app icon per layout (`layout_registry` -> `wm.icon_data_uri`), so
# in production those badges are VS Code, Explorer and Chrome, and they are the
# fastest answer to "which app is this layout" on a row whose name is CUT. A
# fixture that renders a variable as a constant does not merely fail to test
# the feature — it argues, in a picture, for removing it.
#
# Data URIs rather than the real extracted PNGs: the icon comes off an EXE on
# the owner's machine and this audit runs anywhere. What has to be true of the
# stand-ins is what has to be true of the real ones — 20 px, one per row, and
# visibly different from each other and from the Desktop monitor.
_ICON_VSCODE = ("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5v"
                "cmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHJlY3Qgd2lkdGg9Ij"
                "I0IiBoZWlnaHQ9IjI0IiByeD0iNSIgZmlsbD0iIzIzN2NjZCIvPjxwYXRoIGQ9"
                "Ik0xNyA1djE0bC02LTQuNUw3IDE4VjZsNCAzLjV6IiBmaWxsPSIjZmZmIi8+PC"
                "9zdmc+")
_ICON_EXPLORER = ("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My"
                  "5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHJlY3Qgd2lkdG"
                  "g9IjI0IiBoZWlnaHQ9IjI0IiByeD0iNSIgZmlsbD0iI2ZmYzEwNyIvPjxwYX"
                  "RoIGQ9Ik00IDhoNmwyIDJoOHY4SDR6IiBmaWxsPSIjNmQ0YzAwIi8+PC9zdm"
                  "c+")
_ICON_CHROME = ("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5v"
                "cmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PGNpcmNsZSBjeD0iMT"
                "IiIGN5PSIxMiIgcj0iMTEiIGZpbGw9IiMzNGE4NTMiLz48Y2lyY2xlIGN4PSIx"
                "MiIgY3k9IjEyIiByPSI1IiBmaWxsPSIjZmZmIi8+PC9zdmc+")

# THE STAGED TITLE OUTGREW THE ROW, SO THE TITLE GREW (task 172, 2026-08-09).
# The 62-character title below used to elide at every viewport, which is what
# `__kinRows` and `__layoutStars` both lean on — each ends by DEMANDING that a
# >40-character name really overflowed, because an elision rule nothing
# exercises is a rule nobody is checking. Giving the layout list its landscape
# row back (718 px, one column — client/panels.css) made 62 characters FIT,
# and both instruments said so in their own words: "the long title was not
# elided (it fits) — stage a longer one, or the rule is not being exercised".
#
# So the fixture is longer, not the tooth weaker. This is what Claude Code's
# own VS Code window is really called — the CONVERSATION's name in front of
# the project and the app (see the project CLAUDE.md on why no string can
# identify that window) — and at 111 characters it elides in the widest row
# this list can draw as well as in the narrowest, which is the only length
# that exercises the rule at all four audited viewports.
#
# The member titles below stay at 62: their rows are the two-column ones
# (347 px), where 62 characters already overflow, and a fixture that proves
# something at one width proves nothing extra by being longer everywhere.
_LONG_TITLE = ("Widening the layout row so a window title fits"
               " - Claude Code - Remote User - Visual Studio Code"
               " [Administrator]")

# AND `parent` IS NO LONGER A FIELD OF ITS OWN (owner 2026-08-09, task 171 +
# 173). The server derives the ⭐ from the NAMES it would destroy —
# `layout_state.dependents` — so a fixture that staged only the boolean would
# render a star the product can no longer produce, and the ✕ chooser's warning
# would have nothing to be staged from. Both fields ride here, and they agree:
# the starred row is exactly the one whose `dependents` is non-empty.
LAYOUT_LIST_STAGE_JS = (
    "layouts = ["
    f" {{name:'{_LONG_TITLE}',"
    f"  process:'code.exe', orient:'portrait', icon:'{_ICON_VSCODE}',"
    "  ratio:[600,1000],"
    "  pos:0.5, grid:'2', members:2, parent:true, dependents:['Downloads'],"
    "  member_titles:['Claude Code - Remote User - Visual Studio Code"
    " [Administrator]', 'prompt.txt - Remote User']},"
    " {name:'Downloads', process:'explorer.exe', orient:'portrait',"
    f"  icon:'{_ICON_EXPLORER}',"
    "  ratio:null, pos:0.5, grid:null, members:1, parent:false, dependents:[],"
    "  member_titles:['Downloads']},"
    " {name:'Reading', process:'chrome.exe', orient:'landscape',"
    f"  icon:'{_ICON_CHROME}',"
    "  ratio:null, pos:0.5, grid:'4', members:4, parent:false, dependents:[],"
    "  member_titles:['Claude Code - Remote User - Visual Studio Code"
    " [Administrator]', 'Inbox (12) - Gmail', 'Downloads', 'Notes']}];"
    "layoutActive = 0; openLayoutPicker()"
)
LAYOUT_LIST_CLOSE_JS = "layoutActive = null; layouts = []; closeLayoutPanel()"

# THE ⚙ SHEET (owner 2026-08-09, task 175), staged by MEMBER COUNT because the
# sheet's whole content is "what can this layout be asked", and that answer
# differs: a THREE is the fullest it ever gets (three menu rows, two
# orientation chips and the four arrangement chips that only a three has), a
# SOLO the thinnest (no member to throw out, no arrangement to choose). Both
# are audited — a panel measured in one state is a panel half measured, and
# the state nobody stages is where this project's bugs keep arriving.
#
# A function rather than a bare statement: the audit drives it twice with
# different arguments, and a second copy of the fixture would be a second
# thing to keep in step with the first.
LAYOUT_SETTINGS_STAGE_JS = (
    "(spec) => {"
    " layouts = [{name: spec.name, process:'code.exe', orient:'portrait',"
    f"  icon:'{_ICON_VSCODE}', ratio:[600,1000], pos:0.5,"
    "  grid: spec.grid, members: spec.members, parent:false, dependents:[],"
    "  member_titles: spec.titles}];"
    " layoutActive = 0; openLayoutSettings(0); }"
)

# THE ✕ CHOOSER WITH SOMETHING TO LOSE (owner 2026-08-09, task 171). The plain
# chooser is staged above; this is the state that MATTERS — a four-window
# layout one of whose windows another layout's tab was torn out of, so closing
# it destroys that other layout too. Two dependents, because "1" and "several"
# are different sentences and only one of them can be wrong about its grammar.
CLOSE_WARN_STAGE_JS = (
    f"layouts = [{{name:'{_LONG_TITLE}', process:'code.exe',"
    " orient:'portrait', icon:null, members:4, ratio:null, pos:0.5,"
    " parent:true, dependents:['prompt.txt', 'Notes on the release']}];"
    "layoutActive = 0; openCloseChooser(0)"
)

# THE SAME LIST WITH A ROW PICKED UP. The classes are the ones the drag itself
# adds (`lay-drag` on the carried row, `lay-drop` on a legal target, `lay-full`
# on a layout that already holds four) — staged here rather than driven,
# because a screenshot proves what the state LOOKS like and no synthetic
# pointer can hold a finger still for 380 ms. What the gesture DOES is proven
# where it can be: tests/test_hold_gesture.py drives the real arming rule and
# tests/test_layout_protocol.py the real merge. The picture is here so the
# affordance he was promised in words — "Hold and drag it onto another to make
# a grid" — has finally been LOOKED at (rules/GUI.md).
LAYOUT_DRAG_STAGE_JS = (
    LAYOUT_LIST_STAGE_JS + ";"
    "(() => { const r = [...document.querySelectorAll('#layout-panel .lay-item')];"
    " r[1].classList.add('lay-drag');"
    " r[2].classList.add('lay-drop');"
    " r[3].classList.add('lay-full'); })()"
)

# THE CREATION LIST, STAGED WITH EVERY SHAPE A ROW CAN BE (owner 2026-08-09,
# tasks 166 / 167 / 168). Its own constant because two things use it: the panel
# sweep below and the audit's own kin-row check — the creation rows are
# `.lay-item` too, and until now the ONLY creation panel ever staged was one
# with no list at all (`creating.slots` and nothing else), so the entire row
# list this round rewrote had never been drawn in any picture.
#
# ONE ROW CAN SHOW NONE OF IT, which is why the fixture is six:
#
#   hwnd 1  a 62-character VS Code title  -> the elision of task 163
#   hwnd 1  three tabs under it           -> the INDENT of task 168, and the
#                                            only place a kin group has a
#                                            sibling group beside it
#   hwnd 2  one Chrome window, minimized  -> `tabs_hidden`: the row SAYS why it
#                                            offers no tabs (task 167), and the
#                                            card says it once more above
#   hwnd 3  a plain Explorer window       -> the ordinary case, so the three
#                                            special ones are visibly special
#
# THE TAB COUNT IS ALSO THE CAP'S ARITHMETIC (task 166). Three tabs on one
# window are worth THREE members, not four rows and not one window — so this
# staging makes `availableMembers()` return 5 and the header say so. A fixture
# where every window is worth exactly 1 would render the same panel whether
# that rule existed or not.
#
# `kind` is what `entryRow` reads to decide the icon and the indent, and
# `tab` is what `slotFromEntry` carries into the slot — both are the field
# names of client/layout-create.js, not a shape invented here.
CREATION_LIST_STAGE_JS = (
    "creating = newCreation('list');"
    "creating.entries = ["
    " {kind:'window', hwnd:1, title:'Claude Code - Remote User - Visual "
    "Studio Code [Administrator]', process:'code.exe', icon:null,"
    "  x:0.1, y:0.5},"
    " {kind:'tab', hwnd:1, title:'prompt.txt', process:'code.exe',"
    "  icon:null, tab:{name:'prompt.txt'}, x:0.1, y:0.02},"
    " {kind:'tab', hwnd:1, title:'layout_api.py', process:'code.exe',"
    "  icon:null, tab:{name:'layout_api.py'}, x:0.2, y:0.02},"
    " {kind:'tab', hwnd:1, title:'CLAUDE.md', process:'code.exe',"
    "  icon:null, tab:{name:'CLAUDE.md'}, x:0.3, y:0.02},"
    " {kind:'window', hwnd:2, title:'Mail - Google Chrome',"
    "  process:'chrome.exe', icon:null, tabs_hidden:true, x:0.5, y:0.5},"
    " {kind:'window', hwnd:3, title:'Downloads', process:'explorer.exe',"
    "  icon:null, x:0.7, y:0.5}];"
    "renderCreationPanel()"
)
CREATION_CLOSE_JS = "cancelCreation(true)"

# The model the audit's own User-Agent carries — the card must READ it and say
# it. A device name the page silently fails to find is exactly the failure the
# owner reported (a card that describes one phone while he uses two), so the
# fallback wording being present is not enough: the real path is measured.
UA_MODEL = "Pixel 8"

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
    ("Dictation card", DICT_STAGE_JS,
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
     " icon:null, members:4, ratio:null, pos:0.5, dependents:[]}];"
     "layoutActive = 0; openCloseChooser(0)",
     "layoutActive = null; layouts = []; closeLayoutPanel()",
     "#layout-panel .lay-card"),
    # …AND THE SAME CHOOSER WITH SOMETHING TO LOSE (owner 2026-08-09, task
    # 171). The warning is a THIRD line inside a chip that already carries a
    # label and a consequence, on the narrowest card this app has — so it is
    # exactly the line that would be cut, and the only way to know it is not
    # is to measure it and to look at it. Its own entry rather than replacing
    # the plain one above: the ordinary case must stay staged too, or nothing
    # would catch a warning that appears when there is nothing to warn about.
    ("Layout close chooser warned", CLOSE_WARN_STAGE_JS,
     LAYOUT_LIST_CLOSE_JS, "#layout-panel .lay-card"),
    # THE ⚙ SHEET (owner 2026-08-09, task 175) at its FULLEST — a three, which
    # is the only size that adds the four arrangement chips under the two
    # orientation ones. The thin state (a solo) is driven by the audit's own
    # settings-sheet check, which asks both.
    ("Layout settings sheet",
     "(" + LAYOUT_SETTINGS_STAGE_JS + ")({name:'"
     + _LONG_TITLE + "', grid:'3-top', members:3,"
     " titles:['Claude Code - Remote User - Visual Studio Code"
     " [Administrator]', 'prompt.txt - Remote User', 'Downloads']})",
     LAYOUT_LIST_CLOSE_JS, "#layout-panel .lay-card"),
    # The layout list carries a rename button per row (owner
    # 2026-08-05) — a long window title must not push the row's
    # buttons off the card. Staged with THREE rows since 2026-08-09
    # (see LAYOUT_LIST_STAGE_JS above): one row could never show a
    # sibling of a different height, nor a row to drag onto.
    ("Layout list with rename", LAYOUT_LIST_STAGE_JS,
     LAYOUT_LIST_CLOSE_JS, "#layout-panel .lay-card"),
    ("Layout list mid-drag", LAYOUT_DRAG_STAGE_JS,
     LAYOUT_LIST_CLOSE_JS, "#layout-panel .lay-card"),
    # ONE WINDOW OUT OF A GRID (owner request 2026-08-09, task 165), staged on
    # the FOUR — the largest this panel ever gets: four member rows, each with
    # its own cell of the grid lit, plus the arrangement row that only a 4→3
    # ever shows (four drawn chips). One of the four member titles is the
    # 63-character VS Code window title, so the panel is measured against task
    # 163's one-line rule with the longest name a member really has.
    ("Layout member chooser",
     LAYOUT_LIST_STAGE_JS + "; openMemberPanel(2)",
     LAYOUT_LIST_CLOSE_JS, "#layout-panel .lay-card"),
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
    # THE LIST THE WINDOWS ARE PICKED FROM — never photographed until today,
    # although this round rewrote every row in it (tasks 166 / 167 / 168). See
    # CREATION_LIST_STAGE_JS above for what each of the six rows is evidence of.
    ("Creation list with tabs", CREATION_LIST_STAGE_JS,
     CREATION_CLOSE_JS, "#layout-panel .lay-card"),
    # THE CAP, AND THE DEAD CREATE BUTTON (owner report 2026-08-09, task 166:
    # "it offers a grid of 4 when the desktop holds 3", and the half he
    # actually feels — "then the Create button just sits there"). Two windows
    # on the PC, a 2-grid chosen and only one cell filled, which is the ONLY
    # state that puts all three of this task's visible answers on one screen:
    # the 3 and 4 shape chips ABSENT, the line that explains their absence, and
    # a Create that is visibly unavailable instead of looking live and
    # swallowing the tap. Nothing else in the sweep renders a dimmed Create.
    ("Creation panel capped at two",
     "creating = newCreation('list');"
     "creating.entries = ["
     " {kind:'window', hwnd:2, title:'Mail - Google Chrome',"
     "  process:'chrome.exe', icon:null, x:0.5, y:0.5},"
     " {kind:'window', hwnd:3, title:'Downloads', process:'explorer.exe',"
     "  icon:null, x:0.7, y:0.5}];"
     "creating.mode = 'grid'; creating.grid = '2';"
     "creating.slots = [{hwnd:2, title:'Mail - Google Chrome',"
     " process:'chrome.exe', icon:null, tab:null, x:0.5, y:0.5}];"
     "renderCreationPanel()",
     CREATION_CLOSE_JS, "#layout-panel .lay-card"),
)

# The panels SHOT in a non-default look. Shooting all thirteen in all eight
# would be over a hundred pictures nobody will open, and a picture nobody
# opened is not proof (rules/GUI.md). The first three carry colour: the sets
# list with its live badge, the quality panel's segmented rows, and the
# dictation card's status column.
# The layout list joined on 2026-08-09: the ⭐ (owner decision, task 169) is a
# COLOUR EMOJI, the one mark in this product whose ink the palette does not
# own — the theme cannot restyle it, so the only way to know it reads on a
# light card is to look at it on one.
# The creation list joined the same day (tasks 166-168): the newest screen in
# the product, and the only one whose ROWS carry three colour-bearing states at
# once — the accent `sel` border of a chosen row, the `.lc-off` dimming of one
# refused by the window-or-its-own-tab rule, and the secondary ink of the
# "minimized" note.
# The ⚙ sheet joined on 2026-08-09 (task 175): it is the newest screen in the
# product and the one every act on a layout now passes through, so a look in
# which its rows or its drawn chips do not read is a look in which the layout
# feature is unusable. The warned ✕ chooser joined with it (task 171) for the
# one reason a picture can settle: its warning is the only text in this app
# painted in `--warning` on a card, and whether that colour READS on a light
# surface is not a thing geometry can answer.
COLOUR_SHOTS = {"Sets picker", "Quality panel", "Dictation card",
                "Layout list with rename", "Creation list with tabs",
                "Layout settings sheet", "Layout close chooser warned"}

# The panels SHOT IN LANDSCAPE (2026-08-07). Every phone panel is MEASURED in
# both orientations and always was; these two are also photographed there,
# because they are the ones whose content is orientation-dependent: the
# creation panel draws the grid catalogue on a LANDSCAPE outer box, and the
# arrangement row draws the four landscape three-window variants that no
# picture had ever shown. The controls and the wheel are shot in landscape in
# every look, separately.
# The Region grab joined them on 2026-08-07: its bar is the panel whose
# layout depends most on the width it is given, and landscape is where it
# gets three times as much of it.
# The ✕ chooser joined on 2026-08-08: it is two big side-by-side chips, which
# is exactly the shape landscape squeezes — 46% of a wide card each, with a
# consequence line that must still wrap rather than clip.
# The ⚙ sheet and the warned ✕ chooser joined on 2026-08-09 (tasks 175 / 171),
# and the creation LIST with them: landscape is where all three are tightest —
# the sheet's chips have half the width, the chooser's two big chips take 46%
# of a wide card each with a third line under them, and the creation list is
# the panel this round had to restructure to make its rows whole there at all.
LANDSCAPE_SHOTS = {"Creation panel + Name field", "Grid arrangement choice",
                   "Sets picker", "Quality panel", "Dictation card",
                   "Layout list with rename", "Region grab",
                   "Layout close chooser", "Layout close chooser warned",
                   "Layout settings sheet", "Creation list with tabs"}

# ONE FOLDER, ONE SUBJECT (owner 2026-08-08, his second word on this): a topic
# folder per ROUND was still a dump — he asked for sub-folders rather than one
# directory of 161 pictures. So the round's folder holds SUBJECT folders, and a
# subject is what the picture is OF, read from its own name. Anything
# unrecognised lands in `other`, which is a signal rather than a hiding place:
# an `other` that grows means a new screen exists and nobody named it.
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
    ("Layout_member_chooser", "layouts"),
    ("Layout_settings_sheet", "layouts"),
    ("Layout_list", "layouts"),
    ("Rename_card", "layouts"),
    ("Aspect_panel", "layouts"),
    ("Creation_panel", "layouts"),
    ("Creation_list", "layouts"),
    ("Grid_arrangement", "layouts"),
    ("MainWindow", "desktop-windows"),
    ("SettingsWindow", "desktop-windows"),
    ("TrafficWindow", "desktop-traffic"),
    ("WheelOrderDialog", "desktop-windows"),
)
