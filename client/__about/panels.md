# panels.js + panels.css — Settings overlay panels (Sets picker + Dictation)

Split out of `controls.js` on 2026-08-05 (THE STRUCTURE LAW): `controls.js`
owns the D-pad groups, the wheel and the button actions; this module owns the
full-screen card overlays those actions open. Loads right after `controls.js`
(same global scope — it uses its prefs helpers, wheel state and `keepFocus`).
Rows of its lists use [`keepRowTap`](row-tap.md) instead, so a finger landing
on one can still scroll the card (owner report 2026-08-15).

**Two files, one doc** — the `layouts.css`/`layouts.js` precedent.
`client/panels.css` is the same feature's styling, split out of `style.css` on
2026-08-09 when the dictation card's listen control pushed that file past
1,000 lines. It holds every overlay card's shape and the `.sets-card` /
`.sets-row` / `.sets-list` / `.sets-done` vocabulary the Quality panel
(`quality.js`), the notices card and the notification-voice card (`notify.js`) and the command chooser share,
plus the landscape rules that name `.lay-card` too — one rule about what a
panel card does with a landscape screen's spare width, written once. It loads
after `style.css` and before `layouts.css`; the `body` prefix on those rules is
what keeps them winning over `layouts.css`'s own `.lay-card` width, by
specificity rather than by load order.

The landscape WIDTH (`min(760px, 100%)`) reaches every card. The two-column
REFLOW is opt-in, on **`.card-columns`** (owner width question 2026-08-09,
task 172): columns are a height remedy paid for in row width, which is free
for a card of short items and ruinous for one whose rows carry names — see
`style.md` for the measurements and for which cards ask. A card that declares
nothing keeps the whole width in one column, because that is the failure mode
the audit can already see.

## `PANEL_KINDS` — which built-in opens which card

One table, and it lives here because this module owns the overlay cards:
`controls.js` builds the D-pad button and knows only that a `kind` may name a
card (`makeActionButton` → `PANEL_KINDS[b.kind]()`). It was one `else if` per
kind in controls.js, which was fine while there were two and was the thing
standing between that file and THE STRUCTURE LAW's 1,000-line ceiling by the
time Settings → **Voice** needed a seventh (2026-08-12).

`sets` · `region` · `quality` · `dictation` · `phone` · `notifyvoice` ·
`notices` ([Notify](notify.md) — WHEN this phone listens: only while the app
is open in the background, the default, or always) · `appearance` ([Appearance Panel](appearance-panel.md), owner ballot
2026-08-12 — how THIS device looks; it left the PC's Settings window for the
same reason **Voice** did) · `anywhere` — every kind whose whole action is
"open that card". Each entry is
WRAPPED in an arrow rather than named directly: the openers live in five
different modules (this one, `quality.js`, `phone-panel.js`, `region.js`,
`notify.js`, `chrome.js`) and several load AFTER this file, so a bare
reference would be read at load time and throw. The arrow is read at tap time,
by which point every script is in.

A `kind` with no entry falls through to nothing, exactly as an unknown kind
always did. `tests/test_claude_panels.py` checks both halves of one such door
— the built-in in controls.js AND the wiring here — because a button that is
drawn and does nothing is the failure this table could hide.

## Sets picker (`openSetsPanel`)

Chooses which sets ride in the wheel on THIS phone: required built-ins are
locked on; optional shipped sets and desktop-made custom sets toggle up to
`WHEEL_MAX` total, plus the app-shortcuts toggle. Stored per device via the
prefs bridge (`prefGet`/`prefSet` in controls.js) — origin-independent, see
the bridge note there (owner bug 2026-08-05: pure localStorage split state
between the LAN and Tailscale origins, the picker "rotated").

**This card DECLARES its columns — it is not a fragmentainer** (`card-split`,
2026-08-09). The landscape reflow gives a card `column-count: 2`, and a
multicol with a definite height answers "content no longer fits" by making
ANOTHER column: two rows more and this card grew a third one 273 px off the
right edge of a 915 px screen, carrying the app-shortcuts row and the Done
button with it (measured `scrollWidth` 1129 in a 758 px card; the card itself
never scrolled, which is why only the phone audit saw it). It now takes the
mechanism the creation panel took for the same reason: an auto-fill GRID on
the LISTS — 300 px tracks, sized from the widest row, because 200 px clipped
the app rows at 278>200 — the card filling the panel (a scroll is only legal
with no width idle beside it), the title and counter sharing a line, and the
Done button PINNED outside a scrolling `.sets-body`. On a 915x412 phone the
body still hides ~32 px: that is rung 4 of the ladder, taken after rungs 1
and 2, because fitting ten rows and a paragraph in 377 px means touch targets
under 30 px. `card-split` is this card's own class, so the four other
`.sets-card` panels keep the reflow they were measured with — and their
latent version of the same spill is a known, unfixed risk, recorded here.

**The D-pad shape ticks LEFT this card on 2026-08-11** (task 218a). They asked
about the shape of the CONTROL GROUPS on this handset while sitting in a card
titled "Wheel sets", which is about which sets ride the wheel — ALG-9 SECTION
TAXONOMY, and the owner named the misplacement himself. Their home is the
Phone card ([phone-panel.md](phone-panel.md)). The BUILDER `padShapeRow` stays
here beside the other row builders; its callers do not.

**`segRow`** — the shared segmented control (a caption, a strip of mutually
exclusive buttons, one lit). It was born in quality.js as `qualitySegRow` and
was lifted here on 2026-08-11 when the Phone card needed the identical row.
Its `.q-row` / `.q-seg` class names were kept: they are already styled,
already audited and already photographed, and renaming measured CSS buys
nothing.

App-shortcut rows are ticked one by one under a master switch — and since
2026-08-06 they are **counted**: `visibleCount()` includes `appSetReserve()`,
the card states `N of 8 used — M held for app shortcuts`, and a tick that
would overflow is refused with the same toast an optional set gets. The rule
is the owner's: "ako označi oba … onda može samo još 6 dodatnih umesto 7" —
VSCode and Claude ride together on a Claude tab, so both ticked reserve two
slots. The tick is applied first and rolled back on refusal, because the
reserve is computed from the stored prefs, not from the checkbox.

## Quality panel — moved out

Lives in [quality.js](quality.md) since 2026-08-05: it edits the quality
prefs and reads the PC's base, so panel and prefs are one responsibility.

## Dictation setup card (`openDictationPanel`, owner round 2 2026-08-05)

The dictation language is a USER CHOICE — round-1 evidence: pinning to the
phone's first system locale transcribed the owner's Serbian as English
garbage (his phone lists English first). Opens on the FIRST Mic tap (no
choice stored, or `__voiceEnd("nolang")`) and from Settings → Language.
Rows come from `Android.voiceLangs()` (system locales + keyboard languages)
with plain-language statuses: "ready on this phone" / "model will download —
online until it arrives" / "recognized over the internet"; a radio tap calls
`Android.voiceSetLang(tag)` and re-renders (a download may have just
started). Never a transient toast — the card stays until Done/backdrop.
Round 4 (owner 2026-08-05): languages beyond the phone's own (`extra` —
downloadable models + the online service's list) sit behind a collapsed
"More languages (N)…" row (the chosen one always surfaces), and a
"Mute listening beeps" checkbox (default ON) drives
`Android.voiceSetMuteBeeps` — the round tones stay quiet while dictating.

### The card names THIS device (owner 2026-08-09, task 127)

His report, with a screenshot of this card (lang-ok: owner quote below):
*"koristim dva uredjaja — jezik, ako je vec vezan za uredjaj, treba da kaze
OVAJ UREDJAJ ima te i te jezike"*

Every row on this card is a fact about the phone in his hand — its system
locales, its keyboard languages, its installed models — and he owns two
devices with different lists. A card that named none read as if these were
THE languages, so a language missing on the other device looked like a bug in
the app instead of a difference between two phones. A line under the heading
(`.dict-device`) now names it.

**The name is never guessed**, and there are exactly two sources:

1. `navigator.userAgent` — an Android WebView's platform group ends with the
   model (`Linux; Android 15; SM-X910`, a `Build/…` tail stripped). Read
   synchronously, so the FIRST paint already carries it.
2. `navigator.userAgentData.getHighEntropyValues(["model"])` — the same fact
   where the UA no longer carries it, because Chromium's User-Agent reduction
   freezes the model token to the literal `K`. It is a promise, so it lands
   after the first paint and may only REPLACE a name we do not have
   (`dictShowDevice` rewrites the one line, never the card — a re-render would
   re-arm the ghost-click armor).

Anything junk (`K`, `wv`, `unknown`, `generic`…) is refused and the card says
"this device". **No bridge method was added on purpose:** the page is served by
the PC while the shell is installed separately, so a header that needed a new
`window.Android` method would show nothing at all on the shell he has
installed today — which is the very device this line describes.

### Hearing a language before choosing it (owner 2026-08-09, task 127)

The other half of the same report (lang-ok: owner quote below):
*"treba da mogu da CUJEM da bih odabrao, dakle da ima i mikrofon da cujem kako
zvuci taj jezik"*

Each row that CAN be played carries a 44 px speaker button; a tap speaks one
short sentence in that language through `Android.speakAs(text, voice, 1)` —
the same call the PC's spoken notices use. The voices come from
`Android.ttsVoices()`, the same source `notify.js` forwards to the PC as
`tts_info`; there is no second list.

- **The button is a SIBLING of the row's `<label>`, never a child.** A click
  anywhere inside a label activates the control that label owns, so a speaker
  nested in the row would also SELECT that language — the tap meaning "let me
  hear it first" would have decided.
- **Voice matching: the language decides, the region only chooses between
  several.** A row's tag and a voice's locale are spelled differently by
  different parts of Android (`sr-RS` vs `sr-Latn-RS`), so the primary subtag
  decides eligibility and an exact tag match only picks WHICH of the eligible
  voices is used. A Brazilian row takes the Brazilian voice when the device
  has both and the European one rather than nothing when it does not: the
  wrong accent still tells him what Portuguese sounds like.
- **THE HONEST LIMIT IS THE FEATURE'S OWN RULE.** Recognition languages and
  text-to-speech voices are different sets. A row with no voice says
  *"no preview voice on this device"* and offers no button; a row with a voice
  but no sentence in our table says *"no sample sentence for this language
  yet"*. Neither ever falls back to speaking English in the default voice — he
  would hear English, believe he had heard the language he tapped, and choose
  by it. When previewing is impossible for the WHOLE card (no voices at all,
  or a shell without `ttsVoices`/`speakAs`) the card states it once instead of
  repeating one sentence down the list.
- **The samples are written, never machine-translated at runtime**
  (`DICT_SAMPLES`, keyed by BCP-47, longest prefix wins — which is why only
  the languages whose regions genuinely sound apart carry a second key). All
  say the same thing, so what changes between two taps is the SOUND. Covered
  today: the South Slavic set (sr/hr/bs/sl/mk/bg), ru/uk, de/nl/fr/es/ca/it/
  pt (+pt-BR), pl/cs/sk/hu/ro/el/tr, sv/da/nb/no/fi, ar/he/hi/th/vi/id/ms,
  ja/ko/zh (+zh-Hant/TW/HK) and en — 40 keys. Everything else is a GAP by
  design and shows the "no sample sentence" row.
- **One sample at a time, and never a queue.** `Notifier.speak` hands the text
  to `TextToSpeech` with `QUEUE_ADD` and the shell exposes no stop, so a
  second tap could not replace the first — it would line up behind it, and the
  engine's voice is set per call but applies to the whole queue, so BOTH would
  then speak in the second language's voice. A tap during a sample is
  therefore ignored and the speaking button wears `.busy`. The window is an
  estimate of the sentence's length (nothing comes back from the engine),
  rounded up on purpose: too long costs a wait, too short costs the wrong
  voice.

Both preview states — a row WITH a voice and a row WITHOUT one — plus the
device line are staged and measured by the phone audit
(`tests/_audit_panels.py` → `DICT_STAGE_JS`, asserted in
`tests/test_layout_audit.py`), because the state nobody stages is the state
this project's bugs keep arriving in.

## Ghost-click armor (all panels)

The tap that OPENS a panel can deliver a late synthetic click that lands on
whichever row opened under the finger, silently toggling it. A capture-phase
click handler swallows every click within `GHOST_CLICK_MS` of opening.

## The live badge (owner 2026-08-06)

*"hoću da bude štiklirano pored onoga koji je aktivan tj koji može da se
prikaže — da bude uočljivo bolje"*

The app rows carry two different facts, and the picker used to show only one:

- the **tick** = this set is ALLOWED on this phone;
- the **badge** = it is on the wheel RIGHT NOW, for the layout in focus.

`refreshSetsMeta()` updates the badges and the counter line **in place** after
every tick. It deliberately does not rebuild the card: re-rendering re-arms the
ghost-click armor (`GHOST_CLICK_MS`) and would swallow the next tap — the
picker feeling like it "rotates" is a bug this project has already paid for
once. The badge keeps its box when off (transparent, not removed), so a row
never changes height as focus moves.

Both tick handlers now **write, then measure**. They used to disagree — the
basic row measured before saving with `>=`, the app row after saving with `>`
— and a rule the code states twice is a rule the code will break once. The
cap itself moved to [sets.js](sets.md); this module only renders it.

## A capped multicol cannot scroll — it grows sideways (owner 2026-08-10, task 217)

His screenshot: the Dictation language card, held sideways, reflowed into the
two columns he likes — and then vertical scrolling stopped working entirely,
with the lower part of the card and its Done button unreachable. Upright the
same card scrolls perfectly.

**The mechanism is a property of multicol, not a mistake in any one panel.**
`.sets-card` / `.lay-card` carry `max-height: 92vh` and `overflow-y: auto`,
which is exactly right for an ordinary block. Add `column-count` and the box
becomes a FRAGMENTAINER with a DEFINITE height, and a fragmentainer that runs
out of height has one answer: it makes ANOTHER COLUMN. So the overflow is in
the INLINE axis, `scrollHeight` never exceeds `clientHeight`, `overflow-y: auto`
has nothing to do, and the rest of the card is off to the right where no
vertical gesture can reach it. Measured: with the fix removed, the dictation
card at 915×412 overflowed **sideways by 742 px**.

This project met the same trap once before, on the Sets picker (2026-08-09), and
answered it for that ONE card by declaring its columns explicitly (`card-split`).
Every other reflowing card was left with the trap armed, waiting for its content
to grow — and the dictation card's content is the phone's own language list,
which is exactly the content that varies from device to device.

**The fix takes the cap off**, using the same property read the other way: a
multicol with an AUTO height balances into exactly `column-count` columns and
grows TALLER. The card stops being height-constrained, keeps its two columns,
and the scrolling moves out to the panel behind it — a plain fixed box with no
columns of its own. Rung 4 of the ladder is still last: rungs 1 and 2 are what
these columns ARE, and a scrollbar only appears once two full columns genuinely
do not fit. `margin-block: auto` beside `align-items: flex-start` keeps a short
card centred, where plain `align-items: center` would centre an over-tall card
and put its TOP out of reach above the scroll origin — the same bug wearing the
other end of the card.

**Panels checked, all now green in both orientations with content long enough to
require scrolling** (task 215's standing order — a card that never scrolls
proves nothing): Dictation card (the reported one), Sets picker, Quality panel,
Layout list, Creation card, Layout settings sheet, Member chooser, ✕ chooser.
Gate: the reach checks in `tests/test_phone_chrome.py`, and the dictation
staging in `tests/_audit_panels.py` now lists fourteen languages instead of six.
