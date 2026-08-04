// On-screen interactive chrome: icons, built-in action registry, touch-mode
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

const ICONS = {
  mouse: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 7v4"/>',
  right: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 3v7"/><path d="M12 3h2a4 4 0 0 1 4 4v3h-6z" fill="currentColor" stroke="none"/>',
  drag: '<polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><polyline points="15 19 12 22 9 19"/><polyline points="19 9 22 12 19 15"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/>',
  scroll: '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
  click: '<path d="M3 3l7.4 18 2.3-7.3L20 11.4z"/><path d="M14 6.5a7 7 0 0 0-8-2.4"/>',
  keyboard: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M18 13h.01M9 13h6"/>',
  monitor: '<rect x="2" y="4" width="14" height="10" rx="2"/><path d="M9 18h7"/><path d="M9 14v4"/><path d="m17 9 4 3-4 3"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-4.5-4.5L5 21"/>',
  snap: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  x: '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.09a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.09a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>',
  list: '<rect x="4" y="2.5" width="16" height="19" rx="2"/><rect x="9" y="1" width="6" height="3.5" rx="1"/><path d="m7.5 9 1.2 1.2L11 7.8"/><line x1="13" y1="9" x2="17" y2="9"/><path d="m7.5 14 1.2 1.2L11 12.8"/><line x1="13" y1="14" x2="17" y2="14"/><line x1="13" y1="18" x2="17" y2="18"/>',
  input: '<rect x="2" y="6" width="20" height="12" rx="2"/><line x1="6" y1="10" x2="6" y2="14"/><path d="m14 10 3 2-3 2"/>',
  gauge: '<path d="M12 20a8 8 0 1 1 8-8"/><path d="m12 12 5-3"/><path d="M17 17l3 3"/>',
  newwin: '<rect x="3" y="4" width="18" height="16" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><circle cx="6" cy="6.5" r="0.5" fill="currentColor"/><circle cx="8.5" cy="6.5" r="0.5" fill="currentColor"/><line x1="12" y1="11.5" x2="12" y2="17.5"/><line x1="9" y1="14.5" x2="15" y2="14.5"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
  // region inside the screen — the layout aspect-ratio panel
  aspect: '<rect x="2.5" y="4" width="19" height="16" rx="2"/><rect x="7" y="8" width="10" height="8" rx="1"/>',
  desktop: '<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
};

function svg(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
}

// --- Built-in group actions -----------------------------------------------

const BUILTINS = {
  // The finger itself only steers the cursor — clicks are explicit buttons at
  // the CURRENT cursor position; press twice fast for a double click. Right
  // is a click button too (owner decision 2026-07-26 — with the offset
  // pointer NOTHING may act on a canvas tap).
  click:    { label: "Click",  icon: "click",    kind: "send", msg: { type: "click", button: "left" } },
  right:    { label: "Right",  icon: "right",    kind: "send", msg: { type: "click", button: "right" } },
  drag:     { label: "Drag",   icon: "drag",     kind: "mode" },
  scroll:   { label: "Scroll", icon: "scroll",   kind: "mode" },
  keyboard: { label: "Keys",   icon: "keyboard", kind: "kb" },
  monitor:  { label: "Monitor", icon: "monitor", kind: "send", msg: { type: "monitor_switch" } },
  snap:     { label: "Snap",   icon: "snap",     kind: "send", msg: { type: "screenshot" } },
  upload:   { label: "Image",  icon: "image",    kind: "upload" },
  calibrate:{ label: "Calibrate", icon: "target", kind: "calibrate" },
  anywhere: { label: "Anywhere", icon: "globe",  kind: "anywhere" },
  // Phase F+ step 3 (owner spec): UIA-cycled focus through TEXT-INPUT fields
  // only — full desktop → all visible windows, layout focus → that layout —
  // built for the dictation-first workflow.
  next_input: { label: "Next box", icon: "input", kind: "send", msg: { type: "next_input" } },
  // full → reduced (half res, ~10 fps — saves data) → auto (reduced only on
  // mobile data, via the shell's transport bridge)
  quality:  { label: "Quality", icon: "gauge",  kind: "quality" },
};

// --- Stream quality (Phase F+ step 3) --------------------------------------

function qualityMode() {
  return localStorage.getItem("qualityMode") || "full";
}

function transportCellular() {
  try {
    return IN_APP && window.Android.transport && window.Android.transport() === "cellular";
  } catch {
    return false;
  }
}

function effectiveReduced() {
  const m = qualityMode();
  return m === "reduced" || (m === "auto" && transportCellular());
}

function sendQuality() {
  send({ type: "quality", reduced: effectiveReduced() });
}

function refreshQualityButtons() {
  document.querySelectorAll('[data-action="quality"]').forEach((el) =>
    el.classList.toggle("active", effectiveReduced()));
}

function cycleQuality() {
  const order = ["full", "reduced", "auto"];
  const m = order[(order.indexOf(qualityMode()) + 1) % order.length];
  localStorage.setItem("qualityMode", m);
  showToast(m === "full" ? "Quality: full"
    : m === "reduced" ? "Quality: reduced — saves data"
    : "Quality: auto — reduced on mobile data");
  sendQuality();
  refreshQualityButtons();
}

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
  else kbInput.focus({ preventScroll: true });
}

kbInput.addEventListener("focus", () => {
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
    anywhereOffer = localStorage.getItem("anywhereOffered") !== "1";
    localStorage.setItem("anywhereOffered", "1");
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

// --- Phone → PC image upload ----------------------------------------------

const filePick = document.getElementById("filepick");
filePick.addEventListener("change", async () => {
  const file = filePick.files && filePick.files[0];
  if (!file) return;
  showToast("Uploading image…");
  try {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(`/upload?token=${encodeURIComponent(token)}`, { method: "POST", body });
    const j = await res.json();
    // The server pastes it into the focused box by itself (Ctrl+V injected) —
    // picking the image was the whole gesture.
    showToast(j.ok ? "Image pasted on the PC" : "Upload failed");
  } catch (err) {
    showToast(`Upload failed: ${err.message}`);
  }
  filePick.value = "";
});

// --- D-pad groups ---------------------------------------------------------

const groupEls = {
  left: document.getElementById("group-left"),
  right: document.getElementById("group-right"),
};
const POSITIONS = ["up", "left", "right", "down"];

let categories = [];
const groups = { left: 0, right: 0 };

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

function makeActionButton(btn, pos) {
  let el;
  if (btn.action && BUILTINS[btn.action]) {
    const b = BUILTINS[btn.action];
    el = makeButton("ctl", b.icon, b.label);
    el.dataset.action = btn.action;
    if (b.kind === "mode") {
      el.dataset.mode = btn.action;
      keepFocus(el, () => setMode(btn.action));
    } else if (b.kind === "kb") {
      keepFocus(el, toggleKeyboard);
    } else if (b.kind === "send") {
      keepFocus(el, () => send(b.msg));
    } else if (b.kind === "upload") {
      keepFocus(el, () => filePick.click());
    } else if (b.kind === "calibrate") {
      // The offset/calibration system is gone (owner 2026-08-02 — the pointer
      // sits under the finger). The action stays registered so an owner
      // actions.json that still lists it renders a harmless button.
      keepFocus(el, () => showToast("Not needed anymore — the pointer is right under your finger"));
    } else if (b.kind === "anywhere") {
      keepFocus(el, openWizard); // the banner shows only once — this is the permanent way in
    } else if (b.kind === "quality") {
      keepFocus(el, cycleQuality);
    }
  } else if (btn.chord) {
    el = makeButton("ctl text", null, btn.label || btn.chord);
    keepFocus(el, () => send({ type: "chord", chord: btn.chord }));
  } else if (btn.key) {
    el = makeButton("ctl text", null, btn.label || btn.key);
    keepFocus(el, () => send({ type: "key_special", key: btn.key }));
  } else {
    el = makeButton("ctl text", null, btn.label || "?");
  }
  el.style.gridArea = POSITIONS[pos];
  return el;
}

function renderGroup(side) {
  const host = groupEls[side];
  host.innerHTML = "";
  const cat = categories[groups[side]];
  if (!cat) return;

  const center = makeButton("ctl cat", cat.icon, cat.name);
  center.style.gridArea = "center";
  keepFocus(center, () => openWheel(side));
  host.appendChild(center);

  (cat.buttons || []).slice(0, 4).forEach((btn, i) => host.appendChild(makeActionButton(btn, i)));
  refreshModeButtons();
  refreshQualityButtons();
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
  const n = categories.length;
  categories.forEach((cat, i) => {
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
