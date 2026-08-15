// Changing an existing layout: the per-layout ⚙ SHEET and every panel it
// opens — the name, the aspect ratio (with its Move handle), the orientation
// and the arrangement.
//
// WHY IT EXISTS (owner 2026-08-09, task 175). Every act on a layout that
// already exists kept arriving as its own icon on the list's row: a rename
// pencil, an aspect chip, then the drawn shape badge, and task 165 was about
// to add a fourth. His instruction was to put all of it under one common
// settings icon instead of one icon per thing —
// "sve to treba ubaciti pod neku zajedničku settings ikonicu" — lang-ok: owner quote
// — and the portrait list had been honestly graded 6/10 for exactly that
// crowding. So the row keeps only what it can say at a GLANCE (which app,
// what shape) plus the ⚙, and everything else lives behind one door.
//
// It is also where the layout's ORIENTATION finally became changeable (his
// second half of the same task): a layout built portrait could only be turned
// landscape by deleting it and making it again. It rides `layout_grid
// {index, grid, orient}` — the message the rename card used for a three's
// arrangement since 2026-08-07 — so the server needed nothing new: `set_grid`
// stores it, marks the layout for re-placement, and the focus that follows
// re-places the windows and re-locks the phone's rotation off the fresh
// `layout_state`.
//
// Split out of layouts.js the same day, when that file crossed THE STRUCTURE
// LAW's 1,000 lines. The seam is a real one and it is the same one
// layout-create.js was cut on: layouts.js is what you use to LIVE with the
// layouts that exist (the bar, the list, the drag, the ✕ and the membership
// acts), layout-create.js MAKES one, and this file CHANGES one's properties.
//
// Loads immediately AFTER layouts.js and uses its panel vocabulary
// (`layPanel`, `closeLayoutPanel`, `layChip`, `layRow`, `nameField`,
// `openLayoutPicker`, `openMemberPanel`), `svg`/`keepFocus`/`showToast` from
// controls.js, `send`/`layouts` from state.js, the drawings from grids.js /
// grid-icons.js, and `HOLD_DRAG_SLOP` from layouts.js AT LOAD (the Move
// handle's tap slop is derived from it — one digitizer, one number).
// See client/__about/layout-settings.md.
"use strict";

// --- The ⚙ sheet ----------------------------------------------------------
// One card per layout, and the shape of it follows what the layout IS: a solo
// window has no arrangement to choose and no member to throw out, so neither
// is drawn — a control that cannot act is a promise the panel cannot keep
// (the same rule that makes a solo row's shape badge a plain <span>).
//
// TWO KINDS OF CONTROL, AND THE DIFFERENCE IS DELIBERATE. Rename, Aspect
// ratio and Take one window out are DOORS: they open the panel that owns that
// act, with its own Apply. Orientation and Arrangement are the act itself —
// one tap sends it, closes the sheet and raises the loading cube, because
// they are single-choice pickers and the owner's rule for those is that
// picking IS the command (2026-08-05 — lang-ok: owner quote)
// "korisnik odabere a program automatski odradi". A sheet that mixed pending
// state with doors would need an Apply that some of its rows ignore.
function openLayoutSettings(index) {
  const lay = layouts[index];
  if (!lay) return;
  const grid = gridOf(lay.grid);
  const members = lay.members || 1;
  const orient = lay.orient === "portrait" ? "portrait" : "landscape";
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  // `card-columns` — MEASURED, like every other card that answers this
  // question (client/panels.css, task 172). This is the "panel of many SHORT
  // items" side of that rule and not the layout list's side: its rows carry
  // fixed LABELS ("Rename", "Aspect ratio"), not window titles, so halving
  // the row costs nothing readable — and it genuinely needs the height. In
  // one column the fullest sheet (a three: three rows, two orientation chips
  // and four arrangement chips) is 121 px taller than the 335 px a 915x412
  // phone allows, which is BUG A with 155 px of width standing idle beside
  // the scrollbar. Two columns fit it whole. Measured, not reasoned about.
  card.className = "lay-card card-columns";
  const h = document.createElement("h2");
  h.textContent = "Layout settings";
  const sub = document.createElement("p");
  // WHICH layout this is — the one long string on the card, so it takes the
  // list's own treatment (task 163): ONE line, cut by CSS. The full name is
  // one tap away in the Rename card right below it, whose field wraps it,
  // which is exactly the argument the list row is elided under.
  sub.className = "lay-sub lay-name-line";
  sub.textContent = lay.name;
  card.append(h, sub);

  // A menu row is the list's own row markup (`layRow`), not a second row
  // style invented here — the ellipsis, the badge sizing and the kin rule are
  // written once, in layouts.css. `lay-menu` only puts `touch-action` back:
  // a row of the LAYOUT LIST is a drag surface and refuses the browser's pan,
  // while nothing here is ever carried and this card must still scroll.
  const menuRow = (icon, label, note, onTap) => {
    const row = layRow(label, { draw: svg(icon) }, false, onTap);
    row.classList.add("lay-menu");
    if (note) {
      const small = document.createElement("small");
      small.className = "lay-note";
      small.textContent = note;
      row.querySelector(".lay-item-main").appendChild(small);
    }
    card.appendChild(row);
    return row;
  };

  menuRow("edit", "Rename", null, () => openRenamePanel(index));
  // The VALUE beside the label: the row used to carry this chip, so losing the
  // chip must not lose the fact. `ratioLabel` is the same rendering it used.
  menuRow("aspect", "Aspect ratio", ratioLabel(lay), () => openAspectPanel(index));
  if (members > 1) {
    menuRow("grid", "Take one window out", `${members} windows`,
            () => openMemberPanel(index));
    // SPLIT a grid into as many solo layouts as it has members (task 197a) —
    // never offered on a solo, which has nothing to split.
    menuRow("splitwin", "Split into windows", `${members} separate layouts`,
            () => sendSplit(index));
  }
  // ADD a window — solo→2, 2→3, 3→4 (task 195, owner: "if there is room ...
  // unless it already has four"). A button that cannot act is a promise the
  // panel cannot keep (the same rule that hides Take one window out on a
  // solo), so it is simply absent once the layout is already full.
  if (members < 4) {
    menuRow("addwin", "Add a window", null, () => openAddMemberPanel(index));
  }

  // ORIENTATION — the half of this task the owner could not do at all before
  // (a layout built portrait had to be deleted and made again). A picture per
  // choice, never the words alone: the same rule his grid sheet was delivered
  // under (2026-08-07), and `orientChips` draws the layout's OWN shape once
  // per orientation so the choice is "which of these looks right".
  const oLbl = document.createElement("p");
  oLbl.className = "lay-sub";
  oLbl.textContent = "Orientation:";
  const oRow = document.createElement("div");
  oRow.className = "lay-row";
  orientChips((o) => grid ? gridSketch(grid, o) : soloSketch(o), orient,
              (o) => sendLayoutShape(index, grid, o))
    .forEach((chip) => oRow.appendChild(chip));
  card.append(oLbl, oRow);

  // ARRANGEMENT — offered ONLY where a choice exists. `gridIconChoices` is the
  // one place that asymmetry is written down (a 2 and a 4 have exactly one
  // arrangement each, a 3 has four — his sheet, UV/grid_variations.png), and
  // it is asked rather than re-derived so no panel can offer a choice that is
  // not real.
  const choices = gridIconChoices(members, lay.grid);
  if (choices.length) {
    const gLbl = document.createElement("p");
    gLbl.className = "lay-sub";
    gLbl.textContent = "Where does the single window go?";
    const gRow = document.createElement("div");
    gRow.className = "lay-row";
    choices.forEach((g) => gRow.appendChild(gridChip(
      g, orient, g === grid, () => sendLayoutShape(index, g, orient))));
    card.append(gLbl, gRow);
  }

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Back", false, openLayoutPicker));
  card.appendChild(actions);
  layPanel.appendChild(card);
}

// The one sender for both pickers above. `layout_grid` re-places real windows
// on the PC — the server marks the layout for a fresh arrangement and the
// focus that follows carries it out — so the loading cube covers it exactly
// as a reshape does, and the phone's rotation lock follows the `layout_state`
// that comes back (`applyOrientationLock`).
//
// A grid name is sent even when nothing about the arrangement changed: the
// server's `set_grid` only adopts a shape of the RIGHT SIZE and ignores
// anything else, so a solo layout's empty string changes nothing while its
// orientation still lands. One message, one path.
function sendLayoutShape(index, grid, orient) {
  const lay = layouts[index];
  if (!lay) return;
  if (grid === gridOf(lay.grid) && orient === lay.orient) {
    closeLayoutPanel();     // he tapped what is already true — no PC work
    return;
  }
  send({ type: "layout_grid", index, grid: grid || "", orient });
  closeLayoutPanel();
  // LOADING: FULL — re-placing every member into a new arrangement
  showLayLoading("Reshaping the layout…", LOADING_FULL);
}

// --- SPLIT a grid into solo layouts (task 197a) ----------------------------
// One tap acts (owner rule 2026-08-05, "korisnik odabere a program automatski
// odradi") — there is nothing to choose here, unlike Add/Eject below, which
// both need him to point at a window or a cell first.
function sendSplit(index) {
  closeLayoutPanel();
  send({ type: "layout_split", index });
  // LOADING: FULL — the grid comes apart into solo layouts — windows move
  showLayLoading("Splitting the layout…", LOADING_FULL);
}

// --- ADD A WINDOW (task 195) ------------------------------------------------
// `addingTo` is this file's OWN piece of state, exactly the pattern
// `aspecting` already sets beside it: one flow in flight, forgotten by
// `forgetLayoutSettings` when the panel closes under it. The server's answer
// arrives as an ordinary `layout_offer` tagged with `add_to`, routed here by
// connection.js (never through layout-create.js's `creating` session — this
// is not a fresh layout, so it must not share that file's state machine).
let addingTo = null; // {index, hwnd, tab, x, y, grid} | null

function openAddMemberPanel(index) {
  const lay = layouts[index];
  if (!lay || (lay.members || 1) >= 4) return;
  addingTo = { index };
  closeLayoutPanel();
  // LOADING: CUBE — a pure enumeration — nothing on the PC moves
  showLayLoading("Collecting windows and tabs…", LOADING_CUBE);
  send({ type: "layout_member_list", index });
}

// Called from connection.js's layout_offer dispatch when the reply carries
// `add_to` — the same enumeration `layout_list` uses (windows already in ANY
// layout, this one included, are already excluded server-side), drawn with
// the creation panel's own visual language: real icons, tabs indented under
// their window. Rows are built locally rather than reaching into
// layout-create.js's `entryRow` — that file owns the fresh-creation wizard's
// own state and this flow must not couple to it.
function renderAddMemberPanel(msg) {
  hideLayLoading();
  if (!addingTo || addingTo.index !== msg.add_to) return; // a stale reply
  const index = addingTo.index;
  const lay = layouts[index];
  if (!lay) { addingTo = null; return; }
  const entries = msg.entries || [];
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card card-columns";
  const h = document.createElement("h2");
  h.textContent = "Add a window";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = `${lay.name} — tap a window or tab to add it.`;
  card.append(h, sub);

  if (!entries.length) {
    const none = document.createElement("p");
    none.className = "lay-sub";
    none.textContent = "Nothing else is open on the PC right now.";
    card.appendChild(none);
  }
  const list = document.createElement("div");
  list.className = "lc-rows lc-scroll";
  entries.forEach((e) => {
    const row = document.createElement("div");
    row.className = "lay-item lc-row" + (e.kind === "tab" ? " lc-kid" : "");
    const main = document.createElement("button");
    main.type = "button";
    main.className = "lay-item-main";
    if (e.kind === "window" && e.icon) {
      const img = document.createElement("img");
      img.src = e.icon;
      img.alt = "";
      main.appendChild(img);
    }
    const name = document.createElement("span");
    name.textContent = e.title;
    main.appendChild(name);
    if (e.tabs_hidden) {
      const note = document.createElement("small");
      note.className = "lc-note";
      note.textContent = "minimized";
      main.appendChild(note);
    }
    keepRowTap(main, () => {
      addingTo.hwnd = e.hwnd;
      addingTo.tab = e.tab || null;
      addingTo.x = e.x;
      addingTo.y = e.y;
      renderAddMemberGrid();
    });
    row.appendChild(main);
    list.appendChild(row);
  });
  card.appendChild(list);

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, () => {
    addingTo = null;
    openLayoutSettings(index);
  }));
  card.appendChild(actions);
  layPanel.appendChild(card);
}

// Step 2 of Add a window — offered ONLY when the RESULT has a real choice (a
// solo/2 growing to a three has four arrangements; growing to a two or a four
// has exactly one, so nothing is asked and the add ships straight away). The
// same asymmetry `openMemberPanel`'s shrink path reads off `gridIconChoices`.
function renderAddMemberGrid() {
  const index = addingTo.index;
  const lay = layouts[index];
  if (!lay) { addingTo = null; return; }
  const resultCount = (lay.members || 1) + 1;
  const choices = gridIconChoices(resultCount, null);
  if (!choices.length) {
    sendAddMember();
    return;
  }
  addingTo.grid = choices[0];
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card card-columns";
  const h = document.createElement("h2");
  h.textContent = "Add a window";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Where does the single window go?";
  card.append(h, sub);
  const row = document.createElement("div");
  row.className = "lay-row";
  choices.forEach((g) => row.appendChild(gridChip(
    g, lay.orient, g === addingTo.grid,
    () => { addingTo.grid = g; renderAddMemberGrid(); })));
  card.appendChild(row);
  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Back", false, () => {
    send({ type: "layout_member_list", index });
    // LOADING: CUBE — a pure enumeration — nothing on the PC moves
    showLayLoading("Collecting windows and tabs…", LOADING_CUBE);
  }));
  actions.appendChild(layChip("Add", true, sendAddMember));
  card.appendChild(actions);
  layPanel.appendChild(card);
}

function sendAddMember() {
  const a = addingTo;
  if (!a || typeof a.hwnd !== "number") return;
  const msg = { type: "layout_member_add", index: a.index, hwnd: a.hwnd,
                tab: a.tab || null, x: a.x, y: a.y };
  if (a.grid) msg.grid = a.grid;
  send(msg);
  addingTo = null;
  closeLayoutPanel();
  // LOADING: FULL — adding a member re-places the whole layout
  showLayLoading("Arranging the windows…", LOADING_FULL);
}

function ratioLabel(lay) {
  if (!lay.ratio) return "Screen";
  // The stored ratio is FINE-GRAINED (see the aspect panel: w is sent on a
  // 1000-scale), so it is labelled by its closest small pair, not printed raw.
  const [n, d] = ratioPair(lay.ratio[0] / lay.ratio[1], 40);
  return `${n}:${d}`;
}

// Renaming an existing layout (owner 2026-08-05). Nothing on the PC moves —
// only what this layout is CALLED in the bar and the list changes.
//
// IT RENAMES, AND IT DOES NOTHING ELSE (owner 2026-08-09, task 175). Between
// 2026-08-07 and today this card also carried the layout's SHAPE — the
// orientation chips and, for a three, which edge its single window takes —
// because the row had no other door to put them behind. It has one now: the
// ⚙ sheet above owns every act on an existing layout, and the shape is one of
// them. Two copies of that chooser would have been two things to keep in
// step, which is the class of bug this project keeps paying for, so it moved
// rather than being duplicated.
function openRenamePanel(index) {
  const lay = layouts[index];
  if (!lay) return;
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card card-columns";
  const h = document.createElement("h2");
  h.textContent = "Layout name";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Call it whatever you like — the window's title is only the default.";
  const field = nameField(lay.name || "");
  card.append(h, sub, field);

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  // Back ONE step — to the sheet this card was opened from, never straight
  // out to the list: the chain is list → ⚙ sheet → this card, and a Cancel
  // that skipped a rung would strand him wherever he started.
  actions.appendChild(layChip("Cancel", false, () => openLayoutSettings(index)));
  actions.appendChild(layChip("Save", true, () => {
    const name = field.value.trim();
    if (name && name !== lay.name) {
      // OPTIMISTIC (owner report, task 199: he had to re-open Rename before
      // the new name showed). `lay` IS `layouts[index]` — the very object the
      // bar (`updateLayoutBar`), the list row (`layRow(lay.name, …)`) and
      // this sheet's own header (`sub.textContent = lay.name` above) all read
      // — so mutating it here, before the round trip, is what makes every one
      // of them correct the instant the sheet closes rather than on whichever
      // later `layout_state` happens to land. Renaming moves nothing on the
      // PC, unlike the aspect/grid Applies right above it in this same file
      // (`sendLayoutShape`), which get a real loading cube while the windows
      // visibly move on the stream — a rename has no such tell, so with
      // nothing local to show, the round trip's own latency read as "did
      // nothing" the moment Save was tapped. The server's own echoed
      // `layout_state` still arrives a moment later and reconciles with the
      // identical name — a no-op, and the one thing that can ever overwrite
      // this if the two ever disagree.
      lay.name = name;
      updateLayoutBar(); // reads layouts[layoutActive] synchronously — may be a no-op
      send({ type: "layout_rename", index, name });
    }
    closeLayoutPanel();
  }));
  card.appendChild(actions);
  layPanel.appendChild(card);
  field.focus();
  field.select();
}

// The phone's own side ratio as small whole numbers: raw pixels reduce to
// unusable pairs (412x892 → 103:223), so this is the best approximation with
// a denominator of at most 40 — 412x892 → 6:13, 1080x2400 → 9:20.
function ratioPair(value, maxDen) {
  let best = [1, 1];
  let bestErr = Infinity;
  for (let d = 1; d <= maxDen; d++) {
    const n = Math.max(1, Math.round(value * d));
    const err = Math.abs(value - n / d);
    if (err < bestErr - 1e-9) {
      bestErr = err;
      best = [n, d];
    }
  }
  return best;
}

function devicePair(orient) {
  const s = Math.min(window.screen.width, window.screen.height);
  const l = Math.max(window.screen.width, window.screen.height);
  const [n, d] = ratioPair(s / l, 40); // short : long
  return orient === "portrait" ? [n, d] : [d, n];
}

// The panel works on a CONTINUOUS ratio, not on whole units of the device pair
// (owner 2026-08-04): the pair is a coarse approximation of the screen (a
// tablet reduces to 7:5), so stepping it by one unit jumped in ~14% chunks and
// 8:5 was simply unreachable. The state is the plain number W/H; the W:H
// fields are only a readable rendering of it, and both are freely typeable.
// The ONE rule survives: the region may only shrink INWARD from the free axis
// — wide keeps the full height (top/bottom edges pinned), portrait keeps the
// full width (left/right edges pinned).
const ASP_MIN_FRAC = 0.15; // never let the region collapse to a slit
const ASP_SCALE = 1000;    // ratios are sent as round(a * 1000) : 1000

let aspecting = null; // {index, portrait, devA, a, pos, els}

// `closeLayoutPanel` (layouts.js) calls this: the panel is ONE overlay with
// several contents, and only this file knows what state its own content left
// behind. A function rather than layouts.js reaching into `aspecting`, so the
// aspect panel's state never has a second owner.
function forgetLayoutSettings() {
  aspecting = null;
  addingTo = null;   // task 195's add-a-window flow is the panel's other guest
}

function openAspectPanel(index) {
  const lay = layouts[index];
  if (!lay) return;
  const portrait = lay.orient === "portrait";
  const dev = devicePair(lay.orient);
  const devA = dev[0] / dev[1];
  aspecting = { index, portrait, devA, a: devA,
                pos: typeof lay.pos === "number" ? lay.pos : 0.5 };
  if (lay.ratio && lay.ratio[1] > 0) aspecting.a = clampAspect(lay.ratio[0] / lay.ratio[1]);
  renderAspectPanel();
}

// Fraction of the free axis the region currently uses (1 = the whole screen).
function aspFrac(a) {
  const s = aspecting;
  return s.portrait ? s.devA / a : a / s.devA;
}

function clampAspect(a) {
  const s = aspecting;
  if (!Number.isFinite(a) || a <= 0) return s.devA;
  const f = Math.min(1, Math.max(ASP_MIN_FRAC, aspFrac(a)));
  return s.portrait ? s.devA / f : s.devA * f;
}

function renderAspectPanel() {
  const a = aspecting;
  const lay = layouts[a.index];
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card card-columns";

  const h = document.createElement("h2");
  h.textContent = "Aspect ratio";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = `${lay ? lay.name : "Layout"} — ${a.portrait ? "portrait" : "landscape"}: ` +
    (a.portrait ? "full width, free height" : "full height, free width");
  card.append(h, sub);

  // W : H — BOTH are typeable now (owner 2026-08-04: "8:5" must be reachable
  // by typing it). Whatever pair is typed becomes the ratio, clamped by the
  // one rule; the fields are only refreshed while they are not being edited.
  const fields = document.createElement("div");
  fields.className = "asp-fields";
  const inW = document.createElement("input");
  const inH = document.createElement("input");
  [inW, inH].forEach((el) => {
    el.type = "number";
    el.inputMode = "numeric";
    el.min = "1";
    el.addEventListener("input", () => {
      const w = parseFloat(inW.value);
      const h = parseFloat(inH.value);
      if (!(w > 0) || !(h > 0)) return;
      a.a = clampAspect(w / h);
      a.typing = el;
      updateAspectPreview();
      a.typing = null;
    });
    // Leaving the field snaps its text back onto the (possibly clamped) value.
    el.addEventListener("blur", updateAspectPreview);
  });
  const wLbl = document.createElement("b");
  wLbl.textContent = "W";
  const colon = document.createElement("b");
  colon.textContent = ":";
  const hLbl = document.createElement("b");
  hLbl.textContent = "H";
  fields.append(wLbl, inW, colon, hLbl, inH);
  card.appendChild(fields);

  // Preview: dashed phone screen, solid region inside it (owner reference —
  // the Prompt Painter aspect widget).
  const prev = document.createElement("div");
  prev.className = "asp-prev";
  const screenBox = document.createElement("div");
  screenBox.className = "asp-screen";
  screenBox.style.aspectRatio = `${a.devA} / 1`;
  if (a.portrait) screenBox.style.height = "100%";
  else screenBox.style.width = "100%";
  const region = document.createElement("div");
  region.className = "asp-region";
  ["t", "b", "l", "r"].forEach((side) => {
    const dot = document.createElement("i");
    const isFree = a.portrait ? (side === "t" || side === "b") : (side === "l" || side === "r");
    dot.className = `asp-h ${side}${isFree ? " free" : ""}`;
    region.appendChild(dot);
  });
  // The Move handle (owner 2026-08-05): dragging it slides the shrunken
  // region along the free axis — it no longer has to sit centered; a
  // double-tap re-centers it. Everything OUTSIDE the handle still resizes.
  const move = document.createElement("div");
  move.className = "asp-move";
  move.innerHTML = svg("move");
  dragMove(move, screenBox);
  region.appendChild(move);
  screenBox.appendChild(region);
  // The WHOLE preview drags, not just the two 18px dots — on a tablet those
  // dots were nearly unhittable, which is what read as "barely responsive".
  dragAspect(screenBox);
  prev.appendChild(screenBox);
  card.appendChild(prev);

  const value = document.createElement("div");
  value.className = "asp-value";
  card.appendChild(value);

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Screen", false, () => {
    a.a = a.devA;
    updateAspectPreview();
  }));
  actions.appendChild(layChip("Cancel", false, () => {
    const index = a.index;
    aspecting = null;
    openLayoutSettings(index); // back one step — the ⚙ sheet it came from
  }));
  actions.appendChild(layChip("Apply", true, () => {
    // The full screen is "no override" (0/0); anything else goes as a fine
    // 1000-scale pair, so the server region is exactly what the preview showed.
    // `pos` (0–1000, 500 = centered) is the Move handle's position along the
    // free axis (owner 2026-08-05).
    const full = aspFrac(a.a) > 0.999;
    send({
      type: "layout_aspect", index: a.index,
      w: full ? 0 : Math.round(a.a * ASP_SCALE), h: full ? 0 : ASP_SCALE,
      pos: full ? 500 : Math.round(a.pos * 1000),
    });
    aspecting = null;
    closeLayoutPanel();
    // LOADING: FULL — re-placing every member into a new arrangement
    showLayLoading("Reshaping the layout…", LOADING_FULL);
  }));
  card.appendChild(actions);
  layPanel.appendChild(card);

  a.els = { inW, inH, region, value };
  updateAspectPreview();
}

function updateAspectPreview() {
  const a = aspecting;
  if (!a || !a.els) return;
  const [n, d] = ratioPair(a.a, 40);
  if (a.typing !== a.els.inW) a.els.inW.value = n;
  if (a.typing !== a.els.inH) a.els.inH.value = d;
  // The region sits at fraction `pos` of the free-axis slack (the Move
  // handle) — positioned explicitly, replacing the old centered transform.
  const frac = aspFrac(a.a);
  const pct = `${frac * 100}%`;
  const off = `${a.pos * (1 - frac) * 100}%`;
  const st = a.els.region.style;
  st.transform = "none";
  st.width = a.portrait ? "100%" : pct;
  st.height = a.portrait ? pct : "100%";
  st.left = a.portrait ? "0" : off;
  st.top = a.portrait ? off : "0";
  a.els.value.textContent = `${a.a.toFixed(3)}:1   (${n}:${d})`;
}

// Dragging anywhere in the preview resizes the region symmetrically around the
// centre — the region is always centred on the monitor, so a drag can only
// ever pull it IN from both sides at once. The motion is continuous: the ratio
// follows the finger pixel by pixel, with no whole-unit steps to snap to.
function dragAspect(screenBox) {
  const apply = (e) => {
    const a = aspecting;
    if (!a) return; // the panel closed under a captured pointer
    const r = screenBox.getBoundingClientRect();
    const raw = a.portrait
      ? Math.abs(e.clientY - (r.top + r.height / 2)) * 2 / r.height
      : Math.abs(e.clientX - (r.left + r.width / 2)) * 2 / r.width;
    const frac = Math.min(1, Math.max(ASP_MIN_FRAC, raw)); // never divide by 0
    a.a = a.portrait ? a.devA / frac : a.devA * frac;
    updateAspectPreview();
  };
  screenBox.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    screenBox.setPointerCapture(e.pointerId);
    apply(e);
  });
  screenBox.addEventListener("pointermove", (e) => {
    if (screenBox.hasPointerCapture(e.pointerId)) apply(e);
  });
}

// The Move handle's own drag (owner 2026-08-05): slides the region along the
// free axis; a double-tap re-centers. stopPropagation keeps the screen box's
// resize drag out of the gesture.
//
// A DOUBLE TAP IS TWO TAPS, NOT TWO TOUCHES (owner 2026-08-07 — lang-ok: owner quote)
// "smanjio sam dimenzije layout-a i pokušao da ga privučem dole ali on je i
// dalje na sredini". The re-centre used to fire from `pointerdown` on any
// contact within 350 ms of the previous one — so the very common
// tap-then-drag was read as a double tap: it put the region back in the
// MIDDLE and returned without capturing the pointer, killing the drag that
// was just starting. Both halves of his sentence, from one line. A tap is now
// only a tap once it has ENDED, quickly and without travel, and a press is
// always a press.
// -Infinity, never 0: `0` is a real `performance.now()` reading — it means
// "a tap at page load" — so every tap in the page's first 350 ms counted as
// the SECOND tap of a double tap and re-centred the region. The audit caught
// this in landscape, where the panel opens sooner after load than the 350 ms
// window (portrait was past it at 623 ms and passed, which is exactly how a
// timing bug survives a green suite).
// AND THE LESSON OF THIS BLOCK WAS AVAILABLE TO THE NEXT GESTURE WRITTEN THAT
// AFTERNOON, AND WENT UNUSED (task 162, 2026-08-09): the layout list's hold
// shipped the same day with NO tolerance at all, so it never armed on a real
// finger. The slop is one number now — `HOLD_DRAG_SLOP` in client/layouts.js,
// where the hold reads it — because one digitizer asking one question ("did
// this contact stay put?") must not be answered by two constants that can
// drift apart. It is read AT LOAD, which is why this file loads after that one.
let moveTapAt = -Infinity;
const MOVE_TAP_MS = 350;   // two taps closer than this = re-centre
const MOVE_TAP_SLOP = HOLD_DRAG_SLOP;  // px: past this the contact was a drag
function dragMove(handle, screenBox) {
  const apply = (e) => {
    const a = aspecting;
    if (!a) return;
    const r = screenBox.getBoundingClientRect();
    const frac = aspFrac(a.a);
    const freePx = (a.portrait ? r.height : r.width) * (1 - frac);
    if (freePx < 1) return; // full-size region — nowhere to go
    const finger = a.portrait ? e.clientY - r.top : e.clientX - r.left;
    const regionPx = (a.portrait ? r.height : r.width) * frac;
    a.pos = Math.min(1, Math.max(0, (finger - regionPx / 2) / freePx));
    updateAspectPreview();
  };
  let downAt = 0;
  let downX = 0;
  let downY = 0;
  handle.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    e.stopPropagation();
    // Every press captures and may drag. Nothing is decided here — deciding
    // at DOWN is what made a press into a re-centre.
    downAt = performance.now();
    downX = e.clientX;
    downY = e.clientY;
    handle.setPointerCapture(e.pointerId);
  });
  handle.addEventListener("pointermove", (e) => {
    if (handle.hasPointerCapture(e.pointerId)) apply(e);
  });
  const ended = (e) => {
    const now = performance.now();
    const moved = Math.hypot(e.clientX - downX, e.clientY - downY);
    // Only a contact that STAYED PUT and ended quickly was a tap; a drag
    // ends the gesture and arms nothing.
    if (moved > MOVE_TAP_SLOP || now - downAt > MOVE_TAP_MS) {
      moveTapAt = 0;
      return;
    }
    if (now - moveTapAt < MOVE_TAP_MS) {
      moveTapAt = 0;
      if (aspecting) {
        aspecting.pos = 0.5;   // double tap = back to the middle (owner 2026-08-05)
        updateAspectPreview();
      }
      return;
    }
    moveTapAt = now;
  };
  handle.addEventListener("pointerup", ended);
  // A tap Android steals at a screen edge never reaches `pointerup` — the
  // same rule the control buttons live by (CLAUDE.md constraint 9).
  handle.addEventListener("pointercancel", ended);
}
