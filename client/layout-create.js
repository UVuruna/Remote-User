// Making a layout: the source chooser, the armed tap, the slot panel.
//
// Split out of layouts.js on 2026-08-08, when the ✕ chooser pushed that file
// past THE STRUCTURE LAW's 1,000 lines. The boundary is not arithmetic: this
// file is a WIZARD — it owns one piece of state (`creating`), collects slots
// over several taps and ends in a single `layout_create`. layouts.js is what
// you use once layouts EXIST: the bar, the list, the aspect panel, the ✕.
//
// Loads immediately AFTER layouts.js and uses its panel vocabulary
// (`layPanel`, `closeLayoutPanel`, `layChip`, `chooserBtn`, `nameField` and
// the `.lay-item` ROW markup — reused, never copied. Both lists became real
// rows on 2026-08-09, task 168, which left the wrapping title pill
// (`titleChip` / `.lay-chip.lay-title`) with no caller; it was deleted the
// same day), `svg`, `keepFocus`, `showToast`,
// `creating` from loading.js, `layoutArm` from state.js
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
  card.className = "lay-card card-columns";
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

// HOW MANY MEMBERS THIS DESKTOP CAN REALLY FILL — the one number the shape
// chooser and the list header are both answered from (owner report
// 2026-08-09, task 166: "it offers a grid of 4 when the desktop holds 3").
// There was no cap of any kind: the 2/3/4 chips were an unconditional
// literal, `cellsNeeded()` read the mode and never looked at what was open,
// and the token `entries.length` appeared nowhere in the client — so the
// panel promised an arrangement the PC could not fill and the Create button
// then sat there doing nothing.
//
// THE QUANTITY IS NOT `entries.length`, which is the trap this had to avoid:
// a VS Code with three tabs emits FOUR entries (the window plus its tabs) and
// still cannot yield four independent members. What a window is worth is
// "the tabs that can be extracted, plus the window itself only if at least
// one tab stays in it" — take k of its N tabs and you hold k windows plus the
// original while k < N, which is N either way. So a window offering N ≥ 2
// tabs is worth N, and a window offering none is worth exactly 1. (Since task
// 167 the server never offers a lone tab; a `1` here could only come from an
// older PC, and 1 is the honest answer for it too.)
//
// null = the TAP source, where nothing is enumerated and no cap can honestly
// be computed — the chooser stays whole and the tap flow decides.
function availableMembers() {
  const entries = creating && creating.entries;
  if (!entries) return null;
  const tabs = new Map();          // window hwnd → how many of its tabs ride
  entries.forEach((e) => {
    if (e.kind === "tab") tabs.set(e.hwnd, (tabs.get(e.hwnd) || 0) + 1);
    else if (!tabs.has(e.hwnd)) tabs.set(e.hwnd, 0);
  });
  let total = 0;
  tabs.forEach((n) => { total += n >= 2 ? n : 1; });
  return total;
}

// A WINDOW AND ONE OF ITS OWN TABS ARE THE SAME WINDOW (owner 2026-08-09,
// task 167). Choosing both was unprevented and had no good outcome: the tab
// is torn out of the very window standing in the cell beside it, so the
// layout ends up holding one window twice — and when the extraction fails
// (six visible seconds of synthetic mouse drag) the fallback IS that window,
// so both cells name it outright. Two different tabs of one window are fine
// and are the whole point of tab layouts; it is the window plus its own tab
// that cannot stand together.
function ownTabConflict(slot) {
  return creating.slots.some(
    (s) => s.hwnd === slot.hwnd && !!s.tab !== !!slot.tab);
}

// ONE ROW PER THING, AND A TAB IS INDENTED UNDER ITS WINDOW (owner
// 2026-08-09, task 168, in translation): "the indentation stays — a column.
// It does not have to be the same row as its parent, because a sub-tab of a
// window does NOT belong to the same kin group as its parent; that is exactly
// why a minimal indent is allowed, to show that those tabs are children of
// the one above that is not indented. Right now there are arrows, but that is
// less noticeable and less intuitive."
//
// So the literal "↳ " prefix is gone and both lists are REAL ROWS. They were
// a wrapping flow of pills (`.lay-row`), which has no per-row box to indent
// at all — converting them is what makes his ruling drawable, and his ruling
// is what makes it legal under the kin rule of task 163 (a child is not in
// its parent's group, so the indent may make it narrower).
//
// The markup is the layout list's own (`.lay-item` / `.lay-item-main`), not a
// second row style invented here: the ellipsis, the icon sizing and the
// `sel` state are already written there once. `.lc-row` only adds what is
// different — the indent, and putting `touch-action` back, because a row here
// is never carried and this list must still scroll under a finger.
function entryRow(opts) {
  const row = document.createElement("div");
  row.className = "lay-item lc-row" + (opts.tab ? " lc-kid" : "") +
    (opts.off ? " lc-off" : "");
  const main = document.createElement("button");
  main.type = "button";
  main.className = "lay-item-main" + (opts.selected ? " sel" : "");
  // THE ICON BELONGS TO THE WINDOW, IN BOTH LISTS (owner 2026-08-09, task
  // 168). It used to be shown for the wrong one of the two: a tab wore its
  // PARENT's app icon among the chosen slots and no icon at all in the list
  // below — the same tab drawn two different ways, one of them claiming to be
  // an app. A tab is marked by the indent now, and by nothing else.
  if (opts.icon) {
    const img = document.createElement("img");
    img.src = opts.icon;
    img.alt = "";
    main.appendChild(img);
  }
  const name = document.createElement("span");
  name.textContent = opts.label;
  main.appendChild(name);
  if (opts.note) {
    const note = document.createElement("small");
    note.className = "lc-note";
    note.textContent = opts.note;
    main.appendChild(note);
  }
  keepFocus(main, opts.onTap);
  row.appendChild(main);
  return row;
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
  // The panel may never STAND in a state it would not offer (owner
  // 2026-08-09, task 166). The list arrives after the shape row has already
  // been drawn once, and a window can close while the panel is open, so the
  // chosen count is stepped down to the biggest shape the desktop can still
  // fill — the alternative is a Create button that can never be reached.
  const avail = availableMembers();
  if (avail !== null && c.mode === "grid" && GRID_CELLS[c.grid] > avail) {
    c.grid = avail >= 3 ? "3-top" : avail >= 2 ? "2" : null;
    c.mode = c.grid ? "grid" : "solo";
    c.slots = c.slots.slice(0, cellsNeeded());
  }
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  // `card-columns` — a MEASURED decision, not the inheritance it used to be
  // (owner width question 2026-08-09, task 172). This is the tallest panel
  // the phone has, and it is the panel the all-landscape reflow was cut for
  // this morning; one column does not fit it in EITHER landscape size (630 px
  // of content in a 377 px card at 915x412, 749 px in 734 px on a 1280x800
  // tablet), so taking the columns away here trades a scrollbar for names
  // nobody asked to lose — BUG A, with 155 px and 520 px of width standing
  // idle beside it. Its rows carry no trailing controls, so two columns still
  // give the name 319 px of a 347 px row: 48 of a 62-character VS Code title,
  // against the layout list's 12. See the rule in client/panels.css.
  card.className = "lay-card card-columns";

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
    row.className = "lc-rows";
    // THE TITLE IS THE CONTENT, AND CONTENT IS NEVER CUT (owner 2026-08-06:
    // the chosen chip cut the title at 30 CHARACTERS, in JS, before the DOM
    // ever saw the string — so `scrollWidth === clientWidth` and the phone
    // audit's clip test could not fire, which is how three rounds of PASS sat
    // over a defect two people had pointed at).
    //
    // The JS cut is still gone and must never come back — that half stands.
    // What changed on 2026-08-09 (task 163, then 168) is the treatment after
    // it: these are ROWS now, and rows of one kin group are the same size,
    // one line each, CUT by CSS — "the first two words, as many as fit — and
    // three dots". The cut is in the stylesheet, where the audit can see the
    // element overflow and fail on it; the full title still stands one step
    // away in the Name field below, which is a wrapping textarea for exactly
    // this reason.
    //
    // A tab is INDENTED here too (task 168 — "in both lists"). Its parent
    // window is never a row beside it, because a window and its own tab can
    // no longer be chosen together (task 167); the indent still says the
    // thing that matters at a glance — this member is a tab, not a whole
    // window — and the slot ORDER is left exactly as chosen, since slot 1
    // names the layout and every slot after it is a cell of the grid.
    c.slots.forEach((s, i) => row.appendChild(entryRow({
      label: s.title,
      icon: s.tab ? null : s.icon,
      tab: !!s.tab,
      selected: true,
      onTap: () => { c.slots.splice(i, 1); renderCreationPanel(); },
    })));
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
  //
  // AND THE CHOICE IS CAPPED BY WHAT CAN FILL IT (owner 2026-08-09, task
  // 166). A shape that cannot be filled is not an option, so it is not drawn:
  // an offer he cannot complete costs him the whole flow — pick, pick, and
  // then a Create button that does nothing.
  [["2", "2"], ["3-top", "3"], ["4", "4"]]
    .filter(([g]) => avail === null || GRID_CELLS[g] <= avail)
    .forEach(([g, label]) =>
      modeRow.appendChild(shapeChip(
        gridSketch(c.mode === "grid" && GRID_CELLS[c.grid] === GRID_CELLS[g] ? c.grid : g, c.orient),
        label, c.mode === "grid" && GRID_CELLS[c.grid] === GRID_CELLS[g], () => {
          c.mode = "grid";
          c.grid = g;
          c.slots = c.slots.slice(0, GRID_CELLS[g]);
          renderCreationPanel();
        })));
  card.appendChild(modeRow);
  // …and the absence is EXPLAINED. A row that silently holds fewer chips than
  // last time reads as a bug; the number is the same one the cap is made of.
  if (avail !== null && avail < 4) {
    const capLbl = document.createElement("p");
    capLbl.className = "lay-sub";
    capLbl.textContent = avail <= 1
      ? "Only one window is open on the PC — a grid needs at least two."
      : `Only ${avail} windows and tabs are open on the PC — a bigger grid ` +
        "needs more of them.";
    card.appendChild(capLbl);
  }

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
    // The header carries the SAME number the cap is made of — what is on the
    // PC and what can actually go in a layout are different quantities (a
    // three-tab window is four rows and three members), and the panel says
    // the one the choice above is limited by.
    hint.textContent = avail === null
      ? "Windows and tabs on the PC:"
      : `Windows and tabs on the PC — ${avail} can go in a layout:`;
    card.appendChild(hint);
    // A minimized window enumerates NO tabs (Windows reports it as having no
    // size at all), so the list would silently show fewer rows for it than it
    // will after a restore. It says so on the row and here (owner 2026-08-09,
    // task 167) — a list that quietly changes shape is what this replaces.
    if (c.entries.some((e) => e.tabs_hidden)) {
      const note = document.createElement("p");
      note.className = "lay-sub";
      note.textContent = "A minimized window cannot show its tabs — restore " +
        "it on the PC to pick them.";
      card.appendChild(note);
    }
    const list = document.createElement("div");
    list.className = "lc-rows lc-scroll";
    c.entries.forEach((e) => {
      const slot = slotFromEntry(e);
      const idx = c.slots.findIndex((s) => sameSlot(s, slot));
      const off = idx < 0 && ownTabConflict(slot);
      list.appendChild(entryRow({
        // The title is the only thing that tells two windows of one app
        // apart, so it is never cut in JS. The "↳ " prefix that used to be
        // glued in front of a tab's name is gone (owner 2026-08-09, task
        // 168): the indent says it, and says it better.
        label: e.title,
        icon: e.kind === "window" ? e.icon : null,
        tab: e.kind === "tab",
        note: e.tabs_hidden ? "minimized" : null,
        selected: idx >= 0,
        off,
        onTap: () => {
          if (idx >= 0) c.slots.splice(idx, 1);        // tap again = deselect
          else if (off) {
            // Refused, and NAMED. Silently ignoring the tap would read as the
            // dead Create button this round exists to remove.
            showToast("Pick either the window or its tabs — not both");
            return;
          } else if (c.slots.length < cellsNeeded()) c.slots.push(slot);
          else c.slots[c.slots.length - 1] = slot;     // full = replace last
          renderCreationPanel();
        },
      }));
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
  // A BUTTON THAT DOES NOTHING MUST NOT LOOK LIKE A BUTTON THAT WORKS (owner
  // report 2026-08-09, task 166 — this is the half he actually FEELS). A
  // not-ready Create carried no disabled state, no dimming and no word: it
  // looked live and swallowed the tap, so the panel simply seemed broken.
  // Both halves now, because either alone still leaves a question: it is
  // visibly unavailable, AND it says what is missing when tapped. It stays
  // tappable on purpose — a truly disabled button cannot answer, and "why is
  // nothing happening" is the whole complaint.
  const ready = c.slots.length === cellsNeeded();
  const missing = cellsNeeded() - c.slots.length;
  const create = layChip("Create", ready, () => {
    if (!ready) {
      showToast(missing === 1 ? "Pick one more window first"
                              : `Pick ${missing} more windows first`);
      return;
    }
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
  });
  if (!ready) {
    create.classList.add("lc-off");
    create.setAttribute("aria-disabled", "true");
  }
  actions.appendChild(create);
  card.appendChild(actions);
  layPanel.appendChild(card);
}
