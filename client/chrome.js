// The page's own FURNITURE, and what it does with itself: the Hide button,
// the rule that hides the controls after a quiet spell, and the toast.
//
// Split out of controls.js on 2026-08-08, when auto-hide pushed that file past
// THE STRUCTURE LAW's 1,000 lines. The boundary is a real one and it is worth
// saying out loud: everything in controls.js DRIVES THE PC — a button press
// becomes a click, a wheel choice becomes a different set of commands. Nothing
// in this file ever reaches the PC. It decides what our own chrome looks like
// and when it gets out of the way, which is why it can be reasoned about
// without knowing the protocol at all.
//
// Loads immediately AFTER controls.js (uses `keepFocus`), and before the
// panels: `autoHideBlocked` asks them by ELEMENT, so nothing here needs them
// to exist yet. `showToast` is called from almost everywhere at runtime.
// See client/__about/chrome.md.
"use strict";

// --- Corner buttons -------------------------------------------------------

const hideBtn = document.getElementById("btn-hide");

function setControlsHidden(hidden) {
  document.body.classList.toggle("hidden-controls", hidden);
  hideBtn.classList.toggle("active", hidden);
}

keepFocus(hideBtn, () => {
  // Safe to read the CURRENT state: `wakeControls` deliberately ignores a
  // press on this button (see there), so nothing has unhidden underneath
  // between pointerdown and this pointerup.
  setControlsHidden(!controlsHidden());
  lastWake = performance.now();
});

// ── THE CONTROLS GET OUT OF THE WAY BY THEMSELVES (owner 2026-08-08) ──────
//
// His spec, and both halves of it matter. The controls hide after three
// seconds of no contact and come back on any touch — and the BUTTON STAYS,
// because auto-hide is the lazy path and the button is the immediate one
// (his words: it is there so we can hurry it and not wait out the timer).
// They are the same state, so one function owns it.
//
// THE FENCE IS THE OTHER HALF, and it is the part that would otherwise have
// made this feature hated: nothing hides while a panel, the settings, a
// layout being built, or the central set-picking wheel is open — only the
// bare working screen, the one showing two groups of four buttons with the
// layout button and Hide above them. A card he is reading, a wheel he is
// choosing from, a layout he is building: none of those may vanish under his
// thumb.
//
// A TICK, NOT A ONE-SHOT TIMER, and the phone audit is what proved why: a
// blocker can open with NO touch at all — the notices card offers itself on
// connect, the dictation card opens itself on the first Mic tap, and the
// audit drives every panel through `page.evaluate`. A timer armed at load had
// already hidden the controls by then, so the wheel "opened" inside a
// `display: none` group and the audit failed on an invisible element. That is
// not an audit artefact: it is the same page his phone runs. So the rule is
// re-decided on every tick, and a blocker that appears while the controls are
// hidden BRINGS THEM BACK rather than merely stopping the countdown.
// 8 s, not the 3 s he first asked for: he lived with three and came back the
// same evening — "malo sam preterao, tri sekunde je prebrzo da nestanu ove
// komande, jako brzo nestanu" (lang-ok: his own words, quoted). Long enough to
// read a set and reach for the button you meant, short enough that the screen
// still clears itself while he watches something.
const AUTO_HIDE_MS = 8000;
const AUTO_HIDE_TICK_MS = 250;

// Every overlay this page can raise. Asked by ELEMENT rather than by a flag
// each panel would have to remember to set: a panel added next month is
// covered the moment it uses the same #id convention, and a flag someone
// forgot to clear is exactly how a feature like this earns its reputation.
const AUTO_HIDE_BLOCKERS = ["sets-panel", "quality-panel", "layout-panel",
                            "dictation-panel", "choice-panel", "notice-panel",
                            "region-panel"];

function autoHideBlocked() {
  if (document.body.classList.contains("wheel-open")) return true;
  // A creation session is live even while its panel is momentarily closed —
  // that is exactly the "tap a window" state, where the controls must stay.
  if (typeof creating !== "undefined" && creating) return true;
  if (typeof layoutArm !== "undefined" && layoutArm) return true;
  return AUTO_HIDE_BLOCKERS.some((id) => {
    const el = document.getElementById(id);
    return el && !el.hidden;
  });
}

function controlsHidden() {
  return document.body.classList.contains("hidden-controls");
}

let lastWake = performance.now();

// ANY contact brings them back, and restarts the wait. `pointerdown` in the
// CAPTURE phase so it fires whatever the target is — the canvas, a button, a
// backdrop — and before anything can stop it propagating. The Hide button is
// the ONE exception: it owns this state, and waking on its own press would
// leave it unable to unhide.
function wakeControls(e) {
  // THE ONE EXCEPTION, and it is load-bearing: this button OWNS the state.
  // Waking on its own press would unhide on pointerdown and let the toggle on
  // pointerup hide again, so the one button that must always work would be
  // the only one that never does. There is exactly ONE guard for that — the
  // first version also remembered the pre-press state in the handler, and
  // TWO mechanisms for one rule meant neither could be proven: planting a
  // defect in either walked straight through the gate because the other
  // covered it.
  if (e && hideBtn.contains(e.target)) return;
  if (controlsHidden()) setControlsHidden(false);
  lastWake = performance.now();
}

window.addEventListener("pointerdown", wakeControls, true);
window.addEventListener("pointermove", (e) => {
  // Only a real drag counts, not the hover a stylus or a mouse emits while
  // nothing is pressed: waking on hover would mean the controls never leave.
  if (e.buttons) wakeControls(e);
}, true);
window.addEventListener("keydown", wakeControls, true);
// The gamepad is neither a touch nor a keydown — the same hole the screen-awake
// timer fell into (CLAUDE.md constraint 12), and a controller-only session
// would otherwise sit in front of hidden controls it is actively pressing.
window.addEventListener("ru-pad", () => wakeControls());

setInterval(() => {
  if (autoHideBlocked()) {
    // Something he is looking at is open. Bring the controls back if they had
    // already gone, and hold the countdown for as long as it is open.
    if (controlsHidden()) setControlsHidden(false);
    lastWake = performance.now();
    return;
  }
  if (!controlsHidden() && performance.now() - lastWake >= AUTO_HIDE_MS) {
    setControlsHidden(true);
  }
}, AUTO_HIDE_TICK_MS);

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
