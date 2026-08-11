# claude-state.js — what the phone may CLAIM about the PC's Claude Code

New 2026-08-11 (owner ballot verdict, tasks **190 / 191 / 208**). The tables
and the arithmetic behind the three Claude cards, with no DOM anywhere in the
file — the DOM half is [claude-panels.js](claude-panels.md).

**PURE ON PURPOSE**, the `grid-icons.js` / `cursor-shapes.js` / `voice.js`
pattern: `tests/test_claude_panels.py` runs this module WHOLE in node. Every
rule the owner judges is here, where a gate can drive it.

## Why it exists — three reports, one family of defect

| Task | His report | What was really wrong |
|------|-----------|------------------------|
| 190 | the Model panel offered **nine** options; the extension's own picker offers **five** | the nine came out of CLI-transcript vocabulary an agent measured in its own session (`opusplan`, `sonnet[1m]`, `best`) and verified against that same transcript — the authority nobody consulted was the menu HE looks at |
| 191 | Thinking only RAISED a menu, "unazađena" <!-- lang-ok: owner quote --> | `/effort` takes a level, so the panel can finish the command itself; round 30 shipped the safe half and the proving half never got a round |
| 208 | Thinking lit **Medium** while the PC ran on **Max** | what was lit was this PHONE's memory of its own last tap, wearing a live-state look. He believed the panel and reported the command as broken |

All three are one sentence: **a panel stated something it did not know.**

## The three kinds of truth, and they never swap clothes

```
SAVED      a FACT read off the PC's settings file  (config `saved`)
NOW        a FACT read off the live conversation   (`claude_state`)
LAST SENT  this PHONE's memory of its own tap      — NOT a fact about the PC
```

`claudeEffortChips` / `claudeModelChips` / `claudeModeChips` return chips
carrying a `kind` — `"fact"` or `"memory"` — and that field is what the LOOK
must follow (`client/panels.css` → `.cl-fact` / `.cl-memory`). The difference
is carried BY SHAPE (fill and border style), never by colour alone: three of
the eight looks paint no colour on a control at all.

A claim we cannot make is the word **`unknown`** (`CLAUDE_UNKNOWN`), never a
blank, never a guess, and never the other chip's value. An older PC answers
`claude_state` with nothing at all, so that is the DEFAULT case here rather
than an afterthought — every function takes `null`.

## The tables

**`CLAUDE_MODELS`** — the official five, in HIS order (by strength, Default
first), with capability stars beside the names ("kao i na drugim mestima" — a
standing rule for every model list from now on). <!-- lang-ok: owner quote -->

| value (the argument typed) | label | stars | family (what the PC reports) |
|---|---|---|---|
| `default` | Default (recommended) | – | *none* |
| `haiku` | Haiku | 1 | `haiku` |
| `sonnet` | Sonnet | 2 | `sonnet` |
| `opus[1m]` | Opus (1M context) | 3 | `opus` |
| `fable` | Fable | 4 | `fable` |

`value` is the picker ALIAS, which commits with one Enter. `family` is what
comes back in `claude_state.model`, and the two differ on purpose — the phone
asks for `opus[1m]` and the PC says `opus`, which is why `claudeNowModel()`
matches by family and not by string equality. **Default carries no family**:
it resolves to whatever the account picks, so no row may honestly claim to be
it, and marking it would be a guess of exactly the kind 208 was about.

**`CLAUDE_EFFORTS`** — `/effort low|medium|high|xhigh|max`. The label is his
word for it, the value is the argument: "Extra high" is spoken, `xhigh` is
typed.

**`CLAUDE_MODES`** — the Shift+Tab ring, in the order the key steps it:
`default → acceptEdits → plan →` (wrap). There is no `/mode` command, so a
mode button is arithmetic over this ring plus that many presses of one chord.

## `claudeModePresses(current, target)` — and why `null` is the point

Returns `(to - at + 3) % 3`, or **`null`** when the current mode is unknown.
Without `claude_state.mode` the ring has no known starting point, and a button
that pressed "probably one" could land him in **Accept edits**, which edits his
files without asking. The caller must offer the honest act instead — step once,
and say that it stepped — never a computed number over an unknown.

## The stars are DRAWN

`claudeStarsSvg(n)` builds one inline `<svg>` with `n` filled paths, sized in
`em` so the strip scales with the row's text like a glyph would, without being
one. The reason is on the record: the ✥ move handle came out a blunt cross on
the owner's own phone (2026-08-05), after which every mark this app draws
became an SVG path. A typed black-star character would render in whatever the
device's emoji font decides — the same gamble, on the one row whose whole job
is to communicate a ranking at a glance. The gate greps the *whole client* for
such a character (`STAR_GLYPHS`); the layout selector's ⭐ is deliberately
exempt, being a colour emoji the owner asked for by name (task 169) and one
mark rather than a scale.

## The honest lines

`CLAUDE_MODEL_NOTE` / `CLAUDE_EFFORT_NOTE` / `CLAUDE_MODE_NOTE` are product
copy and they carry the half of 190/191/208 no chip can: what the command
actually does to the PC. `/model` **saves** as the default for new
conversations; `/effort` applies to the conversation running now, up to
`/clear` or a new session, and the extension's own slider re-asserts the saved
level at a relaunch; a mode belongs to the running conversation and has no
command at all.

## Gate

`tests/test_claude_panels.py` — 22 checks, each proven by planting its own
defect. See [__flow/claude-state.md](../__flow/claude-state.md) for the shape
of the decisions.
