// Settings → Wheel sets → one set's own editor: WHICH pool commands ride the
// D-pad and IN WHICH SLOT — the same job the desktop Controls editor does.
//
// ── WHY IT IS HERE AND NOT ONLY ON THE PC (owner 2026-08-04 18:27, re-raised
// as a ballot comment on 2026-08-11 — "jako davno sam rekao, toliko davno da
// je zabrinjavajuce sto jos niko to ne spominje", lang-ok: owner quote, the
// dated record of the request). His 2026-08-04 wheel spec gives the user the
// arrangement of a set's buttons in BOTH shapes — the cross and the portrait
// column — and then limits the PHONE's copy of that menu to not CREATING sets.
// Creating is what was withheld. Arranging never was, and arranging is the one
// part of this that can only honestly be judged with the device in the hand:
// which corner of the cross the thumb reaches, which button he keeps hitting
// by mistake. Sending him to the desk to answer a question the desk cannot see
// is what made this sit unbuilt for a week.
//
// ── WHAT IT MAY AND MAY NOT DO
// It edits a set's INTERIOR. It never touches the wheel's COMPOSITION — which
// sets ride is the picker's job and the cap of 8 is a law over that, untouched
// here — and it never edits a COMMAND. Built-in, app-aware and custom sets are
// all editable to exactly this depth: the owner picks from the pool, he does
// not rewrite it (his decision 2026-08-05; custom commands stay on the PC,
// where a keyboard and a chord recorder exist).
//
// Renaming a button is deliberately NOT here even though the desktop allows
// it: this page's typing goes through the invisible full-width capture
// textarea that feeds `key_text` to the PC (CLAUDE.md constraint 5), so a real
// text field in an overlay would be fighting the one element the whole input
// pipeline depends on holding focus. A rename is a desk job; an arrangement is
// not.
//
// ── WHERE IT SAVES
// NOT into SharedPreferences. Every other phone-side switch is per DEVICE on
// purpose (the tablet and the phone want different wheels), but a set's
// arrangement is the OWNER's, and he must find the same D-pad on the PC's
// Controls editor and on both devices. So it travels as `actions_update` to
// the PC, which validates it against the pool and writes the same actions.json
// the desktop editor writes, then re-broadcasts `actions` — the wheel changes
// under his finger without a reconnect (server/actions_api.py).
//
// Loaded after controls.js (activeButtons, btnId, padShape, keepFocus, svg,
// ICONS, paintSet) and after panels.js (ghostClickArmor); panels.js calls
// `openSetEditor` only at runtime.

"use strict";

const setEditorPanel = document.getElementById("set-editor-panel");
const setEditorOpened = { t: 0 };
ghostClickArmor(setEditorPanel, setEditorOpened);

const DPAD_SLOTS = 4;

// The four D-pad arms, in the order `renderGroup` lays them out: slot 0 is up,
// 1 left, 2 right, 3 down (client/controls.js -> POSITIONS). The preview below
// draws the same grid areas, so what he arranges here is literally the picture
// he will be looking at.
const SLOT_AREAS = ["up", "left", "right", "down"];

// The editing state, alive only while the card is open. `order` is over the
// SLOTS: order[slot] = index into `active`, exactly the shape actions.json
// stores and `renderGroup` reads.
let edit = null;

// What one pool command is CALLED on the phone — the same resolution
// `makeActionButton` performs, in the same precedence, so a row in this list
// and the button it becomes can never disagree. A built-in's shipped label is
// the fallback for a command the owner has never renamed.
function poolLabel(btn) {
  if (btn.label) return btn.label;
  const b = btn.action && BUILTINS[btn.action];
  if (b) return b.label;
  return btn.text || btn.chord || btn.key || btn.action || "?";
}

function poolIcon(btn) {
  if (btn.icon && ICONS[btn.icon]) return btn.icon;
  const b = btn.action && BUILTINS[btn.action];
  if (b && ICONS[b.icon]) return b.icon;
  return null;
}

// WHICH ORIENTATION'S ORDER IS BEING EDITED. The page already answers this for
// the D-pad itself (`padColumn()` — the SHAPE, which since task 177 is a
// choice and not the orientation), and the editor asks the identical question:
// arranging a column while looking at a cross is how an arrangement arrives
// scrambled into the four arms (the task 121 lesson, from the other side).
function editedOrderKey() {
  return padColumn() ? "order_port" : "order_land";
}

// The order as stored, or the identity when there is none / when it no longer
// fits the active list. Same acceptance test as `renderGroup`, so the editor
// opens showing what the D-pad is really drawing right now.
function storedOrder(set, key, n) {
  const raw = set[key];
  const ok = Array.isArray(raw) && raw.length === n &&
    [...raw].sort((a, b) => a - b).join() === [...Array(n).keys()].join();
  return ok ? [...raw] : [...Array(n).keys()];
}

function openSetEditor(set) {
  const pool = set.buttons || [];
  const active = activeButtons(set).map(btnId);
  edit = {
    set,
    pool,
    active,
    // Both orders are carried, and the one for the shape NOT on screen is kept
    // only as long as it still fits. When he changes WHICH buttons ride, both
    // reset to the identity — see `pickChanged`.
    order_land: storedOrder(set, "order_land", active.length),
    order_port: storedOrder(set, "order_port", active.length),
    swapFrom: null,
  };
  drawSetEditor();
}

function drawSetEditor() {
  setEditorPanel.innerHTML = "";
  const card = document.createElement("div");
  // `card-split` and never `card-columns`: a multicol card with a capped
  // height answers "I do not fit" by growing a column off the side of the
  // screen instead of scrolling (task 217, and the sets picker's own third
  // column before it). Header and Save stay put, `.sets-body` scrolls.
  card.className = "sets-card card-split";
  const column = padColumn();
  card.innerHTML = `<div class="sets-head"><h2>${edit.set.name}</h2>
    <span class="sets-sub sets-count">${edit.active.length} of ${DPAD_SLOTS} buttons</span></div>
    <p class="sets-sub">Pick which of this set's commands ride the controls, then
       tap two positions to swap them. You are arranging the
       ${column ? "upright column" : "D-pad cross"} — the shape this phone is
       showing now. New commands are made on the PC (Remote User window →
       Controls…).</p>`;

  const body = document.createElement("div");
  body.className = "sets-body";
  card.appendChild(body);

  body.appendChild(buildArrangement(column));
  body.appendChild(buildPool());

  const save = document.createElement("button");
  save.type = "button";
  save.className = "sets-done";
  save.textContent = "Save on the PC";
  keepFocus(save, saveSetEdit);
  card.appendChild(save);

  setEditorPanel.appendChild(card);
  setEditorPanel.hidden = false;
  setEditorOpened.t = performance.now();
}

// ── THE ARRANGEMENT, DRAWN AS THE THING IT IS ────────────────────────────────
// A DRAWING and never a list of words (owner's standing rule, stated for the
// grid chooser on 2026-08-05 and true of every position picker since): the
// cross is drawn as a cross and the column as a column, each cell holding the
// button that will really be there. Tap one cell, tap another, they swap —
// tap-to-swap rather than drag because drag-reorder on his device has failed
// three times (tasks 81 / 162 / 196) and a position picker that needs a
// working drag is a position picker he cannot use.
function buildArrangement(column) {
  const wrap = document.createElement("div");
  wrap.className = "se-arrange" + (column ? " se-column" : "");
  // The preview wears the set's own colour, like the group it previews — one
  // write, and the `colored` look needs nothing else (client/theme.js).
  paintSet(wrap, edit.set.name, "--glass-fill");
  const order = edit[editedOrderKey()];
  order.forEach((bi, slot) => {
    const id = edit.active[bi];
    const btn = edit.pool.find((b) => btnId(b) === id);
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = "se-slot" + (edit.swapFrom === slot ? " picked" : "");
    cell.dataset.slot = String(slot);
    cell.dataset.button = id;
    const icon = btn ? poolIcon(btn) : null;
    cell.innerHTML = (icon ? svg(icon) : "") +
      `<span>${btn ? poolLabel(btn) : "?"}</span>`;
    if (!column) cell.style.gridArea = SLOT_AREAS[slot];
    keepFocus(cell, () => tapSlot(slot));
    wrap.appendChild(cell);
  });
  return wrap;
}

// Tap one, tap the other. Tapping the same cell twice cancels — an armed
// position with no way back is a trap on a touch screen.
function tapSlot(slot) {
  const order = edit[editedOrderKey()];
  if (edit.swapFrom === null) {
    edit.swapFrom = slot;
  } else if (edit.swapFrom === slot) {
    edit.swapFrom = null;
  } else {
    const a = edit.swapFrom;
    [order[a], order[slot]] = [order[slot], order[a]];
    edit.swapFrom = null;
  }
  drawSetEditor();
}

// ── THE POOL ────────────────────────────────────────────────────────────────
// Every command the set HAS (owner 2026-08-05: `buttons` is a pool, `active`
// names the four that ride). A ticked row rides; the cap is the D-pad's four
// arms and a tick past it is refused with a sentence, never silently dropped —
// the wheel-cap law's own lesson, one level down.
function buildPool() {
  const list = document.createElement("div");
  list.className = "sets-list";
  edit.pool.forEach((btn) => {
    const id = btnId(btn);
    const row = document.createElement("label");
    row.className = "sets-row";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = edit.active.includes(id);
    cb.addEventListener("change", () => pickChanged(id, cb));
    const ic = document.createElement("span");
    ic.className = "sets-ic";
    ic.innerHTML = svg(poolIcon(btn) || "grid");
    row.append(cb, ic, document.createTextNode(poolLabel(btn)));
    list.appendChild(row);
  });
  return list;
}

function pickChanged(id, cb) {
  if (cb.checked) {
    if (edit.active.length >= DPAD_SLOTS) {
      cb.checked = false;
      showToast(`The controls hold ${DPAD_SLOTS} buttons — untick one first`);
      return;
    }
    edit.active.push(id);
  } else {
    if (edit.active.length <= 1) {
      cb.checked = true;
      showToast("A set needs at least one button");
      return;
    }
    edit.active = edit.active.filter((x) => x !== id);
  }
  // BOTH arrangements reset to the shipped order when the crew changes, and
  // the card says so above. The alternative — trying to preserve the position
  // of the survivors — has no honest answer for the button that just arrived,
  // and an order that half-survives is the kind of state that reads as the
  // panel doing something it was not asked to do.
  edit.order_land = [...Array(edit.active.length).keys()];
  edit.order_port = [...Array(edit.active.length).keys()];
  edit.swapFrom = null;
  drawSetEditor();
}

// ── SAVING ──────────────────────────────────────────────────────────────────
// One message, carrying ONLY the keys the PC will accept (server/actions_api.py
// -> PHONE_EDITABLE, itself a checked subset of the shipped-pool merge's
// owner-owned keys). Both orders ride: the one he arranged and the one that was
// reset with it, so the file never holds an arrangement of a different length
// than the crew it describes.
function saveSetEdit() {
  send({
    type: "actions_update",
    set: edit.set.name,
    active: edit.active,
    order_land: edit.order_land,
    order_port: edit.order_port,
  });
  closeSetEditor();
  // No local write and no optimistic re-render: the PC is the owner of this
  // file, and the `actions` frame it broadcasts back is what re-renders the
  // wheel (client/connection.js). A phone that painted the new D-pad itself
  // would show a state the PC may have refused — the exact shape of the bug
  // the layout Move handle took four rounds to close.
}

// Closing goes BACK to the picker he came from, never to the bare stream: the
// editor is one level down inside "Wheel sets", and a panel that dumps him out
// of the whole settings tree makes editing a second set a four-tap trip.
function closeSetEditor() {
  setEditorPanel.hidden = true;
  setEditorPanel.innerHTML = "";
  edit = null;
  openSetsPanel();
}

setEditorPanel.addEventListener("pointerdown", (e) => {
  if (e.target === setEditorPanel) closeSetEditor();   // backdrop tap = cancel
});
