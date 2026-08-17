// How the phone LOOKS — theme, whether the controls are coloured, fill, and
// the colour each set wears.
// Build round R3 (owner-approved 2026-08-07), CORRECTED to three independent
// axes 2026-08-08. Loads after controls.js (it uses `prefGet`/`prefSet`) and
// before panels.js/layouts.js. The colours themselves live in
// client/theme.css; this file only decides WHICH of them are in force and
// hands each set its own. See client/__about/theme.md.
//
// THE DESKTOP SETS THE DEFAULT, THE DEVICE MAY CHOOSE (owner ballot
// 2026-08-12: "appearance is also per device, not global, so it belongs on
// the phone / tablet"). Every `config` frame still carries
// `ui = {theme, colored, fill, colors}` — that is the FRAME, and it is what a
// handset wears until it has an opinion of its own. Settings → Appearance
// (client/appearance-panel.js) writes that opinion into THIS DEVICE'S prefs,
// and it is laid over the frame axis by axis.
//
// The 2026-08-07 answer to P4 — one source of truth, no menu on the phone —
// was right that there must be ONE answer and wrong about where it lives: he
// uses a tablet AND a phone, and one desktop dropdown could only ever describe
// one of them. There is still exactly one answer PER DEVICE, and it is still
// never guessed: the device's own dark/light preference stays deliberately
// ignored, because a look he chose must not change when the sun goes down.
//
// TWO STORES, NOT ONE, and the distinction is the feature:
//   `uiLook`   — the last FRAME the PC sent. A cache, so the page does not
//                paint the previous look for the third of a second the socket
//                takes to answer. Overwritten by every `config`.
//   `uiChoice` — the axes THIS DEVICE picked, and only those. Never written by
//                a `config` frame, so a PC that changes its default can never
//                overwrite a choice he made on the handset, and an axis he has
//                not touched is absent rather than pinned — it keeps following
//                the PC for as long as he leaves it alone.
// Both go through `prefGet`/`prefSet` — the shell's SharedPreferences bridge,
// the sets-picker's mechanism. NOT bare localStorage: that is keyed by ORIGIN
// and the shell alternates between the LAN and Tailscale addresses, which is
// exactly how the sets picker came to "rotate" between two states on
// 2026-08-05.
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
// This device's own answer — a PARTIAL look, holding only the axes it chose.
const UI_CHOICE_PREF = "uiChoice";
// The axes a device may claim. `colors` is deliberately not one of them: a
// set's colour is its identity (owner 2026-08-08) and the palette is resolved
// once, on the desktop.
const UI_AXES = ["theme", "colored", "fill"];
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
// THE SHADOW IS THE INK'S OPPOSITE, NEVER THE THEME'S (owner report
// 2026-08-17, his picture 5 — and it CORRECTS the always-black verdict of
// 2026-08-15 rather than quietly setting it aside).
//
// What he ruled on 2026-08-15 was a rendered ballot in which the LIGHT theme
// flipped both shadow tokens to white, and he rejected it in the same words he
// used again now: a shadow the same colour as the ink reads "blury". Both
// readings are his and both are right, because they are about DIFFERENT
// pairings — the ballot's white shadow sat under a 2 px blur (replaced in that
// very round by the 0/1 px, 1 px-blur lift the geometry has today), and what
// he was really naming both times is a shadow that cannot be told apart from
// what it is behind. His own words this round, and then the rule that follows
// them:
//   "kada je senka iste boje kao i slova to izgleda loše i mutno"   lang-ok: owner quote
//   black letters and icons "prate sva ista pravila samo sada sa belim senkama"   lang-ok: owner quote
//
// The cases he photographed are not a theme at all, which is why an
// always-black token could never have covered them: Attach and Claude Tools
// are COLOURED sets whose fills are light, so `inkOn` correctly hands them
// BLACK ink — on the DARK theme — and the page then drew a black shadow under
// it. So the decision belongs where the ink is decided (`paintSet`), per
// element and per fill, and the theme tokens are only the case where the ink
// is `--text-primary`. ONE rule applied at every place an ink is chosen, so
// the further cases he warned were coming are answered in advance rather than
// one screenshot at a time.
//
// The GEOMETRY and the two ALPHAS stay exactly as his 2026-08-15 sliders left
// them (client/style.css, client/theme.css) — only the COLOUR now follows the
// ink, and a 3D lift is still a lift and never a glow.
const SHADOW_DARK = "0 0 0";
const SHADOW_LIGHT = "255 255 255";
// The icon's shadow and the label's, unchanged from his ballot: an icon is a
// solid shape that owes less, a 9 px label is the thing that must be read.
const INK_SHADOW_ALPHA = 0.8;
const LBL_SHADOW_ALPHA = 1;

// Steps the lift walks. 40 rather than 20 (owner correction 2026-08-07): the
// walk now moves LIGHTNESS, and a coarse step there is a visible jump in how
// pale the ink comes out — the finer sweep returns the SMALLEST lift that
// clears, which is the whole point of returning the first step that does.
const LIFT_STEPS = 40;

// The PC's word — the last `config.ui`, or the cache of it before the socket
// has spoken. `uiPick` is this device's own answer, laid over it; `ui` is what
// the page actually renders and is never assigned directly (composeUi does it).
let uiFrame = { ...UI_DEFAULT };
let uiPick = {};
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

// Which shadow an ink of THIS colour must wear, and at which of the two
// alphas. Decided by the ink's own luminance against the same 0.179 crossover
// `inkOn` uses, so the two answers can never disagree: a light ink gets the
// dark shadow it has always had, a dark ink gets the white one his report
// asked for. It is deliberately NOT a contrast walk — the shadow's job is a
// 1 px lift under the shape, not readable text, and the two extremes are the
// only candidates there have ever been.
function shadowFor(rgb, alpha) {
  const base = luminance(rgb) > 0.179 ? SHADOW_DARK : SHADOW_LIGHT;
  return `rgb(${base} / ${alpha})`;
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
// filled in from the SAME palette (the values the desktop sent are the pool —
// ONE table for both themes since 2026-08-08, so there is nothing to keep in
// step and no third list). A custom set
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
    el.style.removeProperty("--set-ink-shadow");
    el.style.removeProperty("--set-ink-lbl-shadow");
    el.style.removeProperty("--set-line-shadow");
    el.style.removeProperty("--set-line-lbl-shadow");
    el.style.removeProperty("--set-on");
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
  const inkHex = inkOn(fillRgb);
  el.style.setProperty("--set-ink", inkHex);
  // …and its shadow is that ink's opposite (owner 2026-08-17). This is the
  // pair he photographed: a light fill takes BLACK ink, and until now the
  // always-black token drew a black shadow under it — Attach and Claude Tools,
  // on the DARK theme, which no theme-level rule could ever have reached.
  const inkRgb = parseHex(inkHex);
  el.style.setProperty("--set-ink-shadow", shadowFor(inkRgb, INK_SHADOW_ALPHA));
  el.style.setProperty("--set-ink-lbl-shadow",
                       shadowFor(inkRgb, LBL_SHADOW_ALPHA));
  // OUTLINED: the colour is the ink, and it lands on the button's own tint.
  const lineRgb = lineOn(rgb, tokenSurface(surfaceVar || "--glass-fill"));
  el.style.setProperty("--set-line", css(lineRgb));
  // The outlined ink is the SET's own lifted colour, so its shadow is decided
  // from that colour and not from the filled look's black-or-white — a set
  // lifted pale on a dark page is a light ink and keeps the dark shadow, while
  // one walked dark on the light page now stops drawing black on black.
  el.style.setProperty("--set-line-shadow",
                       shadowFor(lineRgb, INK_SHADOW_ALPHA));
  el.style.setProperty("--set-line-lbl-shadow",
                       shadowFor(lineRgb, LBL_SHADOW_ALPHA));
  // SWITCHED ON: the button's face flips to the far end of the theme's
  // luminance range (client/style.css → `.ctl.active`, owner 2026-08-09 task
  // 179) — and the set's identity has to survive that flip, so its colour
  // becomes the INK on the flipped face. Same walk, a different surface: the
  // ON face is opaque and known, which is the one case where `lineOn` gets an
  // easy question. Written in EVERY look, like the tokens above, and read
  // only by the rule that needs it — a value that has to be un-set when
  // something changes is a value that will one day be left behind.
  el.style.setProperty("--set-on", css(lineOn(rgb, tokenSurface("--on-face"))));
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

// ── THIS DEVICE'S OWN ANSWER (owner ballot 2026-08-12) ─────────────────────
// A PARTIAL look: only the axes he actually picked here. An axis he never
// touched must stay ABSENT rather than be pinned to whatever the PC happened
// to say the day he opened the panel — otherwise "follow the PC" would quietly
// stop working the first time the card was opened and closed again.

/** The stored choice, sanitised. Unknown keys and impossible values are
 *  dropped rather than rejected — a stale pref must never blank the page. */
function readUiChoice() {
  let raw = {};
  try {
    raw = JSON.parse(prefGet(UI_CHOICE_PREF) || "{}") || {};
  } catch (e) {
    return {};
  }
  // A choice written by an older page can carry the four-value theme too —
  // the same translation the frame gets, at the same single point.
  raw = legacyTheme(raw) || {};
  const out = {};
  if (raw.theme === "dark" || raw.theme === "light") out.theme = raw.theme;
  if (typeof raw.colored === "boolean") out.colored = raw.colored;
  if (raw.fill === "full" || raw.fill === "transparent") out.fill = raw.fill;
  return out;
}

/** What is rendered: the PC's frame with this device's picks laid over it. */
function composeUi() {
  ui = mergedUi(uiFrame, uiPick);
}

/** The look in force — read by the Appearance panel so it can light the step
 *  that is really showing, whether it came from here or from the PC. */
function uiLook() {
  return { ...ui };
}

/** True while this axis still follows the PC — nothing chosen here. */
function uiFollowsPc(axis) {
  return !(axis in uiPick);
}

/** The PC's own value for one axis, so the panel can name what "follow the
 *  PC" would give him right now instead of asking him to guess. */
function uiPcValue(axis) {
  return uiFrame[axis];
}

function saveUiChoice() {
  try {
    prefSet(UI_CHOICE_PREF, JSON.stringify(uiPick));
  } catch (e) {
    // A device that will not store a preference still obeys for this session.
  }
  repaintLook();
}

/** Everything a look change has to touch, once. The controls' per-set colours
 *  are inline styles and the canvas is painted by JS, so neither follows a CSS
 *  variable on its own — the same two calls `applyUi` has always made. */
function repaintLook() {
  composeUi();
  resetSetColors();
  writeLook();
  if (typeof refreshCategories === "function") refreshCategories();
  if (typeof redraw === "function") redraw();
}

/** Claim one axis for this device (Settings → Appearance). */
function setUiAxis(axis, value) {
  if (!UI_AXES.includes(axis)) return;
  uiPick = { ...uiPick, [axis]: value };
  saveUiChoice();
}

/** Hand one axis — or all of them — back to the PC's default. */
function clearUiAxis(axis) {
  const next = { ...uiPick };
  if (axis) delete next[axis];
  uiPick = axis ? next : {};
  saveUiChoice();
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
// It lands on the FRAME, never on the rendered look (owner ballot
// 2026-08-12): a `config` is the PC restating its DEFAULT, and a default that
// could overwrite a choice made on the handset would undo that choice on every
// single reconnect. The device's picks are laid back over it by `repaintLook`,
// so an axis he claimed survives every frame and an axis he left alone follows
// the PC exactly as it always did — including the "byte for byte" case, which
// is simply an empty `uiPick`.
function applyUi(next) {
  if (!next || typeof next !== "object") return;
  uiFrame = mergedUi(uiFrame, next);
  try {
    prefSet(UI_PREF, JSON.stringify(uiFrame));
  } catch (e) {
    // A device that will not store a preference still gets the right look
    // for this session; it only pays the first-paint flash on the next one.
  }
  repaintLook();
}

// The cached frame plus this device's own answer, applied before the socket
// has said anything. This is the whole reason either is stored on the device.
(function restoreUi() {
  try {
    const raw = prefGet(UI_PREF);
    uiFrame = raw ? mergedUi(UI_DEFAULT, JSON.parse(raw)) : { ...UI_DEFAULT };
  } catch (e) {
    uiFrame = { ...UI_DEFAULT };
  }
  uiPick = readUiChoice();
  composeUi();
  writeLook();
})();
