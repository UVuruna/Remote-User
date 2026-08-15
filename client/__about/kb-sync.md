# kb-sync.js — the invisible keyboard field's diff/caret rules

**Script:** [Kb Sync (script)](../kb-sync.js) · **Flow:** [Kb Sync (flow)](../__flow/kb-sync.md)

## Purpose

Turns one edit of the invisible keyboard field ([Caret capture](controls.md) →
`kbInput`) into PC key injections, and decides whether the field's own caret
can still be trusted for the NEXT edit. Split out of `controls.js`'s `input`
handler on 2026-08-13, pure like [Voice](voice.md) and
[Grid Icons](grid-icons.md) before it, so `tests/test_kb_sync.py` can run it
whole in node.

## His report (2026-08-13)

The mic hypothesis was tested live and ruled out first — his own words,
translated: *"dictating with the mic first changes nothing at all; this only
happens while I am typing on the keyboard"*. His sharper evidence: typing,
**most on delete**. The PC's visible caret sits at the **far right**, yet what
he types lands **inserted before a trailing fragment** ("ok") that no amount
of further typing or deleting removes. Only a mouse click outside the field
and back frees it.

## The mechanism

`kbDiff` (below) is the same erase-and-retype arithmetic `controls.js` always
ran, and its own long-standing comment says outright what it assumes: **the
PC caret sits at the END of the mirrored text.** That is only true while the
PHONE's own caret is ALSO at the end of `kbInput` — and an Android IME can
leave it somewhere else with no tap of his (a predictive-completion span still
"claiming" a trailing word, an autocorrect replace that repositions the caret
before the word it just fixed). The field is invisible, so he has no way to
see this happen.

Once the caret sits before a trailing fragment, **every** edit he makes shares
a non-empty common suffix with what came before — that fragment, unchanged —
so the mid-string branch of `kbDiff` fires on every single keystroke: erase
the tail off the PC, retype it. The mirroring stays internally consistent with
what is actually in the field, but the fragment itself was never his edit, so
nothing he types or deletes ever touches it — it simply reappears on the PC
after every character, exactly "inserted before a fragment that will not go
away". A blur clears both `kbInput.value` and the mirror outright (existing
`controls.js` behaviour), which is exactly his working fix (tap away, tap
back) and was the tell that pointed at the caret rather than at the diff
arithmetic itself.

## The fix

`kbShouldRepin` tells `controls.js` when to call
`kbInput.setSelectionRange(value.length, value.length)` after an edit: any
time the field's own caret is not a collapsed selection at its own end, AND
the edit was not mid-composition. This cannot rewrite what the IME already did
to land the edit that just happened — but it guarantees the **next** edit
starts from the end again, so the drift cannot compound: a single stray
fragment is recoverable by one ordinary backspace instead of being permanent
until a blur.

**Never mid-composition.** Forcing a selection while a real multi-keystroke
composition (CJK, an emoji picker) is in flight can break the composing span
itself, and it is not what caused his report — GBoard's own
autocorrect-completion drift does not set `isComposing` true while it happens.

**Never a policy of refusing the mid-string dance itself.** That dance is also
what makes autocorrect and the double-space-period rule work at all (the
original comment on `kbDiff`); disabling it outright would silently drop those
legitimate live edits rather than occasionally mis-place a rare stray one.

## The ghost-suffix diagnostic (2026-08-15, no behaviour change)

He hit the pattern again — mobile data, high latency — and could not
reproduce it the next day to hand over a live session. `kbGhostCandidate`
adds a cheap SIGNAL, never a fix (`kbShouldRepin` above is still the whole
fix and is untouched): a given edit "looks like" the 2026-08-13 pattern when
either

1. `kbDiff` fired its mid-string branch AND retyped more than one character
   (`back > 0 && inserted.length > 1` — an ordinary keystroke is a 0-or-1
   character edit; a stuck fragment produces a multi-character mid-string
   retype on every later keystroke), or
2. `inserted` ends with a real (**>=2 character**) run matching the tail of
   `prevValue` — the fragment reappearing verbatim. One matching character
   is deliberately not enough: ordinary text shares its last character with
   whatever came before constantly (a trailing space, a repeated letter),
   and a threshold of 1 would flag that noise on nearly every keystroke.

`controls.js`'s `logKbGhostCandidate` calls it from the real `input` handler
and, on a hit, sends one `client_log {text: "[kb-ghost] ..."}` naming
`prevLen`/`valLen`/`selStart`/`selEnd`/`composing`/`inputType` and the last
12 characters of `prevValue`/`value` (JSON-escaped, so a stray quote in the
typed text cannot corrupt the log line) — rate-limited to at most one line
every 2 s (`KB_GHOST_LOG_MIN_MS`), because a genuine occurrence keeps
re-triggering the predicate on every following keystroke for as long as the
fragment stays stuck, and that IS the bug, not a reason to flood
`server.log`.

## Connections

### Uses

Nothing. The module is pure by design (see above).

### Used by

- [Controls](controls.md) — the `kbInput` `input` handler calls `kbDiff` for
  every edit, `kbShouldRepin` to decide whether to re-pin the caret, and
  (via `logKbGhostCandidate`) `kbGhostCandidate` for the diagnostic above
- [Tests (folder)](../../tests/___tests.md) — `tests/test_kb_sync.py` runs
  this module whole in node
