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
  card.className = "sets-card";
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

function dictRow(lang, chosen) {
  const row = document.createElement("label");
  row.className = "sets-row dict" + (lang.tag === chosen ? " sel" : "");
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
  row.append(rb, txt, st);
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
  dictPanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card";
  card.innerHTML = `<h2>Dictation language</h2>
    <p class="sets-sub">Pick the language you speak — dictation understands that one. Change it any time: Settings wheel → Language.</p>`;
  const list = document.createElement("div");
  list.className = "sets-list";
  const mine = langs.filter((l) => !l.extra);
  const extra = langs.filter((l) => l.extra);
  // A chosen extra language surfaces with the phone's own — the current
  // choice must never hide behind the collapsed section.
  mine.concat(extra.filter((l) => l.tag === chosen))
    .forEach((lang) => list.appendChild(dictRow(lang, chosen)));

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
    rest.forEach((lang) => list.appendChild(dictRow(lang, chosen)));
  }
  card.appendChild(list);

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
  card.className = "sets-card";
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
