// Making a layout: the source chooser, the armed tap, the slot panel.
//
// Split out of layouts.js on 2026-08-08, when the ✕ chooser pushed that file
// past THE STRUCTURE LAW's 1,000 lines. The boundary is not arithmetic: this
// file is a WIZARD — it owns one piece of state (`creating`), collects slots
// over several taps and ends in a single `layout_create`. layouts.js is what
// you use once layouts EXIST: the bar, the list, the aspect panel, the ✕.
//
// Loads immediately AFTER layouts.js and uses its panel vocabulary
// (`layPanel`, `closeLayoutPanel`, `layChip`, `titleChip`, `chooserBtn`,
// `svg`, `keepFocus`), `creating` from loading.js, `layoutArm` from state.js
// and `GRID_CELLS` from grids.js. gestures.js calls `refreshNewlayButton`
// after an armed tap; connection.js calls `handleLayoutOffer`.
// See client/__about/layouts.md.
"use strict";

const newlayBtn = document.getElementById("btn-newlay");
function refreshNewlayButton() {
  newlayBtn.classList.toggle("active", layoutArm || creating !== null);
}

function cancelCreation(silent) {
  creating = null;
  layoutArm = false;
  refreshNewlayButton();
  closeLayoutPanel();
  hideLayLoading();
  if (!silent) showToast("Layout creation cancelled");
}

keepFocus(newlayBtn, () => {
  if (creating || layoutArm) {
    cancelCreation();
    return;
  }
  openSourceChooser();
});


function newCreation(source) {
  return {
    source,                 // "list" | "tap"
    entries: null,          // list source: [{kind, hwnd, title, process, icon, tab?, x?, y?}]
    slots: [],              // chosen cells, in order — slot 1 names the layout
    name: null,             // owner-typed name; null = follow slot 1's title
    mode: "solo",
    grid: null,
    orient: window.innerHeight >= window.innerWidth ? "portrait" : "landscape",
    awaitingTap: false,
  };
}

// What the app-shortcut ticks start out as: every set whose `process` matches
// the layout's first window, EXCEPT one that also demands a title — Claude is
// exactly that case, and pre-ticking it for every VSCode window would put its
// slash commands on the wheel of a plain editor. The owner adds it with one
// tap on the Claude layout; everything else is right without him.

function openSourceChooser() {
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card";
  const h = document.createElement("h2");
  h.textContent = "New layout";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Where should the windows come from?";
  const row = document.createElement("div");
  row.className = "lay-row lay-sources";
  // The two sources carry the owner's icons (clipboard list / window+plus).
  function sourceBtn(iconName, label, onTap) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "lay-chip lay-source";
    el.innerHTML = svg(iconName) + `<span>${label}</span>`;
    keepFocus(el, onTap);
    return el;
  }
  row.appendChild(sourceBtn("list", "From a list", () => {
    creating = newCreation("list");
    refreshNewlayButton();
    closeLayoutPanel();
    showLayLoading("Collecting windows and tabs…");
    send({ type: "layout_list" });
  }));
  row.appendChild(sourceBtn("newwin", "Tap a window", () => {
    creating = newCreation("tap");
    armNextTap();
  }));
  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, () => cancelCreation()));
  card.append(h, sub, row, actions);
  layPanel.appendChild(card);
}

function armNextTap() {
  creating.awaitingTap = true;
  layoutArm = true;
  refreshNewlayButton();
  closeLayoutPanel();
  showToast("Tap a window or tab on the screen…");
}

function cellsNeeded() {
  return creating.mode === "grid" ? (GRID_CELLS[creating.grid] || 2) : 1;
}

function slotFromOffer(msg) {
  return {
    hwnd: msg.target.hwnd,
    title: msg.tab ? msg.tab.name : msg.target.title,
    process: msg.target.process,
    icon: msg.target.icon,
    // What the PC found running in this window's project — the whole reason
    // Claude no longer needs a tick (owner 2026-08-06).
    agents: msg.target.agents || [],
    tab: msg.tab || null,
    x: msg.x,
    y: msg.y,
  };
}

function slotFromEntry(e) {
  return {
    hwnd: e.hwnd, title: e.title, process: e.process, icon: e.icon,
    agents: e.agents || [],
    tab: e.tab || null, x: e.x, y: e.y,
  };
}

// The layout_offer handler (connection.js delegates here): either the list
// arrived, or one tap's result — both feed the same creation session.
function handleLayoutOffer(msg) {
  hideLayLoading();
  layoutArm = false;
  if (!creating) creating = newCreation("tap");
  if (msg.entries) {
    creating.entries = msg.entries;
  } else if (msg.target) {
    creating.slots.push(slotFromOffer(msg));
    creating.awaitingTap = false;
  }
  refreshNewlayButton();
  renderCreationPanel();
}

function sameSlot(a, b) {
  return a.hwnd === b.hwnd &&
    (a.tab ? b.tab && a.tab.name === b.tab.name : !b.tab);
}

function renderCreationPanel() {
  const c = creating;
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card";

  const h = document.createElement("h2");
  h.textContent = "New layout";
  card.appendChild(h);

  // chosen slots — tap one to remove it
  if (c.slots.length) {
    const sub = document.createElement("p");
    sub.className = "lay-sub";
    sub.textContent = `Chosen (${c.slots.length}/${cellsNeeded()}) — tap to remove:`;
    card.appendChild(sub);
    const row = document.createElement("div");
    row.className = "lay-row";
    // THE TITLE IS THE CONTENT, AND CONTENT IS NEVER CUT (owner 2026-08-06:
    // "čip sa izabranim prozorom skraćuje naziv na 'Claude Code - Remote User
    // - V…', a pun naziv se na tom ekranu ne vidi nigde kada polje Name već
    // prepišeš"). This chip cut at 30 CHARACTERS, in JS, before the DOM ever
    // saw the string — so `scrollWidth === clientWidth` and the phone audit's
    // clip test could not fire, which is how three rounds of PASS sat over a
    // defect two people had pointed at. 225 device px stood idle on that row
    // in portrait, 248 in landscape.
    //
    // Ladder rung 1 then 2 (THE SPACE & LEGIBILITY LAW): the chip takes the
    // free width, and wraps when the title is longer still — the SAME
    // treatment the layout list gives the same titles (`.lay-item-main span`),
    // not a second one invented here. And it is this chip that answers the
    // half he actually complained about: the Name field may be retyped to
    // anything, the chip above it still carries the window's own title.
    c.slots.forEach((s, i) => row.appendChild(
      titleChip(s.title, true,
                () => { c.slots.splice(i, 1); renderCreationPanel(); }, s.icon)));
    card.appendChild(row);
  }

  // The layout's NAME (owner 2026-08-05): the window/tab title is only the
  // default offered here — whatever stands in this field is what the layout
  // bar and the list will call it. Emptying it falls back to the title.
  const nameLbl = document.createElement("p");
  nameLbl.className = "lay-sub";
  nameLbl.textContent = "Name:";
  const nameIn = nameField(
    c.name !== null ? c.name : (c.slots.length ? c.slots[0].title : ""),
    c.slots.length ? c.slots[0].title : "The window's own title");
  nameIn.addEventListener("input", () => { c.name = nameIn.value; });
  card.append(nameLbl, nameIn);

  // The mode row is a picture, not a word (owner round 2, 2026-08-07: "budu
  // skice ... a ne tekstovi tipa 'GRID 2x1'"). Each chip draws the count's
  // own shape in the CURRENTLY chosen orientation — the same drawing his
  // sheet uses, with its own numeral as a caption underneath.
  const modeRow = document.createElement("div");
  modeRow.className = "lay-row";
  modeRow.appendChild(shapeChip(soloSketch(c.orient), "1", c.mode === "solo", () => {
    c.mode = "solo";
    c.grid = null;
    c.slots = c.slots.slice(0, 1);
    renderCreationPanel();
  }));
  // The COUNT is the choice (owner 2026-08-07); the shape follows from it and
  // from the orientation, and only a THREE has anything left to decide. A
  // three's chip shows its currently chosen arrangement once one is picked
  // below, "3-top" by default until then.
  [["2", "2"], ["3-top", "3"], ["4", "4"]].forEach(([g, label]) =>
    modeRow.appendChild(shapeChip(
      gridSketch(c.mode === "grid" && GRID_CELLS[c.grid] === GRID_CELLS[g] ? c.grid : g, c.orient),
      label, c.mode === "grid" && GRID_CELLS[c.grid] === GRID_CELLS[g], () => {
        c.mode = "grid";
        c.grid = g;
        c.slots = c.slots.slice(0, GRID_CELLS[g]);
        renderCreationPanel();
      })));
  card.appendChild(modeRow);

  if (c.mode === "grid" && GRID_CELLS[c.grid] === 3) {
    const arrLbl = document.createElement("p");
    arrLbl.className = "lay-sub";
    arrLbl.textContent = "Where does the single window go?";
    const arrRow = document.createElement("div");
    arrRow.className = "lay-row";
    GRID_THREE.forEach((g) => arrRow.appendChild(
      gridChip(g, c.orient, c.grid === g, () => { c.grid = g; renderCreationPanel(); })));
    card.append(arrLbl, arrRow);
  }

  if (c.source === "list" && c.entries) {
    const hint = document.createElement("p");
    hint.className = "lay-sub";
    hint.textContent = "Windows and tabs on the PC:";
    card.appendChild(hint);
    const list = document.createElement("div");
    list.className = "lay-row lay-list";
    c.entries.forEach((e) => {
      const slot = slotFromEntry(e);
      const idx = c.slots.findIndex((s) => sameSlot(s, slot));
      // The same rule as the chosen chips above: the title is the only thing
      // that tells two windows of one app apart, so it is never cut in JS.
      const label = (e.kind === "tab" ? "↳ " : "") + e.title;
      list.appendChild(titleChip(label, idx >= 0, () => {
        if (idx >= 0) c.slots.splice(idx, 1);          // tap again = deselect
        else if (c.slots.length < cellsNeeded()) c.slots.push(slot);
        else c.slots[c.slots.length - 1] = slot;       // full = replace last
        renderCreationPanel();
      }, e.kind === "window" ? e.icon : null));
    });
    card.appendChild(list);
  } else if (c.source === "tap" && c.slots.length < cellsNeeded()) {
    const row = document.createElement("div");
    row.className = "lay-row";
    row.appendChild(layChip(`Tap window ${c.slots.length + 1} of ${cellsNeeded()}`,
                            false, armNextTap));
    card.appendChild(row);
  }

  // "Which app shortcuts does this layout carry" was a QUESTION here until
  // 2026-08-07, with a row of ticks under it. The owner's answer, twice:
  // "nema potrebe da se vidi ... jer naš program to prepoznaje". He is right,
  // and the PC had been able to answer it since 0.0.266 — `agents` in every
  // state frame. Making the layout carry a written-once copy of that answer
  // is what froze his Claude layout on VS Code. Nothing is asked now.

  // Orientation is exactly the COLUMN of his sheet — a picture too (owner
  // round 2, 2026-08-07): the chosen count's own shape drawn once per
  // orientation, side by side, so the pick is "which of these looks right"
  // rather than reading "Portrait"/"Landscape".
  const orientLbl = document.createElement("p");
  orientLbl.className = "lay-sub";
  orientLbl.textContent = "Shape:";
  const orientRow = document.createElement("div");
  orientRow.className = "lay-row";
  const sketchFor = (o) => c.mode === "grid" ? gridSketch(c.grid, o) : soloSketch(o);
  orientChips(sketchFor, c.orient, (o) => { c.orient = o; renderCreationPanel(); })
    .forEach((chip) => orientRow.appendChild(chip));
  card.append(orientLbl, orientRow);

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, () => cancelCreation()));
  const ready = c.slots.length === cellsNeeded();
  actions.appendChild(layChip("Create", ready, () => {
    if (!ready) return;
    send({
      type: "layout_create",
      slots: c.slots.map((s) => ({ hwnd: s.hwnd, tab: s.tab, x: s.x, y: s.y })),
      name: (c.name || "").trim(), // "" = keep the window/tab title
      mode: c.mode,
      grid: c.grid,
      orient: c.orient,
    });
    creating = null;
    refreshNewlayButton();
    closeLayoutPanel();
    // Tab extraction takes a few seconds of visible work on the PC — the
    // overlay says so instead of a frozen-looking phone (owner 2026-08-02).
    showLayLoading("Arranging the windows…");
  }));
  card.appendChild(actions);
  layPanel.appendChild(card);
}
