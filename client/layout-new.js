// THE NEW SOURCE: a window that is not open yet, and what THIS layout's own
// application can do.
//
// Split out of layout-create.js on 2026-08-13, at THE STRUCTURE LAW's wall and
// by RESPONSIBILITY rather than by line count: layout-create.js is the WIZARD
// (it owns `creating`, collects slots and ends in one `layout_create`), while
// everything here is about the PC's own programs — what they can OPEN
// (`/recents`, task 184) and what the focused layout's app can DO (the acts
// group, owner ballot 2026-08-13, T29). The two questions have different
// owners on the server too (`server/recents.py` and `server/layout_acts.py`).
//
// Loads immediately AFTER layout-create.js and uses its vocabulary — `creating`,
// `newCreation`, `refreshNewlayButton`, `renderCreationPanel`, `cancelCreation`,
// `keepRowTap`, `twoLineRow`, and layouts.js's panel markup (`layPanel`, `layChip`,
// `.lay-item` rows). connection.js calls `handleLayoutActs`.
// See client/__about/layouts.md.
"use strict";

// ── NEW: A WINDOW THAT IS NOT OPEN YET (owner 2026-08-09, task 184) ─────────
//
// His observation is the whole design: "recent imaju svi" (lang-ok: owner
// quote) — VS Code, Chrome and Explorer each keep a recent list the taskbar
// already shows him, so the phone can offer to OPEN one and make a layout out
// of what appears. The PC owns every hard part (server/recents.py, which is
// also where the honest per-app limits are written down); this side is a list
// and one POST.
//
// Over HTTP and not the socket, exactly like the uploads and the window offer:
// a list and a window are plain request/response, and the socket's dispatcher
// belongs to another round.
const APP_ICON = { vscode: "vscode", chrome: "chrome", explorer: "explorer" };
const APP_NAME = { vscode: "VS Code", chrome: "Chrome", explorer: "Explorer" };

// THE LAYOUT'S OWN GROUP (owner ballot 2026-08-13, T29). The panel must know
// where it was opened FROM — the same rule the creation list already follows
// (constraint 21) — and offer the acts of the program this layout is made of
// before the standard "what can the PC open" list.
//
// It is READ from the server and never inferred here: the phone knows a
// layout's process from `layout_state`, but which acts an app really has, and
// whether the PC can perform them at all, is the PC's own answer. `in_layout`
// arrives on that answer rather than being deduced from the layout bar, so the
// panel READS which case it is in instead of guessing (the same reason the
// two-group list carries its own `group` on every entry).
let layActs = null;              // the pending ask, resolved by connection.js

function requestLayoutActs() {
  if (!ws || ws.readyState !== 1) return Promise.resolve(null);
  send({ type: "layout_acts" });
  return new Promise((resolve) => {
    // No timer, no guessed wait (constraint 15): the panel below renders the
    // standard list the moment the HTTP list lands and simply gains its top
    // group when this answers. A connection that dies takes the panel with it.
    layActs = resolve;
  });
}

function handleLayoutActs(msg) {
  const resolve = layActs;
  layActs = null;
  if (resolve) resolve(msg);
}

async function openRecentsPanel() {
  if (!creating) creating = newCreation("new");
  refreshNewlayButton();
  closeLayoutPanel();
  // LOADING: CUBE — a pure query of what the PC could open
  showLayLoading("Asking the PC what it can open…", LOADING_CUBE);
  const actsAsk = requestLayoutActs();
  let list = [];
  try {
    const res = await fetch(`/recents?token=${encodeURIComponent(token)}`);
    const data = await res.json();
    list = data.entries || [];
  } catch (err) {
    hideLayLoading();
    showToast(`Could not read the PC's recent list: ${err.message}`);
    return;
  }
  const acts = await actsAsk;
  hideLayLoading();
  if (!list.length && !(acts && acts.entries && acts.entries.length)) {
    // NAMED, never a blank card. None of the three apps installed is a real
    // state of a PC, and a panel with nothing in it reads as a broken feature.
    showToast("None of VS Code, Chrome or Explorer is installed on the PC");
    return;
  }
  renderRecentsPanel(list, acts);
}

function renderRecentsPanel(list, acts) {
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  // NOT `card-columns` (2026-08-13, measured by photographing it). This panel
  // is one long list, and its landscape reflow is the two-column GRID in
  // layout-create.css — a fragmentainer on top of that produced quarters, and
  // a scroller inside a multicol is the exact combination this project already
  // measured as broken (rows sliced, no scrollbar to say any were missing).
  card.className = "lay-card lc-panel lc-new";
  const scrollWrap = document.createElement("div");
  scrollWrap.className = "lc-scrollwrap";
  card.appendChild(scrollWrap);
  const h = document.createElement("h2");
  h.textContent = "Open a window";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  // ONE SENTENCE MAY NOT STAND OVER TWO GROUPS THAT BEHAVE OPPOSITELY (owner
  // report 2026-08-19). It used to read "It opens on the PC and becomes part
  // of the layout", which was true of the recent rows below (they become a
  // creation slot) and false of the acts above — a new conversation and a new
  // tab open no window at all. Every row now says what IT does on its own
  // second line, so this one says only what is true of all of them.
  sub.textContent = "What opens as a window joins this layout.";
  scrollWrap.append(h, sub);

  const rows = document.createElement("div");
  rows.className = "lc-rows lc-scroll";

  // THE LAYOUT'S OWN GROUP FIRST, under a heading that names the app — the
  // second heading below ("VS Code", "Chrome"…) then reads as the standard
  // list it has always been. From the desktop there is no first group at all,
  // which is his own rule for the creation list (constraint 21).
  const own = (acts && acts.in_layout && acts.entries) || [];
  if (own.length) {
    const head = document.createElement("p");
    head.className = "lay-sub lc-app";
    head.textContent = acts.name ? `In this layout — ${acts.name}` : "In this layout";
    rows.appendChild(head);
    own.forEach((e) => rows.appendChild(actRow(e, acts.app)));
  }

  let app = null;
  list.forEach((e) => {
    if (e.app !== app) {
      app = e.app;
      const head = document.createElement("p");
      head.className = "lay-sub lc-app";
      head.textContent = APP_NAME[app] || app;
      rows.appendChild(head);
    }
    rows.appendChild(recentRow(e));
  });
  scrollWrap.appendChild(rows);

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, () => cancelCreation()));
  card.appendChild(actions);
  layPanel.appendChild(card);
}

// EVERY ROW OF THIS PANEL IS TWO LINES — THE NAME, THEN WHAT IT IS (owner
// decree 2026-08-20, with his screenshot: `Ne…`, `UVu…`, `Vib…`). A row here
// carries a NAME and a fact about it (a folder's whole path, or the sentence
// saying what an act does), and on a 412 px phone those two never shared one
// line: the ladder's step 1 was walked on the row's own children (task 233,
// the 96 px cap) and it kept the row one line tall by starving the only thing
// he actually reads. His ruling ends that: *"ili ide sve u jedan red ili sve u
// 2 reda"* (lang-ok: owner quote) — so the whole panel goes to two.
//
// THE KIN RULE OF TASK 163 IS NOT BROKEN BY THIS, and that was checked before
// it was written: that rule says rows of one group are the SAME height and a
// long name is cut rather than wrapped to an unpredictable number of lines.
// Here every row of the panel gains the same second line, so they stay equal
// — and both lines are still single-line-with-ellipsis, so no row can grow to
// three. The name gets the room it never had; the path, whose beginning is
// what tells two `src` projects apart, gets the whole width of line two.

// A row of the New list. It wears its APP's drawn face (icons.js) rather than
// the process icon the other two lists show — nothing has been opened yet, so
// there is no window whose icon this could be, and drawing one would claim a
// window exists. A `recent` row is INDENTED under its app's heading for the
// same reason a tab is indented under its window (task 168): it belongs to it.
function recentRow(e) {
  const row = document.createElement("div");
  row.className = "lay-item lc-row" + (e.kind === "recent" ? " lc-kid" : "");
  const main = document.createElement("button");
  main.type = "button";
  main.className = "lay-item-main";
  main.innerHTML = svg(APP_ICON[e.app] || "newwin");
  let why = null;
  if (e.open) {
    why = document.createElement("small");
    why.className = "lc-why";
    why.textContent = e.why || "already open";
  }
  twoLineRow(main, e.label, e.sub || "", why);
  // ALREADY OPEN = DIMMED AND UNTAPPABLE (his report 2026-08-13, picture 1).
  // The tap used to launch the app, the app answered by raising the window it
  // already held, no new window ever came into being, and he watched the
  // loading cube over a screen where nothing would happen. The row is still
  // SHOWN — his own ballot: a project simply missing from the list is a thing
  // he would hunt for, while a dimmed row with a reason answers him.
  //
  // `disabled` and not a swallowed tap: a real button that cannot be pressed
  // is what a screen reader, the pointer and the eye all read the same way,
  // and `keepRowTap` is deliberately never attached — a handler that decides
  // to do nothing is a handler that one day forgets to.
  if (e.open) {
    row.classList.add("lc-busy");
    main.disabled = true;
  } else {
    keepRowTap(main, () => openRecentEntry(e));
  }
  row.appendChild(main);
  return row;
}

// A row of the layout's OWN group (T29). It carries the app's face like every
// other row here, and its tap sends one `layout_act` — the PC does the rest
// behind the focus fence and answers with a toast only when it refused.
//
// The panel CLOSES on the tap and the creation session is cancelled silently:
// none of these acts produces a CREATION SLOT (a new conversation, a tab, a
// folder), so leaving the wizard standing would promise a Create button that
// has nothing to create. The one act that opens a WINDOW — VS Code's "New
// window, same folder" — needs no slot either: the PC puts that window into
// this layout itself (owner decree 2026-08-20, constraint 43), so there is
// nothing left here for him to answer.
//
// THE SENTENCE THAT STOOD HERE WAS WRONG AND IT COST HIM THE FEATURE: "that
// is his tap on the ordinary window offer, never ours (constraint 18/19)".
// Neither of those constraints says anything of the kind — 18 is one window,
// one question; 19 is a dialog opening in the middle of its parent — and the
// chip it deferred to is silenced by constraint 33 precisely because the
// window is ours on his tap. So the window opened and nothing on earth
// placed it. See server/layout_acts.py.
function actRow(e, app) {
  const row = document.createElement("div");
  row.className = "lay-item lc-row lc-kid";
  const main = document.createElement("button");
  main.type = "button";
  main.className = "lay-item-main";
  main.innerHTML = svg(APP_ICON[app] || "newwin");
  twoLineRow(main, e.label, e.sub || "", null);
  keepRowTap(main, () => {
    send({ type: "layout_act", id: e.id });
    cancelCreation(true);
    runLayoutAct(e);
  });
  row.appendChild(main);
  return row;
}

// THE ACT IS COVERED WHILE IT RUNS (owner report 2026-08-17, and his sentence
// names the reason: the PC "has a lot of work to do in the background — to
// open it, to move it down"). Until this round the tap sent one message and
// the panel simply closed: the phone looked frozen over a screen where the PC
// really was working, which is the complaint the loading rule exists for.
//
// WHICH ANIMATION IS HIS ANSWER THIS ROUND, and it splits exactly along
// constraint 16's line: FULL for the act that opens a WINDOW, because the desk
// rearranges itself and there is nothing worth watching happen; CUBE for the
// acts that happen inside one window — a conversation, a tab — because there
// the only thing to see IS it opening. The panel reads which case it is in
// from the row's own `opens` field rather than matching its id, so a second
// window-opening act one day is covered without the page being reissued.
//
// THE OVERLAY ENDS ON A FACT, NEVER A TIMER (constraint 15). `layout_act_done`
// is the server's one answer for every ending an act can have — done, refused,
// crashed — so there is nothing here to estimate about how long another
// program needs. A connection that dies takes the overlay with it (see
// `endLayoutAct`, called from connection.js's close path), because the one
// thing worse than a veil that comes down early is one that never does.
function runLayoutAct(e) {
  // LOADING: FULL — a new window climbs onto the desk and the PC re-places it
  // LOADING: CUBE — a tab or a conversation opening is worth seeing open
  showLayLoading(`${e.label}…`, e.opens ? LOADING_FULL : LOADING_CUBE);
}

// The server's answer, routed here by connection.js. It carries no result: a
// refusal has already arrived as its own toast, which is the sentence he can
// act on, while this message says only that the waiting is over.
function endLayoutAct() {
  hideLayLoading();
}

// The chosen thing OPENS, and the window that appears becomes the slot — the
// ordinary creation flow from there on, with nothing new on the wire: the
// panel already knows how to hold a slot, and `layout_create` already knows
// how to resolve one from a handle.
//
// The LOADING OVERLAY covers the whole wait (owner 2026-08-03, repeatedly):
// cold-starting VS Code is several visible seconds of the PC doing something,
// and a phone that looks frozen during it is the complaint that rule exists
// for. The server is what waits for the window, so the overlay's end is the
// window's arrival and not a reply about an intention.
async function openRecentEntry(e) {
  closeLayoutPanel();
  // LOADING: CUBE — his own example: he should SEE the app opening behind
  showLayLoading(`Opening ${e.label}…`, LOADING_CUBE);
  let data = {};
  try {
    const res = await fetch(`/recents/open?token=${encodeURIComponent(token)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: e.id }),
    });
    data = await res.json();
  } catch (err) {
    data = { ok: false, error: err.message };
  }
  hideLayLoading();
  if (!data.ok || !data.window) {
    showToast(data.error || "The PC could not open it");
    renderCreationPanel();
    return;
  }
  const w = data.window;
  creating.slots.push({
    hwnd: w.hwnd, title: w.title, process: w.process, icon: w.icon,
    agents: w.agents || [], tab: null, x: 0.5, y: 0.5,
  });
  refreshNewlayButton();
  renderCreationPanel();
}
