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
// `keepRowTap`, and layouts.js's panel markup (`layPanel`, `layChip`,
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
  sub.textContent = "It opens on the PC and becomes part of the layout.";
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
  const name = document.createElement("span");
  name.textContent = e.label;
  main.appendChild(name);
  if (e.sub) {
    const note = document.createElement("small");
    note.className = "lc-note";
    note.textContent = e.sub;
    main.appendChild(note);
  }
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
    const why = document.createElement("small");
    why.className = "lc-why";
    why.textContent = e.why || "already open";
    main.appendChild(why);
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
// none of these acts produces a slot (a new conversation, a tab, a folder), so
// leaving the wizard standing would promise a Create button that has nothing
// to create. The one act that does open a window — VS Code's "New window" —
// still does not join the layout by itself: that is his tap on the ordinary
// window offer, never ours (constraint 18/19).
function actRow(e, app) {
  const row = document.createElement("div");
  row.className = "lay-item lc-row lc-kid";
  const main = document.createElement("button");
  main.type = "button";
  main.className = "lay-item-main";
  main.innerHTML = svg(APP_ICON[app] || "newwin");
  const name = document.createElement("span");
  name.textContent = e.label;
  main.appendChild(name);
  if (e.sub) {
    const note = document.createElement("small");
    // `lc-act-note`, not the plain `lc-note`: a recent row's note is a PATH
    // whose width the name may take back (the 96 px cap in layout-create.css),
    // while this one is the only sentence saying what the act does — capping
    // it cut "a new conversation in this window" to "a new conversati…",
    // which is the explanation, not a detail.
    note.className = "lc-note lc-act-note";
    note.textContent = e.sub;
    main.appendChild(note);
  }
  keepRowTap(main, () => {
    send({ type: "layout_act", id: e.id });
    cancelCreation(true);
  });
  row.appendChild(main);
  return row;
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
