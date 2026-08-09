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

Nothing here imports anything: every value is a plain string the audit hands to
the live page.
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
