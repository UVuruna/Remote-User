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
      if (cb.checked && visibleCount() >= WHEEL_MAX) {
        cb.checked = false;
        showToast(`The wheel holds ${WHEEL_MAX} sets — untick one first`);
        return;
      }
      const p = setsPrefs();
      p.state[s.name] = cb.checked;
      saveSetsPrefs(p);
      refreshCategories();
    });
  }
  const ic = document.createElement("span");
  ic.className = "sets-ic";
  ic.innerHTML = svg(s.icon && ICONS[s.icon] ? s.icon : "grid");
  row.append(cb, ic, document.createTextNode(s.name + (locked ? " — always on" : "")));
  return row;
}

// One app-aware set (VSCode, Claude, Chrome, Explorer). It carries no wheel
// count — it rides with a focused layout — so this row only says whether it
// may appear at all, per device.
function appSetRow(s) {
  const row = document.createElement("label");
  row.className = "sets-row app";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = appSetOn(s);
  cb.addEventListener("change", () => {
    const p = setsPrefs();
    p.appState[s.name] = cb.checked;
    saveSetsPrefs(p);
    refreshCategories();
  });
  const ic = document.createElement("span");
  ic.className = "sets-ic";
  ic.innerHTML = svg(s.icon && ICONS[s.icon] ? s.icon : "newwin");
  row.append(cb, ic, document.createTextNode(s.name));
  return row;
}

function openSetsPanel() {
  setsPanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card";
  card.innerHTML = `<h2>Wheel sets</h2>
    <p class="sets-sub">Mouse, Input and Settings are always in the wheel. Pick the rest — up to ${WHEEL_MAX} in total. New sets are made on the PC (Remote User window → Controls…).</p>`;

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
    "App shortcuts while a layout is focused"));
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
