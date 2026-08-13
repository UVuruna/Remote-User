# Flow — `client/lang-groups.js`

How a pile of locales becomes a list of languages, and how one language becomes
a list of choices. What each rule is FOR lives in
[__about/lang-groups.md](../__about/lang-groups.md).

Navigation: [client folder](../___client.md) ·
[about](../__about/lang-groups.md)

---

## The two lists that walk this path

```
ANDROID                              THIS MODULE                 THE CARD
─────────────────────────────────────────────────────────────────────────────
VoiceInput.candidateTags()
  system locales + every enabled  ─┐
  IME subtype, exact-string only   │
  → "sr-RS", "sr-Latn-RS", "sr_RS" │
                                   ├─►  groupByLanguage(…)  ─►  dictation-card.js
Notifier.voices()                  │      (default idOf:        rows + drill-down
  every installed TTS voice       ─┘       canonical locale)
  → "sr-rs-x-sfg#female_1", …
                                     ►  groupVoicesByLanguage  ─►  notify.js
                                          (idOf = voice.name)     Settings → Voice
```

Nothing on the Android side changed for this round: nothing is deleted on the
phone, so nothing had to be.

## One pass, then one pass over the groups

```
for each row
  │
  ├─ tag = tagOf(row)
  ├─ lang = langKey(tag) ................. the GROUP. no language → row dropped
  ├─ get-or-create group(lang), remembering first-seen order
  ├─ id  = idOf(row) ?? langVariantKey(tag)
  │        └─ langVariantKey = lang | langScript(tag) | region
  │                                    └─ FILLED IN when the tag omitted it:
  │                                       Intl.Locale.maximize(), else
  │                                       LANG_DEFAULT_SCRIPT, else ""
  ├─ id already in this group?  →  SKIP (first spelling wins)
  └─ push { tag, row };  name the group if it has no name yet

then, for each group                     ← a second pass, and it must be second
  ├─ scripts = { langScript(v.tag) … }
  ├─ regions = { region(v.tag)     … }
  └─ v.label = langVariantLabel(v.tag, scripts, regions)
                └─ names ONLY the axes that differ across THIS group
```

Why the labels need their own pass: a variant's label depends on its
**siblings**. `sr-Latn-RS` reads `Latin` next to a Cyrillic sibling and reads
nothing at all when it is the language's only variant. A per-row rule cannot
know which case it is in, and getting this wrong is one of the gate's planted
defects.

## Naming voices

`groupVoicesByLanguage` runs the same grouping with `idOf = v.name`, then
replaces the script/region labels — a voice's siblings differ by **speaker**, so
calling them all "United States" would name none of them.

```
voiceGroupLabels(group's voices)
  │
  ├─ variants = voices.map(voiceVariant)
  │               tail after "#", minus -local/-network/-compact/-embedded
  │               NO "#"  →  ""   (an engine id says nothing about a speaker)
  │
  ├─ readable = variants.length > 0
  │             AND every variant passes voiceVariantReadable
  │                   each word: [a-z]+[0-9]*  or  [0-9]+ ; ≥1 has letters
  │                   → "female 1" ok · "7f3a2b1c" no · "3" no
  │             AND no two variants are equal
  │
  ├─ label = readable ? variant : `Voice ${i+1}`     ← THE GROUP is the unit
  └─ + " (Region)" only when this group spans more than one region
```

`readable` is computed for the whole group before any label is chosen. That is
the owner's rule made structural: one unreadable variant sends every row of the
group to numbers, so a group can never be half named and half numbered.

## What the cards do with it

```
render (either card)
  │
  ├─ groups = group…(source)
  ├─ open = groups.find(key === <card>OpenLang)
  │
  ├─ open?  →  langBackRow(open.name)          ← the only thing naming the
  │            + one row per variant,            language he is standing in
  │              wearing v.label                 (rows no longer repeat it)
  │
  └─ else   →  per group:
                 variants.length === 1
                   →  a flat, ordinary row       ← a door into a list of one
                                                    hides his only choice
                 else
                   →  langGroupRow(group, holdsChosen)
                        name · count · drawn arrow
                        `sel` when his current choice is INSIDE it
```

`voiceOpenLang` / `dictOpenLang` are separate variables on purpose: the two
cards hold **different** languages (voices installed here vs languages he can
dictate in), so one shared position would open a language the other card does
not have.

Both reset on close — re-opening a card shows the list of languages, not
wherever he happened to be standing last time.
