// The three Claude Code panels the phone opens — Model, Thinking and Mode.
// The tables and every rule they obey live in client/claude-state.js (PURE,
// run whole by tests/test_claude_panels.py); this module is the DOM half:
// one overlay card, the chips of truth at its head, and the sending.
//
// Loaded AFTER panels.js — it uses `ghostClickArmor` and the `.sets-card`
// shape every other overlay in this app wears. controls.js dispatches to
// `openClaudePanel(btn)` at runtime, by the button's `panel` field in
// actions.json, so nothing here is imported at load time.
//
// ── ASKING THE PC WHAT IT IS RUNNING (owner verdict 2026-08-11, item 3) ────
// `claude_state {}` goes up when a panel opens; `claude_state {model,
// model_id, effort, mode, saved}` comes back. THE ANSWER IS OPTIONAL, and
// that is not defensive politeness: an older PC never answers at all, and the
// panels are useless if they need it. Nothing here waits on it, nothing here
// blocks on it, and every chip has a truthful thing to say without it
// ("unknown" — claude-state.js).

"use strict";

const claudePanel = document.getElementById("claude-panel");
const claudeOpened = { t: 0 };
ghostClickArmor(claudePanel, claudeOpened);

// The last answer, and whether we are still waiting for one. `null` state with
// `pending` false is the honest end state of an older server: we asked, it
// said nothing, and the card says unknown rather than spinning forever.
let claudeState = null;
let claudePending = false;
let claudePendingTimer = null;
let claudeOpenPanel = "";     // which of the three is on screen, "" = none

// How long we call it "asking" before we call it unknown. Generous enough for
// a phone on a relay, short enough that a card is never a waiting room.
const CLAUDE_ASK_MS = 2000;
// How long after a command before its effect is worth re-reading. The PC has
// to paste, press Enter and let the app act; asking sooner reads the state
// from BEFORE the tap and would show him a stale answer as a fresh one.
const CLAUDE_SETTLE_MS = 1500;

function requestClaudeState() {
  clearTimeout(claudePendingTimer);
  claudePending = true;
  claudePendingTimer = setTimeout(() => {
    claudePending = false;
    renderClaudePanel();      // "asking…" becomes "unknown", in place
  }, CLAUDE_ASK_MS);
  send({ type: "claude_state" });
}

/** The server's answer (connection.js). Re-renders whatever is open — the
 *  card was drawn with unknowns and this is the moment it can do better. */
function onClaudeState(msg) {
  clearTimeout(claudePendingTimer);
  claudePending = false;
  claudeState = {
    model: msg.model || null,
    model_id: msg.model_id || null,
    effort: msg.effort || null,
    mode: msg.mode || null,
  };
  // `saved` rides the same answer, and it is the SAME fact the `actions`
  // frame already carries — so it may refresh it, never contradict it with a
  // second store nobody keeps in step.
  if (msg.saved && typeof msg.saved === "object") claudeSaved = msg.saved;
  renderClaudePanel();
}

// This device's memory of its own /effort tap (task 208). Through the prefs
// bridge, not bare localStorage: that is per-ORIGIN and split his state
// between the LAN and the Tailscale address once already.
function claudeLastEffort() {
  return prefGet("claudeLastEffort") || "";
}

// ── DRAWING ────────────────────────────────────────────────────────────────

/** One chip. `kind` decides the LOOK and nothing else does — a "memory" chip
 *  may never be styled like a fact (task 208: a per-device memory wearing a
 *  live-state look is the whole bug). */
function claudeChipEl(chip) {
  const el = document.createElement("span");
  el.className = "cl-chip cl-" + chip.kind + (chip.value ? "" : " cl-none");
  const cap = document.createElement("span");
  cap.className = "cl-chip-cap";
  cap.textContent = chip.label;
  const val = document.createElement("b");
  val.textContent = claudePending && !chip.value ? "asking the PC…" : chip.text;
  el.append(cap, val);
  return el;
}

function claudeChipRow(chips) {
  const row = document.createElement("div");
  row.className = "cl-chips";
  chips.forEach((c) => row.appendChild(claudeChipEl(c)));
  return row;
}

/** One option row: the name, its capability stars, and a "now" mark when the
 *  PC says this is the one running. The mark is a FACT chip, so it appears
 *  only when `claude_state` answered. */
function claudeOptionRow(label, starsSvg, marks, onPick) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = "sets-row choice cl-opt";
  const name = document.createElement("span");
  name.className = "cl-opt-name";
  name.textContent = label;
  row.appendChild(name);
  if (starsSvg) {
    const stars = document.createElement("span");
    stars.className = "cl-opt-stars";
    stars.innerHTML = starsSvg;             // drawn paths, built by us
    // The ranking must reach a screen reader too — the strip itself is
    // aria-hidden, so the row says the number in words.
    stars.setAttribute("aria-hidden", "true");
    row.appendChild(stars);
  }
  for (const m of marks) {
    const tag = document.createElement("span");
    tag.className = "sets-hint cl-mark cl-mark-" + m.kind;
    tag.textContent = m.text;
    row.appendChild(tag);
  }
  keepFocus(row, onPick);
  return row;
}

// NOT `card-columns` — a MULTICOL card is a fragmentainer, and a capped one
// answers "I do not fit" by growing a column off the side of the screen
// instead of scrolling (task 217). These cards take the Sets picker's answer
// instead (`card-split`, client/panels.css): the columns are DECLARED on the
// list, which is the tall part and is made of short rows, and the card itself
// is a flex column whose `.sets-body` scrolls under a pinned Cancel.
//
// THE CARD RETURNED IS THE BODY, not the card. Everything a panel appends
// goes inside the scrolling part; only `claudeFinish` reaches the card again,
// to pin the button. That is what keeps the primary action on screen at
// 915x412, where these cards genuinely do not fit.
function claudeCard(title, subtitle) {
  claudePanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card cl-card card-split";
  const body = document.createElement("div");
  body.className = "sets-body";
  const head = document.createElement("h2");
  head.textContent = title;
  const sub = document.createElement("p");
  sub.className = "sets-sub";
  sub.textContent = subtitle;
  body.append(head, sub);
  card.appendChild(body);
  return body;
}

function claudeFinish(body, note) {
  const why = document.createElement("p");
  why.className = "sets-sub cl-note";
  why.textContent = note;
  body.appendChild(why);
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "sets-done";
  cancel.textContent = "Cancel";
  keepFocus(cancel, closeClaudePanel);
  body.parentElement.appendChild(cancel);
  claudePanel.appendChild(body.parentElement);
  claudePanel.hidden = false;
}

/** Send a finished slash command, say so, close, and re-read the PC once it
 *  has had time to act. */
function claudeSend(text, said) {
  // `focus: "claude"` (owner order 2026-08-11, task 200): the PC puts the
  // caret in Claude's own prompt BEFORE typing. Without it a command typed
  // while the editor pane had focus went into a source file — and the server
  // half of this field landed the same day with nothing on the phone sending
  // it, which is a feature that does not exist (the actions.json lesson).
  send({ type: "paste_text", text, enter: true, focus: "claude" });
  showToast(said);
  closeClaudePanel();
  setTimeout(() => { if (socketReady()) requestClaudeState(); }, CLAUDE_SETTLE_MS);
}

// ── MODEL (owner verdict item 2, tasks 190 + 208) ──────────────────────────
function renderClaudeModelPanel() {
  const body = claudeCard(
    "Model",
    "The five the PC's own picker offers, weakest first. Tapping one runs "
    + "the command on the PC.");
  body.appendChild(claudeChipRow(claudeModelChips(claudeState, claudeSaved)));

  const list = document.createElement("div");
  list.className = "sets-list";
  const nowRow = claudeNowModel(claudeState);
  for (const m of CLAUDE_MODELS) {
    const marks = [];
    if (nowRow && m.value === nowRow) marks.push({ kind: "now", text: "now" });
    if (claudeSaved && claudeSaved.model === m.value) {
      marks.push({ kind: "saved", text: "saved" });
    }
    const row = claudeOptionRow(
      m.label, claudeStarsSvg(m.stars), marks,
      () => claudeSend(`/model ${m.value}`, `Model: ${m.label}`));
    if (m.stars) {
      row.setAttribute(
        "aria-label",
        `${m.label} — capability ${m.stars} of 4`);
    }
    if (marks.some((x) => x.kind === "now")) {
      row.classList.add("cl-current");
      row.setAttribute("aria-current", "true");
    }
    list.appendChild(row);
  }
  body.appendChild(list);
  claudeFinish(body, CLAUDE_MODEL_NOTE);
}

// ── THINKING (owner verdict item 1, tasks 191 + 208) ───────────────────────
function renderClaudeEffortPanel() {
  const body = claudeCard(
    "Thinking",
    "How hard the PC thinks about each answer. Tapping one runs the command "
    + "on the PC.");
  body.appendChild(claudeChipRow(
    claudeEffortChips(claudeState, claudeSaved, claudeLastEffort())));

  const list = document.createElement("div");
  list.className = "sets-list";
  const now = claudeState && claudeState.effort ? claudeState.effort : null;
  for (const e of CLAUDE_EFFORTS) {
    // ONLY the live answer marks a row (task 208). The saved level and this
    // phone's last tap are said in the chips above, in their own words —
    // marking a row with either of them is what made him read "Medium" as the
    // PC's state while it was running on Max.
    const marks = now === e.value ? [{ kind: "now", text: "now" }] : [];
    const row = claudeOptionRow(
      e.label, "", marks,
      () => {
        prefSet("claudeLastEffort", e.value);
        claudeSend(`/effort ${e.value}`, `Thinking: ${e.label}`);
      });
    if (marks.length) {
      row.classList.add("cl-current");
      row.setAttribute("aria-current", "true");
    }
    list.appendChild(row);
  }
  body.appendChild(list);
  claudeFinish(body, CLAUDE_EFFORT_NOTE);
}

// ── MODE (owner verdict item 4) ────────────────────────────────────────────
// There is no command for the mode: Shift+Tab steps a three-mode ring and
// wraps. So a target mode is arithmetic — and the arithmetic needs a KNOWN
// starting point, which is exactly why `claude_state.mode` exists.
//
// WITHOUT IT, THE PANEL OFFERS THE ONE HONEST ACT: step once, and say that it
// stepped rather than pretending it arrived. Guessing the current mode and
// pressing "probably two" could land him in Accept edits, which edits his
// files without asking — the one outcome a wrong guess must never buy.
//
// THE PRESSES GO OUT AS ORDINARY `chord` MESSAGES, which is the whole reason
// this button can ship today: `chord` is in the server's TYPING_KINDS, so
// every press passes through `focus_guard.typist()` exactly like the Claude
// set's /usage and /compact do. It needs no focus contract of its own, and it
// is no more exposed than the buttons beside it (constraint 11).
function claudeSendMode(target) {
  const current = claudeState && claudeState.mode ? claudeState.mode : null;
  const presses = claudeModePresses(current, target);
  const row = claudeMode(target);
  if (presses === null) {
    send({ type: "chord", chord: "shift+tab" });
    showToast("Mode stepped once — the PC did not say which mode it was on");
  } else if (presses === 0) {
    showToast(`Already on ${row.label}`);
    closeClaudePanel();
    return;
  } else {
    for (let i = 0; i < presses; i++) send({ type: "chord", chord: "shift+tab" });
    showToast(`Mode: ${row.label}`);
  }
  closeClaudePanel();
  setTimeout(() => { if (socketReady()) requestClaudeState(); }, CLAUDE_SETTLE_MS);
}

function renderClaudeModePanel() {
  const known = !!(claudeState && claudeMode(claudeState.mode));
  const body = claudeCard(
    "Mode",
    known
      ? "How much the PC may do on its own. Tapping one presses Shift+Tab "
        + "until it gets there."
      : "How much the PC may do on its own. This PC has not said which mode "
        + "it is on, so a tap can only step to the NEXT one.");
  body.appendChild(claudeChipRow(claudeModeChips(claudeState)));

  const list = document.createElement("div");
  list.className = "sets-list";
  for (const m of CLAUDE_MODES) {
    const marks = [];
    if (known && claudeState.mode === m.value) {
      marks.push({ kind: "now", text: "now" });
    }
    const row = claudeOptionRow(
      known ? m.label : `${m.label} — steps one`, "", marks,
      () => claudeSendMode(m.value));
    const note = document.createElement("span");
    note.className = "sets-hint cl-opt-note";
    note.textContent = m.note;
    row.appendChild(note);
    if (marks.length) {
      row.classList.add("cl-current");
      row.setAttribute("aria-current", "true");
    }
    list.appendChild(row);
  }
  body.appendChild(list);
  claudeFinish(body, CLAUDE_MODE_NOTE);
}

// ── ONE DOOR IN ────────────────────────────────────────────────────────────

const CLAUDE_PANELS = {
  "claude-model": renderClaudeModelPanel,
  "claude-effort": renderClaudeEffortPanel,
  "claude-mode": renderClaudeModePanel,
};

/** Re-draw whatever is open, in place. Called when an answer lands and when
 *  the wait for one runs out — the card is never rebuilt from scratch by the
 *  owner's finger, so the ghost-click armor's clock keeps its original start. */
function renderClaudePanel() {
  const render = CLAUDE_PANELS[claudeOpenPanel];
  if (render && !claudePanel.hidden) render();
}

/** The D-pad face for a `panel` button (controls.js dispatches here).
 *  It lives in this module rather than in the switch that calls it: controls.js
 *  stands at 990 of the 1,000 lines THE STRUCTURE LAW allows it, and the face
 *  of a Claude card belongs to the file that draws the card. */
function makeClaudePanelButton(btn) {
  const icon = btn.icon && ICONS[btn.icon] ? btn.icon : null;
  const el = makeButton(icon ? "ctl" : "ctl text", icon, btn.label || btn.panel);
  keepFocus(el, () => openClaudePanel(btn));
  return el;
}

function openClaudePanel(btn) {
  const render = CLAUDE_PANELS[btn.panel];
  if (!render) return;
  claudeOpenPanel = btn.panel;
  // Ask FIRST, draw immediately. The card must be on screen in the same frame
  // as the tap; the answer decorates it when it comes, if it comes.
  requestClaudeState();
  render();
  claudeOpened.t = performance.now();
}

function closeClaudePanel() {
  claudePanel.hidden = true;
  claudePanel.innerHTML = "";
  claudeOpenPanel = "";
  clearTimeout(claudePendingTimer);
  claudePending = false;
}

claudePanel.addEventListener("pointerdown", (e) => {
  if (e.target === claudePanel) closeClaudePanel();  // backdrop tap = cancel
});
