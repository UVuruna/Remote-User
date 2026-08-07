// Layouts (Phase F+): the loading animation, the top-center layout bar, the
// layout list, the aspect-ratio panel and the whole creation flow. Split out
// of controls.js when that file crossed THE STRUCTURE LAW's 1,000 lines
// (2026-08-03) — layouts are their own responsibility: the chrome in
// controls.js drives the PC directly, everything here composes and frames
// WINDOWS on it.
//
// Loads AFTER controls.js and before gestures.js: it uses `keepFocus`,
// `svg`, `showToast` and `IN_APP` from there, `send`/`layouts`/`layoutActive`
// /`layoutArm` from state.js and the frame sources from render.js, and
// gestures.js/connection.js call into it (`layoutArm` taps, `handleLayoutOffer`,
// `cubeNext`, `settleLayLoading`, `updateLayoutBar`, `applyOrientationLock`).
// See client/__about/layouts.md.
"use strict";

// --- Layouts (Phase F+ step 1) --------------------------------------------
// The + button opens a source CHOOSER (owner 2026-08-02): build the layout
// "From a list" (the server enumerates every window AND its content tabs) or
// "By tapping" windows/tabs in the stream — a grid then takes one tap per
// cell. A creation session (`creating`) collects SLOTS either way; Create
// ships them and the server extracts any tab slots into their own windows
// (a loading overlay covers those seconds). The top-center bar cycles
// Desktop → layout 1 → … , and its framed name opens the full layout list
// (owner 2026-08-03), where every layout also carries its ASPECT RATIO
// panel; the server owns the list (survives disconnects).

const newlayBtn = document.getElementById("btn-newlay");
const layPanel = document.getElementById("layout-panel");
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

const layoutBar = document.getElementById("layout-bar");
const layPickBtn = document.getElementById("lay-pick");
const layNameEl = document.getElementById("lay-name");
const layIconEl = document.getElementById("lay-icon");
const layCloseBtn = document.getElementById("lay-close");

function updateLayoutBar() {
  layoutBar.hidden = layouts.length === 0;
  layCloseBtn.hidden = layoutActive === null;
  const lay = layoutActive === null ? null : layouts[layoutActive];
  layNameEl.textContent = lay ? lay.name : "Desktop";
  layIconEl.hidden = !(lay && lay.icon);
  if (lay && lay.icon) layIconEl.src = lay.icon;
}

// Switching a layout means the PC restores and re-places real windows — the
// cube covers ALL of it (owner 2026-08-03), never the phone showing windows
// climbing out of the taskbar.
function focusLayout(index) {
  send({ type: "layout_focus", index });
  showLayLoading(index < 0 ? "Back to the desktop…" : "Opening the layout…");
}

// The bar cycles positions [Desktop, layout 0, layout 1, …]; index -1 on the
// wire means "back to the full desktop" (the server then minimizes every
// layout member — the desktop shows only non-layout windows).
function layoutStep(dir) {
  if (!layouts.length) return;
  const total = layouts.length + 1;
  const pos = layoutActive === null ? 0 : layoutActive + 1;
  focusLayout(((pos + dir + total) % total) - 1);
}

keepFocus(document.getElementById("lay-prev"), () => layoutStep(-1));
keepFocus(document.getElementById("lay-next"), () => layoutStep(1));
keepFocus(layPickBtn, openLayoutPicker);
keepFocus(layCloseBtn, () => {
  if (layoutActive !== null) send({ type: "layout_remove", index: layoutActive });
});

// --- Layout list + aspect ratio (owner 2026-08-03) -------------------------
// Tapping the bar's name opens every layout at once — stepping ‹ › through a
// dozen of them to reach one was the reported pain. Each row also carries its
// ASPECT button: the region a layout is framed in may be made SMALLER than
// the phone's own shape (portrait keeps the phone's width and only loses
// height, landscape keeps its height and only loses width). Nothing moves on
// the PC until "Apply" — dragging the handle re-arranges only the preview.

function layRow(label, icon, selected, onTap, ...trailing) {
  const row = document.createElement("div");
  row.className = "lay-item";
  const main = document.createElement("button");
  main.type = "button";
  main.className = "lay-item-main" + (selected ? " sel" : "");
  if (icon) {
    const img = document.createElement("img");
    img.src = icon;
    img.alt = "";
    main.appendChild(img);
  } else {
    main.insertAdjacentHTML("beforeend", svg("desktop"));
  }
  const name = document.createElement("span");
  name.textContent = label;
  main.appendChild(name);
  keepFocus(main, onTap);
  row.appendChild(main);
  trailing.filter(Boolean).forEach((el) => row.appendChild(el));
  return row;
}

function ratioLabel(lay) {
  if (!lay.ratio) return "Screen";
  // The stored ratio is FINE-GRAINED (see the aspect panel: w is sent on a
  // 1000-scale), so it is labelled by its closest small pair, not printed raw.
  const [n, d] = ratioPair(lay.ratio[0] / lay.ratio[1], 40);
  return `${n}:${d}`;
}
function openLayoutPicker() {
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card";
  const h = document.createElement("h2");
  h.textContent = "Layouts";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Tap one to open it. Hold and drag it onto another to make a grid.";
  card.append(h, sub);

  card.appendChild(layRow("Desktop", null, layoutActive === null, () => {
    closeLayoutPanel();
    focusLayout(-1);
  }));

  // DRAGGING A ROW (owner 2026-08-07, "kao kada u eksploreru držiš fajl i
  // onda ga vučeš u neki drugi folder"): hold a row, and dropping it ON
  // another makes a GRID of the two; dropping it BETWEEN two rows only
  // reorders the list. A layout that is already FULL (four windows) greys
  // out while a drag is in flight, so the refusal is visible before the
  // finger arrives rather than as a toast after it.
  const rows = [];
  let drag = null;

  function dragEnd(commit) {
    rows.forEach((r) => r.el.classList.remove("lay-full", "lay-drop", "lay-drag",
                                              "lay-gap"));
    if (commit && drag && drag.overRow !== null && drag.overRow !== drag.from) {
      mergeLayouts(drag.from, drag.overRow);
    } else if (commit && drag && drag.overGap !== null) {
      send({ type: "layout_reorder", source: drag.from, before: drag.overGap });
    }
    drag = null;
  }

  function dragMoveTo(clientY) {
    if (!drag) return;
    drag.overRow = null;
    drag.overGap = null;
    rows.forEach((r, i) => {
      r.el.classList.remove("lay-drop", "lay-gap");
      if (i === drag.from) return;
      const b = r.el.getBoundingClientRect();
      if (clientY < b.top || clientY > b.bottom) return;
      // The middle half of a row is the row; its edges are the gaps around
      // it — the same target shapes a file manager uses.
      const edge = b.height * 0.28;
      if (clientY < b.top + edge) { drag.overGap = i; r.el.classList.add("lay-gap"); }
      else if (clientY > b.bottom - edge) { drag.overGap = i + 1; r.el.classList.add("lay-gap"); }
      else if (!r.full) { drag.overRow = i; r.el.classList.add("lay-drop"); }
    });
  }

  layouts.forEach((lay, i) => {
    // Rename (owner 2026-08-05): the auto name is only the window's title —
    // this is where a layout gets the owner's own name, any time later.
    const ren = document.createElement("button");
    ren.type = "button";
    ren.className = "lay-ratio lay-rename";
    ren.innerHTML = svg("edit");
    keepFocus(ren, () => openRenamePanel(i));
    const asp = document.createElement("button");
    asp.type = "button";
    asp.className = "lay-ratio";
    asp.innerHTML = svg("aspect") + `<span>${ratioLabel(lay)}</span>`;
    keepFocus(asp, () => openAspectPanel(i));
    const row = layRow(lay.name, lay.icon, i === layoutActive, () => {
      if (drag) return;          // the press became a drag — not a tap
      closeLayoutPanel();
      focusLayout(i);
    }, ren, asp);
    const full = (GRID_CELLS[gridOf(lay.grid)] || 1) >= 4;
    rows.push({ el: row, full });
    let holdTimer = null;
    row.addEventListener("pointerdown", (e) => {
      holdTimer = setTimeout(() => {
        holdTimer = null;
        drag = { from: i, overRow: null, overGap: null };
        row.classList.add("lay-drag");
        rows.forEach((r) => { if (r.full) r.el.classList.add("lay-full"); });
        row.setPointerCapture(e.pointerId);
      }, 380);   // a HOLD, so a plain tap still opens the layout
    });
    row.addEventListener("pointermove", (e) => {
      if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
      if (drag) dragMoveTo(e.clientY);
    });
    const stop = (commit) => (e) => {
      if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
      if (drag) { e.preventDefault(); dragEnd(commit); }
    };
    row.addEventListener("pointerup", stop(true));
    row.addEventListener("pointercancel", stop(false));
    card.appendChild(row);
  });

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Close", false, closeLayoutPanel));
  card.appendChild(actions);
  layPanel.appendChild(card);
}

// The name field. A WRAPPING textarea, not a one-line input: window titles
// are long ("Claude Code - Remote User - Visual Studio Code [Administrator]")
// and a single line hides most of one behind its own horizontal scroll —
// exactly what THE SPACE & LEGIBILITY LAW forbids (caught by the layout
// audit, 2026-08-05). Newlines are stripped: a name is one line of text.
function nameField(value, placeholder) {
  const el = document.createElement("textarea");
  el.className = "lay-name-in";
  el.rows = 3;
  el.maxLength = 80;
  el.autocapitalize = "off";
  el.autocomplete = "off";
  el.spellcheck = false;
  el.placeholder = placeholder || "";
  el.value = value || "";
  el.addEventListener("input", () => {
    if (el.value.includes("\n")) el.value = el.value.replace(/\n/g, " ");
  });
  return el;
}

// Renaming an existing layout (owner 2026-08-05). Nothing on the PC moves —
// only what this layout is CALLED in the bar and the list changes.
function openRenamePanel(index) {
  const lay = layouts[index];
  if (!lay) return;
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card";
  const h = document.createElement("h2");
  h.textContent = "Layout name";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Call it whatever you like — the window's title is only the default.";
  const field = nameField(lay.name || "");
  card.append(h, sub, field);

  // The app-shortcut ticks used to live here too. They are GONE (owner
  // 2026-08-07): the PC recognises what is running in a window by itself.
  // What DOES belong here is the layout's SHAPE (owner 2026-08-07): the
  // orientation for every grid, and for a THREE which edge its single window
  // takes. Two and four have nothing else to decide.
  const grid = gridOf(lay.grid);
  let orient = lay.orient === "portrait" ? "portrait" : "landscape";
  let shape = grid;
  if (grid) {
    const oLbl = document.createElement("p");
    oLbl.className = "lay-sub";
    oLbl.textContent = "Shape:";
    const oRow = document.createElement("div");
    oRow.className = "lay-row";
    const draw = () => {
      oRow.innerHTML = "";
      ["portrait", "landscape"].forEach((o) => oRow.appendChild(
        layChip(o === "portrait" ? "Portrait" : "Landscape", orient === o, () => {
          orient = o;
          draw();
        })));
      if (GRID_CELLS[grid] === 3) {
        GRID_THREE.forEach((g) => oRow.appendChild(
          gridChip(g, orient, shape === g, () => { shape = g; draw(); })));
      }
    };
    draw();
    card.append(oLbl, oRow);
  }

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, openLayoutPicker)); // back one step
  actions.appendChild(layChip("Save", true, () => {
    const name = field.value.trim();
    if (name && name !== lay.name) send({ type: "layout_rename", index, name });
    if (grid && (shape !== grid || orient !== lay.orient)) {
      send({ type: "layout_grid", index, grid: shape, orient });
      showLayLoading("Reshaping the layout…");
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
  card.className = "lay-card";

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
    aspecting = null;
    openLayoutPicker(); // back one step, not out of the layouts entirely
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
    showLayLoading("Reshaping the layout…");
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
// A DOUBLE TAP IS TWO TAPS, NOT TWO TOUCHES (owner 2026-08-07: "smanjio sam
// dimenzije layout-a i pokušao da ga privučem dole ali on je i dalje na
// sredini"). The re-centre used to fire from `pointerdown` on any contact
// within 350 ms of the previous one — so the very common tap-then-drag was
// read as a double tap: it put the region back in the MIDDLE and returned
// without capturing the pointer, killing the drag that was just starting.
// Both halves of his sentence, from one line. A tap is now only a tap once it
// has ENDED, quickly and without travel, and a press is always a press.
// -Infinity, never 0: `0` is a real `performance.now()` reading — it means
// "a tap at page load" — so every tap in the page's first 350 ms counted as
// the SECOND tap of a double tap and re-centred the region. The audit caught
// this in landscape, where the panel opens sooner after load than the 350 ms
// window (portrait was past it at 623 ms and passed, which is exactly how a
// timing bug survives a green suite).
let moveTapAt = -Infinity;
const MOVE_TAP_MS = 350;   // two taps closer than this = re-centre
const MOVE_TAP_SLOP = 12;  // px: past this the contact was a drag, not a tap
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

// In the APK, layout focus locks the phone's rotation to the layout's chosen
// orientation; the full desktop unlocks it (owner 2026-08-02). "" = unlock.
function applyOrientationLock() {
  if (!IN_APP || !window.Android.lockOrientation) return;
  window.Android.lockOrientation(
    layoutActive !== null && layouts[layoutActive] ? layouts[layoutActive].orient : "");
}

// --- Layout creation -------------------------------------------------------

function closeLayoutPanel() {
  layPanel.hidden = true;
  layPanel.innerHTML = "";
  aspecting = null;
}

layPanel.addEventListener("pointerdown", (e) => {
  if (e.target !== layPanel) return;
  // Backdrop tap = out. Only a creation session has anything to cancel; the
  // list and the aspect panel just close (nothing was sent).
  if (creating) cancelCreation();
  else closeLayoutPanel();
});

function layChip(label, selected, onTap, icon) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "lay-chip" + (selected ? " sel" : "");
  if (icon) {
    const img = document.createElement("img");
    img.src = icon;
    img.alt = "";
    el.appendChild(img);
  }
  el.appendChild(document.createTextNode(label));
  keepFocus(el, onTap);
  return el;
}

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
    c.slots.forEach((s, i) => row.appendChild(
      layChip(s.title.length > 30 ? s.title.slice(0, 29) + "…" : s.title, true,
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

  const modeRow = document.createElement("div");
  modeRow.className = "lay-row";
  modeRow.appendChild(layChip("Only one", c.mode === "solo", () => {
    c.mode = "solo";
    c.grid = null;
    c.slots = c.slots.slice(0, 1);
    renderCreationPanel();
  }));
  // The COUNT is the choice (owner 2026-08-07); the shape follows from it and
  // from the orientation, and only a THREE has anything left to decide.
  [["2", "Two"], ["3-top", "Three"], ["4", "Four"]].forEach(([g, label]) =>
    modeRow.appendChild(
      layChip(label, c.mode === "grid" && GRID_CELLS[c.grid] === GRID_CELLS[g], () => {
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
      const label = (e.kind === "tab" ? "↳ " : "") +
        (e.title.length > 34 ? e.title.slice(0, 33) + "…" : e.title);
      list.appendChild(layChip(label, idx >= 0, () => {
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

  const orientRow = document.createElement("div");
  orientRow.className = "lay-row";
  orientRow.appendChild(layChip("Portrait", c.orient === "portrait", () => {
    c.orient = "portrait";
    renderCreationPanel();
  }));
  orientRow.appendChild(layChip("Landscape", c.orient === "landscape", () => {
    c.orient = "landscape";
    renderCreationPanel();
  }));
  card.appendChild(orientRow);

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

