// The Bluetooth game controller, as the page sees it (build rounds G1/G2,
// owner spec 2026-08-07). The pad pairs with the PHONE, not with the PC, and
// the WebView does not reliably expose the Gamepad API — so the Android shell
// captures every KeyEvent and MotionEvent and calls the three entry points at
// the bottom of this file (`__padButton`, `__padAxis`, `__padInfo`), exactly
// the way the mic reaches the page through `__voiceResult`. That is the house
// rule: the shell adds ONLY what a browser cannot, and the MAPPING — this file
// — lives on the page, on the existing protocol. The server learns nothing new.
//
// The one law of this module: A PAD PRESS IS A BUTTON PRESS. Every mapped
// button goes through `buttonPress()` in controls.js — the same activator the
// finger's pointerup runs — so CLICK/HOLD semantics, the pointercancel rescue
// and `keepFocus` cannot drift apart from what the pad does (CLAUDE.md
// constraint 9: a second, parallel button path is the failure that killed
// every control on the real device once already).
//
// Loads after layouts.js (it calls `layoutStep`/`openLayoutPicker`) and before
// gestures.js. See client/__about/gamepad.md.
"use strict";

// --- Tunables -------------------------------------------------------------
// The owner's answer to the open question was "start from this table and tune
// it on the real controller" — so these are START values, chosen for reasons,
// and every one of them is meant to move once a real pad is in his hands.
// The GATE pins the SHAPE of the curve, not these numbers, so tuning them
// never turns the build red.

// Sticks rest within roughly ±0.08–0.12 of centre when new and drift further
// as they wear; 0.15 sits above that and still leaves 85% of the travel usable.
const PAD_DEADZONE = 0.15;
// Squared response: half tilt = a quarter of top speed, so the last third of
// the travel carries most of the speed. Linear (1) makes precise placement on
// a 4K desktop nearly impossible; cubed (3) leaves the middle of the stick
// feeling dead.
const PAD_CURVE = 2;
// Monitor widths per second at full tilt — a full traverse in ~1.1 s.
const PAD_CURSOR_SPEED = 0.9;
// Wheel ticks per second at full tilt (one tick = SCROLL_PX_PER_TICK on the PC).
// Shared by both axes of the right stick — vertical (`ry`, shipped first) and
// horizontal (`rx`, closing the gap the gamepad round reported: the protocol
// only carried one wheel value and the injector only knew `MOUSEEVENTF_WHEEL`).
const PAD_SCROLL_TICKS = 12;
// A shoulder held for less than this, with the stick never pointing anywhere,
// was a TAP — the ‹ › layout bar — not an attempt to open the wheel.
const PAD_TAP_MS = 320;
// How far a stick must leave centre before it is POINTING at a wheel item.
// Deliberately well above the deadzone: resting drift must never pick a set.
const PAD_POINT_MIN = 0.45;
// How far OFF an option's own direction the stick may be and still be pointing
// at it (radians). A RING divides the whole circle between its items, so every
// direction belongs to one of them; a FAN does not — the mini radial's three
// options occupy a single quadrant and everything outside it must mean
// "nothing", which is the owner's own rule for releasing at nothing (task
// 186). 60° is wider than the 45° between two neighbouring options, so the
// cones overlap and the NEAREST one wins there — a thumb between two options
// still picks one — while pointing away from the fan altogether picks none.
const PAD_POINT_CONE = Math.PI / 3;
// A frame the page missed (backgrounded, a slow decode) must not teleport the
// cursor across the screen when it comes back.
const PAD_MAX_DT = 100;
// How often pad activity may re-arm the screen-awake timer. Far below
// KEEP_AWAKE_MS, far above one frame.
const PAD_AWAKE_THROTTLE_MS = 5000;

// --- The mapping (owner's table, 2026-08-07) -------------------------------
// The shell names buttons by POSITION, never by a vendor's letter: △ ◻ ○ ✕ on
// a PlayStation pad and Y X B A on an Xbox one sit in the same four places, so
// `f_up` is the top face button on both and the page never learns which brand
// is in the owner's hands.
//
//   group   — one of the two on-screen D-pad groups, by SLOT: the pad presses
//             what he SEES in that direction, whatever the set's arrangement
//   corner  — a fixed corner button, by element id
//   shoulder— hold to open that side's category wheel, tap to step the layouts
//   act     — a pad-only action: there is no on-screen button to share with
const PAD_MAP = {
  d_up:    { group: "left",  pos: "up" },
  d_left:  { group: "left",  pos: "left" },
  d_right: { group: "left",  pos: "right" },
  d_down:  { group: "left",  pos: "down" },
  f_up:    { group: "right", pos: "up" },
  f_left:  { group: "right", pos: "left" },
  f_right: { group: "right", pos: "right" },
  f_down:  { group: "right", pos: "down" },
  // L2 CARRIES THE TWO JOBS THE LAYOUT BUTTON CARRIES (owner 2026-08-09, task
  // 186 — "aha ok onda L2, u pravu si"; lang-ok: owner quote). His sketches
  // said L1, and L1 held is already the left category wheel, so the mapping
  // flag was raised and he moved it: TAP arms the tap-pick, exactly as the
  // Layout button did before it grew a radial, and HOLD opens the source
  // radial with the stick pointing at it. That is the L1/R1 grammar verbatim —
  // hold, point, release confirms, release at nothing changes nothing — which
  // is why it is worth one more entry here and not a second model to learn.
  // R2 keeps its own two modes (tap = hide now, hold = the Hide radial),
  // untouched.
  l2:      { radial: "layout", tap: () => layoutTapSource() },
  r2:      { corner: "btn-hide" },
  l1:      { shoulder: "left",  step: -1 },
  r1:      { shoulder: "right", step: 1 },
  // Double click and middle click have no on-screen button of their own —
  // `click` is the protocol's "at the CURRENT cursor, no coordinates" press,
  // which is precisely what a pad wants: the stick already aimed.
  l3:      { act: () => { padClick("left"); padClick("left"); } },
  r3:      { act: () => padClick("middle") },
  // Start/Select share the FUNCTION the on-screen buttons call, not a copy of
  // it: `toggleKeyboard` is what the Keys button's keepFocus runs, and
  // `openLayoutPicker` is what the layout bar's framed name runs.
  start:   { act: () => toggleKeyboard() },
  select:  { act: () => openLayoutPicker() },
};

function padClick(button) {
  send({ type: "click", button });
}

// --- Stick state ----------------------------------------------------------

const padAxes = { lx: 0, ly: 0, rx: 0, ry: 0 };
let padLoop = null;      // rAF handle while any stick is off centre
let padLast = 0;
let padScrollAcc = 0;    // sub-tick scroll carry (vertical, ry)
let padScrollAccH = 0;   // sub-tick scroll carry (horizontal, rx)
// Which element each held pad button is holding. The element, not the slot:
// a category switch re-renders the group and throws the button away, and a
// PC mouse button left down would then never be released.
const padHeld = new Map();
// {side, step, at, index} while a shoulder is down and the wheel is open.
let padWheel = null;
// {at, index} while L2 is down and the layout-birth radial is open (task 186).
// A SECOND variable rather than a mode inside `padWheel`: the two menus are
// different components with different contents, and folding them together
// would mean every branch below asking which one it is holding.
let padRadial = null;

// Deadzone + gentle curve. Returns 0 inside the deadzone, ±1 at full tilt.
function padCurve(v) {
  const m = Math.abs(v);
  if (!(m > PAD_DEADZONE)) return 0;
  const t = (m - PAD_DEADZONE) / (1 - PAD_DEADZONE);
  return Math.sign(v) * Math.pow(t, PAD_CURVE);
}

function padSticksLive() {
  return !!(padCurve(padAxes.lx) || padCurve(padAxes.ly) ||
            padCurve(padAxes.rx) || padCurve(padAxes.ry));
}

// One cursor step. Split out of the loop so the input gate can drive an exact
// dt through the REAL mapping instead of racing a frame clock.
function padCursorStep(dt) {
  const dx = padCurve(padAxes.lx);
  const dy = padCurve(padAxes.ly);
  if (!dx && !dy) return;
  const from = cursorPos || { x: 0.5, y: 0.5 };
  // In layout focus the cursor lives inside one framed window, a fraction of
  // the monitor — the same tilt must not fly across it in a tenth of a second.
  const rw = viewLocked() ? layoutRegion.w : 1;
  const rh = viewLocked() ? layoutRegion.h : 1;
  const step = PAD_CURSOR_SPEED * dt / 1000;
  sendCursor(clampRemote(from.x + dx * step * rw, from.y + dy * step * rh));
}

// One scroll step, both axes of the right stick. Ticks are whole, so each
// axis's fraction carries to the next frame — a gentle tilt scrolls slowly
// instead of not at all. Only runs while the wheel is closed: padTick (the
// only caller) stops while a shoulder is held, and while it is the stick's
// deflection is spent on padAimWheel() instead — one stick, one job at a time.
function padScrollStep(dt) {
  const v = padCurve(padAxes.ry);
  const h = padCurve(padAxes.rx);
  if (!v && !h) {
    padScrollAcc = 0;
    padScrollAccH = 0;
    return;
  }
  padScrollAcc += v * PAD_SCROLL_TICKS * dt / 1000;
  padScrollAccH += h * PAD_SCROLL_TICKS * dt / 1000;
  const whole = Math.trunc(padScrollAcc);
  const wholeH = Math.trunc(padScrollAccH);
  if (!whole && !wholeH) return;
  padScrollAcc -= whole;
  padScrollAccH -= wholeH;
  const at = cursorPos || { x: 0.5, y: 0.5 };
  // Pushing the stick UP scrolls up, like pushing a wheel forward: the stick's
  // y grows downward, a wheel tick is positive upward. Pushing it RIGHT
  // scrolls right — `rx` and a rightward wheel tick already agree in sign, so
  // `hticks` is `wholeH` unchanged (matches InputInjector.wheel: positive
  // `hticks` = right).
  const msg = { type: "scroll", x: at.x, y: at.y, ticks: -whole };
  if (wholeH) msg.hticks = wholeH;
  send(msg);
}

function padTick(now) {
  const dt = Math.min(PAD_MAX_DT, now - padLast);
  padLast = now;
  padCursorStep(dt);
  padScrollStep(dt);
  padLoop = padSticksLive() && !padWheel && !padRadial
    ? requestAnimationFrame(padTick) : null;
}

function padStartLoop() {
  if (padLoop !== null || padWheel || padRadial || !padSticksLive()) return;
  padLast = performance.now();
  padLoop = requestAnimationFrame(padTick);
}

function padStopLoop() {
  if (padLoop !== null) cancelAnimationFrame(padLoop);
  padLoop = null;
  padScrollAcc = 0;
  padScrollAccH = 0;
}

// --- The category wheel, held and pointed ---------------------------------
// As the user experiences it: hold L1 (or R1) and that side's wheel opens
// under his thumb; tilting a stick puts the ring's frame on the set he is
// pointing at, and letting the shoulder go takes it. Letting go while pointing
// at nothing changes nothing — and if the whole press was quick, that same
// button was the ‹ › layout step instead.

function padShoulderPress(m, down) {
  if (down) {
    if (padWheel) return;  // the other shoulder already owns the wheel
    padReleaseHeld();   // nothing of ours may stay pressed under an open wheel
    padStopLoop();      // the sticks POINT now; they do not steer or scroll
    padWheel = { side: m.shoulder, step: m.step, at: performance.now(), index: null };
    openWheel(m.shoulder);
    return;
  }
  const w = padWheel;
  if (!w || w.side !== m.shoulder) return;  // only the shoulder that opened it closes it
  padWheel = null;
  closeWheel();
  if (w.index !== null) {
    // w.index points into the FILTERED ring (task 181's wheelCats), and
    // `groups` holds an index into the FULL list — the finger's own pick in
    // controls.js maps through allCats().indexOf(cat), and the pad must map
    // the same way or pointing at one set shows another (caught by the
    // input-pipeline gate the day drop-out landed).
    const cat = wheelCats(w.side)[w.index];
    if (cat) {
      groups[w.side] = allCats().indexOf(cat);
      rememberGroup(w.side, cat.name);
      renderGroup(w.side);
    }
  } else if (performance.now() - w.at < PAD_TAP_MS) {
    layoutStep(w.step);
  }
  padStartLoop();
}

// ── L2: THE SAME GRAMMAR, THE OTHER MENU (owner 2026-08-09, task 186; the
// radial re-anchored beside the Layout button 2026-08-12) ──────────────────
// Hold L2 and the layout-birth radial opens beside the Layout button; the
// stick points at New (east) / Tap (south-east) / List (south) and letting go
// takes the one being pointed at. Letting go while pointing at nothing changes nothing, and if the whole
// press was quick it was the TAP instead — the tap-pick, armed as it always
// was. Every line of that sentence is `padShoulderPress` with a different menu
// in it, which is the point: the owner learns one grammar and it is already
// the one his shoulders speak.
//
// The RADIAL ITSELF is chrome.js's, opened by layout-create.js's own
// `openSourceChooser` — the very function the finger runs. Nothing here draws
// anything, and there is no controller-only option list to drift from the
// touch one (constraint 9).
function padRadialPress(m, down) {
  if (down) {
    if (padRadial || padWheel) return;
    padReleaseHeld();   // nothing of ours may stay pressed under an open menu
    padStopLoop();      // the sticks POINT now; they do not steer or scroll
    // A radial a FINGER left open must not be toggled shut by the press that
    // is opening this one: `openMiniRadial` closes on a re-open of the same
    // anchor, and that door is the finger's, not the pad's.
    closeMiniRadial();
    padRadial = { at: performance.now(), index: null };
    openSourceChooser();
    return;
  }
  const r = padRadial;
  if (!r) return;
  padRadial = null;
  if (r.index !== null) {
    padStartLoop();
    miniRadialPick(r.index);      // pointing at one: that is the choice
    return;
  }
  closeMiniRadial();
  // Pointing at nothing: a QUICK press was the tap, a long one was a look.
  if (performance.now() - r.at < PAD_TAP_MS) m.tap();
  padStartLoop();
}

function padAimRadial() {
  const r = padRadial;
  if (!r) return;
  const items = miniRadialItems();
  if (!items.length) return;
  // THE RADIAL IS NO LONGER A RING (owner decision 2026-08-12): its options
  // open as a FAN beside the Layout button — E / SE / S, mirrored on the right
  // half of the screen — so the count no longer tells anyone where an option
  // is. `chrome.js` records the angle each option really landed at, clamp
  // included, and the stick is matched against THOSE. One geometry, written
  // once, pointed at by both hands (constraint 9); deriving the fan's
  // directions a second time here is exactly the drift that rule forbids.
  r.index = padPointedAt(miniRadialAngles());
  miniRadialLight(r.index === null ? -1 : r.index);
}

// Where the pointing thumb is aimed, or null if neither stick has really left
// centre. Either thumb may do it — the sticks have no other job while a menu
// is up, and which hand is free depends on which shoulder is being held.
function padStickAngle() {
  const useLeft = Math.hypot(padAxes.lx, padAxes.ly) >= Math.hypot(padAxes.rx, padAxes.ry);
  const x = useLeft ? padAxes.lx : padAxes.rx;
  const y = useLeft ? padAxes.ly : padAxes.ry;
  if (Math.hypot(x, y) < PAD_POINT_MIN) return null;
  return Math.atan2(y, x);
}

// Which wheel item the stick points at — the RING case, where the items divide
// the whole circle between them and every direction belongs to exactly one.
function padPointedIndex(items) {
  const stick = padStickAngle();
  if (stick === null) return null;
  // openWheel() places item i at angle -PI/2 + i*2PI/n: i = 0 is straight up
  // and increasing i sweeps clockwise on screen — so the stick's own angle,
  // turned a quarter turn, IS the index.
  const n = items.length;
  const a = stick + Math.PI / 2;
  return ((Math.round(a / (2 * Math.PI / n)) % n) + n) % n;
}

// Which of a set of RECORDED directions the stick points along — the FAN case.
// Nearest wins, and only inside `PAD_POINT_CONE`: a fan leaves most of the
// circle unclaimed, and pointing at nothing must stay a real answer.
function padPointedAt(angles) {
  const stick = padStickAngle();
  if (stick === null || !angles || !angles.length) return null;
  let best = null;
  let bestOff = PAD_POINT_CONE;
  angles.forEach((want, i) => {
    // Signed shortest angle between the two, wrapped into (-PI, PI].
    const off = Math.abs(((stick - want + Math.PI * 3) % (Math.PI * 2)) - Math.PI);
    if (off < bestOff) {
      bestOff = off;
      best = i;
    }
  });
  return best;
}

function padAimWheel() {
  const w = padWheel;
  if (!w) return;
  const items = [...wheelEl.querySelectorAll(".wheel-item")];
  if (!items.length) return;
  w.index = padPointedIndex(items);
  // The frame is the wheel's own "this one" ring — while a stick points, it
  // follows the stick; released back to centre, it returns to the set the
  // group is actually showing.
  const lit = w.index === null ? groups[w.side] : w.index;
  items.forEach((el, i) => el.classList.toggle("current", i === lit));
}

// --- Presses --------------------------------------------------------------

function padPressElement(name, el, down) {
  if (down) {
    if (!buttonPress(el, true)) return;
    padHeld.set(name, el);
    return;
  }
  // Release the element the press STARTED on: the group may have re-rendered
  // under a held arrow, and a PC mouse button must never be left down.
  const held = padHeld.get(name) || el;
  padHeld.delete(name);
  buttonPress(held, false);
}

function padReleaseHeld() {
  for (const [name, el] of [...padHeld]) {
    padHeld.delete(name);
    buttonPress(el, false);
  }
}

// --- What the shell calls -------------------------------------------------

// A pad press is not a touch and not a keydown: the shell claims it at
// `dispatchKeyEvent` and hands it here through evaluateJavascript, so the two
// listeners that hold the screen awake (connection.js) never hear it. Without
// this, a session driven ENTIRELY from the controller goes dark after
// KEEP_AWAKE_MS, the page hides, and the server correctly packs the layout
// away in the middle of the owner's work. Throttled, because the axis stream
// arrives every frame and each call crosses the JS bridge.
// -Infinity, never 0 — the lesson layouts.js paid for on 2026-08-07: `0` is a
// REAL performance.now() reading ("at page load"), so a 0 start swallowed
// every pad press in the page's first five seconds, which on a phone is
// exactly the moment the owner picks the controller up.
let padAwakeAt = -Infinity;
function padAwake() {
  const now = performance.now();
  if (now - padAwakeAt < PAD_AWAKE_THROTTLE_MS) return;
  padAwakeAt = now;
  touchedNow();
}

// One physical button changed state. The shell sends transitions only (no key
// repeat, no duplicate from a pad that reports its D-pad as both keys and a
// hat), so this is a clean down/up pair per press.
window.__padButton = (name, down) => {
  const m = PAD_MAP[name];
  if (!m) return;
  padAwake();
  if (m.shoulder) {
    padShoulderPress(m, down);
    return;
  }
  if (m.radial) {
    padRadialPress(m, down);
    return;
  }
  // A menu is open: only the button holding it is listened to.
  if (padWheel || padRadial) return;
  if (m.group) {
    padPressElement(name, groupButton(m.group, m.pos), down);
    return;
  }
  if (m.corner) {
    padPressElement(name, document.getElementById(m.corner), down);
    return;
  }
  // Pad-only actions have no on-screen twin to borrow a release rule from, so
  // they fire on the press — that is where a game controller feels right.
  if (m.act && down) m.act();
};

// Both sticks, -1..1, y positive DOWNWARD (Android's own convention). The
// shell sends this only when a value actually changed.
window.__padAxis = (lx, ly, rx, ry) => {
  if (lx || ly || rx || ry) padAwake();   // centred sticks are not activity
  padAxes.lx = lx;
  padAxes.ly = ly;
  padAxes.rx = rx;
  padAxes.ry = ry;
  if (padWheel) {
    padAimWheel();
    return;
  }
  if (padRadial) {
    padAimRadial();
    return;
  }
  padStartLoop();
};

// Silent evidence, exactly like `__voiceInfo` (owner round 2, 2026-08-05 — a
// diagnostic panel flashed at the user was rejected angrily): which controller
// attached, which axes it declares, any keycode this table does not know. It
// goes to the PC's server log, where the developer reads it.
window.__padInfo = (text) => {
  send({ type: "client_log", text: `[pad] ${text}` });
};
