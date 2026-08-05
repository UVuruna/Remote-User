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

  const appRow = document.createElement("label");
  appRow.className = "sets-row apps";
  const appCb = document.createElement("input");
  appCb.type = "checkbox";
  appCb.checked = setsPrefs().apps;
  appCb.addEventListener("change", () => {
    const p = setsPrefs();
    p.apps = appCb.checked;
    saveSetsPrefs(p);
    refreshCategories();
  });
  appRow.append(appCb, document.createTextNode("App shortcuts while a layout is focused (VSCode, Chrome…)"));
  card.appendChild(appRow);

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

// --- Quality panel (Settings → Quality, owner 2026-08-05) ------------------
// Per-device overrides of the desktop defaults. Every tap saves and applies
// immediately (the server resets this client's encoder within a second);
// Done just closes.

const qualityPanel = document.getElementById("quality-panel");
const qualityOpened = { t: 0 };
ghostClickArmor(qualityPanel, qualityOpened);

function qualitySegRow(title, values, labels, current, onPick) {
  const row = document.createElement("div");
  row.className = "q-row";
  const cap = document.createElement("span");
  cap.className = "q-cap";
  cap.textContent = title;
  const seg = document.createElement("div");
  seg.className = "q-seg";
  values.forEach((v, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = labels[i];
    b.classList.toggle("on", v === current);
    b.addEventListener("click", () => {
      seg.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      onPick(v);
    });
    seg.appendChild(b);
  });
  row.append(cap, seg);
  return row;
}

function saveQuality(patch) {
  prefSet("qualityPrefs", JSON.stringify({ ...qualityPrefs(), ...patch }));
  sendQuality();
  refreshQualityButtons();
}

function openQualityPanel() {
  const p = qualityPrefs();
  qualityPanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card";
  card.innerHTML = `<h2>Stream quality</h2>
    <p class="sets-sub">Lower steps save data and battery. "Max" / "Full" / "High" follow the PC's own settings (Remote User window).</p>`;

  card.appendChild(qualitySegRow("FPS", QUALITY_FPS,
    ["Max", "10", "15", "30", "60"], p.fps, (v) => saveQuality({ fps: v })));
  card.appendChild(qualitySegRow("Resolution", QUALITY_RES,
    ["Full", "⅔", "½"], p.res, (v) => saveQuality({ res: v })));
  card.appendChild(qualitySegRow("Bitrate", QUALITY_BR,
    ["High", "Mid", "Low"], p.bitrate, (v) => saveQuality({ bitrate: v })));

  const autoRow = document.createElement("label");
  autoRow.className = "sets-row apps";
  const autoCb = document.createElement("input");
  autoCb.type = "checkbox";
  autoCb.checked = p.auto;
  autoCb.addEventListener("change", () => saveQuality({ auto: autoCb.checked }));
  autoRow.append(autoCb, document.createTextNode(
    "Save data on mobile networks (10 fps, ½ resolution, low bitrate)"));
  card.appendChild(autoRow);

  const done = document.createElement("button");
  done.type = "button";
  done.className = "sets-done";
  done.textContent = "Done";
  keepFocus(done, closeQualityPanel);
  card.appendChild(done);

  qualityPanel.appendChild(card);
  qualityPanel.hidden = false;
  qualityOpened.t = performance.now();
}

function closeQualityPanel() {
  qualityPanel.hidden = true;
  qualityPanel.innerHTML = "";
}

qualityPanel.addEventListener("pointerdown", (e) => {
  if (e.target === qualityPanel) closeQualityPanel(); // backdrop tap = done
});
