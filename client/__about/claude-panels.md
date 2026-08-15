# claude-panels.js — the Model, Thinking and Mode cards

New 2026-08-11 (owner ballot verdict, tasks **190 / 191 / 208** and item 4 of
the verdict). The DOM half of the three Claude Code panels; every rule they
obey lives in [claude-state.js](claude-state.md), which is kept pure so its
gate can run it whole.

Loads after `panels.js` — it uses that file's `ghostClickArmor` and the
`.sets-card` shape every overlay in this app wears. `controls.js` dispatches
here at runtime from a button's `panel` field in `actions.json`, so nothing
here is referenced at load time.

**Every row here acts on the LIFTED finger** — [`keepRowTap`](row-tap.md),
never `keepFocus` — so a finger landing on a row can still scroll the list
(owner report 2026-08-15; the same defect task 227b had fixed inside the
creation panel alone).

## The three cards

| `panel` | Card | What a tap sends |
|---------|------|------------------|
| `claude-model` | **Model** — the official five, weakest first, with drawn capability stars | `paste_text "/model <alias>"`, one Enter |
| `claude-effort` | **Thinking** — Low / Medium / High / Extra high / Max | `paste_text "/effort <level>"`, one Enter |
| `claude-mode` | **Mode** — Default / Accept edits / Plan | N × `chord {shift+tab}` |

Each opens with a chip strip at its head, the options below it, and one honest
line above Cancel saying what the command really changes.

## The chips of truth

Model carries **SAVED** and **NOW**; Thinking carries **SAVED**, **NOW** and
**LAST SENT**; Mode carries **NOW** alone (nothing saves a mode). The look is
decided by the chip's `kind` and by nothing else — a `"memory"` chip may never
be styled like a `"fact"`, because a per-device memory wearing a live-state
look is task 208 itself.

Model has no third chip on purpose: a `/model` tap **saves**, so "last sent
from this phone" and "saved on the PC" would be one claim written twice, the
weaker copy able to go stale.

## `claude_state` — asked for, never depended on

The panel asks (`send {type:"claude_state"}`) and draws in the same frame,
with unknowns. If an answer comes (`connection.js` → `onClaudeState`) the card
re-renders in place and the chips fill in. If it never comes — an older PC has
no such handler — a 2 s timer turns "asking the PC…" into "unknown" and the
card stays fully usable. **Nothing here waits or blocks on the answer.**

The answer's `saved` object refreshes `claudeSaved`, the same fact the
`actions` frame already carries. It may refresh it; it never becomes a second
store to keep in step.

## Mode, and the honest step

There is no `/mode` command: Shift+Tab steps a three-mode ring and wraps. With
`claude_state.mode` known, a target is `claudeModePresses()` chords. **Without
it, the card says so in its own subtitle, labels each row "— steps one", and
one tap sends exactly one press.** Guessing the start could land him in Accept
edits, which edits his files without asking — the one outcome a wrong guess
must never buy.

The presses go out as ordinary `chord` messages, which is why this button
could ship on the day the verdict landed: `chord` is in the server's
`TYPING_KINDS`, so each press passes through `focus_guard.typist()` exactly
like `/usage` and `/compact` beside it (CLAUDE.md constraint 11). No new focus
field was needed and none was invented.

## Gate

`tests/test_claude_panels.py`. See
[__flow/claude-state.md](../__flow/claude-state.md).
