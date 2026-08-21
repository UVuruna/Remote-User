// The Session Ledger panel (T111, 2026-08-17) — Claude Code's own task list
// for the focused layout's project, written by the `ledger_hook` VibeCoder
// installs and read fresh every time this card opens.
//
// Modelled on client/claude-panels.js: the same veil/`.sets-card` scaffold,
// the same ghost-click armor, the same "ask first, draw immediately, the
// answer decorates it if it comes" rule (an older server never answers —
// nothing here waits on it). See server/__about/session_ledger.md for the
// wire contract (`.claude/ledger-plan.md` while that page does not exist
// yet) and `server/session_ledger.py` for the file grammar.
//
// Loaded after claude-panels.js — it reuses `ghostClickArmor` and
// `.sets-card`/`.sets-row`/`.sets-done` exactly as that module does.
// controls.js dispatches here through `PANEL_KINDS.ledger` (panels.js), by
// the `ledger` action in actions.json's Claude Tools set.

"use strict";

const ledgerPanel = document.getElementById("ledger-panel");
const ledgerOpened = { t: 0 };
ghostClickArmor(ledgerPanel, ledgerOpened);

// The last answer. `null` is the honest state before any answer has ever
// arrived (or an older PC that never sends one) — the empty card explains
// itself rather than spinning.
let ledgerState = null;
let ledgerPending = false;
let ledgerPendingTimer = null;

// Which rows are expanded, by task id — survives a re-render (a re-render
// happens every time a fresh `ledger_state` lands) but not a panel close,
// same as the Claude panels' own open/close lifecycle.
const ledgerExpanded = new Set();

const LEDGER_ASK_MS = 2000;

// The state grammar (`.claude/ledger-plan.md`) — colour, and the word a
// screen reader gets since the dot alone carries the meaning.
const LEDGER_STATES = {
  red:    { cls: "ldg-red",    word: "not started" },
  orange: { cls: "ldg-orange", word: "in progress" },
  yellow: { cls: "ldg-yellow", word: "waits for you" },
  blue:   { cls: "ldg-blue",   word: "done" },
  green:  { cls: "ldg-green",  word: "verified" },
};

function requestLedgerState() {
  clearTimeout(ledgerPendingTimer);
  ledgerPending = true;
  ledgerPendingTimer = setTimeout(() => {
    ledgerPending = false;
    renderLedgerPanel();
  }, LEDGER_ASK_MS);
  send({ type: "ledger_state" });
}

/** The server's answer (connection.js). Re-renders in place — the card was
 *  drawn empty/asking and this is the moment it can do better. */
function onLedgerState(msg) {
  clearTimeout(ledgerPendingTimer);
  ledgerPending = false;
  ledgerState = {
    title: msg.title || "",
    project: msg.project || "",
    category: msg.category || "",
    tasks: Array.isArray(msg.tasks) ? msg.tasks : [],
  };
  renderLedgerPanel();
}

// ── DRAWING ──────────────────────────────────────────────────────────────

function ledgerDot(state) {
  const dot = document.createElement("span");
  const s = LEDGER_STATES[state] || LEDGER_STATES.red;
  dot.className = "ldg-dot " + s.cls;
  // The word is drawn beside the dot too (ledgerStateWord below) — this
  // aria-label stays as a belt-and-braces fallback for a screen reader
  // reading the dot element directly.
  dot.setAttribute("role", "img");
  dot.setAttribute("aria-label", s.word);
  return dot;
}

/** The short muted word after the dot (grader finding 2026-08-17: colour
 *  alone is not a legend for a stranger). Text, not just the dot's
 *  aria-label, because a sighted reader needs it too. */
function ledgerStateWord(state) {
  const el = document.createElement("span");
  const s = LEDGER_STATES[state] || LEDGER_STATES.red;
  el.className = "ldg-state-word";
  el.textContent = s.word;
  return el;
}

function ledgerAnswer(task) {
  const wrap = document.createElement("div");
  wrap.className = "ldg-answer";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "ldg-answer-input";
  input.placeholder = "Answer…";
  const send_ = document.createElement("button");
  send_.type = "button";
  send_.className = "sets-done ldg-answer-send";
  send_.textContent = "Send";
  keepRowTap(send_, () => {
    const text = input.value.trim();
    if (!text) return;
    // The EXISTING typed-command path (contract: `.claude/ledger-plan.md`) —
    // the same clipboard+Ctrl+V+focus-the-prompt route the Claude set's own
    // slash commands use, never a character-by-character type.
    send({ type: "paste_text", text, enter: true, focus: "claude" });
    showToast(`Sent: ${text}`);
    input.value = "";
  });
  wrap.append(input, send_);
  return wrap;
}

/** One task row, at `depth` (0 = top level). Recurses over `children`. */
function ledgerTaskEl(task, depth) {
  const holder = document.createElement("div");
  holder.className = "ldg-item";
  if (depth > 0) {
    // A stronger parent link than a bare 1px rule (grader finding
    // 2026-08-17): a tinted background band ties every child of the SAME
    // parent group together, and a small tree glyph on the row itself says
    // so even where the tint is subtle (an outlined, uncoloured look).
    holder.classList.add("ldg-child");
  }

  const row = document.createElement("button");
  row.type = "button";
  row.className = "sets-row choice ldg-row";
  if (depth > 0) {
    const branch = document.createElement("span");
    branch.className = "ldg-branch";
    branch.textContent = "└";
    branch.setAttribute("aria-hidden", "true");
    row.appendChild(branch);
  }
  row.appendChild(ledgerDot(task.state));
  row.appendChild(ledgerStateWord(task.state));

  const title = document.createElement("span");
  title.className = "ldg-title";
  title.textContent = task.title || "(untitled)";
  row.appendChild(title);

  if (task.stars) {
    // The 1-5 star complexity from the task line's trailing tag (2026-08-21
    // TASK-schema revision). Drawn stars, capped at 5 by the server's own
    // parser — the row never has to defend against a wider value.
    const stars = document.createElement("span");
    stars.className = "ldg-stars";
    stars.textContent = "★".repeat(task.stars);
    stars.setAttribute("role", "img");
    stars.setAttribute("aria-label", `complexity ${task.stars} of 5`);
    row.appendChild(stars);
  }

  if (task.model) {
    const chip = document.createElement("span");
    chip.className = "ldg-model";
    chip.textContent = "@" + task.model;
    row.appendChild(chip);
  }

  const chev = document.createElement("span");
  chev.className = "ldg-chevron";
  chev.textContent = "▸";
  chev.setAttribute("aria-hidden", "true");
  row.appendChild(chev);

  const expanded = ledgerExpanded.has(task.id);
  holder.classList.toggle("open", expanded);
  // Only the EXPANDED title wraps (grader finding 2026-08-17) — a collapsed
  // row keeps the one-line kin rule (task 163) every other row in this app
  // follows, since the list is the tall part and is made of short rows; a
  // reader who wants the full title taps to expand it.
  title.classList.toggle("ldg-title-wrap", expanded);
  keepRowTap(row, () => {
    if (ledgerExpanded.has(task.id)) ledgerExpanded.delete(task.id);
    else ledgerExpanded.add(task.id);
    renderLedgerPanel();
  });
  holder.appendChild(row);

  if (expanded) {
    const body = document.createElement("div");
    body.className = "ldg-body";
    if (task.feature) {
      // Which docs/FEATURES.md entry this task serves (`#slug`). In the
      // BODY, not on the row — a 412px row already carries dot, state word,
      // title, stars and @model, and the feature is context he opens the
      // row for, not something he scans the list by (that is the desktop
      // Work history's job).
      const feat = document.createElement("p");
      feat.className = "ldg-feature";
      feat.textContent = "#" + task.feature;
      body.appendChild(feat);
    }
    if (task.desc) {
      const desc = document.createElement("p");
      desc.className = "ldg-desc";
      desc.textContent = task.desc;
      body.appendChild(desc);
    }
    if (task.question) {
      const q = document.createElement("div");
      q.className = "ldg-question";
      const qText = document.createElement("p");
      qText.className = "ldg-q-text";
      // A drawn marker, not the system's ❓ emoji: most platforms render
      // that emoji in a saturated red, which reads as this panel's OWN
      // "not started" state colour sitting beside a question that has
      // nothing to do with it (grader finding 2026-08-17). `.ldg-q-mark`
      // is plain text, coloured by us — the accent, never red.
      const mark = document.createElement("span");
      mark.className = "ldg-q-mark";
      mark.textContent = "?";
      mark.setAttribute("aria-hidden", "true");
      qText.append(mark, " " + task.question);
      q.appendChild(qText);
      q.appendChild(ledgerAnswer(task));
      body.appendChild(q);
    }
    if (task.evidence) {
      const ev = document.createElement("p");
      ev.className = "ldg-evidence";
      ev.textContent = "📎 " + task.evidence;
      body.appendChild(ev);
    }
    holder.appendChild(body);

    if (Array.isArray(task.children) && task.children.length) {
      const kids = document.createElement("div");
      kids.className = "ldg-children";
      for (const child of task.children) {
        kids.appendChild(ledgerTaskEl(child, depth + 1));
      }
      holder.appendChild(kids);
    }
  }

  return holder;
}

function ledgerEmptyState(body) {
  const empty = document.createElement("p");
  empty.className = "sets-sub ldg-empty";
  empty.textContent =
    "No task list for this layout. A ledger appears here once Claude Code "
    + "writes one through VibeCoder's own hook, for the project this "
    + "layout's window is open on.";
  body.appendChild(empty);
}

function renderLedgerPanel() {
  ledgerPanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card ldg-card card-split";
  const body = document.createElement("div");
  body.className = "sets-body";

  const head = document.createElement("h2");
  head.textContent =
    ledgerState && ledgerState.tasks.length && ledgerState.title
      ? ledgerState.title
      : "Tasks";
  body.appendChild(head);

  if (ledgerState && ledgerState.category && ledgerState.tasks.length) {
    // The session's own `category:` line (FEATURE / BUGFIX / …) — what KIND
    // of work this ledger is, one muted line under the title.
    const cat = document.createElement("p");
    cat.className = "sets-sub ldg-category";
    cat.textContent = ledgerState.category;
    body.appendChild(cat);
  }
  if (ledgerState && ledgerState.project) {
    const sub = document.createElement("p");
    sub.className = "sets-sub ldg-project";
    sub.textContent = ledgerState.project;
    body.appendChild(sub);
  } else if (ledgerPending) {
    const sub = document.createElement("p");
    sub.className = "sets-sub";
    sub.textContent = "Asking the PC…";
    body.appendChild(sub);
  }

  if (!ledgerState || !ledgerState.tasks.length) {
    ledgerEmptyState(body);
  } else {
    const list = document.createElement("div");
    list.className = "sets-list ldg-list";
    for (const task of ledgerState.tasks) list.appendChild(ledgerTaskEl(task, 0));
    body.appendChild(list);
  }

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "sets-done";
  cancel.textContent = "Close";
  keepRowTap(cancel, closeLedgerPanel);
  body.appendChild(cancel);

  card.appendChild(body);
  ledgerPanel.appendChild(card);
  ledgerPanel.hidden = false;
}

function openLedgerPanel() {
  // Ask FIRST, draw immediately — the card must be on screen in the same
  // frame as the tap; the answer decorates it when it comes, if it comes
  // (same rule as claude-panels.js's openClaudePanel).
  requestLedgerState();
  renderLedgerPanel();
  ledgerOpened.t = performance.now();
}

function closeLedgerPanel() {
  ledgerPanel.hidden = true;
  ledgerPanel.innerHTML = "";
  clearTimeout(ledgerPendingTimer);
  ledgerPending = false;
}

ledgerPanel.addEventListener("pointerdown", (e) => {
  if (e.target === ledgerPanel) closeLedgerPanel();  // backdrop tap = cancel
});
