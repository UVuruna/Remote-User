// How the phone LOOKS — theme, whether the controls are coloured, fill, and
// the colour each set wears.
// Build round R3 (owner-approved 2026-08-07), CORRECTED to three independent
// axes 2026-08-08. Loads after controls.js (it uses `prefGet`/`prefSet`) and
// before panels.js/layouts.js. The colours themselves live in
// client/theme.css; this file only decides WHICH of them are in force and
// hands each set its own. See client/__about/theme.md.
//
// THE DESKTOP DECIDES, THE PHONE OBEYS (owner answer P4). Every `config`
// frame carries `ui = {theme, colored, fill, colors}` and that is the only
// input: no menu on the phone, no auto-detection, and the device's own
// dark/light preference is deliberately ignored. One source of truth means
// the owner never has to wonder which of two places is winning.
//
// THREE AXES, NOT A FOURTH THEME NAME (owner correction 2026-08-08). His own
// words: "teme postoje samo dve, svetla i tamna … a ove komande … on može da
// bude obojen, neobojen, i može da bude transparentan ili pun." The
// 2026-08-07 shape folded colour into `theme` ("colored" / "colored-light"),
// which produced the same eight looks by accident but claimed the page has
// four themes when only the CONTROLS (the D-pad groups and the radial wheel)
// carry the extra switch. `theme` is now `"dark"` / `"light"` only; `colored`
// is its own boolean, independent of both.
//
// `colors` is ONE flat map, THE SAME ON BOTH THEMES (owner decision
// 2026-08-08: "nema dve verzije za obojene setove — oni ce uvijek imati ove
// jake upecatljive boje"). A set's colour is its identity; the theme moves
// everything AROUND the controls and never the controls' own colours. It
// rides on every `config` frame whether or not `colored` is on; the palette
// is resolved once, on the desktop (server/config.py → `set_colors`), and
// this file never holds a table.
//
// The choice is CACHED per device so the page does not paint the previous
// look for the third of a second it takes the socket to open and the server
// to answer — a flash the owner would see on every single connect.
"use strict";

const UI_PREF = "uiLook";
// The SEED, not a fallback. It is what a device that has never been told
// anything wears, and nothing else: `applyUi` merges onto the look in force
// and never onto this (see its own comment — a `config` with no `ui` used to
// reset the owner's choice to these values).
const UI_DEFAULT = { theme: "dark", colored: false, fill: "transparent", colors: {} };

// BACKWARD COMPATIBILITY (owner correction 2026-08-08). Two things can still
// hand this file the OLD four-value `theme` ("colored" / "colored-light"):
// an older server not yet rebuilt, and THIS DEVICE'S OWN cache
// (`prefGet(UI_PREF)`) written by an older page before this build ever
// ran — the cache is read at load, before any socket exists, so it is a path
// a server-side translation alone can never reach (see server/config.py →
// `_migrate_legacy_ui` for that half). Translated once, at the single point
// every incoming `ui` object passes through (`mergedUi`), so the owner's
// SAVED CHOICE never silently becomes something else: "colored-light" meant
// light-page-with-colour, and that is exactly {theme:"light",colored:true}
// spelled with two fields instead of one — not a value to fall back away
// from.
function legacyTheme(next) {
  if (!next || typeof next !== "object") return next;
  const LEGACY = { colored: { theme: "dark", colored: true },
                   "colored-light": { theme: "light", colored: true } };
  const hit = LEGACY[next.theme];
  if (!hit) return next;
  const rest = { ...next };
  delete rest.theme;
  return { ...rest, theme: hit.theme,
           colored: next.colored !== undefined ? next.colored : hit.colored };
}

// Ink on a coloured button. Computed, never tabled (rules/CODE.md — Compute,
// Don't Generate): the owner may retune the palette on the desktop whenever he
// likes — he did, one day after adopting the first one — and a hand-written
// ink per colour would be wrong the first time he does. It is also what let
// this round replace thirteen bright hexes with thirteen dark ones and change
// no ink rule at all.
//
// AND IT IS COMPUTED AGAINST THE SURFACE THE TEXT ACTUALLY SITS ON (independent
// grader, 2026-08-07 — the finding that blocked the release). The first version
// asked only "is this hex brighter than luminance 0.179", which answers the
// question for ONE of the two fills: in `full` the button really is painted
// with the set colour, so black-or-white against that hex is right. In the
// OUTLINED fill nothing is painted with it at all — the colour is the ink, and
// what it lands on is `--glass-fill` composited over the page. A colour that is
// perfectly readable AS a fill can be a poor INK on the same page, and nothing
// in the old rule could tell those two questions apart. The current palettes
// make the point at its sharpest: a #1C3878 navy is an excellent FILL under a
// white label and completely illegible as ink on a near-black page.
//
// So both inks are derived from the LIVE tokens, every time the look changes:
//   --set-ink   ink ON the set colour   (the `full` fill)
//   --set-line  the set colour ITSELF, lifted until it is readable on the
//               surface it is drawn over (the outlined fill)
// The border keeps the raw `--set-color`, so the set's identity is untouched
// — a border is a graphic (3:1), a 9 px label is text (4.5:1).
//
// WHY THE TARGET IS 7:1 AND NOT 4.5:1. These buttons do not live on the page.
// They float over the PC's own screen — a white document one minute, a photo
// the next — and that backdrop is unknowable, so the only defences are the
// label's shadow (`--lbl-shadow`) and keeping the ink as far from the middle of
// the luminance range as the colour allows. A 9 px semibold label is not
// "large text" by any reading of WCAG, so 4.5:1 is its FLOOR, not its target;
// AAA (7:1) is what a label with an unknown backdrop deserves and it is what
// the palettes can pay — the target survived the whole palette being darkened,
// because a lift that keeps hue and saturation can pay it without going grey.
//
// (The other half of the grader's finding was not an ink problem at all and is
// not fixed here: the numbers it measured — 2.66:1 — were read through the
// category wheel's own full-screen veil, which used to be painted ABOVE the
// D-pad. Under a 0.55 veil the maximum contrast ACHIEVABLE between any two
// colours is 4.83:1, so no ink could have answered it; the veil moved below
// our own chrome instead. See client/style.css → `body.wheel-open::before`.)
const INK_DARK = "#0b1220";
const INK_LIGHT = "#ffffff";
const INK_TARGET = 7.0;
// The FILLED fill is a KNOWN, controlled surface (unlike the outlined ink's
// unknowable PC backdrop), so it only owes WCAG AA — 4.5:1 for a label this
// small — not the AAA margin `lineOn` pays for the unknown case.
const FILL_INK_TARGET = 4.5;
// The category button (style.css `.ctl.cat`) sits at 0.85 opacity over its
// own fill — a REAL, visible dilution of its ink toward that same fill, not
// a measurement artefact (the phone photographs it exactly as diluted). It
// is the binding constraint: a plain `.ctl` has no opacity at all, so
// whatever clears AA after this dilution clears it before too.
const CAT_OPACITY = 0.85;
// Steps the lift walks. 40 rather than 20 (owner correction 2026-08-07): the
// walk now moves LIGHTNESS, and a coarse step there is a visible jump in how
// pale the ink comes out — the finer sweep returns the SMALLEST lift that
// clears, which is the whole point of returning the first step that does.
const LIFT_STEPS = 40;

let ui = { ...UI_DEFAULT };
let setColorCache = null;

function parseHex(hex) {
  const m = String(hex || "").trim().replace("#", "");
  if (m.length !== 6) return null;
  return [0, 2, 4].map((i) => parseInt(m.slice(i, i + 2), 16));
}

// Any CSS colour the page can hand back — `#rrggbb` from the desktop's table,
// `rgb(r g b / a)` from a computed custom property. Returns [r, g, b, a].
function parseColor(css) {
  const hex = parseHex(css);
  if (hex) return [...hex, 1];
  const m = String(css || "").match(/[\d.]+/g);
  if (!m || m.length < 3) return null;
  return [+m[0], +m[1], +m[2], m.length > 3 ? +m[3] : 1];
}

// One translucent layer painted over an opaque one.
function over(top, bottom) {
  return [0, 1, 2].map((i) => top[i] * top[3] + bottom[i] * (1 - top[3]));
}

function luminance(rgb) {
  const [r, g, b] = rgb.map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a, b) {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

// A straight line between two colours. Used ONLY to simulate a real
// compositing step (the category button's 0.85 opacity over its own fill) —
// never to make a colour readable. See `lift` for why.
function mix(rgb, toward, t) {
  return [0, 1, 2].map((i) => rgb[i] + (toward[i] - rgb[i]) * t);
}

// --- HSL, because LIGHTNESS is the axis a lift is allowed to move ----------
// The owner's correction of 2026-08-07 is a statement about lightness and
// saturation ("jako tamne nijanse, dakle mali lightness/brightness … sto
// saturacija ne treba ni u jednom modu"), so the code that adjusts a colour
// has to speak the same language he does. Straight RGB cannot: mixing toward
// white raises lightness AND drains saturation, which is why the previous
// version's comment claiming "hue and saturation ride along" was simply
// false — a dark navy lifted toward white came out grey-blue, and a palette
// of dark shades would have arrived on the phone as a row of pastels.
function toHsl(rgb) {
  const [r, g, b] = rgb.map((v) => v / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  if (!d) return [0, 0, l];
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h;
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
  else if (max === g) h = ((b - r) / d + 2) / 6;
  else h = ((r - g) / d + 4) / 6;
  return [h, s, l];
}

function fromHsl(h, s, l) {
  if (!s) return [l * 255, l * 255, l * 255];
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const at = (t) => {
    t = (t + 1) % 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  return [at(h + 1 / 3), at(h), at(h - 1 / 3)].map((v) => v * 255);
}

// Walk this colour's LIGHTNESS toward one end — white when `up`, black when
// not — and return the first step that satisfies `ok`, together with how far
// it had to go. Hue and saturation are untouched, so a lifted teal is still
// unmistakably the teal set: it is the same colour at the lightness the
// surface demands. The far end is white (or black), which clears any target
// there is, so the walk always terminates with an answer.
function lift(rgb, up, ok) {
  const [h, s, l0] = toHsl(rgb);
  const end = up ? 1 : 0;
  let cand = rgb;
  for (let i = 0; i <= LIFT_STEPS; i++) {
    cand = fromHsl(h, s, l0 + (end - l0) * (i / LIFT_STEPS));
    if (ok(cand)) return { rgb: cand, steps: i };
  }
  return { rgb: cand, steps: LIFT_STEPS };
}

function css(rgb) {
  return `rgb(${rgb.map((v) => Math.round(v)).join(" ")})`;
}

// What one of this page's own tokens actually looks like once it has been
// painted: the token's own colour composited over the page. Read from the LIVE
// stylesheet, never copied here — that is the whole anti-drift mechanism. A
// theme that retunes `--glass-fill`, or a fill axis that stops being
// translucent, moves this number by itself.
function pageSurface() {
  if (typeof getComputedStyle !== "function") return [15, 23, 42];
  const page = parseColor(getComputedStyle(document.body).backgroundColor);
  return page ? page.slice(0, 3) : [15, 23, 42];
}

function tokenSurface(name) {
  if (typeof getComputedStyle !== "function") return [15, 23, 42];
  const page = pageSurface();
  const layer = parseColor(
    getComputedStyle(document.body).getPropertyValue(name));
  return layer ? over(layer, page) : page;
}

// Black or white — whichever reads better ON this colour. Used where the
// colour really is the fill (the `full` look), so the surface IS the colour.
function inkOn(surface) {
  const dark = parseHex(INK_DARK);
  const light = parseHex(INK_LIGHT);
  return contrast(dark, surface) >= contrast(light, surface) ? INK_DARK : INK_LIGHT;
}

// A hue sitting near the black/white crossover (luminance ~0.179) fails BOTH
// inks almost equally — no ink choice can save it, because black and white
// are already the two most extreme options (independent grader, 2026-08-07:
// the first palette's VSCode #3B82F6 filled measured 4.27:1 with the BETTER
// of the two, just under AA). The only remaining lever is the fill's own
// LIGHTNESS, walked the shorter way — darker or lighter — so the set is still
// unmistakably its own hue at its own saturation.
//
// A CORRECTION, NOT A DESIGN. Neither shipped palette needs it (server/
// config.py picks lightnesses that clear AA on their own, so what the desktop
// shows is what the phone paints); this is the net under a colour the owner
// retunes tomorrow, and it stays because the day he does is the day nobody is
// measuring.
function fillOn(rgb) {
  // The category button's own dilution, simulated up front rather than
  // discovered by the audit: ink blended 85:15 toward the fill it sits on is
  // what a photograph of THAT button actually shows.
  const ok = (cand) => {
    const ink = parseHex(inkOn(cand));
    return contrast(mix(ink, cand, 1 - CAT_OPACITY), cand) >= FILL_INK_TARGET;
  };
  if (ok(rgb)) return rgb;
  const down = lift(rgb, false, ok);
  const up = lift(rgb, true, ok);
  const downOk = ok(down.rgb);
  const upOk = ok(up.rgb);
  if (downOk && (!upOk || down.steps <= up.steps)) return down.rgb;
  if (upOk) return up.rgb;
  return rgb;   // nothing clears it — leave the colour alone
}

// The set colour with its LIGHTNESS walked away from the surface — up on a
// dark page, down on a light one — until it clears the target. Hue and
// saturation genuinely ride along now (see `lift`), so a lifted teal is a
// lighter teal and not a grey with a memory of teal, and that is what lets
// the dark page's palette be as dark as the owner asked: the fill wears the
// shade he chose, and the OUTLINED look wears the same shade at the lightness
// a near-black page demands. Returns the FIRST step that clears, so a colour
// that already reads on its surface is returned untouched.
function lineOn(rgb, surface) {
  const dark = parseHex(INK_DARK);
  const light = parseHex(INK_LIGHT);
  const up = contrast(light, surface) >= contrast(dark, surface);
  return lift(rgb, up, (c) => contrast(c, surface) >= INK_TARGET).rgb;
}

// The halo an ACTIVE toggle wears (Keys on, Scroll on). It is fed the LIFTED
// colour, not the raw one (owner correction 2026-08-07): "switched on" is a
// signal, and a signal drawn in a #1C3878 navy on a #0f172a page is no signal
// at all. The lifted colour is by construction far from its surface — lighter
// on a dark page, darker on a light one — so the same rule keeps the halo
// visible on both without a token per theme.
function glowFor(rgb) {
  if (!rgb) return null;
  return `rgb(${rgb.map((v) => Math.round(v)).join(" ")} / 0.30)`;
}

// The full name → colour map, shipped colours first and the owner's own sets
// filled in from the SAME palette (the values of whichever table the desktop
// sent for the theme in force are the pool — one table to tune per surface, no
// third list to keep in step). A custom set
// takes the next colour nothing already wears; if he ever makes more sets
// than there are colours the pool simply cycles, which is a repeat, not a
// crash. Deterministic: the order is the order the sets arrive in, so a set's
// colour does not change from one connection to the next.
function setColors() {
  if (setColorCache) return setColorCache;
  const map = { ...(ui.colors || {}) };
  const pool = Object.values(ui.colors || {});
  const used = new Set(Object.values(map).map((c) => String(c).toLowerCase()));
  const named = new Set(Object.keys(map));
  let cursor = 0;
  for (const set of [...categories, ...customSets, ...appSets]) {
    const name = set && set.name;
    if (!name || named.has(name) || map[name] || !pool.length) continue;
    let tries = 0;
    while (tries < pool.length &&
           used.has(String(pool[cursor % pool.length]).toLowerCase())) {
      cursor++;
      tries++;
    }
    map[name] = pool[cursor % pool.length];
    used.add(String(map[name]).toLowerCase());
    cursor++;
  }
  setColorCache = map;
  return map;
}

// Called whenever the set list itself changes (a fresh `actions` frame) —
// a new custom set has to be able to claim a colour.
function resetSetColors() {
  setColorCache = null;
}

// Paint one element with the colour of the set it belongs to. The element is
// the OWNER of the set (a D-pad group, a wheel item), so its buttons, labels
// and icons all inherit through the custom properties — one write per group
// instead of one per button.
//
// `surfaceVar` names the token the element's own buttons are painted with —
// `--glass-fill` for a D-pad button, `--glass-strong` for a wheel item, which
// really are different surfaces (0.20 vs 0.85 of the same navy) and therefore
// really do want different lifts. The caller states it because the caller is
// the only one that knows; nothing here guesses from the DOM.
//
// The properties are set in EVERY theme and read only in the two coloured
// ones (client/theme.css): a rule that has to un-set itself when the theme
// changes is a rule that will one day be left behind.
function paintSet(el, name, surfaceVar) {
  const color = setColors()[name];
  const rgb = parseHex(color);
  if (!color || !rgb) {
    el.style.removeProperty("--set-color");
    el.style.removeProperty("--set-fill");
    el.style.removeProperty("--set-ink");
    el.style.removeProperty("--set-line");
    el.style.removeProperty("--set-glow");
    return;
  }
  const page = pageSurface();
  el.style.setProperty("--set-color", color);
  // FILLED: the button IS this colour, composited over the page in case the
  // fill token ever carries an alpha of its own — its lightness nudged the
  // shorter way ONLY when black-or-white ink cannot otherwise clear AA on it
  // (fillOn; neither shipped palette moves at all today), THEN given its ink
  // against that same surface, never the raw hue.
  const fillRgb = fillOn(over([...rgb, 1], page));
  el.style.setProperty("--set-fill", css(fillRgb));
  el.style.setProperty("--set-ink", inkOn(fillRgb));
  // OUTLINED: the colour is the ink, and it lands on the button's own tint.
  const lineRgb = lineOn(rgb, tokenSurface(surfaceVar || "--glass-fill"));
  el.style.setProperty("--set-line", css(lineRgb));
  // …and the ACTIVE halo rides the same lifted colour, for the same reason:
  // it has to be seen against the surface, not against nothing.
  const glow = glowFor(lineRgb);
  if (glow) el.style.setProperty("--set-glow", glow);
}

// Put the choice on <body>; every rule in theme.css hangs off these three.
function writeLook() {
  document.body.dataset.theme =
    ["dark", "light"].includes(ui.theme) ? ui.theme : "dark";
  document.body.dataset.colored = ui.colored ? "true" : "false";
  document.body.dataset.fill = ui.fill === "full" ? "full" : "transparent";
  // The canvas is painted by JS, not by CSS, so it cannot inherit a variable
  // — it is TOLD the page colour once per look change (client/render.js).
  if (typeof getComputedStyle === "function") {
    setCanvasBackdrop(getComputedStyle(document.body).backgroundColor);
  }
}

// One look laid over another, field by field. The base is what is in force —
// never a constant — so an axis nobody mentioned keeps the value it has.
// `next` is translated through `legacyTheme` FIRST — the one point every
// incoming `ui` object passes through, server frame or device cache alike.
//
// `colored` needs an explicit-undefined check, not `||`: it is a boolean, and
// `false || base.colored` would silently discard a real "turn colour off"
// instruction the moment the owner actually chose it — the same class of bug
// `theme`/`fill` cannot have, because an empty string is never a value either
// side sends.
function mergedUi(base, rawNext) {
  const next = legacyTheme(rawNext);
  return {
    theme: (next && next.theme) || base.theme,
    colored: next && typeof next.colored === "boolean"
      ? next.colored : (base.colored || false),
    fill: (next && next.fill) || base.fill,
    colors: (next && next.colors) || base.colors || {},
  };
}

// The server's word, from `config.ui`.
//
// SILENCE IS NOT AN INSTRUCTION (independent grader, 2026-08-07 — the finding
// that blocked the release, and the only product bug the three grading rounds
// found by measuring pixels instead of reading code). This function used to
// default every missing field to `UI_DEFAULT`, so a `config` frame carrying no
// `ui` at all — or one that named only the theme — put the phone back to
// dark/transparent within half a second of the owner choosing anything else.
// The desktop's Appearance card looked like it did nothing.
//
// The old comment justified it with "a server that stops sending `ui` (an
// older PC) must put the phone back to the look that PC actually renders for",
// and that sentence is simply not true of anything: the PC renders nothing for
// the phone — the phone paints itself. A server too old to have a `phone_theme`
// setting has no opinion about appearance to impose, and overwriting the
// owner's only choice with a constant is not obedience, it is a reset.
//
// So the rule is IGNORE-OR-MERGE, and the fallback is the CACHE, never
// `UI_DEFAULT`:
//   no `ui`      -> nothing happens at all. Not a state change, not a pref
//                   write, not a repaint. The look in force stays in force,
//                   and on a device that has never been told anything that is
//                   `UI_DEFAULT` anyway (restoreUi below seeds it).
//   partial `ui` -> merged onto the look in force, so naming the theme cannot
//                   silently discard the fill or the set colours.
// The cache is the phone's memory of the last thing the DESKTOP said; that is
// a far better answer to "what look does this owner want" than a constant
// compiled into the page.
function applyUi(next) {
  if (!next || typeof next !== "object") return;
  ui = mergedUi(ui, next);
  resetSetColors();
  writeLook();
  try {
    prefSet(UI_PREF, JSON.stringify(ui));
  } catch (e) {
    // A device that will not store a preference still gets the right look
    // for this session; it only pays the first-paint flash on the next one.
  }
  // The controls are already on screen when a `config` arrives on a
  // reconnect, and their per-set colours are inline styles — re-render so a
  // theme change reaches them without waiting for the next set switch.
  if (typeof refreshCategories === "function") refreshCategories();
  // …and the canvas is painted by JS, so it keeps the previous backdrop until
  // something draws again. That is every frame while a stream runs, but the
  // letterbox around a layout region and the screen before the first frame
  // would otherwise wear the old theme until one arrives.
  if (typeof redraw === "function") redraw();
}

// The cached look, applied before the socket has said anything. This is the
// whole reason the choice is stored on the device at all.
(function restoreUi() {
  try {
    const raw = prefGet(UI_PREF);
    if (raw) ui = mergedUi(UI_DEFAULT, JSON.parse(raw));
  } catch (e) {
    ui = { ...UI_DEFAULT };
  }
  writeLook();
})();
