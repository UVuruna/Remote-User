// Overlay panels opened from the Settings set: the Sets picker and the
// Quality panel. Split out of controls.js (THE STRUCTURE LAW) — controls.js
// owns the D-pad groups, wheel and button actions; this module owns the
// full-screen card overlays those actions open. Loaded after controls.js
// (uses its prefs helpers, wheel state and keepFocus); controls.js calls
// openSetsPanel/openQualityPanel only at runtime, after every script loaded.

// --- Sets picker (Settings → Sets, owner 2026-08-05) ----------------------
// Chooses WHICH sets ride in the wheel on THIS phone: the required built-ins
// are always on; the rest toggle up to WHEEL_MAX total (creation on the
// desktop — creation never happens here) plus the app-shortcuts toggle.
// Stored per device via the prefs bridge, overriding the desktop defaults.

const setsPanel = document.getElementById("sets-panel");

// Ghost-click armor (owner bug report 2026-08-05 — "the picker rotates"):
// the tap that OPENS a panel can still deliver a late synthetic click, which
// then lands on whichever row the panel happened to open under the finger —
// silently toggling it. Swallow every click in the first moments after
// opening; no human re-taps that fast.
const GHOST_CLICK_MS = 400;

function ghostClickArmor(panel, openedAt) {
  panel.addEventListener(
    "click",
    (e) => {
      if (performance.now() - openedAt.t < GHOST_CLICK_MS) {
        e.preventDefault();
        e.stopPropagation();
      }
    },
    true
  );
}

const setsOpened = { t: 0 };
ghostClickArmor(setsPanel, setsOpened);

function setsRow(s, locked) {
  const row = document.createElement("label");
  row.className = "sets-row";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = locked || setOn(s);
  cb.disabled = locked;
  if (!locked) {
    cb.addEventListener("change", () => {
      // Both tick paths ask the SAME question the same way (owner 2026-08-06):
      // write the choice, then measure — the two used to disagree (this one
      // measured before saving with >=, the app one after saving with >), and
      // a rule the code states twice is a rule the code will break once.
      const p = setsPrefs();
      const was = p.state[s.name];
      p.state[s.name] = cb.checked;
      saveSetsPrefs(p);
      if (cb.checked && visibleCount() > WHEEL_MAX) {
        cb.checked = false;
        if (was === undefined) delete p.state[s.name]; else p.state[s.name] = was;
        saveSetsPrefs(p);
        showToast(`The wheel holds ${WHEEL_MAX} sets — untick one first`);
        return;
      }
      refreshCategories();
      refreshSetsMeta();  // the counter and the live badges follow every tick
    });
  }
  const ic = document.createElement("span");
  ic.className = "sets-ic";
  ic.innerHTML = svg(s.icon && ICONS[s.icon] ? s.icon : "grid");
  row.append(cb, ic, document.createTextNode(s.name + (locked ? " — always on" : "")));
  return row;
}

// One app-aware set (VSCode, Claude, Chrome, Explorer). It costs a wheel slot
// like any other set, and it also carries a LIVE badge: which of them is on
// the wheel right now, for the layout currently focused (owner 2026-08-06 —
// "hoću da bude štiklirano pored onoga koji je aktivan, da bude uočljivo").
// Ticked means allowed; the badge means actually riding this second.
function appSetRow(s) {
  const row = document.createElement("label");
  row.className = "sets-row app";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = appSetOn(s);
  cb.addEventListener("change", () => {
    const p = setsPrefs();
    const was = p.appState[s.name];
    p.appState[s.name] = cb.checked;
    saveSetsPrefs(p);
    // An app set costs a wheel slot like any other (owner 2026-08-06) — and
    // VSCode + Claude cost two, because a Claude tab shows both. Refuse the
    // tick that would overflow instead of letting the wheel drop a set the
    // owner already chose, and say why.
    if (cb.checked && visibleCount() > WHEEL_MAX) {
      cb.checked = false;
      if (was === undefined) delete p.appState[s.name]; else p.appState[s.name] = was;
      saveSetsPrefs(p);
      showToast(`The wheel holds ${WHEEL_MAX} sets — untick one first`);
      return;
    }
    refreshCategories();
    refreshSetsMeta();
  });
  const ic = document.createElement("span");
  ic.className = "sets-ic";
  ic.innerHTML = svg(s.icon && ICONS[s.icon] ? s.icon : "newwin");
  const badge = document.createElement("span");
  badge.className = "sets-live";
  badge.dataset.set = s.name;
  badge.textContent = "on the wheel now";
  row.append(cb, ic, document.createTextNode(s.name), badge);
  return row;
}

// The two things that change without a re-render: the counter line and which
// app sets are live. Updated in place — rebuilding the card would re-arm the
// ghost-click armor and swallow the owner's next tick.
function refreshSetsMeta() {
  const count = setsPanel.querySelector(".sets-count");
  if (count) {
    const reserve = appSetReserve();
    count.textContent = `${visibleCount()} of ${WHEEL_MAX} used`
      + (reserve ? ` — ${reserve} held for app shortcuts` : "");
  }
  const live = new Set(visibleAppSets().map((s) => s.name));
  for (const b of setsPanel.querySelectorAll(".sets-live")) {
    b.classList.toggle("on", live.has(b.dataset.set));
  }
}

function openSetsPanel() {
  setsPanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card card-columns";
  const reserve = appSetReserve();
  card.innerHTML = `<h2>Wheel sets</h2>
    <p class="sets-sub">Mouse, Input and Settings are always in the wheel. Pick the rest — up to ${WHEEL_MAX} in total, app shortcuts included. New sets are made on the PC (Remote User window → Controls…).</p>
    <p class="sets-sub sets-count">${visibleCount()} of ${WHEEL_MAX} used${reserve ? ` — ${reserve} held for app shortcuts` : ""}</p>`;

  const list = document.createElement("div");
  list.className = "sets-list";
  categories.forEach((s) => list.appendChild(setsRow(s, !!s.required)));
  customSets.forEach((s) => list.appendChild(setsRow(s, false)));
  card.appendChild(list);

  // App sets are ticked ONE BY ONE (owner 2026-08-05, when Claude joined
  // VSCode on the same window): a single master switch could only say "all
  // app shortcuts or none", and two sets riding the same process is exactly
  // the case where you want one of them gone. The master switch stays as the
  // heading's own checkbox — it still turns the whole group off in one tap.
  const appHead = document.createElement("label");
  appHead.className = "sets-row apps";
  const appCb = document.createElement("input");
  appCb.type = "checkbox";
  appCb.checked = setsPrefs().apps;
  appCb.addEventListener("change", () => {
    const p = setsPrefs();
    p.apps = appCb.checked;
    saveSetsPrefs(p);
    refreshCategories();
    openSetsPanel();  // the per-app rows below follow the master switch
  });
  appHead.append(appCb, document.createTextNode(
    "App shortcuts while a layout is focused — they take wheel slots too"));
  card.appendChild(appHead);

  if (setsPrefs().apps) {
    const appList = document.createElement("div");
    appList.className = "sets-list apps";
    appSets.forEach((s) => appList.appendChild(appSetRow(s)));
    card.appendChild(appList);
  }

  // THE SHAPE OF THE TWO GROUPS, IN PORTRAIT (owner 2026-08-08, task 121).
  // Landscape has always drawn the D-pad cross; upright it stacks into a
  // column, because a 412 px phone has no room for two crosses with the
  // picture between them. A 10" tablet held upright has ~800 px and plenty of
  // room, and he wants the cross there — so it is a CHOICE, per device, and
  // not a width rule that would guess wrong on the next screen size.
  const shape = document.createElement("label");
  shape.className = "sets-row apps";
  const shapeCb = document.createElement("input");
  shapeCb.type = "checkbox";
  shapeCb.checked = padCross();
  shapeCb.addEventListener("change", () => setPadCross(shapeCb.checked));
  shape.append(shapeCb, document.createTextNode(
    "Keep the D-pad cross when the screen is upright — for a wide screen"));
  card.appendChild(shape);

  const done = document.createElement("button");
  done.type = "button";
  done.className = "sets-done";
  done.textContent = "Done";
  keepFocus(done, closeSetsPanel);
  card.appendChild(done);

  setsPanel.appendChild(card);
  setsPanel.hidden = false;
  refreshSetsMeta();
  setsOpened.t = performance.now();
}

function closeSetsPanel() {
  setsPanel.hidden = true;
  setsPanel.innerHTML = "";
}

setsPanel.addEventListener("pointerdown", (e) => {
  if (e.target === setsPanel) closeSetsPanel(); // backdrop tap = done
});

// The quality panel moved to client/quality.js (owner 2026-08-05) — it edits
// the quality prefs and now reads the PC's base, so it belongs with them.

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
  keepFocus(btn, () => dictListen(lang, voice, btn));
  return btn;
}

/** One candidate row: the choice on the left, the listen button on the right.
 *
 *  The button is a SIBLING of the <label>, never a child of it. A click
 *  anywhere inside a label activates the control the label owns, so a speaker
 *  button nested in this row would also SELECT that language — the tap that
 *  means "let me hear it before I decide" would have decided. */
function dictRow(lang, chosen, voices) {
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
  txt.textContent = lang.name;
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
  // A chosen extra language surfaces with the phone's own — the current
  // choice must never hide behind the collapsed section.
  mine.concat(extra.filter((l) => l.tag === chosen))
    .forEach((lang) => list.appendChild(dictRow(lang, chosen, voices)));

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
    keepFocus(more, () => {
      dictMoreOpen = true;
      renderDictationCard();
    });
    list.appendChild(more);
  } else if (dictMoreOpen) {
    rest.forEach((lang) => list.appendChild(dictRow(lang, chosen, voices)));
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
  keepFocus(done, closeDictationPanel);
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

// --- Command chooser (owner idea 2026-08-05) -------------------------------
// His question, and it is the better design: *"jel ne možemo u centar da
// prikažemo opcije pa korisnik odabere a program automatski odradi selekciju"*.
//
// Some commands are not an ACTION but a CHOICE — `/effort` takes a level, so
// sending it alone only prints its usage, and the first version left Claude's
// own menu on screen for the finger to pick from. That worked, but it made the
// phone depend on another app's menu staying where it is. A button with
// `options` now shows the choices HERE, on the phone, and sends the finished
// command in one go: `/effort` + `high` → `paste_text "/effort high"`.
//
// Any future command of this shape gets it for free — it is a property of the
// button, not a special case for Claude.

const choicePanel = document.getElementById("choice-panel");
const choiceOpened = { t: 0 };
ghostClickArmor(choicePanel, choiceOpened);

function openChoicePanel(btn) {
  const options = (btn.options || []).map((o) =>
    (typeof o === "string" ? { label: o, value: o } : o));
  if (!options.length) return;

  choicePanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card card-columns";
  const title = btn.label || btn.text;
  card.innerHTML = `<h2>${title}</h2>` +
    `<p class="sets-sub">Pick one — the PC types it and runs it.</p>`;

  const list = document.createElement("div");
  list.className = "sets-list";
  for (const option of options) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "sets-row choice";
    row.textContent = option.label;
    // The one he already chose is marked — and marked as SAVED, never as
    // "active" (owner 2026-08-08 asked for a tick; honesty asks for the right
    // word). A `/model` button reads `saved.model`, `/effort` reads
    // `saved.effort`; a command we know nothing about marks nothing.
    const key = btn.text === "/model" ? "model"
      : btn.text === "/effort" ? "effort" : null;
    if (key && claudeSaved[key] === option.value) {
      row.classList.add("chosen");
      row.setAttribute("aria-current", "true");
      const tag = document.createElement("span");
      tag.className = "sets-hint";
      tag.textContent = "saved";
      row.appendChild(tag);
    }
    keepFocus(row, () => {
      send({
        type: "paste_text",
        text: `${btn.text} ${option.value}`.trim(),
        enter: true,
      });
      showToast(`${title}: ${option.label}`);
      closeChoicePanel();
    });
    list.appendChild(row);
  }
  card.appendChild(list);

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "sets-done";
  cancel.textContent = "Cancel";
  keepFocus(cancel, closeChoicePanel);
  card.appendChild(cancel);

  choicePanel.appendChild(card);
  choicePanel.hidden = false;
  choiceOpened.t = performance.now();
}

function closeChoicePanel() {
  choicePanel.hidden = true;
  choicePanel.innerHTML = "";
}

choicePanel.addEventListener("pointerdown", (e) => {
  if (e.target === choicePanel) closeChoicePanel(); // backdrop tap = cancel
});
