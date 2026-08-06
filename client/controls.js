// On-screen interactive chrome: built-in action registry, touch-mode
// toggles, invisible keyboard capture, the "access from anywhere" wizard, the
// in-app update banner, phone->PC image upload, the two D-pad control groups,
// the category wheel, corner buttons and the toast pill. The whole LAYOUT
// feature (bar, list, aspect panel, creation flow, loading animation) lived
// here until 2026-08-03 and now has its own file — see
// [Layouts](layouts.js), which loads right after this one and uses
// `keepFocus`/`svg`/`showToast` from here. What is left may NOT be split
// further: `keepFocus` is called at the top level by the wizard section
// before its own definition further down, relying on function hoisting within
// THIS SAME script — a script boundary there would break it. Part of the
// app.js split — loads after input-geometry.js.
// See client/__about/controls.md.
"use strict";

// --- Icons ----------------------------------------------------------------
// The table itself moved to [icons.js](icons.js) (owner's approved icon round,
// 2026-08-05 — THE STRUCTURE LAW); it loads first, so `ICONS` is already here.

function svg(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
}

// --- Built-in group actions -----------------------------------------------

const BUILTINS = {
  // The finger itself only steers the cursor — clicks are explicit buttons at
  // the CURRENT cursor position (owner decision 2026-07-26: with the pointer
  // under the finger NOTHING may act on a canvas tap). Click/Right/Middle are
  // CLICK/HOLD buttons like a real mouse (owner 2026-08-04): a tap is a
  // click, keeping the finger down holds the PC button down (what the old
  // Drag toggle did) — press twice fast for a double click.
  click:    { label: "Click",  icon: "click",    kind: "hold", button: "left" },
  right:    { label: "Right",  icon: "right",    kind: "hold", button: "right" },
  middle:   { label: "Middle", icon: "middle",   kind: "hold", button: "middle" },
  // The SIDE buttons of a 5-button mouse (owner 2026-08-05) — Windows'
  // XBUTTON1/2, "Back"/"Forward" in most apps. Reserves in the Mouse pool:
  // the owner ticks one in place of another when he wants it.
  x1:       { label: "Btn 4",  icon: "btn4",     kind: "hold", button: "x1" },
  x2:       { label: "Btn 5",  icon: "btn5",     kind: "hold", button: "x2" },
  drag:     { label: "Drag",   icon: "drag",     kind: "mode" },
  scroll:   { label: "Scroll", icon: "scroll",   kind: "mode" },
  keyboard: { label: "Keys",   icon: "keyboard", kind: "kb" },
  // Enter/Esc first switch OFF both input switchers (keyboard + mic), then
  // press the real key (owner 2026-08-04 — "skida off i radi funkcionalnost").
  enter:    { label: "Enter",  icon: "enter",    kind: "key-off", key: "enter" },
  esc:      { label: "Esc",    icon: "esc",      kind: "key-off", key: "escape" },
  // New row (owner 2026-08-04): Shift+Enter — the dictation flow has no
  // keyboard, so line breaks need their own button. Deliberately NOT
  // key-off: you break the line mid-dictation and keep talking.
  newrow:   { label: "New row", icon: "newrow",  kind: "send", msg: { type: "chord", chord: "shift+enter" } },
  mic:      { label: "Mic",    icon: "mic",      kind: "mic" },
  monitor:  { label: "Monitor", icon: "monitor2", kind: "send", msg: { type: "monitor_switch" } },
  snap:     { label: "Snap",   icon: "snap",     kind: "send", msg: { type: "screenshot" } },
  // Attach set (owner 2026-08-04): every source ends the same way — the
  // picked/made picture lands in the PC clipboard and is PASTED right away.
  // pcshot captures exactly the REGION the phone currently views (zoom /
  // layout focus), never the whole desktop.
  upload:   { label: "Image",  icon: "image",    kind: "upload" },
  gallery:  { label: "Gallery", icon: "gallery", kind: "pick", input: "pick-gallery" },
  camera:   { label: "Camera", icon: "snap",     kind: "pick", input: "pick-camera" },
  files:    { label: "Files",  icon: "folder",   kind: "pick", input: "pick-files" },
  pcshot:   { label: "Shot",   icon: "shot",     kind: "shot" },
  // Region (owner 2026-08-05): a frame the finger sizes and moves anywhere,
  // captured and PASTED like every other Attach source — Snipping Tool's
  // rectangle, from the phone.
  region:   { label: "Region", icon: "region",   kind: "region" },
  calibrate:{ label: "Calibrate", icon: "target", kind: "calibrate" },
  anywhere: { label: "Anywhere", icon: "globe",  kind: "anywhere" },
  // Dictation setup (owner round 2, 2026-08-05): replaces Anywhere in the
  // default Settings set (the anywhere ACTION stays in this pool — future
  // preset combining, see ROADMAP). Opens the language card; the same card
  // auto-opens on the first Mic tap.
  dictation: { label: "Language", icon: "globe", kind: "dictation" },
  // Phase F+ step 3 (owner spec): UIA-cycled focus through TEXT-INPUT fields
  // only — full desktop → all visible windows, layout focus → that layout —
  // built for the dictation-first workflow.
  next_input: { label: "Next box", icon: "input", kind: "send", msg: { type: "next_input" } },
  // Phone-side wheel picker (owner 2026-08-05, replacing next_input in the
  // Settings defaults): choose WHICH custom sets ride in the wheel (max 3)
  // and whether app-aware sets appear at all. Creation stays desktop-only.
  sets:     { label: "Sets",   icon: "grid",   kind: "sets" },
  // Opens the quality panel (fps / resolution / bitrate + auto-save on
  // mobile data — owner 2026-08-05, replacing the full/reduced cycler)
  quality:  { label: "Quality", icon: "gauge",  kind: "quality" },
};

// --- Device prefs (owner bug report 2026-08-05) ----------------------------
// localStorage is keyed by ORIGIN, and the shell deliberately alternates
// between two addresses (LAN / Tailscale) — pure localStorage therefore
// splits the device's saved state into two silently diverging copies (the
// sets picker "rotated" between two states). The shell's SharedPreferences
// bridge is the real store; localStorage stays as the dev-browser fallback
// and as migration source for state saved before the bridge existed.

function prefGet(key) {
  try {
    if (IN_APP && window.Android.prefGet) {
      const v = window.Android.prefGet(key);
      if (v !== "") return v;
    }
  } catch {}
  try { return localStorage.getItem(key); } catch { return null; }
}

function prefSet(key, value) {
  try {
    if (IN_APP && window.Android.prefSet) window.Android.prefSet(key, String(value));
  } catch {}
  try { localStorage.setItem(key, String(value)); } catch {}
}

// Stream quality (per-device overrides of the PC's own settings) lives in
// client/quality.js — prefs and panel are one responsibility.

// --- Touch-mode toggles ---------------------------------------------------

function setMode(mode) {
  touchMode = touchMode === mode ? "move" : mode;
  refreshModeButtons();
}

function refreshModeButtons() {
  document.querySelectorAll("[data-mode]").forEach((el) =>
    el.classList.toggle("active", el.dataset.mode === touchMode));
}

// --- Keyboard capture (invisible textarea) --------------------------------
// The field never shows — what you type appears in the focused box on the PC
// screen itself (owner decision 2026-07-22: a mirror bar duplicated it). A
// textarea, so the phone IME offers ↵ (new row) instead of a Send/Go key:
// ↵ makes a new row on the PC (Shift+Enter — messengers keep typing instead
// of sending); the D-pad Enter button sends the real Enter.

const kbInput = document.getElementById("kb");
let kbPrev = "";

const SPECIAL_KEYS = {
  Backspace: "backspace", Tab: "tab", Escape: "escape",
  Delete: "delete", Home: "home", End: "end",
  ArrowLeft: "left", ArrowUp: "up", ArrowRight: "right", ArrowDown: "down",
};

function keyboardOpen() {
  return document.activeElement === kbInput;
}

function toggleKeyboard() {
  if (keyboardOpen()) kbInput.blur();
  else kbInput.focus({ preventScroll: true }); // focus -> micStop (only one of mic/keyboard may be ON)
}

kbInput.addEventListener("focus", () => {
  micStop();
  document.querySelectorAll('[data-action="keyboard"]').forEach((el) => el.classList.add("active"));
});
kbInput.addEventListener("blur", () => {
  kbInput.value = "";
  kbPrev = "";
  document.querySelectorAll('[data-action="keyboard"]').forEach((el) => el.classList.remove("active"));
});

kbInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    send({ type: "chord", chord: "shift+enter" }); // new row, never "send"
    return;
  }
  const special = SPECIAL_KEYS[e.key];
  if (!special) return;
  e.preventDefault();
  send({ type: "key_special", key: special });
});

function sendTyped(text) {
  // Some IMEs commit "\n" without any keydown — those newlines become the
  // same Shift+Enter new row as the ↵ key.
  const parts = text.split("\n");
  parts.forEach((part, i) => {
    if (i) send({ type: "chord", chord: "shift+enter" });
    if (part) send({ type: "key_text", text: part });
  });
}

kbInput.addEventListener("input", (e) => {
  const value = kbInput.value;
  const minLen = Math.min(kbPrev.length, value.length);
  let p = 0;
  while (p < minLen && kbPrev[p] === value[p]) p++;
  let s = 0;
  while (s < minLen - p && kbPrev[kbPrev.length - 1 - s] === value[value.length - 1 - s]) s++;
  const removed = kbPrev.length - p - s;
  let inserted = value.slice(p, value.length - s);
  let back = removed;
  if (s > 0 && (removed > 0 || inserted)) {
    // Mid-string edit (multi-word autocorrect, double-space period): the PC
    // caret sits at the END of the text, so the surviving tail must be
    // erased and retyped too — replaying only the middle would land the
    // edit after the tail ("cant believe" → "cant believe'").
    back += s;
    inserted += value.slice(value.length - s);
  }
  for (let i = 0; i < back; i++) send({ type: "key_special", key: "backspace" });
  if (inserted) sendTyped(inserted);
  kbPrev = value;
  if (!e.isComposing && value.length > 200) {
    kbInput.value = "";
    kbPrev = "";
  }
});

// --- Mic (voice input) switcher -------------------------------------------
// Owner 2026-08-04: the Mic button opens voice input DIRECTLY — no opening
// the keyboard first, then hunting the IME's mic key. The page cannot listen
// itself (Android WebView has no Speech API), so the shell does: the
// `Android.startVoice()` bridge runs a SpeechRecognizer and calls
// `__voiceResult(text)` back with each recognized utterance; `__voiceEnd`
// closes one listening round — while the switcher is ON the page restarts it,
// so dictation keeps flowing sentence after sentence. Only one of mic /
// keyboard is ever ON (owner rule).

let micOn = false;

function micSupported() {
  return IN_APP && typeof window.Android.startVoice === "function";
}

function setMicActive(on) {
  document.querySelectorAll('[data-action="mic"]').forEach((el) =>
    el.classList.toggle("active", on));
}

function micStart() {
  if (!micSupported()) {
    showToast("Voice input needs the updated app — update from the banner");
    return;
  }
  // First contact (owner round 2, 2026-08-05): no chosen dictation language
  // yet → the setup card opens INSTEAD of listening. Never guess a language
  // — the phone's system-locale order proved wrong on the owner's device.
  if (window.Android.voiceChosen && !window.Android.voiceChosen()) {
    openDictationPanel();
    return;
  }
  if (keyboardOpen()) kbInput.blur();
  micOn = true;
  setMicActive(true);
  // A microphone permission dialog (and Google's own voice UI) hides the page
  // — an excursion, not the end of work (owner 2026-08-05).
  markExcursion();
  window.Android.startVoice();
}

function micStop() {
  if (!micOn) return;
  micOn = false;
  setMicActive(false);
  if (micSupported()) window.Android.stopVoice();
}

function toggleMic() {
  if (micOn) micStop();
  else micStart();
}

// Called by the shell (evaluateJavascript) with each recognized utterance.
window.__voiceResult = (text) => {
  if (text) sendTyped(text + " ");
};

// Diagnostic line from the shell — SILENT evidence (owner round 2, angrily:
// never a panel flashed at the user): forwarded to the PC's server log,
// where the developer reads it.
window.__voiceInfo = (text) => {
  send({ type: "client_log", text: `[voice] ${text}` });
};

// Model-download state from the shell: the Mic button wears an alternate
// look while the chosen language's model downloads (dictation keeps working
// online meanwhile — owner round 2).
let voiceDownloading = false;
window.__voiceState = (state) => {
  voiceDownloading = state === "downloading";
  refreshMicButtons();
};

function refreshMicButtons() {
  if (IN_APP && window.Android.voiceState) {
    try { voiceDownloading = window.Android.voiceState() === "downloading"; } catch {}
  }
  document.querySelectorAll('[data-action="mic"]').forEach((el) =>
    el.classList.toggle("dl", voiceDownloading));
}

// One listening round ended (silence, error, permission). Restart while ON.
window.__voiceEnd = (reason) => {
  if (!micOn) return;
  if (reason === "denied") {
    micStop();
    showToast("Microphone permission was denied — allow it in Android settings");
    return;
  }
  if (reason === "unavailable") {
    micStop();
    showToast("Voice recognition is not available on this phone");
    return;
  }
  if (reason === "nolang") {
    micStop();
    openDictationPanel(); // choose first, then dictate
    return;
  }
  setTimeout(() => {
    if (micOn && micSupported()) window.Android.startVoice();
  }, 250);
};

// Enter/Esc and a tap on the stream switch every input switcher OFF
// (owner 2026-08-04 — no manual toggling off before the next action).
function inputOff() {
  if (keyboardOpen()) kbInput.blur();
  micStop();
}

// --- "Access from anywhere" wizard ----------------------------------------
// The server's config carries tailscale_url when the PC is on Tailscale.
// If this page runs on the home (LAN) address, a banner offers a guided
// one-time setup: install the Tailscale app (Play Store link), sign in,
// and the page DETECTS the moment the phone joins (probing /ping on the
// Tailscale address) — then hands over the works-anywhere link. The user
// only follows on-screen steps; nothing is explained outside the app.

let tailscaleUrl = null;
const anywhereBanner = document.getElementById("anywhere-banner");
const wizardEl = document.getElementById("wizard");
const wizStep3 = document.getElementById("wiz-step-3");
const wizStatus = document.getElementById("wiz-status");
const wizHint = document.getElementById("wiz-hint");
const wizOpen = document.getElementById("wiz-open");
let wizTimer = null;

// The banner auto-appears ONCE per device (owner decision 2026-07-26 — "ok
// once, not constantly"): the first page load that could offer it sets a
// localStorage flag and keeps offering for THAT load; every later load stays
// clean. The wizard remains reachable any time via Settings → Anywhere.
let anywhereOffer = null; // null = undecided for this load, then true/false
function updateAnywhereBanner() {
  const onAnywhere = tailscaleUrl && new URL(tailscaleUrl).host === location.host;
  if (anywhereOffer === null && tailscaleUrl && !onAnywhere) {
    anywhereOffer = prefGet("anywhereOffered") !== "1";
    prefSet("anywhereOffered", "1");
  }
  anywhereBanner.hidden = !(tailscaleUrl && !onAnywhere && anywhereOffer === true &&
                            sessionStorage.getItem("wizDismissed") !== "1");
}

function openWizard() {
  wizardEl.hidden = false;
  if (!tailscaleUrl) {
    // Settings → Anywhere can open this before the PC is on Tailscale — the
    // probe would wait forever with no explanation. Say what unblocks it
    // (owner principle: every step guided in-app, never left hanging).
    wizStatus.textContent = "The PC is not on Tailscale yet";
    wizHint.textContent = "On the PC, open the Remote User window and press " +
      "“Set up Tailscale”. Then come back here — this screen finishes by itself.";
  }
  wizProbe();
  if (!wizTimer) wizTimer = setInterval(wizProbe, 3000);
}

function closeWizard(dismiss) {
  wizardEl.hidden = true;
  if (wizTimer) {
    clearInterval(wizTimer);
    wizTimer = null;
  }
  if (dismiss) sessionStorage.setItem("wizDismissed", "1");
  updateAnywhereBanner();
}

async function wizProbe() {
  if (!tailscaleUrl) return;
  try {
    // no-cors: an opaque success still proves the address is reachable —
    // exactly the "phone joined the mesh" signal we need.
    await fetch(`${new URL(tailscaleUrl).origin}/ping`, { mode: "no-cors", cache: "no-store" });
  } catch {
    return; // not on the mesh yet — keep waiting
  }
  wizStep3.classList.add("done");
  wizStatus.textContent = "Connected — your phone is in!";
  wizHint.textContent = "Open your permanent link below and save it (Add to Home screen). It works at home AND anywhere.";
  wizOpen.hidden = false;
  wizOpen.href = tailscaleUrl;
  if (wizTimer) {
    clearInterval(wizTimer);
    wizTimer = null;
  }
}

// keepFocus, not `click`: both sit where Android steals touches (the banner
// hugs the bottom gesture zone) — a stolen tap must still open/close.
keepFocus(anywhereBanner, openWizard);
keepFocus(document.getElementById("wiz-close"), () => closeWizard(true));
wizardEl.addEventListener("pointerdown", (e) => {
  if (e.target === wizardEl) closeWizard(true); // backdrop tap = later
});

// window.Android is the APK shell's JS bridge — present = running in the app.
// (Android BROWSERS never reach this page at all: the server routes them to
// the install funnel by User-Agent.)
const IN_APP = typeof window.Android !== "undefined";

// --- In-app update (the PC carries the newer APK) --------------------------
// The phone never checks the internet for updates: `config.app_version` says
// what the PC runs, the bridge says what this shell is, and /app.apk on the
// SAME PC is the newer build (the desktop app updates itself from GitHub).

const updateBanner = document.getElementById("update-banner");

function versionNumbers(v) {
  return (String(v).match(/\d+/g) || []).slice(0, 3).map(Number);
}

function isNewer(server, app) {
  const s = versionNumbers(server);
  const a = versionNumbers(app);
  if (!s.length || !a.length) return false;
  for (let i = 0; i < 3; i++) {
    const d = (s[i] || 0) - (a[i] || 0);
    if (d) return d > 0;
  }
  return false;
}

function refreshUpdateBanner(apkVersion) {
  // Compare against the APK the PC actually SERVES (config.apk_version) —
  // comparing against the server version offered phantom updates whenever a
  // release changed only the desktop side (owner bug 2026-08-02).
  updateBanner.hidden = !(
    IN_APP && window.Android.appVersion && window.Android.update &&
    apkVersion && isNewer(apkVersion, window.Android.appVersion())
  );
}

keepFocus(updateBanner, () => {
  window.Android.update(`${location.origin}/app.apk`);
  showToast("Downloading — open the file to install the update");
});

// --- Phone → PC upload (gallery / camera / any files) ---------------------
// The server pastes by itself (Ctrl+V injected) — picking was the whole
// gesture. ONE image goes as a bitmap (/upload — pastes into any image box);
// several files, or any non-image (PDF…), go as real FILES (/upload_files —
// CF_HDROP on the PC clipboard, pasted into apps that accept files). Owner
// 2026-08-04: gallery and Files allow selecting more than one.

async function uploadPicked(files) {
  if (!files || !files.length) return;
  const list = [...files];
  showToast(list.length > 1 ? `Uploading ${list.length} files…` : "Uploading…");
  const single = list.length === 1 && list[0].type.startsWith("image/");
  try {
    const body = new FormData();
    let url;
    if (single) {
      body.append("file", list[0]);
      url = `/upload?token=${encodeURIComponent(token)}`;
    } else {
      list.forEach((f) => body.append("files", f));
      url = `/upload_files?token=${encodeURIComponent(token)}`;
    }
    const j = await (await fetch(url, { method: "POST", body })).json();
    showToast(j.ok
      ? (single ? "Image pasted on the PC" : `${list.length} file${list.length > 1 ? "s" : ""} pasted on the PC`)
      : "Upload failed");
  } catch (err) {
    showToast(`Upload failed: ${err.message}`);
  }
}

const filePick = document.getElementById("filepick");
const PICKERS = ["filepick", "pick-gallery", "pick-camera", "pick-files"];
for (const id of PICKERS) {
  const el = document.getElementById(id);
  el.addEventListener("change", async () => {
    await uploadPicked(el.files);
    el.value = "";
  });
}

// --- D-pad groups ---------------------------------------------------------

const groupEls = {
  left: document.getElementById("group-left"),
  right: document.getElementById("group-right"),
};
const POSITIONS = ["up", "left", "right", "down"];

let categories = [];
let appSets = [];    // app-aware sets from actions.json (owner 2026-08-04)
let customSets = []; // owner-made sets from the desktop editor (owner 2026-08-05)
const groups = { left: 0, right: 0 };

// Phone-side wheel preferences (the Settings → Sets picker): which custom
// sets this DEVICE hides, and whether app-aware sets appear. Per-phone on
// purpose — the desktop editor sets the defaults, the phone overrides them.
function setsPrefs() {
  try {
    const p = JSON.parse(prefGet("setsPrefs") || "{}");
    return {
      state: p.state && typeof p.state === "object" ? p.state : {},
      // Per-app-set choice (owner 2026-08-05): `apps` is still the master
      // switch, `appState` names the ones hidden inside it — two sets can now
      // match the same process (VSCode + Claude), and hiding one of them is
      // the whole point.
      appState: p.appState && typeof p.appState === "object" ? p.appState : {},
      apps: p.apps !== false,
    };
  } catch {
    return { state: {}, appState: {}, apps: true };
  }
}

// Effective on/off for one toggleable set (an optional shipped category OR a
// custom set — required ones never ask): the phone's explicit choice wins,
// otherwise the desktop editor's default (`enabled` in actions.json).
function setOn(s) {
  const choice = setsPrefs().state[s.name];
  return choice !== undefined ? choice : s.enabled !== false;
}

function saveSetsPrefs(p) {
  prefSet("setsPrefs", JSON.stringify(p));
}

// App-aware sets exist ONLY in layout focus (owner decision 2026-08-04):
// when the focused layout's app matches a set's `process`, that set appears
// as an extra category in the wheel — nothing switches by itself, and the
// category vanishes with the layout focus.
function appSetOn(s) {
  const choice = setsPrefs().appState[s.name];
  return choice !== undefined ? choice : s.enabled !== false;
}

// A set may also demand a TITLE match (owner 2026-08-05): Claude Code runs
// INSIDE VSCode, same process, so the process alone cannot tell the two
// apart. `title` is matched against the layout's ORIGINAL window/tab title —
// never its name, which the owner may have renamed to anything. A set with
// no `title` matches the process as before, which is why VSCode and Claude
// can ride together while only one of them knows it is Claude.
//
// The test is a WORD, not a substring, and a DOCUMENT never matches (owner
// 2026-08-06, shouted): the Claude set may appear for the Claude conversation
// tab and for nothing else — an open `CLAUDE.md`, a transcript, any text file
// is still plain VSCode. Substring matching gave every one of those the
// Claude wheel. `title` may be a list, so one set can name several spellings.
const DOC_TITLE = /\.[a-z0-9]{1,6}(\s*[-—•]\s*.*)?$/i;  // "CLAUDE.md", "notes.txt — Visual Studio Code"

function titleMatches(want, title) {
  const t = String(title || "").toLowerCase().trim();
  if (!t || DOC_TITLE.test(t)) return false;  // a file tab is a document
  const words = (Array.isArray(want) ? want : [want]).map((w) => String(w).toLowerCase());
  return words.some((w) => w && new RegExp(`(^|[^a-z0-9])${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^a-z0-9]|$)`).test(t));
}

function appSetMatches(s, lay) {
  const proc = String(lay.process || "").toLowerCase();
  if (!proc.includes(String(s.process || "").toLowerCase())) return false;
  // No title test = the whole app. VSCode therefore rides ALONGSIDE Claude on
  // a Claude tab — the owner's rule of 2026-08-06: this is the one case where
  // two app sets appear at once, and both are wanted (the editor's own
  // shortcuts stay reachable while Claude's commands are there).
  if (!s.title) return true;
  return titleMatches(s.title, lay.title);
}

function visibleAppSets() {
  if (!setsPrefs().apps) return [];
  if (layoutActive === null || !layouts[layoutActive]) return [];
  const lay = layouts[layoutActive];
  return appSets.filter((s) => appSetMatches(s, lay) && appSetOn(s));
}

// How many wheel slots the ticked app sets RESERVE (owner 2026-08-06). Not
// simply "how many are ticked": Chrome, Explorer and VSCode can never appear
// together, so ticking all of them costs one slot, not three. What costs two
// is VSCode + Claude — the one case where two sets share a process and both
// are meant to ride. The charge is therefore the largest group of ticked sets
// that CAN match at the same time, which is the group per process.
function appSetReserve() {
  if (!setsPrefs().apps) return 0;
  const perProcess = {};
  for (const s of appSets) {
    if (!appSetOn(s)) continue;
    const key = String(s.process || "").toLowerCase();
    perProcess[key] = (perProcess[key] || 0) + 1;
  }
  return Math.max(0, ...Object.values(perProcess));
}

// The wheel's composition (owner 2026-08-05, revised same day): Mouse, Input
// and Settings are REQUIRED (`required` in actions.json — never hidden); the
// other shipped sets (Edit, Attach, Navigate, Cursor, Media, Windows) and
// the custom sets are toggleable; the app set rides along in layout focus.
// Hard cap WHEEL_MAX total — over the cap, non-required sets are bumped from
// the END (they come back when the app set goes away).
const WHEEL_MAX = 8;

function visibleCount() {
  // What the picker charges against the cap. App sets are NOT free (owner
  // 2026-08-06): a Claude tab puts BOTH VSCode and Claude on the wheel, so
  // ticking both leaves room for six others, not seven. Counting them as
  // free let the picker promise eight while the wheel silently dropped two.
  return categories.filter((c) => c.required || setOn(c)).length +
    customSets.filter(setOn).length +
    appSetReserve();
}

function allCats() {
  const list = categories.filter((c) => c.required || setOn(c))
    .concat(visibleAppSets())
    .concat(customSets.filter(setOn));
  for (let i = list.length - 1; list.length > WHEEL_MAX && i >= 0; i--) {
    if (!list[i].required) list.splice(i, 1);
  }
  return list;
}

// Re-render after anything that changes the category list (actions arrived,
// layout focus changed) — a group left pointing past the end falls back to 0.
function refreshCategories() {
  const n = allCats().length;
  for (const side of ["left", "right"]) {
    if (groups[side] >= n) groups[side] = 0;
    renderGroup(side);
  }
}

// Buttons fire on pointerUP — the moment a touch grants transient user
// activation (the file picker and IME focus NEED it; pointerdown does not
// grant it for touch) — PLUS a rescue path for the Android theft that killed
// every button on the real device (owner report 2026-07-26): the system
// claims touches that start near screen edges / gesture zones and ends them
// with a pointercancel, so an up-only handler simply never ran. A cancel
// that barely travelled IS the stolen tap and still fires; a cancel after
// real travel is a system swipe (home/back) crossing the button and must
// NOT act on the PC. preventDefault keeps focus where it is (the keyboard
// field stays open). Proven by the cancel cases in tests/test_input_pipeline.py.
const CANCEL_TAP_SLOP = 18; // CSS px of travel that still counts as a stolen tap
function keepFocus(el, onTap) {
  let press = null; // {id, x, y, moved} — implicit touch capture routes the events here
  el.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    press = { id: e.pointerId, x: e.clientX, y: e.clientY, moved: false };
  });
  el.addEventListener("pointermove", (e) => {
    if (press && e.pointerId === press.id &&
        Math.hypot(e.clientX - press.x, e.clientY - press.y) > CANCEL_TAP_SLOP) {
      press.moved = true;
    }
  });
  el.addEventListener("pointerup", (e) => {
    e.preventDefault();
    if (press && e.pointerId === press.id) onTap(e);
    press = null;
  });
  el.addEventListener("pointercancel", (e) => {
    if (press && e.pointerId === press.id && !press.moved) onTap(e);
    press = null;
  });
}

function makeButton(cls, iconName, label) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = cls;
  el.innerHTML = (iconName ? svg(iconName) : "") + `<span class="lbl">${label}</span>`;
  return el;
}

// CLICK/HOLD mouse buttons (owner 2026-08-04 — like a real mouse): the PC
// button goes DOWN on pointerdown and UP on release, at the current cursor.
// A tap is a click; keeping the finger down drags/selects. pointercancel
// releases too — Android stealing the touch must never leave the PC button
// stuck down (so a system swipe crossing the button costs one stray click,
// the price of real hold semantics — unlike keepFocus buttons, down cannot
// wait to see how the touch ends).
function holdButton(el, button) {
  let pid = null;
  el.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    pid = e.pointerId;
    el.classList.add("held");
    send({ type: "press", button, down: true });
  });
  const release = (e) => {
    if (pid === null || e.pointerId !== pid) return;
    pid = null;
    el.classList.remove("held");
    send({ type: "press", button, down: false });
  };
  el.addEventListener("pointerup", (e) => { e.preventDefault(); release(e); });
  el.addEventListener("pointercancel", release);
}

// The monitor-normalized rect the phone is LOOKING at right now — what the
// Shot button captures (owner 2026-08-04: never the whole desktop; zoomed =
// the zoomed part, layout focus = that layout's region).
function shotRegion() {
  const D = drawnRect();
  let x1 = Math.max(0, -D.x / D.w);
  let y1 = Math.max(0, -D.y / D.h);
  let x2 = Math.min(1, (canvas.width - D.x) / D.w);
  let y2 = Math.min(1, (canvas.height - D.y) / D.h);
  if (viewLocked()) {
    x1 = Math.max(x1, layoutRegion.x);
    y1 = Math.max(y1, layoutRegion.y);
    x2 = Math.min(x2, layoutRegion.x + layoutRegion.w);
    y2 = Math.min(y2, layoutRegion.y + layoutRegion.h);
  }
  return { x: x1, y: y1, w: Math.max(0, x2 - x1), h: Math.max(0, y2 - y1) };
}

function makeActionButton(btn, pos) {
  let el;
  if (btn.action && BUILTINS[btn.action]) {
    const b = BUILTINS[btn.action];
    // A built-in's NAME may be overridden per button (owner 2026-08-05): the
    // side buttons Btn 4 / Btn 5 carry whatever the user's mouse driver put
    // on them, so "Back", "Forward" or "Undo" must be sayable on the face.
    // Only the name — what the button DOES stays ours.
    el = makeButton("ctl", b.icon, btn.label || b.label);
    el.dataset.action = btn.action;
    if (b.kind === "mode") {
      el.dataset.mode = btn.action;
      keepFocus(el, () => setMode(btn.action));
    } else if (b.kind === "kb") {
      keepFocus(el, toggleKeyboard);
    } else if (b.kind === "hold") {
      holdButton(el, b.button);
    } else if (b.kind === "key-off") {
      keepFocus(el, () => {
        inputOff();
        send({ type: "key_special", key: b.key });
      });
    } else if (b.kind === "mic") {
      keepFocus(el, toggleMic);
    } else if (b.kind === "shot") {
      keepFocus(el, () => send({ type: "screenshot", paste: true, ...shotRegion() }));
    } else if (b.kind === "region") {
      keepFocus(el, openRegionPanel);
    } else if (b.kind === "pick") {
      // The picker/camera hides the page — an EXCURSION, not the end of work:
      // the PC must keep the layout standing while the owner picks (owner
      // 2026-08-05).
      keepFocus(el, () => {
        markExcursion();
        document.getElementById(b.input).click();
      });
    } else if (b.kind === "sets") {
      keepFocus(el, openSetsPanel);
    } else if (b.kind === "send") {
      keepFocus(el, () => send(b.msg));
    } else if (b.kind === "upload") {
      keepFocus(el, () => {
        markExcursion();
        filePick.click();
      });
    } else if (b.kind === "calibrate") {
      // The offset/calibration system is gone (owner 2026-08-02 — the pointer
      // sits under the finger). The action stays registered so an owner
      // actions.json that still lists it renders a harmless button.
      keepFocus(el, () => showToast("Not needed anymore — the pointer is right under your finger"));
    } else if (b.kind === "anywhere") {
      keepFocus(el, openWizard); // the banner shows only once — this is the permanent way in
    } else if (b.kind === "quality") {
      keepFocus(el, openQualityPanel);
    } else if (b.kind === "dictation") {
      keepFocus(el, openDictationPanel);
    }
  } else if (btn.text && btn.options) {
    // A command whose answer is a CHOICE (owner idea 2026-08-05): the phone
    // shows the options itself and sends the finished command, instead of
    // typing a bare `/effort` and leaving another app's menu to be poked at.
    const icon = btn.icon && ICONS[btn.icon] ? btn.icon : null;
    el = makeButton(icon ? "ctl" : "ctl text", icon, btn.label || btn.text);
    keepFocus(el, () => openChoicePanel(btn));
  } else if (btn.text) {
    // TYPED commands (owner 2026-08-05, for the Claude set): the things he
    // wants — how much usage is left, switch model, set the thinking level —
    // are not shortcuts at all, they are slash commands written into the
    // app's own prompt. The PC pastes the text (clipboard + Ctrl+V, one
    // atomic insert instead of a character storm through an autocomplete
    // menu) and presses Enter when the command asks for it. `enter: false`
    // leaves the line standing — that is the "/" button, which opens the
    // command menu and lets the finger pick from it.
    const icon = btn.icon && ICONS[btn.icon] ? btn.icon : null;
    el = makeButton(icon ? "ctl" : "ctl text", icon, btn.label || btn.text);
    keepFocus(el, () => send({
      type: "paste_text", text: btn.text, enter: btn.enter !== false,
    }));
  } else if (btn.chord) {
    // actions.json buttons may name an icon from ICONS (owner-approved icon
    // set 2026-08-04 — e.g. Edit's Copy/Cut/Paste/All); no icon = text button.
    const icon = btn.icon && ICONS[btn.icon] ? btn.icon : null;
    el = makeButton(icon ? "ctl" : "ctl text", icon, btn.label || btn.chord);
    keepFocus(el, () => send({ type: "chord", chord: btn.chord }));
  } else if (btn.key) {
    const icon = btn.icon && ICONS[btn.icon] ? btn.icon : null;
    el = makeButton(icon ? "ctl" : "ctl text", icon, btn.label || btn.key);
    keepFocus(el, () => send({ type: "key_special", key: btn.key }));
  } else {
    el = makeButton("ctl text", null, btn.label || "?");
  }
  el.style.gridArea = POSITIONS[pos];
  return el;
}

// --- Command pools (owner 2026-08-05) --------------------------------------
// A set's `buttons` list is its POOL — it may hold more commands than the
// four a D-pad shows (the reserves: VSCode's Markdown preview, Explorer's
// tab hops, …). `active` names the four that ride on the D-pad, by ID, so
// that adding or reordering pool entries in a later version never silently
// re-points the owner's choice the way indices would. No `active` = the
// first four, which is exactly the pre-pool behaviour.

function btnId(b) {
  return b.id || b.action || b.chord || b.key || b.label || "";
}

function activeButtons(cat) {
  const pool = cat.buttons || [];
  if (!Array.isArray(cat.active)) return pool.slice(0, 4);
  const picked = [];
  for (const id of cat.active) {
    const found = pool.find((b) => btnId(b) === id);
    if (found && !picked.includes(found)) picked.push(found);
    if (picked.length === 4) break;
  }
  return picked.length ? picked : pool.slice(0, 4);
}

function renderGroup(side) {
  const host = groupEls[side];
  host.innerHTML = "";
  const cat = allCats()[groups[side]];
  if (!cat) return;

  const center = makeButton("ctl cat", cat.icon, cat.name);
  center.style.gridArea = "center";
  keepFocus(center, () => openWheel(side));
  host.appendChild(center);

  // Per-set, per-orientation button arrangement (owner 2026-08-05): the set
  // may carry order_land (slots T·L·R·B) and order_port (top→bottom column)
  // from the desktop editor; ours is the default and always restorable there.
  const btns = activeButtons(cat);
  const raw = matchMedia("(orientation: portrait)").matches ? cat.order_port : cat.order_land;
  const order = Array.isArray(raw) && raw.length === btns.length &&
    [...raw].sort().join() === btns.map((_, i) => i).join()
    ? raw : btns.map((_, i) => i);
  order.forEach((bi, slot) => host.appendChild(makeActionButton(btns[bi], slot)));
  refreshModeButtons();
  refreshQualityButtons();
  refreshMicButtons();
  if (keyboardOpen()) {
    host.querySelectorAll('[data-action="keyboard"]').forEach((el) => el.classList.add("active"));
  }
}

// --- Category wheel (tap to open, tap an item, X to cancel) ---------------

const wheelEl = document.getElementById("wheel");
const WHEEL_RADIUS = 118;

function openWheel(side) {
  wheelEl.innerHTML = "";
  const cx = window.innerWidth / 2;
  const cy = window.innerHeight / 2;
  const cats = allCats();
  const n = cats.length;
  cats.forEach((cat, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / Math.max(1, n);
    const item = document.createElement("div");
    item.className = "wheel-item" + (i === groups[side] ? " current" : "");
    item.innerHTML = svg(cat.icon) + `<span>${cat.name}</span>`;
    item.style.left = `${cx + WHEEL_RADIUS * Math.cos(angle)}px`;
    item.style.top = `${cy + WHEEL_RADIUS * Math.sin(angle)}px`;
    keepFocus(item, () => {
      groups[side] = i;
      renderGroup(side);
      closeWheel();
    });
    wheelEl.appendChild(item);
  });

  const x = document.createElement("div");
  x.className = "wheel-x";
  x.innerHTML = svg("x");
  keepFocus(x, closeWheel);
  wheelEl.appendChild(x);

  wheelEl.addEventListener("pointerdown", backdropCancel);
  wheelEl.classList.add("open");
}

function backdropCancel(e) {
  if (e.target === wheelEl) {
    e.preventDefault();
    closeWheel();
  }
}

function closeWheel() {
  wheelEl.classList.remove("open");
  wheelEl.removeEventListener("pointerdown", backdropCancel);
  wheelEl.innerHTML = "";
}

// The Sets picker and Quality panel overlays live in panels.js (split out
// 2026-08-05, THE STRUCTURE LAW) — openSetsPanel/openQualityPanel are called
// only at runtime, after every script has loaded.

// Rotation may carry a different button order per set (order_port).
matchMedia("(orientation: portrait)").addEventListener("change", () => {
  renderGroup("left");
  renderGroup("right");
});

// --- Corner buttons -------------------------------------------------------

const hideBtn = document.getElementById("btn-hide");
keepFocus(hideBtn, () => {
  const hidden = document.body.classList.toggle("hidden-controls");
  hideBtn.classList.toggle("active", hidden);
});

// --- Toast ----------------------------------------------------------------

// A toast borrows the status pill. When it expires the pill must simply FADE
// OUT — going straight back to the "connected" state flashed a blue
// "Connected" pill after every toast (owner 2026-08-04), because that state's
// opacity:0 is reached through a 0.4 s transition while its blue background
// applies instantly. So the amber pill fades in place first, and only the
// invisible pill is switched back to the connected state.
let toastTimer = null;
let toastFadeTimer = null;
function showToast(text) {
  setStatus("connecting", text);   // clears .fade — a new toast always shows
  clearTimeout(toastTimer);
  clearTimeout(toastFadeTimer);
  toastTimer = setTimeout(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;  // not connected: the real state must stay visible
    statusEl.classList.add("fade");
    toastFadeTimer = setTimeout(() => setStatus("connected", "Connected"), 450);
  }, 2500);
}
