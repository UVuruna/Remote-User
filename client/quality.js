/* Stream quality — this device's overrides of the PC's own settings.
 *
 * Split out of controls.js + panels.js (THE STRUCTURE LAW) because quality is
 * one responsibility with two halves that only make sense together: the saved
 * per-device preferences and the panel that edits them.
 *
 * The model is a HIERARCHY, not two competing dials (owner 2026-08-05, after
 * "the desktop settings seem to do nothing"): the Vibe Coder window sets the
 * BASE (frame rate, encoded width, bitrate) and this panel may only go BELOW
 * it. That was already true in the server, but invisible here — the panel
 * happily showed "30 fps" selected while a 10 fps PC ignored it. So the panel
 * now states the PC's live values and greys out every step that cannot take
 * effect.
 */

// --- Saved preferences -----------------------------------------------------

const QUALITY_FPS = [0, 10, 15, 30, 60]; // 0 = follow the PC (its own max)
// "native" is ABOVE the PC's own encoder width — see RAISING below.
const QUALITY_RES = ["native", "full", "2/3", "1/2"];
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

// --- RAISING (owner decision, task 131) ------------------------------------
// The PC's card is the DEFAULT, not a wall. LOWERING is free — it happens
// inside this client's own ffmpeg on the PC and touches nothing else. RAISING
// is not: the shared capture has to grab faster or wider, so every encoder
// running off it is rebuilt and THE PICTURE BLINKS. That is affordable only
// because one device at a time is a hard rule (4409), and it is never done
// silently — a raised step SAYS it will blink, before he taps it.
//
// Two axes can be raised, and they are the two the PC's own defaults take
// away: the frame rate, and the encoder width (task 130 lowered the shipped
// default to 2560, so "Native" is how he gets his 4K monitor back). The
// bitrate cannot: its steps are PERCENTAGES of the PC's own choice by the
// owner's 2026-08-05 rule, so there is no number above "High" to ask for.

/** True when this fps step is ABOVE what the PC is set to — reachable, but
 *  only by rebuilding capture. Replaces the old `fpsUnreachable`, which greyed
 *  these out on the belief that the server would clamp them away. */
function fpsRaises(fps) {
  return !!(streamBase && fps > 0 && fps > streamBase.fps);
}

/** An fps step EQUAL to the PC's rate is simply "Max" said twice — not a
 *  raise, and not a lie either. Left selectable and unmarked. */
function fpsUnreachable() {
  return false;
}

/** "Native" asks for the monitor's own width when the PC's encoder is set
 *  lower. When the PC already streams the full monitor it is the same picture
 *  as "Full" and is marked so rather than offered as a phantom upgrade. */
function resRaises(res) {
  return !!(res === "native" && streamBase && monitor &&
            streamBase.width < monitor.w);
}

/** What the server needs in order to rebuild capture — absent (0) whenever
 *  nothing is being raised, so an ordinary panel tap carries nothing extra. */
function raiseRequest() {
  const p = qualityPrefs();
  return {
    raise_fps: fpsRaises(p.fps) ? p.fps : 0,
    raise_width: resRaises(p.res) && monitor ? monitor.w : 0,
  };
}

// --- THE DEVICE'S DECODER CEILING (owner report 2026-08-12) -----------------
// "Native 20 Mbps still sends no picture." His log: 3840×2160@30 played
// smoothly (jumps=0); the moment the PC card went to 60 fps the same tablet
// threw the picture forward ten times every 15 s — a decoder drowning, not a
// network. The rules live in client/decode-caps.js (pure, gated); this is the
// wiring: probe what THIS device decodes smoothly per resolution step, cap
// what we request, and SAY the cap — in a toast and in the panel.
//
// Two ceilings, lower wins (combinedCeiling): the persisted probe result, and
// a session-only override from the runtime backstop below. The probe is
// per-device (prefGet/prefSet — the sets-picker precedent), so from the next
// connection on even the FIRST auth message carries the capped fps and the
// encoder is never built at a rate this device cannot drink.
let decodeCeilings = {};
try { decodeCeilings = JSON.parse(prefGet("decodeCeilings") || "{}") || {}; } catch { decodeCeilings = {}; }
let decodeSessionCeilings = {};
let decodeProbeSig = "";
let decodeCapSaid = "";
let decodeBadWindows = 0;

function ceilingFor(width) {
  return combinedCeiling(decodeCeilings[String(width)] || 0,
                         decodeSessionCeilings[String(width)] || 0);
}

/** The width the CURRENT prefs would have the server encode — REGION-AWARE
 *  (owner order 2026-08-12): a stream cropped to a layout is a fraction of
 *  the step's width, and the ceiling must judge what is actually decoded,
 *  or a cap earned by the full 4K desktop would hold an easy layout crop at
 *  the capped fps. 0 before the first config — nothing capped before the
 *  base is known. */
function effectiveWidth(p) {
  if (!streamBase) return 0;
  const w = stepWidth(p.res, streamBase.width, monitor ? monitor.w : 0);
  return streamRegion && streamRegion.w > 0 ? Math.round(w * streamRegion.w) : w;
}

/** The cap decision for the current prefs — one source for the wire, the
 *  toast and the panel note, so they can never disagree. */
function decodeCapState(p) {
  return capFps(p.fps, streamBase ? streamBase.fps : 0, ceilingFor(effectiveWidth(p)));
}

/** Probe every resolution step's width once per PC shape (monitor + base),
 *  persist the ceilings, and restate quality if the running stream is above
 *  what this device just admitted to. Called on every h264 `config`; the
 *  signature check makes repeats free. Probe results only ever LOWER a
 *  stored ceiling — mediaCapabilities answers from the spec sheet, and a
 *  ceiling the runtime backstop had to lower must not creep back up. */
async function refreshDecodeCeilings() {
  if (!streamBase || !monitor || !monitor.w) return;
  const sig = `${monitor.w}x${monitor.h}|${streamBase.width}|${streamBase.fps}`;
  if (sig === decodeProbeSig) return;
  decodeProbeSig = sig;
  const before = JSON.stringify(effectiveQuality());
  const widths = [...new Set(QUALITY_RES.map((r) => stepWidth(r, streamBase.width, monitor.w)))];
  for (const w of widths) {
    const h = Math.round((w * monitor.h) / monitor.w);
    const smooth = await probeSmoothFps(w, h, bitrateBits(streamBase.bitrate), DECODE_FPS_STEPS);
    if (!smooth) return; // no API on this device — never cap anything
    const probed = smoothCeiling(smooth, DECODE_FPS_STEPS);
    const kept = decodeCeilings[String(w)] || 0;
    decodeCeilings[String(w)] = kept ? Math.min(kept, probed) : probed;
  }
  prefSet("decodeCeilings", JSON.stringify(decodeCeilings));
  if (JSON.stringify(effectiveQuality()) !== before) sendQuality();
}

/** The runtime backstop: render.js hands over each 15 s live window's jump
 *  count. Two drowning windows in a row lower this width's ceiling one step
 *  below what is running — session-only, so one bad evening on hotel Wi-Fi
 *  cannot permanently dull the stream; a decoder that really cannot keep up
 *  re-lowers within a minute of every session, which is the honest state. */
function noteDecodeStruggle(jumps) {
  decodeBadWindows = jumps >= DECODE_BAD_JUMPS ? decodeBadWindows + 1 : 0;
  if (decodeBadWindows < DECODE_BAD_WINDOWS) return;
  decodeBadWindows = 0;
  if (streamMode !== "h264" || !streamBase) return;
  const p = qualityPrefs();
  const width = effectiveWidth(p);
  const running = decodeCapState(p).fps || streamBase.fps || 0;
  const lower = struggleCeiling(running, DECODE_FPS_STEPS);
  if (!lower) return;
  decodeSessionCeilings[String(width)] = lower;
  showToast(`The picture keeps falling behind — dropping to ${lower} fps for this session.`);
  send({ type: "client_log", text:
    `[decode] struggle at ${width}px/${running}fps — session ceiling ${lower}fps` });
  sendQuality();
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
  // The device's decoder ceiling caps what we ask for (owner report
  // 2026-08-12): a 60 fps request at a width this SoC decodes at 30 goes out
  // as 30 — lowering is per-client and free, and a capped stream that PLAYS
  // beats an uncapped one that freezes. Uncapped, `fps` is the saved pref
  // untouched, "follow the PC" (0) included.
  return { fps: decodeCapState(p).fps, res: p.res, bitrate: p.bitrate };
}

function qualityOverridden() {
  const e = effectiveQuality();
  return e.fps !== 0 || e.res !== "full" || e.bitrate !== "high";
}

function sendQuality() {
  // `raise_*` rides the existing message as optional fields (the cursor-shape
  // pattern): a PC that predates task 131 ignores them and the panel simply
  // cannot go above its card, which is exactly the old behaviour.
  const p = qualityPrefs();
  const cap = decodeCapState(p);
  if (cap.capped) {
    // The cap is never silent — but said once per distinct decision, not on
    // every restatement of the same one (a reconnect restates quality).
    const key = `${effectiveWidth(p)}@${cap.fps}`;
    if (decodeCapSaid !== key) {
      decodeCapSaid = key;
      showToast(`This device decodes that resolution up to ${cap.fps} fps — using ${cap.fps}.`);
    }
  }
  lastQualitySent = JSON.stringify({ ...effectiveQuality(), ...raiseRequest() });
  send({ type: "quality", ...effectiveQuality(), ...raiseRequest() });
}

// The server re-applies this connection's STORED quality to every new
// session, so a value computed under one stream region outlives the region
// unless restated. Called by connection.js on every `config` (the frame that
// changes the region): a no-op whenever nothing effective moved.
let lastQualitySent = "";

function restateQualityIfChanged() {
  const now = JSON.stringify({ ...effectiveQuality(), ...raiseRequest() });
  if (now !== lastQualitySent && (qualityOverridden() || lastQualitySent)) sendQuality();
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
       — change that in the Vibe Coder window on the PC.`
    : "Waiting for the PC's own settings…";
  // A step marked ↑ is ABOVE the PC's own card (task 131). It is allowed —
  // the PC is a default, not a wall — but it rebuilds the shared capture, so
  // the picture blinks. Said here, before he taps, rather than discovered.
  const raised = QUALITY_FPS.some(fpsRaises) || resRaises("native");
  card.innerHTML = `<h2>Stream quality</h2>
    <p class="sets-sub">${pcLine}</p>
    <p class="sets-sub">Lower steps apply instantly.${raised ? `
       Steps marked <b>↑</b> are above what the PC is set to — they still work,
       but the picture <b>blinks once</b> while the PC rebuilds the capture.` : ""}</p>`;

  const upIf = (test) => (v, label) => (test(v) ? `${label} ↑` : label);
  const fpsLabel = upIf(fpsRaises);
  card.appendChild(segRow("FPS", QUALITY_FPS,
    ["Max", "10", "15", "30", "60"].map((l, i) => fpsLabel(QUALITY_FPS[i], l)),
    p.fps, (v) => saveQuality({ fps: v })));
  // The device's own wall, stated where he chooses (owner report 2026-08-12:
  // "native still sends no picture" was this tablet drowning in 4K@60). Only
  // shown when the ceiling actually bites the current choice — a device that
  // decodes everything sees nothing here.
  const capNow = decodeCapState(p);
  if (capNow.capped) {
    const capLine = document.createElement("p");
    capLine.className = "sets-sub";
    capLine.innerHTML = `This device decodes the chosen resolution up to
      <b>${capNow.fps} fps</b> — higher steps run at ${capNow.fps} automatically.`;
    card.appendChild(capLine);
  }
  card.appendChild(segRow("Resolution", QUALITY_RES,
    [resRaises("native") ? "Native ↑" : "Native", "Full", "⅔", "½"],
    p.res, (v) => saveQuality({ res: v }),
    // "Native" with nothing above the PC's width is the same picture as
    // "Full" — greyed rather than offered as a phantom upgrade.
    (v) => v === "native" && !resRaises("native")));
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
