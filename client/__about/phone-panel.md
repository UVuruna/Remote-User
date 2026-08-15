# phone-panel.js — Settings → Phone: the switches about THIS device

New 2026-08-11 (owner **task 161**, ordered again as **218a**). Opened by the
`phone` built-in action in the Settings set; the same overlay card pattern as
[Quality](quality.md) and the dictation card.

**Every row here acts on the LIFTED finger** — [`keepRowTap`](row-tap.md),
never `keepFocus` — so a finger landing on a row can still scroll the list
(owner report 2026-08-15; the same defect task 227b had fixed inside the
creation panel alone).

## Why it exists

Every switch on this card already shipped, and every one of them shipped in
the wrong room:

| Switch | Old home | Why that was wrong |
|--------|----------|--------------------|
| D-pad shape, per orientation (task 177) | the **Wheel sets** picker | that card is about which SETS ride the wheel. His words: "to se sada nalazi gde se podešavaju setovi" <!-- lang-ok: owner quote --> |
| Layout bar Top / Bottom (task 160) | the **layout list** card | that card is about LAYOUTS. Task 160's own comment said so and promised to move it "the day 161 lands" |
| What Hide means (task 159) | a **hold** on the Hide button | discoverable only by accident |

That is ALG-9 SECTION TAXONOMY (rules/GUI.md → Zubi v2) three times over. The
subject that gathers them is **the phone**: each is a per-device preference
through the SharedPreferences bridge, each changes this handset and nothing on
the PC, and none belongs to any other card in the product.

**Moved, not copied.** The sets picker and the layout list gave theirs up in
the same round — a switch with two doors is two states to keep in step.

## The rows

1. **Layout bar** — Top / Bottom (`layBarPos` / `setLayBarPos`, layouts.js)
2. **When hidden** — Comes back / Stays hidden (`hideMode` / `setHideMode`,
   chrome.js). Both costs are his own words: "comes back" makes the buttons'
   corner unusable for the mouse; "stays hidden" leaves the Hide button's own
   corner covered until he presses it again. Neither is better, which is why
   both ship.
3. **Held upright / Held sideways** — the D-pad shape ticks (`padShapeRow`,
   panels.js). Neither changes a default: each starts on the shape that
   orientation renders TODAY, and ticking writes the explicit choice that
   outranks it.
4. **Notification channels** (task 226, owner ballot verdict; label wording
   corrected under grader flag d, task 233) — three on/off rows, one per
   carrier `notify.js` already read and never had a door to write: banner,
   speak, tone. Each row is `notifyPrefs()`'s own current value, and ticking
   one calls `saveNotifyPrefs()` with the merged object and re-renders the
   card so the tick lights correctly. The last-resort rule (`notify.js` →
   `effectiveNotifyPrefs()`, documented in full in [Notify](notify.md): muting
   all three still leaves the banner on) used to be stated INSIDE the banner
   row's own label, which wrapped 5-6 lines in this card's narrow column. It
   now sits ONCE, as a `.sets-sub` note above all three rows, and each row's
   own label is a short name — "Notification banner" — never a sentence.
5. A **pointer** to the dictation card for the listening beeps and the
   language.

## Why the dictation beeps stayed put

That switch is read and written by the Android speech engine through
`Android.voiceMuteBeeps`, and it only makes sense beside the language it
mutes. This card carries a link to it, never a second copy.

## Layout

A plain `.sets-card` block — deliberately **not** `card-columns`. Five short
rows gain nothing from a landscape multicol reflow, and a capped multicol is
what once put the sets picker's Done button 273 px off the right edge of a
915 px screen (see [panels.md](panels.md)).

The first two rows use `segRow` (panels.js), the shared segmented control
lifted out of quality.js in this same round so the Phone card and the Quality
panel cannot drift apart.

## Gate

The relocation and the Settings wiring are held by
`tests/test_claude_panels.py` →
`check_the_phone_card_gathered_the_switches`, which fails both when the card
loses a switch and when an OLD home keeps one.
