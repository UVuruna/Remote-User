// Layouts (Phase F+): LIVING with the layouts that exist — the top-center
// bar, the layout list and its drag, the ✕ chooser and the member chooser.
// What a layout IS (its name, its aspect ratio, its orientation and its
// arrangement) moved to layout-settings.js on 2026-08-09; what this file owns
// is which layouts exist, which one is shown, and which windows are in them.
// Split out of controls.js when that file crossed THE STRUCTURE LAW's 1,000
// lines (2026-08-03) — layouts are their own responsibility: the chrome in
// controls.js drives the PC directly, everything here composes and frames
// WINDOWS on it. MAKING one is layout-create.js, split off the same way on
// 2026-08-08; CHANGING one is layout-settings.js, split off on 2026-08-09
// (task 175 — every act on an existing layout moved under one ⚙). The panel
// vocabulary below (`layPanel`, `closeLayoutPanel`, `layChip`, `chooserBtn`,
// `nameField`, `layRow`, `ratioLabel`) and the `.lay-item` ROW markup its
// stylesheet owns are shared with both.
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

const layPanel = document.getElementById("layout-panel");
const layoutBar = document.getElementById("layout-bar");
const layPickBtn = document.getElementById("lay-pick");
const layNameEl = document.getElementById("lay-name");
const layIconEl = document.getElementById("lay-icon");
const layCloseBtn = document.getElementById("lay-close");

// ── WHERE THE BAR STANDS IS HIS, PER DEVICE (owner 2026-08-09, task 160) ────
// "top" (the default, and what has always shipped) or "bottom". Read through
// the shell's SharedPreferences bridge like every other phone-side switch,
// never bare localStorage — that is per-ORIGIN and split this device's state
// across the LAN and Tailscale addresses once already (the "picker rotates" bug
// of 2026-08-05). A value that is neither word means "top", so a pref written
// by a future version, or a corrupted one, renders today's default rather than
// an empty top row.
const LAY_BAR_POSITIONS = ["top", "bottom"];

function layBarPos() {
  const stored = prefGet("layBarPos");
  return LAY_BAR_POSITIONS.includes(stored) ? stored : "top";
}

// ONE class, and it names the DECISION (client/layouts.css): top is the base
// rule and this class is the page asking for the bottom.
function applyLayBarPos() {
  document.body.classList.toggle("laybar-bottom", layBarPos() === "bottom");
}

function setLayBarPos(pos) {
  prefSet("layBarPos", LAY_BAR_POSITIONS.includes(pos) ? pos : "top");
  applyLayBarPos();
  layBarFit();
}

applyLayBarPos();

// ── HIS SIZING RULE, TASK 237 (verdict ~21:4x) ──────────────────────────────
// The bar has a MINIMUM width it needs to draw the name usefully; below it,
// the row can't hold both the bar AND its neighbours (the corner buttons at
// top, the two D-pad columns at bottom), so it takes its OWN full row instead
// of shrinking further — `body.laybar-overflow`, toggled here.
//
// THE NUMBER: 340 CSS px for the bar's own content width, chosen from his two
// real devices (owner spec ~21:5x): on his PHONE (portrait 412-class CSS
// width) the row must NOT fit — the overflow layout applies; on his TABLET
// (portrait ~800-class, a 1280x800 tablet rotated) it MUST fit between the
// columns. Measured against both device classes at both bar positions:
//   TOP    reserves 2 * (space-m 16 + corner 58 + space-s 8) = 164px, plus
//          the bar's own 2 * space-s (8px) gap to those buttons = 16px more,
//          so the threshold GAP between the two corner buttons is 340+16=356.
//   BOTTOM reserves the two D-pad groups' own width (190px each in the
//          default cross shape) the same way: gap threshold 356 as well —
//          the SAME 340px bar content plus the SAME 16px of margin either
//          side, whatever sits beside it.
//   Phone @ top:    338 - 74  =  264px gap  → under 356 → OVERFLOW.
//   Phone @ bottom: 206 - 206 =    0px gap  → under 356 → OVERFLOW.
//   Tablet @ top:   726 - 74  =  652px gap  → over  356 → fits, in-row.
//   Tablet @ bottom:594 - 206 =  388px gap  → over  356 → fits, in-row.
// A number anywhere in 320-360 clears the same four cases; 340 sits in the
// middle of his stated range with margin either side (up to ~92px of slack
// at the phone, ~30px at the tightest tablet case) so a later font or corner
// retune does not flip the verdict by a few pixels.
const LAY_BAR_MIN_GAP = 356;  // = 340 (bar content) + 2 * 8 (space-s margins)

// Landscape is its OWN geometry (ballot drawings 1-3, approved as drawn): a
// centered bar with a max width, never the portrait in-row/overflow choice —
// see client/layouts.css. Measuring the portrait gap there would be
// meaningless (the bar is never asked to stand between the corners or the
// D-pad columns in landscape), so this function does nothing there and the
// CSS media query carries the whole rule by itself.
function layBarFit() {
  if (window.matchMedia && window.matchMedia("(orientation: landscape)").matches) {
    document.body.classList.remove("laybar-overflow");
    return;
  }
  let gap;
  if (layBarPos() === "bottom") {
    const left = document.querySelector(".group.left");
    const right = document.querySelector(".group.right");
    if (!left || !right) return;   // groups not built yet — re-run once they are
    gap = right.getBoundingClientRect().left - left.getBoundingClientRect().right;
  } else {
    const tl = document.getElementById("btn-newlay");
    const tr = document.getElementById("btn-hide");
    if (!tl || !tr) return;
    gap = tr.getBoundingClientRect().left - tl.getBoundingClientRect().right;
  }
  document.body.classList.toggle("laybar-overflow", gap < LAY_BAR_MIN_GAP);
}

window.addEventListener("resize", layBarFit);
if (window.visualViewport) window.visualViewport.addEventListener("resize", layBarFit);

function updateLayoutBar() {
  layoutBar.hidden = layouts.length === 0;
  layCloseBtn.hidden = layoutActive === null;
  const lay = layoutActive === null ? null : layouts[layoutActive];
  layNameEl.textContent = lay ? lay.name : "Desktop";
  layIconEl.hidden = !(lay && lay.icon);
  if (lay && lay.icon) layIconEl.src = lay.icon;
  layBarFit();
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
// The ✕ ASKS now (owner 2026-08-08, task 116). It used to remove the layout
// and nothing else, which is one of the two things he means by it.
keepFocus(layCloseBtn, () => {
  if (layoutActive !== null) openCloseChooser(layoutActive);
});

// --- The layout list (owner 2026-08-03) ------------------------------------
// Tapping the bar's name opens every layout at once — stepping ‹ › through a
// dozen of them to reach one was the reported pain. A row is
// [icon][⭐][name][shape][⚙] since task 175 (owner 2026-08-09): the two facts
// it can carry at a glance, and ONE door to everything else
// (client/layout-settings.js).

// `icon` is the row's LEADING BADGE and it comes in three kinds now: an app
// icon (a PNG data URI from the server), `{draw: markup}` for a drawing we
// made ourselves, or null for the Desktop row's monitor. The tagged object
// rather than sniffing the string for a "<": the member chooser's badge is a
// third thing — the layout's own grid with ONE CELL LIT (owner 2026-08-09,
// task 165) — and a row builder that could only ever draw two of the three
// would have been copied instead of reused.
function layRow(label, icon, selected, onTap, ...trailing) {
  const row = document.createElement("div");
  row.className = "lay-item";
  const main = document.createElement("button");
  main.type = "button";
  main.className = "lay-item-main" + (selected ? " sel" : "");
  if (icon && icon.draw) {
    main.insertAdjacentHTML("beforeend", icon.draw);
  } else if (icon) {
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

// A HOLD IS A CONTACT THAT STAYED PUT — NOT ONE THAT NEVER MOVED A PIXEL
// (owner report 2026-08-09, task 162: he held a row without moving it and the
// layout OPENED). The two limits the row's press is judged by; the RULE
// itself is `pressVerdict` in client/hold-gesture.js, pure so its gate can
// drive it with a real jitter sequence.
//
// THE LESSON THAT WAS AVAILABLE AND UNUSED: `MOVE_TAP_SLOP` below is the same
// idea, written for the Move handle's own tap-versus-drag bug on the SAME DAY
// this gesture shipped with no tolerance at all (see its comment, "A DOUBLE
// TAP IS TWO TAPS, NOT TWO TOUCHES"). One digitizer, one question, so one
// number: MOVE_TAP_SLOP is now derived FROM this constant rather than
// re-typed beside it, and neither can drift from the other again.
const HOLD_DRAG_MS = 380;   // ms a still finger must stay down to pick a row up
const HOLD_DRAG_SLOP = 12;  // px of wander a RESTING finger is allowed

function openLayoutPicker() {
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  // NO `card-columns` — deliberate, not forgotten (owner width question
  // 2026-08-09, task 172). The landscape reflow in client/panels.css starves
  // this one panel: its rows carry a name AND four trailing controls, so two
  // columns leave the name 87 px of 347 — 12 characters of a 62-character
  // title, fewer than the same tablet shows UPRIGHT. One column makes the row
  // 718 px and the whole title fits. That rule carries the counted price, why
  // the other two name-bearing panels answer differently, and why this card
  // is a stated exception to BUG A rather than an oversight.
  card.className = "lay-card";
  const h = document.createElement("h2");
  h.textContent = "Layouts";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Tap one to open it. Hold and drag it onto another to make a grid.";
  card.append(h, sub);

  // ── ONE ROW PER MONITOR, NOT ONE "DESKTOP" (owner 2026-08-09, task 155) ──
  // His instruction, in translation: Monitor leaves the Settings menu and
  // becomes part of these layout panels — where it now says "Desktop" it will
  // say, if there is more than one monitor, Monitor 1 and its resolution,
  // Monitor 2, and so on. The Settings set had a slot spent on a CYCLER that
  // told you nothing about where you were going; a named row carrying its own
  // resolution says which screen it opens before it is tapped.
  //
  // THE DESKTOP ROW SURVIVES AS THE ONE-MONITOR CASE, and that is not a
  // fallback bolted on: a PC with one screen has nothing to choose between, and
  // "Monitor 1 — 3840x2160" would be a list of one pretending to be a choice.
  // The same row is also what a server too old to send `monitors` draws, so an
  // old PC and a single-screen PC take the identical, already-proven path.
  //
  // TAPPING ONE IS TWO ACTS AND IT SENDS ONLY WHAT IT MUST: the monitor it is
  // ALREADY on is a plain "back to the desktop" (`layout_focus -1`), and any
  // other is a `monitor_switch` carrying that index — which the server already
  // answers by leaving the focused layout and showing the bare desktop there
  // (server/web.py → _switch_monitor, since 2026-08-05). `index` is an OPTIONAL
  // field on the message that has always existed: a server that ignores it
  // still cycles, which on a two-monitor PC lands on the same screen anyway.
  //
  // NO LOADING CUBE FOR THE SWITCH, deliberately: the cube is dropped by the
  // `layout_state` that follows a placement, and a monitor switch made from the
  // DESKTOP sends none — the overlay would sit there until the settle watchdog
  // gave up. The server answers this one with its own toast ("Monitor 2/2") and
  // the picture changes by itself, which is the whole event.
  if (monitorList.length > 1) {
    monitorList.forEach((mon) => {
      const size = mon.width && mon.height ? ` — ${mon.width}×${mon.height}` : "";
      const here = mon.index === monitorIndex;
      card.appendChild(layRow(
        `Monitor ${mon.index + 1}${size}`, null,
        here && layoutActive === null, () => {
          closeLayoutPanel();
          if (here) focusLayout(-1);
          else send({ type: "monitor_switch", index: mon.index });
        }));
    });
  } else {
    card.appendChild(layRow("Desktop", null, layoutActive === null, () => {
      closeLayoutPanel();
      focusLayout(-1);
    }));
  }

  // DRAGGING A ROW (owner 2026-08-07, "kao kada u eksploreru držiš fajl i
  // onda ga vučeš u neki drugi folder"): hold a row, and dropping it ON
  // another makes a GRID of the two; dropping it BETWEEN two rows only
  // reorders the list. A layout that is already FULL (four windows) greys
  // out while a drag is in flight, so the refusal is visible before the
  // finger arrives rather than as a toast after it.
  const rows = [];
  let drag = null;

  // EDGE AUTO-SCROLL — the honest price of `touch-action: none` on a row
  // (owner 2026-08-09, task 162). A row has to refuse the browser's own pan
  // gesture, or Android takes the touch away the moment the carried row
  // travels and drops it with a `pointercancel`; but refusing it also means a
  // long list can no longer be scrolled by dragging a row, and a drop target
  // below the fold would be unreachable — the cheap fix would have traded one
  // broken gesture for another. So while a row is being CARRIED, holding it
  // near the card's top or bottom edge scrolls the card itself, proportionally
  // (faster the closer to the edge). It runs on FRAMES, not on pointer events:
  // a finger held still at the edge sends none, and that is exactly the moment
  // it has to keep scrolling. It dies with the drag.
  const AUTO_EDGE = 0.15;  // of the card's height, at the top and the bottom
  const AUTO_MAX = 16;     // px per frame, right at the edge
  let autoRaf = null;
  let autoY = 0;

  function autoScrollStop() {
    if (autoRaf !== null) cancelAnimationFrame(autoRaf);
    autoRaf = null;
  }

  function autoScrollFrame() {
    // `isConnected` as well as `drag`: a second finger on the backdrop can
    // close the panel while the first is still carrying a row, and a loop
    // measuring a detached card would spin for the rest of the session.
    if (!drag || !card.isConnected) { autoRaf = null; return; }
    const b = card.getBoundingClientRect();
    const edge = Math.max(1, b.height * AUTO_EDGE);
    let dy = 0;
    if (autoY < b.top + edge) {
      dy = -AUTO_MAX * Math.min(1, (b.top + edge - autoY) / edge);
    } else if (autoY > b.bottom - edge) {
      dy = AUTO_MAX * Math.min(1, (autoY - (b.bottom - edge)) / edge);
    }
    if (dy) {
      const was = card.scrollTop;
      card.scrollTop = was + dy;
      // The rows just moved under a finger that did not — re-read the target.
      // `autoRaf` still holds this frame's (already fired) handle, so this
      // call cannot start a second loop.
      if (card.scrollTop !== was) dragMoveTo(autoY);
    }
    autoRaf = requestAnimationFrame(autoScrollFrame);
  }

  function dragEnd(commit) {
    autoScrollStop();
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
    autoY = clientY;
    if (autoRaf === null) autoRaf = requestAnimationFrame(autoScrollFrame);
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
    // WHAT SHAPE IS THIS LAYOUT — drawn, on every row (owner request
    // 2026-08-09, task 164). A solo window, a two-split and a four-grid read
    // identically while a row carried only a name, so the only way to find
    // out which was which was to OPEN one. The picture is keyed by the three
    // fields `layout_state` has always carried — `grid`, `members`, `orient`
    // — and drawn by client/grid-icons.js, whose gate compares its partitions
    // to server/grids.py's own arithmetic number for number.
    //
    // A GRID's drawing is also the DOOR to the member chooser (task 165):
    // tapping the shape is how one window is thrown out of it. A SOLO layout
    // has nothing to throw out — the bar's ✕ owns that act — so its shape is
    // a plain <span>: the same picture, without the promise of a tap.
    const hasGrid = (lay.members || 1) > 1;
    const shape = document.createElement(hasGrid ? "button" : "span");
    shape.className = "lay-ratio lay-shape";
    shape.innerHTML = gridIconSvg(lay.members, lay.grid, lay.orient);
    if (hasGrid) {
      shape.type = "button";
      // The drawing itself is aria-hidden (it is geometry, not words), so the
      // button would otherwise have no name at all.
      shape.setAttribute("aria-label", "Take one window out");
      keepFocus(shape, () => openMemberPanel(i));
    }
    // ONE ⚙ FOR EVERYTHING THIS LAYOUT CAN BE ASKED (owner 2026-08-09, task
    // 175). Every act on an existing layout kept arriving as its own icon on
    // the row — a rename pencil, an aspect chip, the shape badge — and task
    // 165 had just added a fourth. His instruction was to put all of it under
    // one common settings icon instead of one icon per thing:
    // "pod neku zajedničku settings ikonicu" — lang-ok: owner quote
    // The portrait list was honestly graded 6/10 for exactly that crowding.
    //
    // Renaming, the aspect ratio, the orientation, the arrangement and taking
    // one window out all live in the SHEET now (client/layout-settings.js).
    // The row keeps the two things it can say at a GLANCE — which app, and
    // what shape — plus the ⚙, and the name inherits the width the pencil and
    // the aspect chip used to spend (the task-172 finding, continued: the
    // aspect chip's own label floor is gone with it, since `__nameRoom`
    // measures the name against the widest button left standing).
    //
    // A DRAWN icon (`ICONS.settings`), never a font glyph — the ✥ move handle
    // came out a blunt cross on his phone in 2026-08-05 and everything has
    // been drawn geometry since.
    const gear = document.createElement("button");
    gear.type = "button";
    gear.className = "lay-ratio lay-gear";
    gear.innerHTML = svg("settings");
    gear.setAttribute("aria-label", "Settings for this layout");
    keepFocus(gear, () => openLayoutSettings(i));
    // WHERE AND WHEN THE FINGER LANDED. Both the hold timer and the row's own
    // tap are decided from it, so it is declared before either exists.
    let holdTimer = null;
    let press = null;   // {x, y, at} — null until this row is touched
    const row = layRow(lay.name, lay.icon, i === layoutActive, () => {
      if (drag) return;          // the press became a drag — not a tap
      // A TAP IS A TAP, NOT MERELY A TOUCH THAT ENDED (owner 2026-08-09, task
      // 162 — the SECOND, independent path that opened the layout under his
      // hold). `keepFocus` fires on `pointerup` with no duration test at all,
      // and its `pointercancel` rescue fires for any cancel under 18 px of
      // travel — while Chrome on Android hands out a cancel at ~8 dp, the
      // moment it decides the touch is a scroll. Both land inside that rescue
      // window, so even with the timer fixed the row would still open under a
      // long press. keepFocus is NOT touched: it is the one activator the
      // gamepad shares (CLAUDE.md constraint 12) and the stolen-tap rescue is
      // constraint 9 — the hold has to live BESIDE it, so the refusal is
      // here, where the hold's own limits are known.
      if (press && performance.now() - press.at >= HOLD_DRAG_MS) return;
      closeLayoutPanel();
      focusLayout(i);
    }, shape, gear);
    // ⭐ = THE TRUNK, NOT A BRANCH (owner decision 2026-08-09, task 169: one
    // emoji before the first letter, and only in THIS list — the layout
    // selector, where Desktop is; the creation list marks parenthood by
    // indentation instead, which is task 168 and not this round's). It means
    // one of this layout's windows is the window ANOTHER layout's content was
    // torn out of, so closing it would take that other layout's tab with it.
    // The server answers it (`layout_state.parent`, read off `Layout.source`);
    // nothing here guesses from a title.
    //
    // AN EMOJI, DELIBERATELY, AGAINST THIS PROJECT'S OWN RULE. Font glyphs
    // are banned for icons since the ✥ move handle came out a blunt cross on
    // his phone (2026-08-05) and every icon is drawn geometry — but ⭐ (U+2B50)
    // is his explicit choice of 2026-08-09: it is a COLOUR EMOJI, carried by
    // Android's own emoji font on every version this app supports, which is
    // exactly what the failed dingbat was not. It is added at the CALL SITE
    // rather than inside `layRow` because that builder also makes the Desktop
    // row and will make the member chooser's rows — a mark for one list must
    // not become a mark for all of them.
    if (lay.parent) {
      const star = document.createElement("i");
      star.className = "lay-star";
      star.textContent = "⭐";
      star.setAttribute("aria-label", "Other layouts show tabs from this window");
      // Before the first letter, after the badge, in the same single line —
      // its own element so task 163's ellipsis can never eat it and its own
      // line-height so a colour emoji's metrics can never make this row
      // taller than its siblings.
      const main = row.querySelector(".lay-item-main");
      main.insertBefore(star, main.querySelector("span"));
    }
    const full = (GRID_CELLS[gridOf(lay.grid)] || 1) >= 4;
    rows.push({ el: row, full });
    row.addEventListener("pointerdown", (e) => {
      press = { x: e.clientX, y: e.clientY, at: performance.now() };
      holdTimer = setTimeout(() => {
        holdTimer = null;
        // CAPTURE FIRST, ARM SECOND — and never arm on a capture that did not
        // take (latent bug, fixed 2026-08-09). `setPointerCapture` throws
        // NotFoundError for a pointer that is already gone; it used to run
        // AFTER `drag` was assigned, so the throw left `drag` non-null with no
        // gesture in flight — and the row's tap guard reads `drag`, which made
        // EVERY row in the list dead until the panel was reopened. Both halves
        // of the fix: the order, and the wrap that abandons the arm cleanly.
        try {
          row.setPointerCapture(e.pointerId);
        } catch (err) {
          return;    // that pointer no longer exists — there is nothing to carry
        }
        drag = { from: i, overRow: null, overGap: null };
        row.classList.add("lay-drag");
        rows.forEach((r) => { if (r.full) r.el.classList.add("lay-full"); });
      }, HOLD_DRAG_MS);   // a HOLD, so a plain tap still opens the layout
    });
    row.addEventListener("pointermove", (e) => {
      // THE FINGER IS ALLOWED TO TREMBLE (owner report 2026-08-09, task 162 —
      // the ROOT CAUSE). This used to clear the timer on ANY movement, which
      // on a capacitive digitizer means "on the first frame": the reported
      // point is the centroid of a contact patch that breathes, so a resting
      // finger wanders a pixel or three and the 380 ms never elapsed. Only
      // real travel — `pressVerdict` past HOLD_DRAG_SLOP — is somebody
      // scrolling or swiping instead of picking a row up.
      if (holdTimer && press &&
          pressVerdict(press, { x: e.clientX, y: e.clientY },
                       performance.now() - press.at,
                       HOLD_DRAG_SLOP, HOLD_DRAG_MS) === PRESS_DRAG) {
        clearTimeout(holdTimer);
        holdTimer = null;
      }
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

  // WHERE THIS BAR ITSELF STANDS LEFT THIS CARD on 2026-08-11 (task 218a).
  // Task 160 put the Top/Bottom chips here with a note saying so in as many
  // words: this is the panel whose subject is the layout bar, task 161 exists
  // to gather the small per-device switches properly, and "guessing at that
  // gathering here would be a second home for the same switch the day it
  // lands". Task 161 landed — the switch lives on the Phone card
  // (client/phone-panel.js, Settings wheel → Phone) and it did not stay here
  // as well, because two doors onto one preference is two states to keep in
  // step. This card is about LAYOUTS again.
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

// In the APK, layout focus locks the phone's rotation to the layout's chosen
// orientation; the full desktop unlocks it (owner 2026-08-02). "" = unlock.
function applyOrientationLock() {
  if (!IN_APP || !window.Android.lockOrientation) return;
  // TASK 204: after a reconnect, the server's FIRST layout_state says desktop
  // — connection.js only sends the layout_focus that restores the real
  // layout a moment later. Calling lockOrientation("") on that interim frame
  // unlocked rotation for the seconds the restore takes, and the tablet spun
  // sideways with blue letterbox bars over a portrait layout. While
  // orientationRestoring is true the previous lock stands untouched; the
  // restore's own later layout_state (landing with layoutActive set) clears
  // the flag and this function runs for real, and a restore that fails to
  // verify clears it too (connection.js) — so a genuinely stuck restore does
  // not hold rotation locked forever.
  if (layoutActive === null && orientationRestoring) return;
  window.Android.lockOrientation(
    layoutActive !== null && layouts[layoutActive] ? layouts[layoutActive].orient : "");
}

// --- Layout creation -------------------------------------------------------

function closeLayoutPanel() {
  layPanel.hidden = true;
  layPanel.innerHTML = "";
  // The overlay is ONE element with several contents, so closing it has to
  // clear whatever state the content that was in it left behind. Only that
  // content's own file knows what that is — hence a call rather than this
  // file reaching into the aspect panel's variable (client/layout-settings.js).
  forgetLayoutSettings();
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

// `titleChip` (a chip whose long label WRAPPED) stood here until 2026-08-09.
// Task 168 made both of its lists real rows, whose title is elided on one
// line, so the creation panel — its only caller — stopped calling it; deleted
// with `.lay-chip.lay-title`, since dead code that still renders is how a
// later round resurrects a treatment the owner ruled out.

// THE BIG SIDE-BY-SIDE CHOICE. One maker, two users: "where do the windows
// come from" when a layout is born, and "which close do you mean" when one
// ends (owner 2026-08-08 — "kao sto kreiranje layouta ima dve opcije"). The
// second line is what makes it a choice and not a quiz: each act says its own
// consequence, so the irreversible one is never picked by elimination.
function chooserBtn(iconName, label, sub, onTap, warn) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "lay-chip lay-source";
  el.innerHTML = svg(iconName) + `<span>${label}</span>`;
  if (sub) {
    const note = document.createElement("small");
    note.textContent = sub;
    el.appendChild(note);
  }
  // `warn` is a consequence this act has BEYOND its own subject (owner
  // 2026-08-09, task 171 — closing these windows would also destroy another
  // layout). It rides INSIDE the button rather than under the row on purpose:
  // a line under the pair would read as applying to both acts, and only one
  // of them can do this. Its own element so it can be styled — and measured —
  // apart from the ordinary consequence line above it.
  if (warn) {
    const bad = document.createElement("small");
    bad.className = "lay-warn";
    bad.textContent = warn;
    el.appendChild(bad);
  }
  keepFocus(el, onTap);
  return el;
}

// WHAT ELSE DIES WITH THESE WINDOWS (owner 2026-08-09, task 171). A layout
// whose content was TORN OUT of a window this one holds is destroyed by
// closing it — the tab has no home to go back to. The server answers which
// ones by name (`layout_state.dependents`, read off `Layout.sources`, one
// record per slot since task 173); nothing here guesses from a title, and a
// server too old to send the field simply produces no line.
//
// It names them rather than counting them: "1 other layout" tells him a
// number, and what he needs before an irreversible tap is WHICH.
function dependentWarning(lay) {
  const deps = Array.isArray(lay.dependents) ? lay.dependents.filter(Boolean) : [];
  if (!deps.length) return "";
  const names = deps.map((n) => `“${n}”`).join(", ");
  return deps.length === 1
    ? `Also destroys ${names} — its tab was taken out of this window`
    : `Also destroys ${names} — their tabs were taken out of these windows`;
}

// THE ✕ ON THE BAR MEANS TWO DIFFERENT THINGS AND USED TO DO ONLY ONE (owner
// 2026-08-08, task 116): "brisanje layouta ga samo obrise iz nase liste ali
// ostavlja prozor na desktopu. Nekad hocemo to, a nekad hocemo bas da
// zatvorimo sve tu." So it asks. The removal stays the plain act the button
// always was; the close is the new one, and it is the only one of the two
// that cannot be undone from the phone — which is why it is named by what it
// does to HIS windows, with their count, not by the word "close" alone.
function openCloseChooser(index) {
  const lay = layouts[index];
  if (!lay) return;
  const n = lay.members || 1;
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  // NO `card-columns` (owner 2026-08-09, task 171 — measured when the
  // dependency warning was added). This card is not the "many short items"
  // shape that reflow was cut for (client/panels.css): it is TWO BIG CHIPS
  // side by side, each capped at 46% of the card, so two columns cut them
  // from 350 px to 160 px and every line inside them wraps two or three times
  // deeper. With the third line this task adds, that overflowed the card
  // SIDEWAYS at 915x412 — a `column-count` card grows a third column rather
  // than a scrollbar — which the audit caught as `noClip` the same hour.
  // In one column the chips are wide, the card is short, and nothing spills.
  card.className = "lay-card";
  const h = document.createElement("h2");
  h.className = "lay-name-line";   // one line, like the row it was opened from
  h.textContent = lay.name;
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "What should happen to it?";
  const row = document.createElement("div");
  row.className = "lay-row lay-sources";
  row.appendChild(chooserBtn("x", "Remove the layout",
    n === 1 ? "The window stays open on the PC"
            : `All ${n} windows stay open on the PC`, () => {
      closeLayoutPanel();
      send({ type: "layout_remove", index });
    }));
  row.appendChild(chooserBtn("closetab",
    n === 1 ? "Close the window" : `Close all ${n} windows`,
    "On the PC, like pressing its own ✕", () => {
      closeLayoutPanel();
      send({ type: "layout_remove", index, close: true });
    }, dependentWarning(lay)));
  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, closeLayoutPanel));
  card.append(h, sub, row, actions);
  layPanel.appendChild(card);
}

// --- ONE WINDOW OUT OF A GRID (owner request 2026-08-09, task 165) ---------
// His words in translation: each row of the list has a rename button and an
// aspect button, "but there must be a button by which I can throw ONE member
// out of the grid — to enter the grid state and remove any member, i.e.
// change it to a single or to a 2-grid." Until this round a grid could only
// be BUILT (drag one row onto another) or removed WHOLE, so losing one window
// of four meant deleting the layout and building it again.
//
// HE PICKS THE WINDOW BY ITS POSITION, NOT BY ITS NAME. Every row's badge is
// this layout's own drawing with THAT cell lit and the rest faint — cell k is
// member k, the same order the server places into (client/grid-icons.js) — so
// a grid of four VS Code windows, whose titles are nearly identical, is still
// unambiguous: only one of them is the top-left square. The title is the word
// beside the picture, elided to one line like every other row (task 163).
//
// IT IS NOT A CLOSE. The window leaves the layout, leaves the topmost band
// and goes on standing exactly where it stands (server/layout_registry.py
// `drop_member`); only the bar's ✕ closes windows, and only when he asked for
// that act (2026-08-08, task 116). Removing the last member removes the
// layout, through the same path the ✕ uses.
function openMemberPanel(index) {
  const lay = layouts[index];
  if (!lay || (lay.members || 1) < 2) return;   // a solo has nothing to lose
  // A FOUR landing on a THREE is the one size with a shape to choose (his
  // sheet, 2026-08-07). Asked of the RESULT and not of the layout as it
  // stands: a three shrinking to a two has nothing to decide. The asymmetry
  // itself stays in the pure module, so no panel can offer a choice that does
  // not exist — and `null` for the result's grid means "the default shape for
  // that count", exactly what the server falls back to.
  const choices = gridIconChoices((lay.members || 1) - 1, null);
  let grid = choices[0] || null;
  const draw = () => {
    layPanel.innerHTML = "";
    layPanel.hidden = false;
    const card = document.createElement("div");
    // `card-columns` — a MEASURED decision, not the inheritance it used to be
    // (owner width question 2026-08-09, task 172). These rows carry names too,
    // but no trailing controls, so two columns still leave 281 px of a 347 px
    // row to the name (42 of 62 characters, against the layout list's 12) —
    // and one column does not FIT: 470 px of content in the 377 px card a
    // 915x412 phone allows, which is BUG A. See client/panels.css.
    card.className = "lay-card card-columns";
    const h = document.createElement("h2");
    h.textContent = "Take one window out";
    const sub = document.createElement("p");
    sub.className = "lay-sub";
    // The consequence, in the panel's own words — the ✕ chooser's rule
    // (2026-08-08): an act names what it does to HIS windows, so the harmless
    // one is never mistaken for the one that cannot be undone.
    sub.textContent = `${lay.name} — tap the one to take out. `
      + "It stays open on the PC, exactly where it is.";
    card.append(h, sub);
    const titles = Array.isArray(lay.member_titles) ? lay.member_titles : [];
    for (let k = 0; k < (lay.members || 1); k++) {
      // EJECT — the twin act beside "take out" (task 197b): the same window,
      // pulled into its OWN new layout instead of left standing on the desk.
      // A small trailing icon button, the same `.lay-ratio` treatment the
      // row's ⚙/shape badges already wear, so it reads as ONE MORE act on
      // this row rather than a second row style.
      const eject = document.createElement("button");
      eject.type = "button";
      eject.className = "lay-ratio lay-eject";
      eject.innerHTML = svg("ejectwin");
      eject.setAttribute("aria-label", "Move to its own layout");
      keepFocus(eject, () => {
        closeLayoutPanel();
        send({ type: "layout_member_eject", index, member: k });
        showLayLoading("Moving the window…");
      });
      card.appendChild(layRow(
        // A server too old to send `member_titles` still gets a usable
        // panel: the CELL is the picture, the title is only the word.
        titles[k] || `Window ${k + 1}`,
        { draw: gridIconSvg(lay.members, lay.grid, lay.orient,
                            { cell: k, className: "lay-cell-ico" }) },
        false,
        () => {
          closeLayoutPanel();
          const msg = { type: "layout_member_remove", index, member: k };
          if (grid) msg.grid = grid;
          send(msg);
          // The survivors are re-placed into the new shape, so real windows
          // move on the PC — the cube covers it, exactly as for a reshape.
          showLayLoading("Rearranging the layout…");
        }, eject));
    }
    if (choices.length) {
      const lbl = document.createElement("p");
      lbl.className = "lay-sub";
      lbl.textContent = "The three that stay — where does the single window go?";
      const row = document.createElement("div");
      row.className = "lay-row";
      choices.forEach((g) => row.appendChild(gridChip(
        g, lay.orient, g === grid, () => { grid = g; draw(); })));
      card.append(lbl, row);
    }
    const actions = document.createElement("div");
    actions.className = "lay-actions";
    // Back one step — the ⚙ sheet, which is where this panel is reached from
    // (the row's shape badge is a SHORTCUT into the same chain, task 175, so
    // backing out of it lands on that layout's sheet and not on the list).
    actions.appendChild(layChip("Cancel", false, () => openLayoutSettings(index)));
    card.appendChild(actions);
    layPanel.appendChild(card);
  };
  draw();
}
