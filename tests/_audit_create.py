"""WHERE A LAYOUT COMES FROM, STAGED — the audit's fixtures for the two
creation lists whose rows carry a NAME and a WHERE.

Split out of tests/_audit_panels.py on 2026-08-20 (THE STRUCTURE LAW) and by
RESPONSIBILITY rather than by line count, the same split `_audit_lang.py` and
`_audit_update.py` already made: that file is the CATALOGUE of every panel the
audit opens, while these two entries are one feature's own staging — the
sources a layout is built from (`client/layout-create.js`,
`client/layout-new.js`, `server/recents.py`, `server/layout_acts.py`).

Both rows here have the SAME SHAPE, which is why they belong in one file and
why they were measured together: a name on line one and where-it-is on line
two (constraint 44, owner decree 2026-08-20). One of them had never been in
the catalogue at all, which is exactly how its 84 px cap went four rounds
without anybody photographing what it did to a 63-character layout name.

Nothing here imports anything: every value is a plain string the audit hands
to the live page.
"""

# THE NEW SOURCE, OPENED FROM INSIDE A LAYOUT (owner ballot 2026-08-13, T28 +
# T29). Staged in its FULLEST state, which is also the one that can starve:
# the layout's own act group under its own heading, then the standard list —
# and in it a row that is ALREADY OPEN, wearing both a long path and the
# "already open" pill on the same line. That row is the whole of his picture-1
# fix, and the one thing it must never do is squeeze the project's NAME out of
# legibility: knowing WHICH project he is looking at is the point of keeping
# the row instead of dropping it. Photographed rather than reasoned about,
# because a dimmed row plus a pill plus an elided path is exactly the
# combination this project keeps getting wrong on a 412 px phone.
NEW_SOURCE_STAGE_JS = (
    "creating = newCreation('new');"
    "renderRecentsPanel(["
    " {app:'vscode', kind:'new', target:'', label:'New window', sub:'',"
    "  id:'vscode|new|', open:false, why:''},"
    # THE PATHS ARE REAL WINDOWS PATHS, backslashes and all. The first version
    # of this stage lost them to escaping and the screenshot read
    # "U:CodingUVuruna…" — a picture of a string this product never produces,
    # which is the one thing a staged shot may never be. `String.raw` on the JS
    # side and a raw Python literal on this one, so neither layer eats them.
    r" {app:'vscode', kind:'recent', target:'U:/Coding/UVuruna/Applications/"
    r"VibeCoder', label:'VibeCoder',"
    r" sub:String.raw`U:\Coding\UVuruna\Applications\VibeCoder`,"
    r" id:'vscode|recent|1', open:true, why:'already open'},"
    r" {app:'vscode', kind:'recent', target:'U:/Coding/UVuruna/Gadgets/"
    r"PromptPainter', label:'PromptPainter',"
    r" sub:String.raw`U:\Coding\UVuruna\Gadgets\PromptPainter`,"
    r" id:'vscode|recent|2', open:false, why:''},"
    " {app:'chrome', kind:'new', target:'', label:'New window', sub:'',"
    "  id:'chrome|new|', open:false, why:''},"
    r" {app:'explorer', kind:'recent', target:'D:/Downloads',"
    r" label:'Downloads', sub:String.raw`D:\Downloads`,"
    r" id:'explorer|recent|3', open:true, why:'already open'}"
    "], {in_layout:true, app:'vscode', name:'VS Code', entries:["
    " {id:'vscode|claude', label:'New Claude Code',"
    "  sub:'a new conversation, in its own tab'},"
    " {id:'vscode|window', label:'New window, same folder',"
    "  sub:'a second VS Code on this project', opens:true}]})"
)
NEW_SOURCE_CLOSE_JS = "cancelCreation(true)"

# RECENT LAYOUTS, STAGED BECAUSE ITS ROW HAS THE SAME SHAPE AS THE ONE ABOVE
# (constraint 44, 2026-08-20). This panel was never in this catalogue, so the
# 84 px cap of task 233 was the last measurement it ever got — and the row it
# caps carries a LAYOUT'S NAME, which is a VS Code window title, 63 characters
# at the length he screenshotted. The first row here is exactly that length,
# beside an ordinary short one and one whose project name is long enough to
# want the whole second line: a list of one has nothing to compare a row's
# height against, which is the lesson task 163 already cost this project once.
RECENT_HISTORY_STAGE_JS = (
    "creating = newCreation('recent');"
    "renderRecentHistoryPanel(["
    " {id:'h1', name:'Popraviti otvaranje prozora iz layouta - VibeCoder - "
    "Visual Studio Code', project:'VibeCoder'},"
    " {id:'h2', name:'Chrome', project:''},"
    " {id:'h3', name:'Rework agentskih instrukcija - UVuruna', "
    "project:'UVuruna monorepo'}"
    "])"
)
RECENT_HISTORY_CLOSE_JS = "cancelCreation(true)"

