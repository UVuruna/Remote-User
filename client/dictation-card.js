// THE DICTATION LANGUAGE CARD — what THIS device hears, and which script it
// writes back. Split out of client/panels.js on 2026-08-13 when that file
// crossed the structure law's 1,000-line wall, and split BY RESPONSIBILITY
// rather than by line count: panels.js answers "which controls ride on the
// phone" (the sets picker, the command chooser), while this file answers a
// question about the DEVICE IN HIS HAND — which languages it can recognise,
// which of its own voices can speak them, and what its samples sound like.
// Two subjects in one file is what let a language list grow into the pile the
// owner reported.
//
// It also owns the two rows a GROUPED language list is built from
// (`langGroupRow` / `langBackRow`), which the notification-voice card in
// client/notify.js uses — that file is loaded after this one, the same
// arrangement `dictVoices` already relied on. The grouping arithmetic itself
// lives in client/lang-groups.js, pure so its gate can run it whole.

// --- Dictation setup card (owner round 2, 2026-08-05) ----------------------
// The dictation language is a USER CHOICE — pinning to the phone's first
// system locale transcribed the owner's Serbian as English garbage (his
// phone lists English first). Opens on the FIRST Mic tap and from the
// Settings set's Language button; plain language, persistent until closed,
// the row states say exactly what will happen (Tailscale-card pattern).

const dictPanel = document.getElementById("dictation-panel");
const dictOpened = { t: 0 };
ghostClickArmor(dictPanel, dictOpened);

const DICT_STATUS = {
  ready: "ready on this phone",
  download: "model will download — online until it arrives",
  online: "recognized over the internet",
};

// ── THE CARD NAMES THE DEVICE IT IS DESCRIBING (owner 2026-08-09) ──────────
// His report came with a screenshot of this very card:
// lang-ok: owner quote
//   *"to je samo za Samsung a koristim dva uredjaja — jezik, ako je vec vezan
//    za uredjaj, treba da kaze OVAJ UREDJAJ ima te i te jezike"*
//
// The list is per DEVICE — system locales, keyboard languages and installed
// models are all facts about the phone in his hand — and he owns two of them.
// A card that names none reads as if these were THE languages, so a language
// missing from the other device looks like a bug in the app instead of a
// difference between two phones.
//
// THE NAME IS NEVER GUESSED. Two sources, in this order, and a plain "this
// device" when neither can answer:
//
//  1. `navigator.userAgent` — an Android WebView's platform group ends with
//     the model ("Linux; Android 15; SM-X910"). Read synchronously, so the
//     card's FIRST paint already carries it.
//  2. `navigator.userAgentData.getHighEntropyValues(["model"])` — the same
//     fact for the WebViews where the UA no longer carries it: Chromium's
//     User-Agent reduction freezes the model token to the literal "K", and a
//     card announcing "K" would be worse than one saying nothing. It is a
//     PROMISE, so it lands after the first paint and may only ever REPLACE a
//     name we do not have.
//
// No bridge method is asked for, deliberately. The shell could answer this in
// one line, but the page is served by the PC while the shell is installed
// separately (the reason written over `speakAs` in Bridge.kt) — a header that
// depended on a NEW bridge method would show nothing at all on the shell he
// has installed today, which is the device this card exists to describe.
const DICT_MODEL_JUNK = new Set(
  ["k", "wv", "build", "unknown", "generic", "android", "linux"]);

let dictDevice = "";        // "" = we do not know, and the card says exactly that
let dictDeviceAsked = false;

function dictModelFromUa() {
  const group = /\(([^)]*)\)/.exec(navigator.userAgent || "");
  if (!group) return "";
  const fields = group[1].split(";").map((s) => s.trim()).filter(Boolean);
  const at = fields.findIndex((f) => /^Android\b/i.test(f));
  if (at < 0) return "";
  for (const field of fields.slice(at + 1)) {
    // "SM-X910 Build/TP1A.220624.014" — the build tail is not a device name.
    const model = field.replace(/\s+Build\/.*$/i, "").trim();
    if (model && !DICT_MODEL_JUNK.has(model.toLowerCase())) return model;
  }
  return "";
}

/** Fills `dictDevice` from the UA at once, and asks the client-hints API for
 *  the same fact in the background. `onLate` runs only if that answer arrives
 *  and is BETTER than what we already show. */
function dictAskDevice(onLate) {
  if (!dictDevice) dictDevice = dictModelFromUa();
  if (dictDeviceAsked) return;
  dictDeviceAsked = true;
  const data = navigator.userAgentData;
  if (!data || !data.getHighEntropyValues) return;
  try {
    data.getHighEntropyValues(["model"]).then((v) => {
      const model = String((v && v.model) || "").trim();
      if (!model || DICT_MODEL_JUNK.has(model.toLowerCase())) return;
      if (model === dictDevice) return;
      dictDevice = model;
      onLate();
    }).catch(() => {});
  } catch {
    // An older WebView without the API — the UA name (or none) stands.
  }
}

function dictDeviceLine() {
  return dictDevice
    ? `These are the languages on ${dictDevice} — your other device has its own list.`
    : "These are the languages on this device — your other device has its own list.";
}

function dictShowDevice() {
  const line = dictPanel.querySelector(".dict-device");
  if (line) line.textContent = dictDeviceLine();   // in place: no re-render
}

// ── HEAR IT BEFORE CHOOSING (owner 2026-08-09) ────────────────────────────
// lang-ok: owner quote
//   *"treba da mogu da CUJEM da bih odabrao, dakle da ima i mikrofon da cujem
//    kako zvuci taj jezik"*
//
// The voices are ALREADY known to this page: `Android.ttsVoices()` is what
// client/notify.js forwards to the PC once per connection so the desktop
// Settings window can offer a voice for spoken notices. Same source, no
// second one — and `Android.speakAs(text, voice, rate)` is the same call the
// PC's notices are read out with.
//
// THE HONEST LIMIT IS THE FEATURE'S OWN RULE, never a footnote. Recognition
// languages and text-to-speech voices are DIFFERENT sets: a language he can
// dictate in may have no voice on this device at all. Such a row says so
// quietly and offers no button. What it must never do is speak the sample in
// the engine's default voice — he would hear English, believe he had just
// heard the language he tapped, and choose by it.
const DICT_NO_VOICE = "no preview voice on this device";
const DICT_NO_SAMPLE = "no sample sentence for this language yet";

/** Every text-to-speech voice this device has, or `null` when previewing is
 *  impossible here at all (a shell too old for either method, a dev browser,
 *  an engine that threw). `[]` is a different answer from `null`: the device
 *  answered, and it has none. */
function dictVoices() {
  try {
    const a = window.Android;
    if (!a || !a.ttsVoices || !a.speakAs) return null;
    const list = JSON.parse(a.ttsVoices() || "[]");
    return Array.isArray(list) ? list : [];
  } catch {
    return null;
  }
}

function dictLangKey(tag) {
  return String(tag || "").replace(/_/g, "-").toLowerCase().split("-")[0] || "";
}

/** The voice that may speak this row, or null.
 *
 *  THE RULE IS THE LANGUAGE, then the region. A row's tag and a voice's
 *  locale are written differently by different parts of Android ("sr-RS" vs
 *  "sr-Latn-RS"), so the language subtag decides whether a voice is eligible
 *  at all and an exact tag match only decides WHICH of several is used — a
 *  Brazilian row takes the Brazilian voice when the device has both, and the
 *  European one rather than nothing when it does not. Speaking Portuguese
 *  with the wrong accent still tells him what Portuguese sounds like;
 *  speaking English at him does not. */
function dictVoiceFor(tag, voices) {
  const want = dictLangKey(tag);
  if (!want || !voices) return null;
  const norm = String(tag || "").replace(/_/g, "-").toLowerCase();
  let other = null;
  for (const v of voices) {
    const loc = String((v && v.locale) || "").replace(/_/g, "-").toLowerCase();
    if (dictLangKey(loc) !== want) continue;
    if (loc === norm) return v;
    if (!other) other = v;
  }
  return other;
}

// THE SAMPLE IS A WRITTEN SENTENCE, NEVER A TRANSLATION MADE AT RUNTIME.
// One short line per language, all saying the same thing, so what changes
// between two taps is the SOUND and nothing else. A language missing from
// this table has NO sample — its row says so and offers no button, because a
// machine-translated or English sentence read by a Japanese voice teaches him
// nothing about dictating in Japanese.
//
// Keyed by BCP-47, longest prefix wins (`dictSample`), which is why only the
// languages whose regions genuinely sound apart carry a second key.
// lang-ok-begin: the product's own sample sentences — one per language, the
// point of the feature is to HEAR each one in its own language
const DICT_SAMPLES = {
  en: "This is how this language sounds.",
  sr: "Ovako zvuči ovaj jezik.",
  hr: "Ovako zvuči ovaj jezik.",
  bs: "Ovako zvuči ovaj jezik.",
  sl: "Takole zveni ta jezik.",
  mk: "Вака звучи овој јазик.",
  bg: "Така звучи този език.",
  ru: "Вот так звучит этот язык.",
  uk: "Ось так звучить ця мова.",
  de: "So klingt diese Sprache.",
  nl: "Zo klinkt deze taal.",
  fr: "Voici comment sonne cette langue.",
  es: "Así suena este idioma.",
  ca: "Així sona aquesta llengua.",
  it: "Ecco come suona questa lingua.",
  pt: "É assim que esta língua soa.",
  "pt-br": "É assim que este idioma soa.",
  pl: "Tak brzmi ten język.",
  cs: "Takto zní tento jazyk.",
  sk: "Takto znie tento jazyk.",
  hu: "Így hangzik ez a nyelv.",
  ro: "Așa sună această limbă.",
  el: "Έτσι ακούγεται αυτή η γλώσσα.",
  tr: "Bu dil böyle geliyor kulağa.",
  sv: "Så här låter det här språket.",
  da: "Sådan lyder dette sprog.",
  nb: "Slik høres dette språket ut.",
  no: "Slik høres dette språket ut.",
  fi: "Tältä tämä kieli kuulostaa.",
  ar: "هكذا تبدو هذه اللغة.",
  he: "כך נשמעת השפה הזאת.",
  hi: "यह भाषा ऐसी सुनाई देती है।",
  th: "ภาษานี้ฟังดูแบบนี้",
  vi: "Ngôn ngữ này nghe như thế này.",
  id: "Beginilah bunyi bahasa ini.",
  ms: "Beginilah bunyi bahasa ini.",
  ja: "この言語はこのように聞こえます。",
  ko: "이 언어는 이렇게 들립니다.",
  zh: "这门语言听起来是这样的。",
  "zh-hant": "這個語言聽起來是這樣的。",
  "zh-tw": "這個語言聽起來是這樣的。",
  "zh-hk": "這個語言聽起來是這樣的。",
};
// lang-ok-end

function dictSample(tag) {
  const parts = String(tag || "").replace(/_/g, "-").toLowerCase()
    .split("-").filter(Boolean);
  for (let n = parts.length; n > 0; n--) {
    const key = parts.slice(0, n).join("-");
    if (DICT_SAMPLES[key]) return DICT_SAMPLES[key];
  }
  return "";
}

// ONE SAMPLE AT A TIME, AND NEVER A QUEUE. `Notifier.speak` hands the text to
// TextToSpeech with QUEUE_ADD and the shell exposes no way to stop it, so a
// second tap during a sample could not replace the first — it would line up
// behind it, and worse: the engine's voice is chosen per CALL but applies to
// the whole queue, so both samples would then be spoken in the SECOND
// language's voice. A tap while one is speaking is therefore ignored, and the
// button that is speaking shows it.
//
// The window is an ESTIMATE, because nothing comes back from the engine to
// the page when it finishes. It is rounded up on purpose: too long costs him
// a short wait, too short costs him a sample in the wrong voice — which is
// the one thing this whole control exists to prevent.
function dictSampleMs(text) {
  return Math.max(2500, Math.min(7000, 1200 + text.length * 100));
}

let dictSpeakingTag = "";
let dictSpeakingTimer = null;

function dictListen(lang, voice, btn) {
  if (dictSpeakingTag) return;               // one at a time — see above
  const text = dictSample(lang.tag);
  if (!text || !voice) return;
  try {
    window.Android.speakAs(text, voice.name || "", 1);
  } catch {
    showToast("This device could not play the sample");
    return;
  }
  dictSpeakingTag = lang.tag;
  btn.classList.add("busy");
  clearTimeout(dictSpeakingTimer);
  dictSpeakingTimer = setTimeout(() => {
    dictSpeakingTag = "";
    btn.classList.remove("busy");   // harmless if the card was re-rendered
  }, dictSampleMs(text));
}

function dictListenButton(lang, voice) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "dict-listen" + (lang.tag === dictSpeakingTag ? " busy" : "");
  btn.innerHTML = svg("listen");
  // The name of the language, not "play": a screen reader saying "button"
  // over a speaker glyph tells him nothing about which row it belongs to.
  btn.setAttribute("aria-label", `Listen to ${lang.name}`);
  btn.title = `Listen to ${lang.name}`;
  keepRowTap(btn, () => dictListen(lang, voice, btn));
  return btn;
}

// --- The two rows a grouped language list is made of ----------------------
//
// Owner 2026-08-13. Both language lists (this card and the notification-voice
// one) are language-first, so both need a row that OPENS a language and a row
// that comes BACK out of one. They live here, once, and notify.js uses them
// because it is loaded after this file — the same reason `dictVoices` is
// shared rather than copied. Two copies of a row is how two cards start
// looking like two different apps.

/** A language row that opens into its variants.
 *
 *  It says how many are inside, because that number is the whole reason the
 *  row is a door rather than a choice, and it marks the row that HOLDS his
 *  current choice — otherwise opening the card would show him no chosen row
 *  anywhere and read as though his choice had been forgotten.
 *
 *  `activeLabel` (owner report 2026-08-15, his screenshot of the voice card:
 *  no way to tell WHICH variant is chosen without opening the door again) is
 *  that variant's own label — "Latin", "Voice 13 (United States)" — and is
 *  written on the SAME row as the language name rather than folded into one
 *  interpolated string, because task 163's rule for this row is that the
 *  language name must never be cut in favour of the suffix: two spans can
 *  shrink independently, one string cannot. `lang-groups.js`'s
 *  `activeGroupVariant` is what finds it — this function only draws what it
 *  is handed, so a card that never asks the question never shows a stale one.
 *
 *  Drawn arrow, never a font glyph: the ✥ move handle came out a blunt cross
 *  on his own phone (2026-08-05), and client/icons.js is the answer to that. */
function langGroupRow(group, hasChosen, activeLabel, onOpen) {
  const row = document.createElement("div");
  row.className = "dict-row";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "sets-row dict lang-group" + (hasChosen ? " sel" : "");
  const txt = document.createElement("span");
  txt.className = "dict-name";
  const nameSpan = document.createElement("span");
  nameSpan.className = "dict-name-lang";
  nameSpan.textContent = group.name;
  txt.appendChild(nameSpan);
  if (hasChosen && activeLabel) {
    const sep = document.createElement("span");
    sep.className = "dict-name-sep";
    sep.textContent = "—";
    const act = document.createElement("span");
    act.className = "dict-name-active";
    act.textContent = activeLabel;
    txt.append(sep, act);
  }
  const count = document.createElement("span");
  count.className = "dict-status";
  // A BARE NUMBER IS NOT A SENTENCE. Photographing the card showed "Srpski"
  // with a naked "2" under it, which says nothing about what the 2 counts —
  // and this line sits exactly where every other row of the card puts a plain
  // statement ("ready on this phone", "recognized over the internet").
  count.textContent = group.variants.length === 1
    ? "1 choice" : `${group.variants.length} choices`;
  const arrow = document.createElement("span");
  arrow.className = "lang-arrow";
  arrow.innerHTML = svg("arrowr");
  btn.append(txt, count, arrow);
  btn.setAttribute("aria-label", hasChosen && activeLabel
    ? `${group.name} — ${activeLabel} chosen — ${group.variants.length} to choose from`
    : `${group.name} — ${group.variants.length} to choose from`);
  keepRowTap(btn, onOpen);
  row.appendChild(btn);
  return row;
}

/** The way back out of one language, and the heading of where he is.
 *
 *  It carries the language NAME rather than the word "Back" alone: it is the
 *  only thing on screen saying which language these rows belong to, since the
 *  rows themselves deliberately no longer repeat it. */
function langBackRow(name, onBack) {
  const row = document.createElement("div");
  row.className = "dict-row";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "sets-row dict lang-back";
  const arrow = document.createElement("span");
  arrow.className = "lang-arrow";
  arrow.innerHTML = svg("arrowl");
  const txt = document.createElement("span");
  txt.className = "dict-name";
  txt.textContent = name;
  btn.append(arrow, txt);
  btn.setAttribute("aria-label", `Back to all languages (leaving ${name})`);
  keepRowTap(btn, onBack);
  row.appendChild(btn);
  return row;
}

/** One candidate row: the choice on the left, the listen button on the right.
 *
 *  The button is a SIBLING of the <label>, never a child of it. A click
 *  anywhere inside a label activates the control the label owns, so a speaker
 *  button nested in this row would also SELECT that language — the tap that
 *  means "let me hear it before I decide" would have decided. */
function dictRow(lang, chosen, voices, variantLabel, groupName) {
  const row = document.createElement("div");
  row.className = "dict-row";
  const label = document.createElement("label");
  label.className = "sets-row dict" + (lang.tag === chosen ? " sel" : "");
  const rb = document.createElement("input");
  rb.type = "radio";
  rb.name = "dict-lang";
  rb.checked = lang.tag === chosen;
  rb.addEventListener("change", () => {
    try { window.Android.voiceSetLang(lang.tag); } catch {}
    renderDictationCard(); // statuses may change (download starts)
  });
  const txt = document.createElement("span");
  txt.className = "dict-name";
  // INSIDE a language, the row wears only what tells it from its siblings —
  // the script or the region (lang-groups.js), because the back row above is
  // already the language's name.
  //
  // Outside one it is NAMED IN ENGLISH (owner 2026-08-13). It used to wear
  // `lang.name`, the endonym Android hands us, and that is the half of the
  // divergence the arithmetic's gate could not see: it checks a GROUP's heading,
  // while on his phone almost every language is a group of ONE and its row is
  // drawn straight from the platform's word. Only the phone audit caught it, by
  // opening the picture and reading "Deutsch" beside "Serbian". `groupName` is
  // that group's English name; `langFullName` covers the flat "More languages"
  // bag, where nothing grouped the rows and the region must therefore be said.
  txt.textContent = variantLabel || groupName
    || langFullName(lang.tag, lang.name);
  const st = document.createElement("span");
  st.className = "dict-status";
  st.textContent = DICT_STATUS[lang.status] || "";
  label.append(rb, txt, st);
  row.appendChild(label);

  // Only a row that can be played gets a button; the others say WHY, quietly
  // and per row — but only while previewing works here at all, since a device
  // with no voices would otherwise repeat one sentence down the whole card
  // (the card states that case once, above the list).
  const voice = dictVoiceFor(lang.tag, voices);
  const sample = dictSample(lang.tag);
  if (voice && sample) {
    row.appendChild(dictListenButton(lang, voice));
  } else if (voices && voices.length) {
    const note = document.createElement("span");
    note.className = "dict-note";
    note.textContent = voice ? DICT_NO_SAMPLE : DICT_NO_VOICE;
    label.appendChild(note);
  }
  return row;
}

// The "More languages" section stays collapsed until asked (owner round 4:
// the phone's own languages first, everything downloadable/online behind
// one row) — remembered while the card is open, reset on close.
let dictMoreOpen = false;

// WHICH language is open, or "" for the list of languages (owner 2026-08-13:
// *"po jezicimo ... npr Engleski pa kad otvorimo ponudi se Voice 1,2,3"*).
// lang-ok: owner quote
// Reset on close like `dictMoreOpen` — re-opening the card shows the list.
let dictOpenLang = "";

/** Every row of ONE language, in the order the platform offered them.
 *
 *  Built from the WHOLE candidate list rather than from the section he opened
 *  it in: a language can have a ready variant among the phone's own and a
 *  downloadable one among the extras (his Serbian is exactly that — a keyboard
 *  subtype for one script, a downloadable model for the other), and splitting
 *  one language's scripts across two sections is the pile this round removes. */
function dictGroups(langs) {
  return groupByLanguage(langs, (l) => l.tag, (l) => l.name);
}

/** The collapsed "More languages" section — or the extras themselves once he
 *  has opened it (owner round 4, 2026-08-05: the phone's own languages first,
 *  everything downloadable or online behind one row).
 *
 *  Its own function since 2026-08-13, and not merely for tidiness: it is the
 *  one part of this list that has NO meaning while standing INSIDE a language.
 *  It is a door out of the list of languages, not a row of it. */
function dictMoreRow(list, extra, chosen, voices) {
  const rest = extra.filter((l) => l.tag !== chosen);
  if (rest.length && !dictMoreOpen) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "sets-row dict-more";
    more.textContent = `More languages (${rest.length})…`;
    // This row's ellipsis means "there is more behind me", not "your text was
    // cut" — the audit's truncation check (tests/test_layout_audit.py) reads
    // this marker, so the ONE deliberate ellipsis this app draws is declared
    // in the product instead of being spelled out in a test's allow-list.
    more.dataset.opensMore = "";
    keepRowTap(more, () => {
      dictMoreOpen = true;
      renderDictationCard();
    });
    list.appendChild(more);
  } else if (dictMoreOpen) {
    rest.forEach((lang) => list.appendChild(dictRow(lang, chosen, voices)));
  }
}

function renderDictationCard() {
  let langs = [];
  let chosen = "";
  let muted = true;
  try {
    langs = JSON.parse(window.Android.voiceLangs());
    chosen = window.Android.voiceChosen();
    if (window.Android.voiceMuteBeeps) muted = window.Android.voiceMuteBeeps();
  } catch {}
  const voices = dictVoices();
  dictAskDevice(dictShowDevice);
  dictPanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card card-columns";
  card.innerHTML = `<h2>Dictation language</h2>
    <p class="sets-sub">Pick the language you speak — dictation understands that one. Change it any time: Settings wheel → Language.</p>`;
  // WHICH device these languages belong to (owner 2026-08-09). Built as a
  // node with `textContent`, never interpolated into the card's HTML: the
  // name comes from the User-Agent, which is a string this page did not write.
  const who = document.createElement("p");
  who.className = "sets-sub dict-device";
  who.textContent = dictDeviceLine();
  card.appendChild(who);
  const list = document.createElement("div");
  list.className = "sets-list";
  const mine = langs.filter((l) => !l.extra);
  const extra = langs.filter((l) => l.extra);

  // ONE LANGUAGE OPEN: its variants and nothing else, whichever section they
  // came from. Nothing below runs — "More languages" is a door out of the
  // list of languages, and it has no meaning while standing inside one.
  const openGroup = dictOpenLang
    ? dictGroups(langs).find((g) => g.key === dictOpenLang)
    : null;
  if (openGroup) {
    list.appendChild(langBackRow(openGroup.name, () => {
      dictOpenLang = "";
      renderDictationCard();
    }));
    for (const v of openGroup.variants) {
      list.appendChild(dictRow(v.row, chosen, voices, v.label));
    }
  } else {
    // A chosen extra language surfaces with the phone's own — the current
    // choice must never hide behind the collapsed section.
    const shown = mine.concat(extra.filter((l) => l.tag === chosen));
    for (const g of dictGroups(shown)) {
      // A language with ONE variant stays a plain row: a door into a list of
      // one shows him nothing he could not already see, and it would put his
      // only Serbian behind a tap.
      if (g.variants.length === 1) {
        // Its group's ENGLISH name, never the row's own endonym — a group of one
        // is still a group, and it is the shape his phone mostly has.
        list.appendChild(
          dictRow(g.variants[0].row, chosen, voices, "", g.name));
      } else {
        const active = activeGroupVariant(g, (v) => v.tag === chosen);
        const row = langGroupRow(g, !!active, active ? active.label : "", () => {
          dictOpenLang = g.key;
          renderDictationCard();
        });
        // A LANGUAGE IS ONE SOUND, so a group row can still be HEARD — which
        // is half of what he asked for ("koji mozemo da poslusamo") and was
        // lost the moment his two most-used languages became doors: the phone
        // audit caught the top level offering no preview at all.
        // lang-ok: owner quote
        // Cyrillic and Latin Serbian are the same speech — the script decides
        // how it is WRITTEN — so previewing the group's first variant is not a
        // choice made for him. The voice card deliberately does NOT do this:
        // there the variants are different SPEAKERS, and picking one to stand
        // for the language would be exactly the arbitrary choice this avoids.
        const gv = dictVoiceFor(g.variants[0].tag, voices);
        if (gv && dictSample(g.variants[0].tag)) {
          row.appendChild(dictListenButton(g.variants[0].row, gv));
        }
        list.appendChild(row);
      }
    }
    dictMoreRow(list, extra, chosen, voices);
  }
  card.appendChild(list);

  // Why no row can be played — said ONCE, and only when it is true of the
  // whole card. Per-row it would be the same sentence repeated down the list;
  // left out entirely, a missing speaker button would read as a bug.
  if (!voices || !voices.length) {
    const why = document.createElement("p");
    why.className = "sets-sub dict-note";
    why.textContent = voices
      ? "This device has no text-to-speech voice installed, so no language can be played here."
      : "Hearing a language needs the updated app — update it from the banner.";
    card.appendChild(why);
  }

  // Listening beeps (owner round 4): Android tones every round start/stop
  // and rounds cycle on each silence — muted while dictating by default.
  const muteRow = document.createElement("label");
  muteRow.className = "sets-row apps";
  const muteCb = document.createElement("input");
  muteCb.type = "checkbox";
  muteCb.checked = muted !== false;
  muteCb.addEventListener("change", () => {
    try { window.Android.voiceSetMuteBeeps(muteCb.checked); } catch {}
  });
  muteRow.append(muteCb, document.createTextNode("Mute listening beeps while dictating"));
  card.appendChild(muteRow);

  const done = document.createElement("button");
  done.type = "button";
  done.className = "sets-done";
  done.textContent = "Done";
  keepRowTap(done, closeDictationPanel);
  card.appendChild(done);

  dictPanel.appendChild(card);
  dictPanel.hidden = false;
}

function openDictationPanel() {
  if (!IN_APP || !window.Android.voiceLangs) {
    showToast("Voice input needs the updated app — update from the banner");
    return;
  }
  renderDictationCard();
  dictOpened.t = performance.now();
}

function closeDictationPanel() {
  dictPanel.hidden = true;
  dictPanel.innerHTML = "";
  dictMoreOpen = false;
  refreshMicButtons(); // a download may have started — show it on the Mic
}

dictPanel.addEventListener("pointerdown", (e) => {
  if (e.target === dictPanel) closeDictationPanel(); // backdrop tap = done
});

