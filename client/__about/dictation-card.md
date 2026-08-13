# `client/dictation-card.js` — what THIS device hears

The dictation setup card: which language the phone listens in, what each one
sounds like before he commits to it, and whether the listening beeps are muted.
Opens on the **first Mic tap** and from the Settings set's **Language** button.

Navigation: [client folder](../___client.md) · grouping:
[lang-groups](lang-groups.md) · siblings: [panels](panels.md) ·
[notify](notify.md)

---

## Why it is its own file

Split out of [`panels.js`](panels.md) on 2026-08-13, when grouping the language
list pushed that file past THE STRUCTURE LAW's 1,000-line wall — and split **by
responsibility rather than by line count**, which is the only split that stays
split:

* `panels.js` answers *which controls ride on this phone* — the sets picker, the
  command chooser.
* this file answers a question about **the device in his hand** — which
  languages it can recognise, which of its own voices can speak them, what its
  samples sound like.

Two subjects in one file is what let a language list quietly grow into the pile
the owner reported on 2026-08-13.

It also owns the two rows a **grouped** language list is built from —
`langGroupRow` (the door into a language) and `langBackRow` (the way back out) —
which `notify.js` uses for Settings → Voice. That file is loaded after this one,
the same arrangement `dictVoices` already relied on. Two copies of a row is how
two cards start looking like two different apps.

## What the card holds

| Part | Rule |
|------|------|
| Device line | Names the phone the list describes (owner 2026-08-09, task 127 — he owns two devices, and a card naming none read as if these were *the* languages). From the User-Agent, refined by `userAgentData`, falling back to a plain "this device" rather than guessing. |
| Language rows | Grouped by language ([lang-groups](lang-groups.md)); a language with several variants is a **door**, one with a single variant is a plain row. |
| Status per row | `ready` / `model will download` / `online`, language-agnostic. |
| Listen button | One written sample sentence per language, spoken by a voice of **that** language — never the engine default. A **sibling** of the `<label>`, never a child: a click inside a label activates the control that label owns, so a nested speaker would also *choose* the language. |
| More languages | Downloadable models and the online service's list, collapsed behind one row. Its ellipsis is declared with `data-opens-more` so the truncation audit knows it means "more behind me", not "your text was cut". |
| Mute listening beeps | Default on — the round tones cycle on every silence. |

## The honest limits, which are rules and not footnotes

* **Recognition languages and TTS voices are different sets.** A language he can
  dictate in may have no voice here at all. Such a row says so quietly and
  offers no button, and it **never** speaks the sample in the engine's default
  voice — he would hear English, believe he had heard the language he tapped,
  and choose by it.
* **A language with no written sample** says so too. `DICT_SAMPLES` is
  hand-written, one short line per language all saying the same thing, so what
  changes between two taps is the sound and nothing else. Nothing is translated
  at runtime.
* **One sample at a time, never a queue.** The shell hands text to
  `TextToSpeech` with `QUEUE_ADD` and exposes no stop, and the voice is chosen
  per call but applies to the whole queue — so a second tap during a sample
  would speak **both** in the second language's voice. A tap while one is
  speaking is ignored, and the button that is speaking shows it. The window is
  an estimate rounded up: too long costs a short wait, too short costs a sample
  in the wrong voice, which is the one thing the control exists to prevent.
* Both no-preview states and the device line are staged and measured by the
  phone audit (`tests/_audit_panels.py` → `DICT_STAGE_JS`).

## Where the grouping lives, and why not here

The arithmetic — what makes two locales the same, which script a bare tag means,
what tells two variants apart — is in [`lang-groups.js`](lang-groups.md), pure so
`tests/test_lang_groups.py` runs it whole in node. This card renders; it decides
nothing that could be wrong in a way the owner would judge, except **one** thing
it deliberately owns: a language with a single variant is rendered flat rather
than behind a door, because a drill-down into a list of one shows him nothing he
could not already see and would put his only Serbian behind a tap.
