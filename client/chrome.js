// The page's own FURNITURE, and what it does with itself: the Hide button and
// its two modes, the mini radial a two-job button opens, the rule that hides
// the controls after a quiet spell, and the toast.
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

// STICKY KEEPS ITS OWN DOOR (owner report 2026-08-12: pressing Hide made
// everything vanish for good). `body.hidden-controls` took the Hide button
// with it — and in `sticky` NOTHING else brings the controls back, by design,
// so the one press that hides was also the last press the page would ever
// accept. His own spec for the mode had already said what must not go:
//   lang-ok: owner quote
//   "jedino što mora da ostane u tom modu je dugme Hide"
// So the state class is joined by a class that names the MODE, and
// client/style.css hides `.corner-tr` only under
// `body.hidden-controls:not(.hide-sticky)`. In `auto` nothing changes — any
// contact brings everything back, so the corner may go with the rest. The
// Layout corner stays hidden in BOTH modes: hidden means hidden, and the one
// exception is the way out, not a second button.
//
// This function stays the ONE writer of the hidden state, and the mode class
// is written here for the same reason: two writers of one visual state is how
// a flag someone forgot to clear earns this feature its reputation.
function setControlsHidden(hidden) {
  document.body.classList.toggle("hidden-controls", hidden);
  document.body.classList.toggle("hide-sticky", hideMode() === "sticky");
  hideBtn.classList.toggle("active", hidden);
}

// ── A BUTTON WITH MORE THAN ONE JOB OPENS A SMALL RADIAL BESIDE IT (owner
// 2026-08-09, task 158, with his sketch; widened to THREE 2026-08-12) ────────
//
// His geometry, and the reason for it: the two options drop straight below the
// button and below-diagonal from it — SOUTH and SOUTH-EAST — and that pair was
// chosen for the ANALOG STICK that is coming, not for the finger:
//   lang-ok: owner quote, kept verbatim because it names WHY these two angles
//   "važi za analog koji će na taj način lakše to birati"
// Two directions a thumb can point at without ambiguity is a gamepad
// affordance first; the finger simply inherits it. So the angles are fixed and
// named here rather than spread from the option count.
//
// THREE OPTIONS TAKE THE SAME FAN, ONE QUARTER-TURN WIDE (owner decision
// 2026-08-12, reversing task 186's centered ring for the Layout button):
// EAST, SOUTH-EAST, SOUTH. Every option sits 45° from its neighbour — exactly
// the separation the two-option pair already has — and all three stay inside
// the quadrant a TOP-LEFT corner button has free, so nothing is ever clamped
// by an edge. His verdict is that a button's options belong beside the button
// in ALL situations, phone portrait included: the Layout row stands above the
// picture, so the fan opens into it with room to spare. A FOURTH direction
// would have to shrink the separation below 45° or leave the quadrant, which
// is why the cap is stated out loud below (`MINI_MAX`) instead of being an
// accident of how many options a caller happens to pass.
//
// EACH OPTION IS A REAL BUTTON, drawn AND labelled:
//   lang-ok: owner quote
//   "isto kao i svi ostali batoni sa slikom i sa tekstom šta oni označavaju"
// `makeButton` from controls.js is what builds it, so an option wears the same
// 58 px face, the same icon size and the same label treatment as the D-pad and
// the corners — one implementation, exactly the rule constraint 9 exists for.
//
// MIRRORED ON THE RIGHT HALF OF THE SCREEN, deliberately. Hide sits in the
// top-RIGHT corner, so a south-east option would open off the screen; the pair
// becomes south / south-WEST there. The two directions stay distinct and
// diagonal, which is all the stick needs, and nothing is ever clamped on top of
// its sibling.
// EVERY OPTION IS THE PARENT'S OWN SQUARE, EVENLY SPACED ON ONE ARC (owner
// report 2026-08-12, with two screenshots of his own tablet). Round trip:
// the fan used to widen its faces to fit the longest label ("From a list")
// and grow its radius to the widest face, so a two-word option ("Stays
// hidden") sat in a visibly bigger box than "New" and the whole fan read as
// eyeballed rather than measured. His words, in translation: "their
// DIMENSIONS must be THE SAME AS THE PARENT, i.e. SQUARE, and their
// positions evenly spaced — exact angle." So the face is now exactly
// `--corner` (58px) — the SAME `.ctl` square the D-pad and the corners wear —
// and the radius is DERIVED from the tokens rather than a retuned constant:
// two neighbours sit 45° apart, and the chord between two circle points R
// apart in angle θ is 2R·sin(θ/2); requiring that chord to clear a face's own
// width plus one `--space-s` of daylight (the same gap `--space-s` names
// everywhere else on this page) gives R = (corner + gap) / (2·sin(22.5°)).
// Read from the CSS tokens at load, once — a later retune of `--corner` or
// `--space-s` carries straight through with no second number to remember.
function miniToken(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name);
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : fallback;
}
const MINI_FACE = miniToken("--corner", 58);
const MINI_GAP = miniToken("--space-s", 8);
const MINI_RADIUS = (MINI_FACE + MINI_GAP) / (2 * Math.sin(Math.PI / 8));

const MINI_EDGE = 8;         // px an option keeps clear of the screen edge
const MINI_MAX = 3;          // directions this quadrant holds — see above
// THE ONE DECLARED TABLE both the drawing and the gamepad's pointing read —
// `miniAngleSet` places the options by it and `miniRadialAngles()` (below)
// hands the gamepad exactly what was placed, clamp included, so there is no
// second copy of these three numbers anywhere to drift from this one.
const MINI_ANGLES = { east: 0, diagonal: Math.PI / 4, south: Math.PI / 2 };

// WHICH directions a radial of N options takes, in the order its options were
// given. Written out per count rather than spread from it: a PAIR hangs below
// the button (S, SE) while a FAN opens across the quadrant (E, SE, S), so the
// pair is not "the first two of the three" and never was. Hide is the pair;
// the Layout button's three sources are the fan.
function miniAngleSet(count) {
  return count >= 3
    ? [MINI_ANGLES.east, MINI_ANGLES.diagonal, MINI_ANGLES.south]
    : [MINI_ANGLES.south, MINI_ANGLES.diagonal];
}

const miniEl = document.createElement("div");
miniEl.id = "mini-radial";
miniEl.hidden = true;
document.body.appendChild(miniEl);

// WHICH button this radial belongs to right now — the second press of that same
// button is what CLOSES it (see openMiniRadial). Kept beside the element rather
// than on it: it is an element reference, not a string.
let miniAnchor = null;

// THE ANGLE EACH OPTION REALLY ENDED UP AT, measured from the anchor's centre
// AFTER the edge clamp — the controller's half of the same geometry (task 186,
// re-pointed 2026-08-12). The pad used to derive the direction of item i from
// the count, which is only true of a ring; the fan's directions are E/SE/S and
// a right-half anchor mirrors them. Recording what was placed means the stick
// points at where the option IS, whatever the placement rule does next, and
// there is no second copy of the arithmetic to drift (constraint 9).
let miniAngles = [];

function miniRadialAngles() {
  return miniAngles;
}

function closeMiniRadial() {
  miniEl.hidden = true;
  miniEl.innerHTML = "";
  miniAnchor = null;
  miniAngles = [];
}

// What the CONTROLLER needs of this component, and nothing more (task 186).
// The pad holds L2, points, and lets go — so it must be able to ask which
// options are on screen, light the one being pointed at, and run it. All three
// go through the SAME elements the finger taps.
function miniRadialItems() {
  return [...miniEl.querySelectorAll(".mini-item")];
}

function miniRadialOpen() {
  return !miniEl.hidden;
}

function miniRadialLight(index) {
  miniRadialItems().forEach((el, i) => el.classList.toggle("current", i === index));
}

function miniRadialPick(index) {
  const el = miniRadialItems()[index];
  if (el && el.__miniPick) el.__miniPick();
}

// PURE — the geometry alone, so its gate can drive every corner by argument
// instead of by opening a panel (tests/test_mini_radial.py). Returns the
// option centres in screen coordinates, already clamped to the viewport.
function miniRadialPoints(anchor, count, screen) {
  const cx = anchor.left + anchor.width / 2;
  const cy = anchor.top + anchor.height / 2;
  // The anchor's own side decides which way the diagonal leans — measured from
  // the anchor, never from where the finger happened to land.
  const lean = cx > screen.width / 2 ? -1 : 1;
  const angles = miniAngleSet(count);
  const half = anchor.size / 2 + MINI_EDGE;
  return angles.slice(0, count).map((a) => {
    // SOUTH's own cosine is zero, so the pair's first option still lands on the
    // anchor's axis exactly as it did when that case was written out by index.
    const dx = lean * MINI_RADIUS * Math.cos(a);
    const dy = MINI_RADIUS * Math.sin(a);
    return {
      x: Math.min(Math.max(cx + dx, half), screen.width - half),
      y: Math.min(Math.max(cy + dy, half), screen.height - half),
    };
  });
}

// ── THE CENTERED RING IS GONE (owner decision 2026-08-12) ──────────────────
//
// Between 2026-08-09 and this date the layout-birth radial had a SECOND
// placement: a ring in the middle of the screen behind the category wheel's
// veil, with the wheel's own ✕, adopted when its options became three
// ("najbolje da se držimo istog pravila" — lang-ok: owner quote). He reversed
// it after living with it: the options open BESIDE the Layout button, in every
// situation, as the fan above. The ring, its radius, its veil
// (`body.mini-open::before`) and its ✕ were deleted the same day rather than
// left standing unreachable — a second placement nobody opens is the legacy
// this project keeps paying for (CLAUDE.md constraint 6).
//
// The D-pad group's own CATEGORY wheel (controls.js -> openWheel) draws a
// bigger, plain ring of its own — that one is alive and is what the points
// below place. It is the SAME fix for the SAME shape: task
// 238, owner screenshot, "in landscape the wheel shows only four sets while
// portrait shows all enabled ones". `openWheel` used a fixed 118 px radius
// with NO clamp at all — unlike the mini radial, which has always clamped an
// option back onto the screen rather than letting it leave. A phone's landscape
// HEIGHT is its SHORT side (~360-412 px, against an ~900 px portrait height),
// so the same 118 px radius that comfortably fits six-plus items in portrait
// leaves only a thin margin in landscape — and on a real device (a slightly
// shorter phone, or the transient system bars constraint 9 describes) that
// margin goes negative and an item's CENTRE lands outside the viewport. The
// item never left the DOM — every one of them still rendered — but a finger
// cannot reach a centre off-screen and a screenshot shows a hole where it
// should be, which reads as "the wheel dropped it". Shrinking the radius
// keeps every item ON the ring and ON screen, whatever the count; nothing is
// ever sliced off the list — the actual "drop entries silently" failure is
// what this function exists to NOT do. PURE, so its gate can drive every
// size and count by argument, the same discipline `miniRadialPoints` keeps.
const WHEEL_RADIUS = 118;
const WHEEL_ITEM_SIZE = 74;  // px — matches .wheel-item in style.css
const WHEEL_EDGE = 8;        // px an item keeps clear of the screen edge

function wheelPoints(count, screen, size) {
  const half = (size || WHEEL_ITEM_SIZE) / 2 + WHEEL_EDGE;
  const r = Math.max(0, Math.min(WHEEL_RADIUS, Math.min(screen.width, screen.height) / 2 - half));
  const cx = screen.width / 2;
  const cy = screen.height / 2;
  return Array.from({ length: count }, (_, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / Math.max(1, count);
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  });
}

// `options` = [{icon, label, onPick}] — at most `MINI_MAX`, anchored beside
// the button that owns them (see the geometry note above).
//
// A SECOND PRESS OF THE SAME BUTTON CLOSES IT, and that is not a convenience —
// it is the only way OUT for the gamepad (found by the input gate, 2026-08-11).
// A finger cancels on the backdrop, which covers the whole screen and therefore
// covers the anchor button too; the PAD has no backdrop to tap. L2 is Layout (+)
// (CLAUDE.md constraint 12), so without this a controller-only session could
// open the source radial and never dismiss it — it would simply re-open on
// every press, with a full-screen overlay standing over the picture. The
// activator is unchanged and still the one a finger runs: what changed is that
// the activator's own body now toggles, so BOTH input paths get the same door
// in and the same door out, which is what constraint 12 is for.
function openMiniRadial(anchorEl, options) {
  const reopening = !miniEl.hidden && miniAnchor === anchorEl;
  closeMiniRadial();
  if (reopening) return;
  miniAnchor = anchorEl;
  const screen = { width: window.innerWidth, height: window.innerHeight };
  const r = anchorEl.getBoundingClientRect();
  const items = options.slice(0, MINI_MAX);
  const points = miniRadialPoints(
    // `size` is the OPTION's own face — now the SAME square as the parent
    // corner button (`--corner`, owner report 2026-08-12), so this is exactly
    // `anchorEl`'s own measured size and never a wider, label-fitted face.
    { left: r.left, top: r.top, width: r.width, height: r.height, size: MINI_FACE },
    items.length, screen);
  // The direction the CONTROLLER has to point along, per option, measured from
  // what was actually placed — lean and edge clamp already in it.
  const cx = r.left + r.width / 2;
  const cy = r.top + r.height / 2;
  miniAngles = points.map((p) => Math.atan2(p.y - cy, p.x - cx));
  items.forEach((opt, i) => {
    // The SAME maker every other button on this page goes through.
    const el = makeButton("ctl mini-item", opt.icon, opt.label);
    el.style.left = `${points[i].x}px`;
    el.style.top = `${points[i].y}px`;
    // The pick is held ON the element so BOTH input paths reach the same one:
    // the finger through `keepFocus`, the pad through `miniRadialPick`. A
    // second copy of the option list for the controller is exactly the
    // parallel button path constraint 9 was written about.
    el.__miniPick = () => {
      closeMiniRadial();
      opt.onPick();
    };
    keepFocus(el, () => el.__miniPick());
    miniEl.appendChild(el);
  });
  miniEl.hidden = false;
}

// A tap anywhere but on an option cancels — the same contract the category
// wheel's backdrop has had since it shipped, so there is nothing new to learn.
miniEl.addEventListener("pointerdown", (e) => {
  if (e.target === miniEl) {
    e.preventDefault();
    closeMiniRadial();
  }
});

// ── HIDE HAS TWO MODES, AND HE NAMED THE TRADE-OFF HIMSELF (owner 2026-08-09,
// task 159) ─────────────────────────────────────────────────────────────────
//
// Mode `auto` is what has always shipped: the controls go after a quiet spell
// and ANY contact brings them back. Its cost, in his words: sometimes he wants
// to move the mouse TO the place the buttons occupy, and he cannot, because the
// moment the finger moves they are back.
// Mode `sticky` is the answer to that: hidden stays hidden until Hide is
// pressed again — nothing brings the controls back by itself. Its cost, also
// his: the Hide button's own corner is then permanently covered by whatever he
// is doing. Neither is better, which is exactly why BOTH ship and the choice is
// his, per device.
//
// A BLOCKER STILL BRINGS THEM BACK IN BOTH MODES, and that is not a loophole.
// A panel, a card or the wheel is something he must READ, and every one of them
// is reached THROUGH the controls — except the two that open themselves (the
// notices card on connect, the dictation card on the first Mic tap). Leaving a
// card on screen with its own controls hidden underneath is not "hidden stays
// hidden", it is a dialog with no way out.
const HIDE_MODES = ["auto", "sticky"];

function hideMode() {
  const stored = prefGet("hideMode");
  return HIDE_MODES.includes(stored) ? stored : "auto";
}

function setHideMode(mode) {
  prefSet("hideMode", HIDE_MODES.includes(mode) ? mode : "auto");
}

// THE PRIMARY ACT IS NEVER LOST. A tap on Hide hides — that is the one thing
// this button has always done, and a radial that swallowed it would be a
// regression dressed as a feature. The MODE lives on a HOLD, the same 380 ms
// hold a layout row is picked up by (client/layouts.js), so the two gestures on
// this page that mean "tell me more about this thing" agree.
const HIDE_HOLD_MS = 380;
// A REAL fingertip jitters: pointermove fires within milliseconds of the
// touch, so cancelling the hold on ANY move meant the radial could never open
// on a phone — only on a perfectly still mouse, which is exactly what every
// gate used (owner repeat report 2026-08-11: the hold "does not exist" on his
// device). The hold survives movement under this slop; real travel (a swipe
// across the button) still cancels.
const HIDE_HOLD_SLOP = 12;
let hideHoldTimer = null;
let hideHeld = false;
let hideHoldX = 0;
let hideHoldY = 0;

function openHideModes() {
  const current = hideMode();
  openMiniRadial(hideBtn, [
    { icon: "hideauto", label: "Comes back",
      onPick: () => {
        setHideMode("auto");
        showToast("Hide: the controls come back on any touch");
      } },
    { icon: "hidestay", label: "Stays hidden",
      onPick: () => {
        setHideMode("sticky");
        showToast("Hide: they stay hidden until you press Hide again");
      } },
  ]);
  // The one already chosen is lit, so the radial SAYS which state he is in
  // instead of only offering two.
  const lit = current === "auto" ? 0 : 1;
  if (miniEl.children[lit]) miniEl.children[lit].classList.add("active");
}

hideBtn.addEventListener("pointerdown", (e) => {
  hideHeld = false;
  hideHoldX = e.clientX;
  hideHoldY = e.clientY;
  hideHoldTimer = setTimeout(() => {
    hideHoldTimer = null;
    hideHeld = true;
    openHideModes();
  }, HIDE_HOLD_MS);
});
for (const kind of ["pointerup", "pointercancel"]) {
  hideBtn.addEventListener(kind, () => {
    if (hideHoldTimer) {
      clearTimeout(hideHoldTimer);
      hideHoldTimer = null;
    }
  });
}
hideBtn.addEventListener("pointermove", (e) => {
  if (!hideHoldTimer) return;
  if (Math.hypot(e.clientX - hideHoldX, e.clientY - hideHoldY) > HIDE_HOLD_SLOP) {
    clearTimeout(hideHoldTimer);
    hideHoldTimer = null;
  }
});

keepFocus(hideBtn, () => {
  // The hold already answered this press — it opened the mode radial, and the
  // release that ends a hold must not ALSO hide.
  if (hideHeld) {
    hideHeld = false;
    return;
  }
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
// `mini-radial` joins them (task 158): it is two buttons floating beside a
// corner, drawn OUTSIDE `.group`, so the auto-hide rule could not see it at all
// — and a set of options that vanishes while he is deciding between them is the
// exact failure the fence exists to stop.
const AUTO_HIDE_BLOCKERS = ["sets-panel", "quality-panel", "layout-panel",
                            "dictation-panel", "choice-panel", "notice-panel",
                            "region-panel", "mini-radial"];

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
  // MODE `sticky` (owner 2026-08-09, task 159): hidden stays hidden until Hide
  // is pressed again. The wait is still restarted below, so switching back to
  // `auto` while hidden does not immediately re-arm a stale countdown — the
  // only thing this mode changes is that contact no longer UNHIDES.
  if (controlsHidden() && hideMode() === "sticky") return;
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
  // `sticky` never hides by itself either (task 159): the mode is "the state
  // changes ONLY when Hide is pressed", and a timer that took the controls away
  // would break that promise from the other side.
  if (hideMode() === "sticky") return;
  if (!controlsHidden() && performance.now() - lastWake >= AUTO_HIDE_MS) {
    setControlsHidden(true);
  }
}, AUTO_HIDE_TICK_MS);

// ── THE LAYOUT BAR ALSO SWITCHES BY SWIPE (owner 2026-08-11, with his
// screenshot of v0.0.107) ────────────────────────────────────────────────────
//
// He asked for it in the same breath as making the arrows small again: the bar
// should step the layouts when a finger is dragged across it left or right,
// not only when one of the two arrows is hit. The two are one thought — the
// arrows shrink to give the NAME the row, and the gesture is what makes that
// affordable, because a small glyph is a smaller target and the whole bar
// becomes the big one.
//
// It lives HERE rather than in layouts.js for the reason this file exists:
// nothing in it reaches the PC. A swipe decides which layout the bar is
// showing by calling `layoutStep`, the very function the arrows call — one
// activator, never a second path (constraint 9).
//
// CAPTURE PHASE, and that is the load-bearing detail. The bar's inner controls
// (the framed name, the ✕) fire on pointerup through `keepFocus`; a drag that
// ENDS on the name would otherwise both step the layout AND open the list. So
// the decision is taken before the target hears anything, and a real swipe
// stops the event there.
const SWIPE_MIN_PX = 44;      // below this it is a tap with a shaky finger
const layBar = document.getElementById("layout-bar");
let swipeFrom = null;

layBar.addEventListener("pointerdown", (e) => {
  swipeFrom = { x: e.clientX, y: e.clientY, id: e.pointerId };
}, true);

layBar.addEventListener("pointerup", (e) => {
  const from = swipeFrom;
  swipeFrom = null;
  if (!from || from.id !== e.pointerId) return;
  const dx = e.clientX - from.x;
  // HORIZONTAL, and more horizontal than vertical: a finger travelling mostly
  // downward is reaching for the picture, not stepping a layout.
  if (Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) <= Math.abs(e.clientY - from.y)) {
    return;
  }
  e.preventDefault();
  e.stopPropagation();
  // Dragging LEFT moves forward, the way a stack of cards behaves under a
  // finger — the same direction the › arrow on that side points.
  layoutStep(dx < 0 ? 1 : -1);
}, true);

layBar.addEventListener("pointercancel", () => { swipeFrom = null; }, true);

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
