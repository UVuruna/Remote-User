/* Stream quality — this device's overrides of the PC's own settings.
 *
 * Split out of controls.js + panels.js (THE STRUCTURE LAW) because quality is
 * one responsibility with two halves that only make sense together: the saved
 * per-device preferences and the panel that edits them.
 *
 * The model is a HIERARCHY, not two competing dials (owner 2026-08-05, after
 * "the desktop settings seem to do nothing"): the Remote User window sets the
 * BASE (frame rate, encoded width, bitrate) and this panel may only go BELOW
 * it. That was already true in the server, but invisible here — the panel
 * happily showed "30 fps" selected while a 10 fps PC ignored it. So the panel
 * now states the PC's live values and greys out every step that cannot take
 * effect.
 */

// --- Saved preferences -----------------------------------------------------

const QUALITY_FPS = [0, 10, 15, 30, 60]; // 0 = follow the PC (its own max)
const QUALITY_RES = ["full", "2/3", "1/2"];
const QUALITY_BR = ["high", "mid", "low"];
const QUALITY_DEFAULTS = { fps: 0, res: "full", bitrate: "high", auto: false };

// The PC's Settings card, refreshed by every `config` message.
// { fps, width, height, bitrate, bitrate_mid, bitrate_low } or null before
// the first config.
let streamBase = null;

function setStreamBase(base) {
  streamBase = base && base.fps ? base : null;
  // A PC that dropped below a saved choice makes that choice a lie — reset it
  // to "Max" rather than leave a step lit that can never happen.
  const raw = rawQualityPrefs();
  if (raw.fps && fpsUnreachable(raw.fps)) {
    prefSet("qualityPrefs", JSON.stringify({ ...raw, fps: 0 }));
  }
}

// An fps step at or above the PC's own frame rate is identical to "Max" — the
// server clamps it away (it only ever lowers). Saying so beats pretending.
function fpsUnreachable(fps) {
  return !!(streamBase && fps > 0 && fps >= streamBase.fps);
}

function rawQualityPrefs() {
  try {
    const p = JSON.parse(prefGet("qualityPrefs") || "{}");
    return {
      fps: QUALITY_FPS.includes(p.fps) ? p.fps : 0,
      res: QUALITY_RES.includes(p.res) ? p.res : "full",
      bitrate: QUALITY_BR.includes(p.bitrate) ? p.bitrate : "high",
      auto: p.auto === true,
    };
  } catch {
    return { ...QUALITY_DEFAULTS };
  }
}

function qualityPrefs() {
  const p = rawQualityPrefs();
  if (fpsUnreachable(p.fps)) p.fps = 0;
  return p;
}

function transportCellular() {
  try {
    return IN_APP && window.Android.transport && window.Android.transport() === "cellular";
  } catch {
    return false;
  }
}

// What the server should actually run for this device right now: the saved
// choices, except that auto-on-mobile-data overrides them with the saving
// profile while on cellular (re-evaluated on every (re)connect — a network
// switch reconnects by rule).
function effectiveQuality() {
  const p = qualityPrefs();
  if (p.auto && transportCellular()) return { fps: 10, res: "1/2", bitrate: "low" };
  return { fps: p.fps, res: p.res, bitrate: p.bitrate };
}

function qualityOverridden() {
  const e = effectiveQuality();
  return e.fps !== 0 || e.res !== "full" || e.bitrate !== "high";
}

function sendQuality() {
  send({ type: "quality", ...effectiveQuality() });
}

function refreshQualityButtons() {
  document.querySelectorAll('[data-action="quality"]').forEach((el) =>
    el.classList.toggle("active", qualityOverridden()));
}

// --- The panel -------------------------------------------------------------
// Every tap saves and applies immediately (the server resets this client's
// encoder within a second); Done just closes.

const qualityPanel = document.getElementById("quality-panel");
const qualityOpened = { t: 0 };
ghostClickArmor(qualityPanel, qualityOpened);

// The segmented row this panel invented moved to panels.js as `segRow` on
// 2026-08-11, when the Phone card (task 161) needed the identical control.
// One builder, three callers — never a second copy to drift from.

function saveQuality(patch) {
  prefSet("qualityPrefs", JSON.stringify({ ...qualityPrefs(), ...patch }));
  sendQuality();
  refreshQualityButtons();
}

// "12000k" → "12 Mbps", "1200k" → "1.2 Mbps" — the panel speaks the same
// units as the PC window's Bitrate combo.
function mbpsLabel(text) {
  const raw = String(text || "").trim();
  const unit = raw.slice(-1).toLowerCase();
  const number = parseFloat(raw) || 0;
  const mbps = unit === "m" ? number : unit === "k" ? number / 1000 : number / 1e6;
  return `${mbps >= 10 ? Math.round(mbps) : Math.round(mbps * 10) / 10} Mbps`;
}

function openQualityPanel() {
  const p = qualityPrefs();
  const b = streamBase;
  qualityPanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card card-columns";
  // The truth first: what the PC itself is set to. Without it "Max/Full/High"
  // are three words that could mean anything.
  const pcLine = b
    ? `This PC is set to <b>${b.fps} fps · ${b.width}×${b.height} · ${mbpsLabel(b.bitrate)}</b>
       — change that in the Remote User window on the PC.`
    : "Waiting for the PC's own settings…";
  card.innerHTML = `<h2>Stream quality</h2>
    <p class="sets-sub">${pcLine}</p>
    <p class="sets-sub">The steps below can only go <b>lower</b> than the PC —
       greyed-out steps are already above what it allows.</p>`;

  card.appendChild(segRow("FPS", QUALITY_FPS,
    ["Max", "10", "15", "30", "60"], p.fps, (v) => saveQuality({ fps: v }),
    fpsUnreachable));
  card.appendChild(segRow("Resolution", QUALITY_RES,
    ["Full", "⅔", "½"], p.res, (v) => saveQuality({ res: v })));
  card.appendChild(segRow("Bitrate", QUALITY_BR,
    b ? [mbpsLabel(b.bitrate), mbpsLabel(b.bitrate_mid), mbpsLabel(b.bitrate_low)]
      : ["High", "Mid", "Low"],
    p.bitrate, (v) => saveQuality({ bitrate: v })));

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
