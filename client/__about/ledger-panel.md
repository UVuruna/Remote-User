# ledger-panel.js + ledger-panel.css — the Session Ledger card

New 2026-08-17 (T111). Claude Code's own task list for the focused layout's
project, drawn on the phone from `ledger_state {}`'s answer — see
[Session Ledger](../../server/__about/session_ledger.md) for the grammar,
the five states and the hook that keeps the file honest. This module is the
DOM half only: every rule about what a line MEANS lives on the server side
of that doc, exactly the split `claude-panels.js`/`claude-state.js` already
draw.

Modelled directly on [claude-panels.js](claude-panels.md): the same
veil/`.sets-card` scaffold, the same ghost-click armor
(`ghostClickArmor(ledgerPanel, ledgerOpened)`), and the same "ask first, draw
immediately, the answer decorates it if it comes" rule — an older server that
never answers `ledger_state` leaves the panel in its honest empty state,
nothing here waits on it. Loads after `claude-panels.js`. `controls.js`
dispatches here through `PANEL_KINDS.ledger` (`panels.js`), from the
`ledger` action in `actions.json`'s Claude Tools set.

**Two files, one doc** — the `panels.js`/`panels.css` precedent, and here it
falls out for free: both files share the basename `ledger-panel`.
`ledger-panel.css` styles only what is NEW beyond `panels.css`'s shared
`.sets-card`/`.sets-row`/`.sets-body`/`.sets-list`/`.sets-done` vocabulary —
the state dot, the row anatomy (branch glyph / dot / state word / title /
`★` stars / `@model` chip / chevron) and the expanded body (`#feature` /
description / question+answer / evidence / children).

## The 2026-08-21 tags (TASK-schema revision)

The wire's tasks now carry `stars` (0–5) and `feature` (slug, `""`), and the
frame a `category` line. The ROW shows the stars — `claudeStarsSvg(n, 5)`
([claude-state.js](claude-state.md)'s own drawn paths, ONE KIND ONE CLASS),
in the row's muted ink. The first cut typed a font star in `--ledger-yellow`
and was refused twice: the panels gate on the glyph (a dingbat renders as
the device pleases) and the audit on the colour (2.71:1 on every light look
— a 12px dot FILL is not a text ink); the `#feature`
slug sits in the expanded BODY, not on the row — a 412 px row already carries
dot, state word, title, stars and `@model`, and the feature is context he
opens a row for, while scanning BY feature is the desktop Work history's job
(`server/__about/work_history.md`). The session's `category:` renders as one
muted line under the card title, above the project path. All three absent →
nothing is drawn, the pre-tag look exactly.

## Reading the tree

`ledger_state`'s `tasks` array is exactly the shape `session_ledger.parse()`
returns, one entry per top-level task, each carrying `children` recursively.
`ledgerTaskEl(task, depth)` draws one row and recurses over `children` —
depth only ever changes the row's visual nesting (`.ldg-child`, the branch
glyph, the indent), never how a task is read.

Expansion state (`ledgerExpanded`, keyed by task id) survives a re-render — a
fresh `ledger_state` frame redraws the whole tree, and a row he had opened
must not silently close under him — but not a panel close, the same
open/close lifecycle `claude-panels.js`'s own cards follow.

## The five states, read as colour AND word

`LEDGER_STATES` maps the server's five colour names (`red`/`orange`/`yellow`/
`blue`/`green` — [Session Ledger](../../server/__about/session_ledger.md)'s
own `STATE_COLORS`, already collapsed through the `[x]`-without-evidence
downgrade rule before this module ever sees it) to a CSS class and a plain
word ("not started" / "in progress" / "waits for you" / "done" /
"verified"). Both the dot's `aria-label` and a visible `.ldg-state-word` span
carry the word — a grader finding (2026-08-17) that colour alone is not a
legend for a stranger reading this panel for the first time, and a sighted
reader needs the word beside the dot as much as a screen reader needs it on
the dot.

## The answer field — the existing typed-command path, not a new one

A `[?]` task's expanded body shows its `question` text and an input +
**Send** button (`ledgerAnswer`). Sending calls
`send({type: "paste_text", text, enter: true, focus: "claude"})` — the SAME
clipboard → Ctrl+V → focus-the-prompt route the Claude set's own slash
commands already use (`server/claude_api.py`'s `focus_prompt`), never a
character-by-character type and never a new protocol message. Answering a
ledger question is, on the wire, indistinguishable from typing any other
Claude command from the phone.

## Honest empty state

`ledgerEmptyState` explains what would have to happen for a ledger to
appear — Claude Code writing one through the hook, for the project the
FOCUSED layout's window is open on — rather than a bare "nothing here",
because the two reasons a panel is empty (no server answer yet vs.
genuinely no ledger for this project) are both real and neither is a
failure.

## Gate

`tests/test_session_ledger.py`, and the phone audit stages the panel by
calling `renderLedgerPanel()` directly rather than `openLedgerPanel()` — the
first shot of it showed the EMPTY state under a green audit because the
open path asks the real server, whose desktop answer overwrote the staged
fixture.
