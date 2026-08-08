// On-screen interactive chrome: built-in action registry, touch-mode
// toggles, invisible keyboard capture, the "access from anywhere" wizard, the
// in-app update banner, phone->PC image upload, the two D-pad control groups
// and the category wheel. EVERYTHING HERE DRIVES THE PC — a press becomes a
// click, a wheel choice becomes a different set of commands. Our own furniture
// (the Hide button, the auto-hide rule, the toast) drives nothing and moved to
// [Chrome](chrome.js) on 2026-08-08. The whole LAYOUT
// feature (bar, list, aspect panel, creation flow, loading animation) lived
// here until 2026-08-03 and now has its own file — see
// [Layouts](layouts.js), which loads right after this one and uses
// `keepFocus`/`svg`/`showToast` from here. One thing here may NOT move:
// `keepFocus` is called at the top level by the wizard section before its own
// definition further down, relying on function hoisting within THIS SAME
// script — a script boundary between those two would break it. Part of the
// app.js split — loads after input-geometry.js.
// See client/__about/controls.md.
"use strict";

// --- Icons ----------------------------------------------------------------
// The table itself moved to [icons.js](icons.js) (owner's approved icon round,
// 2026-08-05 — THE STRUCTURE LAW); it loads first, so `ICONS` is already here.

function svg(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
}

// --- One activation per button (build round G1, 2026-08-07) ----------------
// A gamepad press must BE a button press, not a second implementation of one.
// CLAUDE.md constraint 9 exists because a parallel path is exactly what died
// on the real device: an up-only handler that drifted from Android's stolen
// touches killed every control at once. So every control button registers
// exactly ONE activator here — the same function object its own pointer
// handlers call — and `buttonPress()` is the single door the pad
// ([Gamepad](gamepad.js)) comes in by. Nothing is copied: a CLICK/HOLD
// button's `hold` IS what pointerdown/pointerup run, and a tap button's `tap`
// IS what pointerup and the pointercancel rescue run.
//
// It lives HERE, at the top, for the same hoisting reason the file header
// gives: `keepFocus` is called at the top level by the wizard section further
// down, before its own definition, so the WeakMap it writes into must already
// be initialized by then (a `const` further down is in its temporal dead zone
// at that moment — caught by client/load_test.js the first time).
const ACTIVATORS = new WeakMap(); // button element -> {tap} | {hold}

// `down` follows the physical press. A CLICK/HOLD mouse button holds the PC
// button down BETWEEN the two calls (owner 2026-08-04 — a held pad arrow is a
// held finger); every other button acts on the RELEASE, which is exactly where
// a finger's pointerup acts. Returns false for an element carrying no action —
// a D-pad slot the current set left empty.
function buttonPress(el, down) {
  const a = el && ACTIVATORS.get(el);
  if (!a) return false;
  if (a.hold) {
    a.hold(down);   // hold buttons light themselves — the PC button IS down
    return true;
  }
  // The screen always SHOWS what the pad did (build round G2): `.held` is the
  // pressed-in glow a finger already earns on a CLICK/HOLD button, borrowed
  // for the moment a pad key is down on a tap button.
  el.classList.toggle("held", down);
  if (!down) a.tap();
  return true;
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
// `__voiceHeard(text, isFinal)` back per round (see below); `__voiceEnd`
// closes one listening round — while the switcher is ON the page restarts it,
// so dictation keeps flowing sentence after sentence. Only one of mic /
// keyboard is ever ON (owner rule).

// WHICH recognized words are typed, and WHEN, is [Voice](voice.js) — a pure
// module split out of this file on 2026-08-08 (THE STRUCTURE LAW), holding
// the settle rule that types AS he speaks and the round-boundary trim that
// keeps a re-heard tail from being typed twice. This file keeps the mic
// SWITCHER below and does the typing.

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
  voiceLastOut = ""; // the mic went off: whatever comes next is a new sentence
  voiceStreamReset(); // ...and the round in flight is abandoned with it
  if (micSupported()) window.Android.stopVoice();
}

function toggleMic() {
  if (micOn) micStop();
  else micStart();
}

// Called by the shell on every LIVE partial (owner 2026-08-08 — the text must
// appear while he speaks, not after he stops): type what has settled, hold the
// tail back. A shell too old to call this simply never does, and the page
// behaves as it did before — round-end delivery only.
window.__voicePartial = (text) => {
  const out = voiceStream(text);
  if (out) sendTyped(out + " ");
};

// Called by the shell when a ROUND ends — `isFinal` for a real result, false
// for the rescue copy of a round that died. Flushes whatever the settle rule
// still holds; [Voice](voice.js) trims off what streaming already sent.
window.__voiceHeard = (text, isFinal) => {
  const out = voiceDedup(text, isFinal);
  if (out) sendTyped(out + " ");
};

// Called by the shell (evaluateJavascript) with each recognized utterance —
// LEGACY path, kept for a shell too old to call __voiceHeard above.
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

// Which sets ride the wheel — the per-device composition rules, the cap
// of 8 and the app-aware matching — now live in client/sets.js, loaded
// before this file (THE STRUCTURE LAW, 2026-08-06).
const groups = { left: 0, right: 0 };  // which category each D-pad group shows

// The button sitting in one D-pad slot ("up"/"left"/"right"/"down"), or null
// when the current set has nothing there. The slot IS the grid area
// `makeActionButton` stamps on it, so this stays true whatever `order_land` /
// `order_port` did to the arrangement — which is the point: the pad's arrows
// press what the owner SEES in that direction, not a fixed index into the set.
function groupButton(side, pos) {
  return [...groupEls[side].children].find((el) => el.style.gridArea === pos) || null;
}


// Re-render after anything that changes the category list (actions arrived,
// layout focus changed) — a group left pointing past the end falls back to 0.
function refreshCategories() {
  // A fresh set list may hold a custom set that has never been given a
  // colour — the map is rebuilt here, once, rather than per button
  // (client/theme.js).
  resetSetColors();
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
  // ONE activator per button — see the top of this file. `onTap` is stored,
  // never re-implemented: the pad calls this very function object.
  ACTIVATORS.set(el, { tap: onTap });
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
  // The one body both the finger and the pad run (see buttonPress above).
  const hold = (down) => {
    el.classList.toggle("held", down);
    send({ type: "press", button, down });
  };
  ACTIVATORS.set(el, { hold });
  el.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    pid = e.pointerId;
    hold(true);
  });
  const release = (e) => {
    if (pid === null || e.pointerId !== pid) return;
    pid = null;
    hold(false);
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
  // The GROUP wears the set's colour, so its four buttons and its category
  // button inherit it — one write instead of five, and the `colored` theme
  // needs nothing else (client/theme.css). A no-op in every other theme.
  // `--glass-fill` is what a D-pad button is painted with, and the readable
  // ink is derived from that surface, so the surface is NAMED rather than
  // guessed (client/theme.js → paintSet).
  paintSet(host, cat.name, "--glass-fill");

  const center = makeButton("ctl cat", cat.icon, cat.name);
  center.style.gridArea = "center";
  keepFocus(center, () => openWheel(side));
  host.appendChild(center);

  // Per-set, per-orientation button arrangement (owner 2026-08-05): the set
  // may carry order_land (slots T·L·R·B) and order_port (top→bottom column)
  // from the desktop editor; ours is the default and always restorable there.
  const btns = activeButtons(cat);
  // Keyed off the SHAPE, not the orientation (owner 2026-08-08, task 121).
  // `order_port` is his top-to-bottom COLUMN order and `order_land` his
  // T·L·R·B CROSS order — two different questions. A portrait tablet showing
  // the cross must take the cross's order, or his arrangement would arrive
  // scrambled into the four arms.
  const raw = padColumn() ? cat.order_port : cat.order_land;
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
    // The wheel is where the colours SAY what they are — and a wheel item is
    // painted with `--glass-strong` (0.85), a different surface from a D-pad
    // button's 0.20 tint, so it gets its own ink.
    paintSet(item, cat.name, "--glass-strong");
    item.style.left = `${cx + WHEEL_RADIUS * Math.cos(angle)}px`;
    item.style.top = `${cy + WHEEL_RADIUS * Math.sin(angle)}px`;
    keepFocus(item, () => {
      groups[side] = i;
      // His choice outlives the next excursion (sets.js -> rememberGroup).
      rememberGroup(side, cat.name);
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
  // The dimming veil is a layer of its own, under our chrome and over the
  // stream (client/style.css → body.wheel-open::before) — see the note there.
  document.body.classList.add("wheel-open");
}

function backdropCancel(e) {
  if (e.target === wheelEl) {
    e.preventDefault();
    closeWheel();
  }
}

function closeWheel() {
  wheelEl.classList.remove("open");
  document.body.classList.remove("wheel-open");
  wheelEl.removeEventListener("pointerdown", backdropCancel);
  wheelEl.innerHTML = "";
}

// The Sets picker and Quality panel overlays live in panels.js (split out
// 2026-08-05, THE STRUCTURE LAW) — openSetsPanel/openQualityPanel are called
// only at runtime, after every script has loaded.

// Rotation may carry a different button order per set (order_port) — and,
// since 2026-08-08, a different SHAPE (the cross is a choice in portrait too).
matchMedia("(orientation: portrait)").addEventListener("change", () => {
  applyPadShape();
  renderGroup("left");
  renderGroup("right");
});

// ── THE D-PAD SHAPE IS HIS CHOICE, IN BOTH ORIENTATIONS (task 121) ────────
// A 10" tablet held upright is ~800 CSS px wide, which fits two crosses with
// the picture between them; a 412 px phone does not. So the column stays the
// default and the cross is a per-device preference, exactly like every other
// phone-side switch (through the shell's SharedPreferences bridge, never bare
// localStorage — that is per-ORIGIN and split his state between the LAN and
// Tailscale addresses once already).
//
// `padColumn()` is the ONE question the rest of the page asks: the CSS shape
// and the per-set arrangement must never disagree about which of the two is
// on screen.
function padCross() {
  return prefGet("padCross") === "1";
}

function padColumn() {
  return matchMedia("(orientation: portrait)").matches && !padCross();
}

function applyPadShape() {
  document.body.classList.toggle("pad-cross", padCross());
}

function setPadCross(on) {
  prefSet("padCross", on ? "1" : "0");
  applyPadShape();
  renderGroup("left");
  renderGroup("right");
}

applyPadShape();
