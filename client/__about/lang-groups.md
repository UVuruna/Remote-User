# `client/lang-groups.js` — language first, variant second

The grouping arithmetic **both** of the app's language lists read: the
notification-voice card (`client/notify.js`, Settings → Voice) and the dictation
language card (`client/dictation-card.js`, the first Mic tap / Settings →
Language). Pure by design — no DOM, no socket, no state of its own — so
`tests/test_lang_groups.py` can run it whole in node, the same reason
`grid-icons.js`, `view-anchor.js`, `cursor-shapes.js` and `voice.js` are pure.

Navigation: [client folder](../___client.md) ·
[flow](../__flow/lang-groups.md) · readers: [notify](notify.md) ·
[dictation card](dictation-card.md)

---

## Why it exists

Owner report 2026-08-13, about both lists at once: the voice that speaks and the
language he speaks to were each **one flat pile** of everything the device had,
and the dictation one offered *"vise puta iste odabire"* — the same choice
several times over. <!-- lang-ok: owner quote -->

Two separate causes sat behind one complaint:

* **The voice card** printed whatever the TTS engine returned, in engine order,
  with no grouping and no sort — and every row wore its own language word,
  because `Notifier.kt` builds each label as `"<language> <variant>"`. So the
  same word ran down the entire column.
* **The dictation card** printed every system locale plus every enabled
  keyboard subtype, deduped by **exact tag string only**. Android hands one
  locale over in more than one spelling — `LocaleList.getAdjustedDefault()`
  says `sr-RS` while a Gboard subtype says `sr-Latn-RS` or `sr_RS` — so his
  Serbian appeared two and three times.

## The rule that is easy to get visibly right and quietly wrong

The first plan was to **dedupe the dictation list by language**. The owner
overruled it and the reason is the whole design: *"da ali sa podgrupama jer
korisnik treba da bira da li ce output da ide cirilica ili latinica isto kao
sto engleski ima vise odabira"*. <!-- lang-ok: owner quote -->

`sr-Latn` and `sr-Cyrl` are not two spellings of one row. They decide **what
his dictated text comes out as**, exactly as `en-US` and `en-GB` are a real
choice. A merge would have produced the tidy card he asked for while silently
removing a decision — so:

> **Grouping removes repetition. It never removes a choice.**

What *is* collapsed is only ever the same variant written twice, and that needs
the script **filled in** when a tag left it out: without resolution, `sr-RS`
looks as different from `sr-Cyrl-RS` as it does from `sr-Latn-RS`, which is the
original duplicate. `Intl.Locale.maximize()` answers this where the WebView has
it; `LANG_DEFAULT_SCRIPT` is a deliberately **small** fallback, because a wrong
guess here splits one language into two rows — the very defect being fixed.

**The tag is never rewritten.** A canonical key decides sameness; the string
handed back is the exact one the platform offered, because that is what goes to
`Android.voiceSetLang()` and `Android.speakAs()`, and a spelling we invented may
simply not be accepted.

## What a group looks like

```
groupByLanguage(rows, tagOf, nameOf, idOf)
  -> [{ key, name, variants: [{ tag, row, label }] }]
```

Groups come back in **first-seen order** — the platform's own preference order,
his system locale first — and so do variants. A group of one still comes back as
a group: the caller decides whether one variant is worth a drill-down (both
cards say no, and render it flat).

`idOf` is **what makes two rows the same**, and the two cards answer it
differently. Running this module before wiring it proved they must:

| Card | A row is… | Keyed by |
|------|-----------|----------|
| Dictation | a locale | canonical language + script + region (the default) |
| Voice | a voice | `voice.name` |

Keying a voice by its locale silently threw away every voice of a language but
the first — his American *male 1* would have vanished, and the card would have
looked tidier while offering **less**.

`label` is what tells a variant from its siblings **inside its own group**, and
it can only be chosen once the whole group is known: the same tag reads `Latin`
beside a Cyrillic sibling and reads nothing at all when it is alone. Only the
axes that actually differ are named, so a lone German variant wears no
"Germany" under a heading already saying German.

## Naming a voice

The owner's ruling, in his two cases: keep the engine's variant when it reads
like `female 1` or `male 1`; fall back to `Voice 1, 2, 3` when it is nonsense
characters.

* `voiceVariant(name)` is the tail after `#`, minus the `-local` / `-network`
  qualifiers that say where a voice **runs** rather than who it sounds like.
  **No `#`, no variant** — `sr-rs-x-sfg` carries a locale and a private-use id
  and nothing about the speaker.
* `voiceVariantReadable` is stricter than it first looks, and its own gate
  caught the loose version: every word must be a word optionally carrying a
  trailing number, so a hex id like `7f3a2b1c` is refused. "Letters and digits
  and spaces" was not enough — that id is letters and digits, and it went out
  under his ruling as a name.
* **The group is the unit.** One unreadable or duplicated variant numbers the
  whole group, because half a group named and half numbered is not a sequence
  he can read.

## One name source, and it answers in English

The owner's decision of 2026-08-13, taken after an independent grader **opened
the two screenshots** and read the same language spelled two ways two screens
apart: the dictation card said `Srpski` while the voice card said the Cyrillic
endonym, and `Icelandic` was the one English name among the endonyms.
<!-- lang-ok: the defect being described is a Cyrillic rendering; the word itself is not reproduced -->

The cause was structural rather than a slip. Android hands the dictation card a
full endonym per row (`Locale.getDisplayName(locale)` — the language in its own
words); the voice card is given no such name and must look one up, and asked for
`sr` a lookup answers the Cyrillic endonym. Preferring the platform's word where
there was one and looking one up where there was not is **two sources**, and two
sources cannot agree by accident. One source cannot disagree.

So every heading is asked of `Intl.DisplayNames(["en"])`, whatever the platform
supplied, and **whatever the group's size** — the earlier code kept the
platform's wording for a group of one and looked the name up only for a group of
several, which on his phone means the exception was the common case.

Two things are deliberately NOT translated:

* **The rows inside a group** keep `Cyrillic` / `Latin` / `United Kingdom`,
  because what those rows decide is what his dictated text **comes out as** —
  they are choices, not labels.
* **The spoken samples** stay in the language they demonstrate. A sample read out
  in English would be the exact deception the honest-limit rule exists to
  prevent.

## Honest limits

* Script resolution is the platform's (or the small table's). A language with an
  unusual script and no `Intl.Locale` gets **no** assumed script rather than a
  plausible one — it may then show one row where two were possible, which is
  strictly better than two rows for one choice.
* Group headings are the **English** language name, from `Intl.DisplayNames`
  (owner 2026-08-13 — see "One name source" below). The endonym the platform
  handed the row survives only as the fallback for a runtime with no
  `Intl.DisplayNames`, shortened of its region; the upper-cased subtag is the
  last resort and reads as a code rather than as a misspelt word.
* Variant words (`Latin`, `United Kingdom`) come from `Intl.DisplayNames` in
  English, not in the language being named — the app's own language is English
  everywhere but its samples.

## Gate

`tests/test_lang_groups.py`, fail-closed in `setup/gates.py` (0b0/6), fourteen
checks. It runs the real module in node, one fresh interpreter per scenario, and
each defence is proven by planting its own defect — including the two that
shipped wrong inside this round (the locale-keyed voice, and the id offered as a
name).

The English-heading check **supplies** an endonym and demands it be ignored: a
heading that merely happened to read `Serbian` because nothing was supplied would
prove nothing.

Its own honest limit, and it is why the phone audit is the second half: this gate
can only see a **group's** heading. A group of ONE is drawn from the row itself
(`dictation-card.js`), so the leaf rows kept their endonyms after the arithmetic
was already correct — green gate, wrong card. `tests/_audit_lang.py` →
`LANG_GROUP_CHECK_JS` sweeps the rendered names for the endonyms its own stage
supplies, which is what caught it.
