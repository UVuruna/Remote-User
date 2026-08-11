// What the phone KNOWS about the Claude Code conversation on the PC — the
// tables and the arithmetic, with no DOM anywhere in the file.
//
// PURE ON PURPOSE (the grid-icons.js / cursor-shapes.js / voice.js pattern):
// `tests/test_claude_panels.py` runs this module WHOLE in node. Every rule the
// owner judges — which five models exist and in what order, which /effort
// levels commit, how many Shift+Tab presses reach a mode, and above all what
// the panels say when the PC has told us NOTHING — lives here, where a gate
// can drive it. The DOM half is client/claude-panels.js.
//
// ── WHY THE PANELS EXIST IN THIS SHAPE (owner ballot 2026-08-11) ────────────
//
// Task 190: our Model panel offered NINE options while the extension's own
// picker offers FIVE. The nine came from CLI-transcript vocabulary measured in
// an agent's own session (`opusplan`, `sonnet[1m]`, `best`) and verified
// against that same transcript — the one authority nobody consulted was the
// menu HE looks at. The five below are that menu, in HIS order: by strength,
// Default first, with capability stars beside the names ("kao i na drugim
// mestima" — a standing rule for every model list from now on).
// # lang-ok: owner quote
//
// Task 191: /effort TAKES a level, so Thinking is a real chooser, not a button
// that types `/effort` and leaves another app's menu standing for the finger.
//
// Task 208: the panels must TELL THE TRUTH about current state. His report was
// exact — "Thinking highlighted Medium while the PC was on Max" — and the
// cause was a per-device LAST-SENT memory wearing a look that reads as live
// state. So this module separates three different claims and never lets one
// wear another's clothes:
//
//   SAVED      — a FACT read off the PC's settings file (config `saved`).
//   NOW        — a FACT read off the live conversation (`claude_state`).
//   LAST SENT  — this PHONE's memory of its own tap. NOT a fact about the PC.
//
// A claim we cannot make is written "unknown" and never guessed. An older
// server answers `claude_state` with nothing at all, and that case is the
// DEFAULT here rather than an afterthought: every function below takes null.

"use strict";

// ── THE OFFICIAL FIVE (owner verdict 2026-08-11, item 2) ───────────────────
// `value` is the literal the picker ALIASES commit with, one Enter — proven
// against the Claude Code sources, not inferred from a transcript. `family` is
// what the PC reports back in `claude_state.model`, which is a family name and
// never an alias: "opus[1m]" is asked for and "opus" comes back.
//
// Default carries NO family deliberately. It resolves to whatever the account
// picks, so no row of this list can honestly claim to be it — marking Default
// as NOW would be a guess of exactly the kind task 208 was about.
const CLAUDE_MODELS = [
  { value: "default", label: "Default (recommended)", stars: 0, family: null },
  { value: "haiku", label: "Haiku", stars: 1, family: "haiku" },
  { value: "sonnet", label: "Sonnet", stars: 2, family: "sonnet" },
  { value: "opus[1m]", label: "Opus (1M context)", stars: 3, family: "opus" },
  { value: "fable", label: "Fable", stars: 4, family: "fable" },
];

// ── THE FIVE THINKING LEVELS (owner verdict item 1) ────────────────────────
// `/effort low|medium|high|xhigh|max`. The label is the owner's word for it,
// the value is the argument — "Extra high" is spoken, `xhigh` is typed.
const CLAUDE_EFFORTS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "xhigh", label: "Extra high" },
  { value: "max", label: "Max" },
];

// ── THE MODE CYCLE (owner verdict item 4) ──────────────────────────────────
// Shift+Tab steps this ring, in this order, and wraps. That is the ONLY way to
// reach a mode — there is no `/mode` command — so a mode button is arithmetic
// over the ring plus that many presses of one chord.
const CLAUDE_MODES = [
  { value: "default", label: "Default", note: "asks before it edits" },
  { value: "acceptEdits", label: "Accept edits", note: "edits without asking" },
  { value: "plan", label: "Plan", note: "plans, changes nothing" },
];

/** How many Shift+Tab presses take the conversation from `current` to
 *  `target`, or **null** when we do not know where it is.
 *
 *  NULL IS THE POINT. Without `claude_state.mode` the ring has no known
 *  starting point, and a button that pressed "probably one" would land him in
 *  a mode he did not choose — Accept edits, if it guessed wrong, which edits
 *  his files without asking. The caller must offer the honest act instead
 *  (step ONE, and say so), never a computed number over an unknown. */
function claudeModePresses(current, target) {
  const ring = CLAUDE_MODES.map((m) => m.value);
  const at = ring.indexOf(current);
  const to = ring.indexOf(target);
  if (at < 0 || to < 0) return null;
  return (to - at + ring.length) % ring.length;
}

/** The mode entry for a value, or null. */
function claudeMode(value) {
  return CLAUDE_MODES.find((m) => m.value === value) || null;
}

/** Which model ROW the live conversation is on, by `claude_state.model` — a
 *  family name — or null when the PC did not say (or said something no row
 *  claims). Never falls back to `saved`: saved and now are different facts,
 *  and conflating them is task 208 itself. */
function claudeNowModel(state) {
  const family = state && state.model ? String(state.model) : "";
  if (!family) return null;
  const row = CLAUDE_MODELS.find((m) => m.family === family);
  return row ? row.value : null;
}

/** Which model ROW the PC has SAVED as its default, or null.
 *
 *  BY FAMILY, EXACTLY LIKE THE LIVE ONE ABOVE (grader 2026-08-11). `saved.model`
 *  is the literal in his settings.json — `claude-fable-5[1m]` on the owner's
 *  own PC — and comparing that against this list's `value` field ("fable",
 *  "opus[1m]", …) matched nothing, ever, so no row was marked saved and the
 *  chip printed the raw id. `saved.model_family` is the server's normalised
 *  answer through the same `model_family()` the live path uses; an older
 *  server that does not send it leaves this null, which is the honest
 *  "unknown" and never a guess. */
function claudeSavedModel(saved) {
  const family = saved && saved.model_family ? String(saved.model_family) : "";
  if (!family) return null;
  const row = CLAUDE_MODELS.find((m) => m.family === family);
  return row ? row.value : null;
}

// ── THE STARS ARE DRAWN, NEVER TYPED ───────────────────────────────────────
// A dingbat character is not an icon in this product, and the reason is on the
// record: the ✥ move handle came out a blunt cross on the owner's own phone
// (2026-08-05), after which every mark this app draws became an SVG path.
// A typed black-star CHARACTER would render in whatever the device's emoji
// font decides — the same gamble, on the very row whose whole job is to
// communicate a ranking at a glance.
//
// One filled star per capability level, laid out along a viewBox as wide as it
// needs to be, so the strip scales with `font-size` like text does and needs
// no CSS of its own.
const CLAUDE_STAR_PATH =
  "M12 2.6l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.5 6.1 20.6l1.2-6.5L2.5 9.5l6.6-.9z";

/** `n` capability stars as ONE inline SVG string, or "" for none (Default).
 *  Pure string building — the gate runs it and asserts no font glyph ever
 *  leaves this function. */
function claudeStarsSvg(n) {
  const count = Math.max(0, Math.min(4, n | 0));
  if (!count) return "";
  const body = [];
  for (let i = 0; i < count; i++) {
    body.push(`<path transform="translate(${i * 22} 0)" d="${CLAUDE_STAR_PATH}"/>`);
  }
  return `<svg class="cl-stars" viewBox="0 0 ${count * 22 + 2} 24" `
    + `fill="currentColor" stroke="none" aria-hidden="true">`
    + body.join("") + "</svg>";
}

// ── THE THREE CHIPS OF TRUTH (owner verdict item 1, task 208) ──────────────
// `kind` is what the LOOK must follow, and it is the whole fix:
//
//   "fact"   — read off the PC. May be lit like state, because it IS state.
//   "memory" — this phone's own record of its own tap. It must NEVER wear a
//              state-claiming look: he watched a "Medium" chip while the PC
//              ran on Max, believed the panel, and reported the command as
//              broken. A memory says whose memory it is.
//
// An absent fact is "unknown" — the word, not a blank and not a fallback to
// the other chip. `saved` may be an empty object (an older server), `state`
// may be null forever (a server with no claude_state at all), and `lastSent`
// may be "": all three are ordinary, and none of them may invent a value.
const CLAUDE_UNKNOWN = "unknown";

function claudeChipValue(v) {
  const text = v === null || v === undefined ? "" : String(v).trim();
  return text || CLAUDE_UNKNOWN;
}

function claudeLabelFor(list, value) {
  const row = list.find((e) => e.value === value);
  return row ? row.label : claudeChipValue(value);
}

/** The chip row for the Thinking panel: SAVED / NOW / LAST SENT.
 *  `state` = the last `claude_state` answer (or null), `saved` = config's
 *  `saved` object (or {}), `lastSent` = this device's own memory (or ""). */
function claudeEffortChips(state, saved, lastSent) {
  const now = state && state.effort ? String(state.effort) : "";
  const was = saved && saved.effort ? String(saved.effort) : "";
  return [
    { key: "saved", kind: "fact", label: "Saved on the PC",
      text: was ? claudeLabelFor(CLAUDE_EFFORTS, was) : CLAUDE_UNKNOWN,
      value: was || null },
    { key: "now", kind: "fact", label: "This conversation now",
      text: now ? claudeLabelFor(CLAUDE_EFFORTS, now) : CLAUDE_UNKNOWN,
      value: now || null },
    { key: "sent", kind: "memory", label: "Last sent from this phone",
      text: lastSent ? claudeLabelFor(CLAUDE_EFFORTS, String(lastSent))
        : CLAUDE_UNKNOWN,
      value: lastSent ? String(lastSent) : null },
  ];
}

/** The chip row for the Model panel: SAVED / NOW. There is no third chip here
 *  — a model tap SAVES, so "last sent from this phone" and "saved on the PC"
 *  would be the same claim written twice, one of them weaker. */
function claudeModelChips(state, saved) {
  const now = state && state.model ? String(state.model) : "";
  const was = saved && saved.model ? String(saved.model) : "";
  const nowRow = claudeNowModel(state);
  const wasRow = claudeSavedModel(saved);
  return [
    { key: "saved", kind: "fact", label: "Saved as the default",
      // Same rule as the NOW chip below it: the family is the fact and the
      // row's label is only how we spell it. A saved id no row claims — an
      // alias like `default`, or a model this page has never heard of — is
      // printed exactly as the PC holds it rather than dropped.
      text: was ? (wasRow ? claudeLabelFor(CLAUDE_MODELS, wasRow) : was)
        : CLAUDE_UNKNOWN,
      value: wasRow || was || null },
    { key: "now", kind: "fact", label: "This conversation now",
      // The family is the fact; the row's label is only how we spell it. A
      // family no row claims (a model we have never heard of) is printed as
      // the PC said it, never silently dropped.
      text: now ? (nowRow ? claudeLabelFor(CLAUDE_MODELS, nowRow) : now)
        : CLAUDE_UNKNOWN,
      value: now || null },
  ];
}

/** The chip row for the Mode panel: just NOW, because nothing saves a mode. */
function claudeModeChips(state) {
  const now = state && state.mode ? String(state.mode) : "";
  const row = claudeMode(now);
  return [
    { key: "now", kind: "fact", label: "This conversation now",
      text: now ? (row ? row.label : now) : CLAUDE_UNKNOWN,
      value: now || null },
  ];
}

// The honest lines. They are product copy and they are the half of tasks
// 190/191/208 that no chip can carry: what the command actually DOES to the
// PC, in the tense it does it.
const CLAUDE_MODEL_NOTE =
  "This saves the model as the default for new conversations too — "
  + "not only for this one.";
const CLAUDE_EFFORT_NOTE =
  "This applies to the conversation running now — up to /clear or a new "
  + "session. If that conversation is relaunched, the extension's own slider "
  + "puts the saved level back.";
const CLAUDE_MODE_NOTE =
  "The mode belongs to the conversation running now. There is no command for "
  + "it — the PC presses Shift+Tab the right number of times.";

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    CLAUDE_MODELS, CLAUDE_EFFORTS, CLAUDE_MODES, CLAUDE_UNKNOWN,
    CLAUDE_STAR_PATH, CLAUDE_MODEL_NOTE, CLAUDE_EFFORT_NOTE, CLAUDE_MODE_NOTE,
    claudeModePresses, claudeMode, claudeNowModel, claudeSavedModel,
    claudeStarsSvg,
    claudeChipValue, claudeLabelFor,
    claudeEffortChips, claudeModelChips, claudeModeChips,
  };
}
