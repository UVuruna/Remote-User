"""The LANGUAGE CARDS' audit stages and measurements.

Two cards ask one kind of question — which language, and in whose voice:
  * the dictation setup card (`client/dictation-card.js`) — what THIS device
    hears, and which script it writes back;
  * Settings -> Voice (`client/notify.js`) — which of this device's voices reads
    a notice out loud.

Its own module since 2026-08-13, when grouping both lists pushed
`tests/_audit_panels.py` past THE STRUCTURE LAW's 1,000-line wall — and split by
RESPONSIBILITY, the `_audit_laybar.py` precedent: `_audit_panels.py` owns every
overlay card's staging in general, while these two share one subject, one
grouping module (`client/lang-groups.js`) and one owner report.

Imported by tests/test_layout_audit.py, which drives the sweep.
"""

# cover; the check below fails loudly rather than silently losing the case.
DICT_STAGE_JS = (
    "window.Android = {"
    " voiceLangs: () => JSON.stringify(["
    # THE GROUPING IS ONLY PROVEN BY A COLLISION (owner 2026-08-13). His own
    # phone hands Serbian over twice — `LocaleList.getAdjustedDefault()` says
    # 'sr-RS' while a Gboard subtype says 'sr-Latn-RS' — plus 'sr_RS' from an
    # IME that spells it with an underscore. Those three must become ONE row
    # holding TWO choices (Cyrillic, Latin), which is the whole round: a stage
    # with one spelling per language would photograph a card that cannot show
    # either the repetition or the drill-down.
    "  {tag:'sr-RS', name:'Srpski (Srbija)', status:'download'},"
    "  {tag:'sr-Latn-RS', name:'Srpski (latinica, Srbija)', status:'ready'},"
    "  {tag:'sr_RS', name:'Srpski (Srbija)', status:'download'},"
    "  {tag:'en-US', name:'English (United States)', status:'ready'},"
    "  {tag:'en-GB', name:'English (United Kingdom)', status:'ready'},"
    "  {tag:'de-DE', name:'Deutsch (Deutschland)', status:'online'},"
    "  {tag:'is-IS', name:'Íslenska (Ísland)', status:'online'},"
    "  {tag:'pt-BR', name:'Português (Brasil)', status:'download', extra:true},"
    "  {tag:'ja-JP', name:'日本語 (日本)', status:'online', extra:true},"
    # A CARD THAT NEVER SCROLLS PROVES NOTHING ABOUT SCROLLING (owner standing
    # order of 2026-08-10, task 215; the defect it exposed is task 217). Six
    # rows FIT sideways, so every landscape measurement this card has ever
    # passed was a measurement of a card with nothing to scroll — while the
    # list it really draws is the phone's own languages, and his has many. The
    # rows below are ordinary real locales, added only to make the card longer
    # than the screen it is judged on; nothing else about the staging changes.
    "  {tag:'fr-FR', name:'Français (France)', status:'online'},"
    "  {tag:'es-ES', name:'Español (España)', status:'online'},"
    "  {tag:'it-IT', name:'Italiano (Italia)', status:'online'},"
    "  {tag:'nl-NL', name:'Nederlands (Nederland)', status:'online'},"
    "  {tag:'pl-PL', name:'Polski (Polska)', status:'ready'},"
    "  {tag:'tr-TR', name:'Türkçe (Türkiye)', status:'online'},"
    "  {tag:'ru-RU', name:'Русский (Россия)', status:'online'},"
    "  {tag:'hu-HU', name:'Magyar (Magyarország)', status:'online'},"
    "  {tag:'ro-RO', name:'Română (România)', status:'online', extra:true},"
    "  {tag:'cs-CZ', name:'Čeština (Česko)', status:'download', extra:true}]),"
    # The same source the PC's own voice list comes from (`tts_info`), so the
    # card is measured against a REAL shape: Android reports `{name, label,
    # locale}` per voice and `name` is what `speakAs` takes back.
    " ttsVoices: () => JSON.stringify(["
    # SEVERAL VOICES PER LANGUAGE, or the voice card's own grouping is staged
    # by three languages holding one voice each — which draws no group at all.
    # English carries three across two regions (so the region tie-break shows),
    # Serbian two, and German two whose engine names have NO '#': those have no
    # variant to show, so that group must come out as 'Voice 1 / Voice 2' — the
    # owner's fallback, photographed beside the named case rather than assumed.
    "  {name:'sr-rs-x-sfg#female_1', label:'Serbian female', locale:'sr-RS'},"
    "  {name:'sr-rs-x-sfg#male_1', label:'Serbian male', locale:'sr-RS'},"
    "  {name:'en-us-x-tpf#male_1', label:'English male', locale:'en-US'},"
    "  {name:'en-us-x-tpd#female_1', label:'English female', locale:'en-US'},"
    "  {name:'en-gb-x-gba#female_2', label:'English female', locale:'en-GB'},"
    "  {name:'de-de-x-nfh', label:'German', locale:'de-DE'},"
    "  {name:'de-de-x-nfg', label:'German', locale:'de-DE'},"
    "  {name:'is-is-x-isf#female_1', label:'Icelandic female', locale:'is-IS'}]),"
    " speakAs: () => {},"
    " voiceMuteBeeps: () => true, voiceSetMuteBeeps: () => {},"
    " voiceChosen: () => 'sr-RS', voiceSetLang: () => {},"
    " voiceState: () => '' };"
    "renderDictationCard()"
)

# SETTINGS -> VOICE, THE OTHER HALF OF HIS 2026-08-13 REPORT.
#
# This card had never been in the sweep, so the pile he reported existed in a
# surface no picture in this repo had ever shown — the same gap the loading
# overlay was found in (constraint 16: "the overlay had never been PHOTOGRAPHED
# in this project's life until this round", and staging it immediately found two
# defects). It reuses DICT_STAGE_JS's shim because both cards read the SAME
# `ttsVoices`, which is exactly the claim being made.
#
# Two states are staged, because the round's whole shape is a drill-down and a
# picture of the closed list proves nothing about the open one:
#   the LIST of languages (groups, counts, the chosen group marked), and
#   ONE LANGUAGE OPEN (the back row, and the rows wearing variant names only).
# WHICH voice is CHOSEN (owner report 2026-08-15): the English group's UK
# female voice — the group also holds a US male and a US female, so this
# proves the region tie-break ("female 2 (United Kingdom)") survives onto the
# CLOSED row too, not only the open one. `prefGet`/`prefSet` fall back to
# localStorage whenever `window.Android.prefGet` is absent (controls.js), and
# this shim never stubs it — the same path a dev browser takes.
NOTIFY_VOICE_CHOSEN_JS = (
    "localStorage.setItem('notifyVoice', 'en-gb-x-gba#female_2');")

NOTIFY_VOICE_STAGE_JS = (
    DICT_STAGE_JS.replace("renderDictationCard()", "")
    + NOTIFY_VOICE_CHOSEN_JS
    + "voiceOpenLang = ''; openNotifyVoicePanel()"
)

NOTIFY_VOICE_OPEN_STAGE_JS = (
    DICT_STAGE_JS.replace("renderDictationCard()", "")
    + NOTIFY_VOICE_CHOSEN_JS
    # English is the group with three voices across two regions — the widest a
    # row here gets, since the region tie-break is appended to the variant.
    + "voiceOpenLang = 'en'; openNotifyVoicePanel()"
)

# THE DICTATION CARD WITH ONE LANGUAGE OPEN — his Serbian, the collision that
# made this round: one row on the list, two scripts behind it.
DICT_OPEN_STAGE_JS = (
    DICT_STAGE_JS.replace("renderDictationCard()", "")
    + "dictOpenLang = 'sr'; renderDictationCard()"
)

# ONE ROW PER LANGUAGE, AND HIS CHOICE STILL VISIBLE (owner 2026-08-13:
# *"tu isto se ponavljaju bez potrebe pa imamo vise puta iste odabire"*).
# lang-ok: owner quote
#
# tests/test_lang_groups.py proves the ARITHMETIC groups correctly. This proves
# the CARD renders what the arithmetic returned, which is a different claim and
# the one HE judges: the stage above plants his own collision (sr-RS +
# sr-Latn-RS + sr_RS, and en-US + en-GB), so a card still printing a row per tag
# would show five rows where two belong.
#
# It also holds the two promises grouping could quietly break — that the group
# holding his current choice is MARKED (with the choice one level down, that
# mark is the only thing saying the card remembers it), and that a door says HOW
# MANY choices are behind it.
#
# It lives here rather than inline in test_layout_audit.py because that file sits
# at THE STRUCTURE LAW's wall, and this module is already where the panel stages
# and their measurements live.
LANG_GROUP_CHECK_JS = """([panelSel, activeSubstr]) => {
                  const bad = [];
                  const card = document.querySelector(
                    panelSel || '#dictation-panel .sets-card');
                  if (!card) return ['the card did not open'];
                  const rows = [...card.querySelectorAll('.dict-row')];
                  const names = rows.map((r) => {
                    const n = r.querySelector('.dict-name');
                    return n ? n.textContent.trim() : '';
                  });
                  // The staged collision: Serbian three ways, English two.
                  // The heading is the ENGLISH name (owner 2026-08-13), so it
                  // is 'Serbian' although every staged row supplied the Latin
                  // endonym 'Srpski (Srbija)' — which is the point: the card
                  // must IGNORE what the platform handed it.
                  const serbian = names.filter((t) => /^Serbian/i.test(t));
                  if (serbian.length !== 1) {
                    bad.push('Serbian appears on ' + serbian.length +
                             ' rows — his repetition, unfixed: ' +
                             JSON.stringify(serbian));
                  }
                  const english = names.filter((t) => /^English/i.test(t));
                  if (english.length !== 1) {
                    bad.push('English appears on ' + english.length +
                             ' rows: ' + JSON.stringify(english));
                  }
                  // NO HEADING IS AN ENDONYM, and this is measured on the CARD
                  // rather than only in the arithmetic's gate, because the
                  // divergence it fixes was found by OPENING a screenshot and by
                  // nothing else: the two cards spelled one language two ways
                  // and every assertion in the repo was green. The staged rows
                  // supply these words, so any of them reaching a heading means
                  // the platform's wording is being preferred again.
                  for (const endonym of ['Srpski', 'Deutsch', 'Íslenska',
                                         'Português', 'Русский']) {
                    if (names.some((t) => t.startsWith(endonym))) {
                      bad.push('a heading reads the endonym ' + endonym +
                               ' — headings are English (owner 2026-08-13), ' +
                               'and two name sources cannot agree by accident');
                    }
                  }
                  // A door says how many are behind it, and the door holding
                  // the chosen variant is lit.
                  const doors = rows.filter(
                    (r) => r.querySelector('.lang-group'));
                  if (!doors.length) {
                    bad.push('no language opens into its variants — the list ' +
                             'is flat, only shorter');
                  }
                  for (const d of doors) {
                    const n = d.querySelector('.dict-status');
                    // A NUMBER AND A WORD. The first version of this check
                    // demanded a bare integer and passed a card whose row read
                    // "Srpski" over a naked "2" — a count with nothing saying
                    // what it counts, on the line every other row uses for a
                    // plain statement.
                    if (!n || !/^[0-9]+\s+choices?$/.test(
                          n.textContent.trim())) {
                      bad.push('a language door does not say how many ' +
                               'choices are behind it');
                    }
                  }
                  const lit = doors.filter(
                    (d) => d.querySelector('.lang-group.sel'));
                  if (lit.length !== 1) {
                    bad.push(lit.length + ' doors are marked as holding his ' +
                             'choice — the staged choice is sr-RS, so exactly ' +
                             'one must be');
                  }
                  // THE CLOSED ROW STATES THE ACTIVE CHOICE (owner report
                  // 2026-08-15): "English — Voice 13 (United States)" /
                  // "Serbian — Latin", read WITHOUT opening the door. Checked
                  // on the CARD rather than only in the arithmetic's gate,
                  // because the arithmetic proving `activeGroupVariant`
                  // correct says nothing about whether the row ever calls it.
                  if (lit.length === 1 && activeSubstr) {
                    const nameEl = lit[0].querySelector('.dict-name');
                    const activeEl = lit[0].querySelector('.dict-name-active');
                    if (!activeEl || !activeEl.textContent.trim()) {
                      bad.push('the row holding his choice states no active ' +
                               'variant — he cannot see what is chosen ' +
                               'without opening the door');
                    } else if (activeEl.textContent.indexOf(activeSubstr) < 0) {
                      bad.push('the active-choice suffix reads "' +
                               activeEl.textContent + '", expected it to ' +
                               'name "' + activeSubstr + '"');
                    }
                    // The language NAME must survive beside the suffix —
                    // task 163's rule for this row, not merely a check that
                    // SOMETHING is written.
                    const langEl = nameEl && nameEl.querySelector('.dict-name-lang');
                    if (!langEl || !langEl.textContent.trim()) {
                      bad.push('the active-choice row lost its own language ' +
                               'name — the suffix must never replace it');
                    }
                  }
                  // No door is marked lit AND carries a suffix when nothing
                  // was chosen inside it — a stale or invented suffix on a
                  // group that does not hold the choice would be worse than
                  // none.
                  for (const d of doors) {
                    if (d.querySelector('.lang-group.sel')) continue;
                    if (d.querySelector('.dict-name-active')) {
                      bad.push('a door NOT holding his choice still shows an ' +
                               'active-choice suffix');
                    }
                  }
                  // NO ROW-HEIGHT CLAIM IS MADE HERE, deliberately. The
                  // first version of this check asserted every row within 6 px
                  // of its siblings and failed on the card's own correct
                  // behaviour twice: a row saying "no preview voice on this
                  // device" is honestly three lines tall, and a long endonym
                  // wraps on a 412 px phone. Both predate grouping. Uniform row
                  // height is the LAYOUT LIST's promise (task 163, its own
                  // check above) and never this card's, and inventing a promise
                  // mid-round to give a new check something to measure is how a
                  // gate starts testing itself instead of the product. What
                  // this card promises about size is that nothing is CUT, and
                  // the panel sweep measures that in all eight looks.
                  return bad;
                }"""

# THE DICTATION CARD SAYS WHOSE LANGUAGES THESE ARE, AND WHICH OF THEM HE CAN
# HEAR (owner 2026-08-09, task 127 — a screenshot of this card and: "koristim
# dva uredjaja … treba da kaze OVAJ UREDJAJ ima te i te jezike" plus "treba da
# mogu da CUJEM da bih odabrao").  # lang-ok: owner quote
#
# The panel sweep measures the card's fit and contrast in all eight looks; what
# it cannot say is whether the three ROW STATES are on it at all — and a row
# state nobody stages is exactly where this project's bugs keep arriving. The
# device name is measured, never merely present: the fallback wording ("this
# device") renders perfectly while the real path is broken, so the card must
# contain the model THIS context's own User-Agent carries.
#
# Moved out of test_layout_audit.py 2026-08-13 (THE STRUCTURE LAW's wall), to the
# module that already owns the panel stages and their measurements.
DICT_CHECK_JS = """(model) => {
                  const bad = [];
                  const card = document.querySelector('#dictation-panel .sets-card');
                  const cr = card.getBoundingClientRect();
                  const who = card.querySelector('.dict-device');
                  const said = who ? who.textContent.trim() : '';
                  if (!said) bad.push('the card does not say which device it describes');
                  else if (said.indexOf(model) < 0) {
                    bad.push('the device line does not name this device: "' + said + '"');
                  }
                  const rows = [...card.querySelectorAll('.dict-row')];
                  const play = rows.filter((r) => r.querySelector('.dict-listen'));
                  const noted = rows.filter((r) => r.querySelector('.dict-note'));
                  if (play.length < 2) bad.push('no row offers a listen button');
                  if (!noted.length) bad.push('no row states the honest limit');
                  // The two limits are DIFFERENT facts and each has to be on
                  // screen: no voice for this language, and a voice with no
                  // sample sentence written for it.
                  const said2 = noted.map((r) => r.querySelector('.dict-note').textContent);
                  if (!said2.some((t) => /preview voice/.test(t))) {
                    bad.push('the "no voice on this device" row is not staged');
                  }
                  if (!said2.some((t) => /sample sentence/.test(t))) {
                    bad.push('the "no sample sentence" row is not staged');
                  }
                  for (const b of card.querySelectorAll('.dict-listen')) {
                    const r = b.getBoundingClientRect();
                    if (r.width < 40 || r.height < 40) {
                      bad.push('a listen button is ' + Math.round(r.width) + 'x' +
                               Math.round(r.height) + ' — not a finger target');
                    }
                    if (r.left < cr.left - 1 || r.right > cr.right + 1 ||
                        r.top < cr.top - 1 || r.bottom > cr.bottom + 1) {
                      bad.push('a listen button leaves the card');
                    }
                    // …and it never lands ON the row's own text.
                    const name = b.closest('.dict-row').querySelector('.dict-name');
                    const nr = name.getBoundingClientRect();
                    if (nr.right > r.left + 1) {
                      bad.push('the language name runs under its listen button');
                    }
                  }
                  return bad;
                }"""

