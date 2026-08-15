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
  // The source radial (task 158) is not inside `layPanel` — it floats beside
  // the corner button — so closing the panel does not take it with it.
  closeMiniRadial();
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

// THE PAD'S SHORT PRESS, and the same act the Layout button performs when a
// session is already live (task 186: "L2 tap = arm tap-pick as today, HOLD =
// this radial"). It is a FUNCTION and not a copy of the handler above: the
// controller must never grow a second creation path — constraint 9, the rule
// that keeps `buttonPress` the one activator.
function layoutTapSource() {
  if (creating || layoutArm) {
    cancelCreation();
    return;
  }
  startTapSource();
}

// TAP HAS ONE MEANING EVERYWHERE (owner correction 2026-08-13, overruling the
// same day's earlier "claim" reading of his ballot vote): the next tap on the
// screen ALWAYS starts a new layout seeded with what is under the finger —
// whether or not a layout happens to be focused. His own words on why the
// other reading cannot mean anything: "tap in an already-created layout
// claims a window for that layout — what are you trying to say? If I tapped
// on something in that layout it IS ALREADY in that layout." Inside a
// focused layout the only thing under the finger that is NOT already a
// member is a content TAB inside one — and tearing a tab into its own window
// is exactly what this ordinary flow already does. See `handleLayoutOffer`
// below for the one new case this leaves: a tap that lands on a member
// window itself, with no tab, has nothing to create.
function startTapSource() {
  creating = newCreation("tap");
  armNextTap();
}

function startListSource() {
  creating = newCreation("list");
  refreshNewlayButton();
  closeLayoutPanel();
  // LOADING: CUBE — a pure enumeration — nothing on the PC moves
  showLayLoading("Collecting windows and tabs…", LOADING_CUBE);
  send({ type: "layout_list" });
}


function newCreation(source) {
  return {
    source,                 // "list" | "tap" | "new" | "recent"
    entries: null,          // list source: [{kind, hwnd, title, process, icon, tab?, x?, y?, group}]
    inLayout: null,         // name of the focused layout whose tabs lead the list (4B)
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

// THE TWO SOURCES ARE A RADIAL BESIDE THE BUTTON, NOT A CARD OVER THE SCREEN
// (owner 2026-08-09, task 158, with his sketch). They used to be a full-screen
// modal with a heading, a question and two big chips — a whole card raised to
// ask a question with two answers, both of which he already knows. His
// instruction was that a button carrying two or three jobs simply drops its
// options beside itself:
//   lang-ok: owner quote
//   "kada neki button kao što su ti gornji ima dve tri funkcije … onako pored
//    njega spuste dve te opcije"
// BESIDE THE BUTTON, in the directions the analog stick can pick without
// ambiguity — the geometry and its reason live once, in client/chrome.js →
// openMiniRadial. Each option is a real button with its icon and its words,
// exactly like every other button on this page — the same `makeButton`, so it
// can never drift from them.
//
// CANCELLING IS THE BUTTON ITSELF, and that is why no Cancel chip came across:
// the radial's backdrop is the whole screen, a tap anywhere outside the
// options closes it, and Layout's own press already cancels an armed session
// (see the handler above). A modal needed a Cancel; buttons on the picture do
// not.
//
// THREE SOURCES, AND THEY OPEN AS A FAN AROUND THE BUTTON (owner decision
// 2026-08-12, superseding task 186's centered ring and task 228's fourth
// option). Between 2026-08-09 and now this radial stood in the MIDDLE of the
// screen behind a veil, because three options had felt like the category
// wheel's job; he reversed that after using it — the options belong beside the
// button they came out of, exactly like the Hide button's two modes, in ALL
// situations (his own check: it fits phone portrait too, since the Layout
// button's row stands above the picture). So: **New → EAST, Tap → SOUTH-EAST,
// List → SOUTH**, and THE ORDER OF THIS ARRAY IS THAT MAPPING — `chrome.js`
// hands option i the i-th direction of the fan, and the controller points at
// the direction the option really ended up at (no second table to keep in
// step).
//
// **Recent** left the radial in the same decision. Its panel, its
// `layout_recent` messages and the PC's whole history file stay exactly as
// they are (`openRecentHistoryPanel` below) — what he dropped is the entry
// point on this radial, which is why nothing about the protocol changed.
//
// ONE WORD EACH, AND THE DRAWING CARRIES IT (his ruling ~20:25, task 184):
// "the SVG matters more than the word — users learn the radial after a couple
// of uses or from the guide". So New / Tap / List, each with a face of its own
// in icons.js.
function openSourceChooser() {
  openMiniRadial(newlayBtn, [
    { icon: "winplus", label: "New", onPick: openRecentsPanel },
    { icon: "tapwin", label: "Tap", onPick: startTapSource },
    { icon: "listwin", label: "List", onPick: startListSource },
  ]);
}


// ── RECENT: A LAYOUT ALREADY BUILT BEFORE (owner report 2026-08-11, task
// 228) ───────────────────────────────────────────────────────────────────
//
// Unlike Tap/List/New, nothing here is a slot picked one at a time — the
// SERVER remembers every layout it has ever created
// (`server/layout_history.py`, across restarts) and re-creates one whole,
// matching its remembered members against whatever stands open right now.
// This file only asks for the list and shows it; the match/create/toast all
// happen server-side (`layout_api.layout_recent_use`), because the desk can
// change in the seconds between the ask and the tap and only the server ever
// sees it fresh — the same reasoning `openRecentsPanel`'s New source lives
// by, one door further in.
//
// IT IS NOT ON THE BIRTH RADIAL ANY MORE (owner decision 2026-08-12): the fan
// carries New / Tap / List and nothing else. The panel and the whole
// `layout_recent` protocol behind it were deliberately KEPT — only the entry
// point was withdrawn, so the next door onto this list costs one call and no
// server work.
async function openRecentHistoryPanel() {
  if (!creating) creating = newCreation("recent");
  refreshNewlayButton();
  closeLayoutPanel();
  // LOADING: CUBE — a pure read of the creation log
  showLayLoading("Reading the layout history…", LOADING_CUBE);
  send({ type: "layout_recent" });
}

// Answered by `layout_recent` (connection.js routes it here). An empty
// history — a fresh install, or a history file nothing could be read from —
// is NAMED, never a blank card, the same rule `openRecentsPanel` follows.
function handleLayoutRecent(msg) {
  hideLayLoading();
  if (!creating || creating.source !== "recent") return;
  const entries = msg.entries || [];
  if (!entries.length) {
    cancelCreation(true);
    showToast("No layout has been created on this PC yet");
    return;
  }
  renderRecentHistoryPanel(entries);
}

function renderRecentHistoryPanel(entries) {
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card card-columns lc-panel";
  const scrollWrap = document.createElement("div");
  scrollWrap.className = "lc-scrollwrap";
  card.appendChild(scrollWrap);
  const h = document.createElement("h2");
  h.textContent = "Recent layouts";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Re-creates it from whatever of its windows is open now.";
  scrollWrap.append(h, sub);

  const rows = document.createElement("div");
  rows.className = "lc-rows lc-scroll";
  entries.forEach((e) => rows.appendChild(recentHistoryRow(e)));
  scrollWrap.appendChild(rows);

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, () => cancelCreation()));
  card.appendChild(actions);
  layPanel.appendChild(card);
}

// One row per history entry. `keepRowTap` (task 227b), not `keepFocus` — this
// list scrolls exactly like the other two creation lists and must not steal
// that scroll either.
function recentHistoryRow(e) {
  const row = document.createElement("div");
  row.className = "lay-item lc-row";
  const main = document.createElement("button");
  main.type = "button";
  main.className = "lay-item-main";
  main.innerHTML = svg("recentwin");
  const name = document.createElement("span");
  name.textContent = e.name;
  main.appendChild(name);
  if (e.project) {
    const note = document.createElement("small");
    // Task 233 (grader flag c): `.lc-recent-note` caps the trailing fact's
    // own width and ellipses IT instead of letting an unbounded note (e.g.
    // "used 5 days ago") eat the room a real project/window name needs —
    // `.lay-item-main span` already shrinks the name first, so a long note
    // was squeezing the one thing he actually reads off this row.
    note.className = "lc-note lc-recent-note";
    note.textContent = e.project;
    main.appendChild(note);
  }
  keepRowTap(main, () => useRecentHistory(e));
  row.appendChild(main);
  return row;
}

// The tap. Nothing is built here — `layout_recent_use` on the server does
// the matching, the creation and the "N of M found" toast; this side only
// asks and shows the same loading cube every other creation flow shows
// while the PC works.
function useRecentHistory(e) {
  closeLayoutPanel();
  // LOADING: FULL — re-creating a layout really places windows
  showLayLoading(`Re-creating ${e.name}…`, LOADING_FULL);
  send({ type: "layout_recent_use", id: e.id });
  creating = null;
  refreshNewlayButton();
}

function armNextTap() {
  creating.awaitingTap = true;
  layoutArm = true;
  refreshNewlayButton();
  closeLayoutPanel();
  showToast("Tap a window or tab on the screen…");
}

// The row activator (`keepRowTap`) used to live here, where task 227b fixed
// this panel's own rows. It is client/row-tap.js now — the owner's 2026-08-15
// report is the same bug in a card three files away, and a rule kept inside
// one panel's file is a rule the next panel's author never reads.

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
  keepRowTap(main, opts.onTap);
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
// A TAP THAT LANDED ON A MEMBER'S OWN WINDOW HAS NOTHING TO CREATE (owner
// correction 2026-08-13): everything a focused layout shows on the phone is
// ALREADY a member of it — the only thing under the finger that is not is a
// content TAB inside one, and `msg.tab` is exactly how the server already
// tells the two apart (`uia.tab_at` beside `window_at` in `layout_pick`).
// `member_hwnds` rides `layout_state` per layout ([Layout Registry]
// server/layout_registry.py) for precisely this question — a plain fact,
// not a guess, and never re-derived from anything the phone remembers on
// its own.
function tapTargetIsExistingMember(msg) {
  if (!msg.target || msg.tab) return false;         // a tab is never a member
  if (layoutActive === null) return false;           // the desktop has none
  const lay = layouts[layoutActive];
  return !!(lay && lay.member_hwnds && lay.member_hwnds.includes(msg.target.hwnd));
}

function handleLayoutOffer(msg) {
  hideLayLoading();
  layoutArm = false;
  if (tapTargetIsExistingMember(msg)) {
    // Nothing armed survives this — a plain statement of fact, not an error,
    // and never a swallowed tap (his own "or some other warning" instruction).
    creating = null;
    refreshNewlayButton();
    showToast("That window is already in this layout — there's nothing to create.");
    return;
  }
  if (!creating) creating = newCreation("tap");
  if (msg.entries) {
    creating.entries = msg.entries;
    // The layout whose own tabs lead the list, or null at the desktop (4B).
    creating.inLayout = msg.in_layout || null;
  } else if (msg.target) {
    creating.slots.push(slotFromOffer(msg));
    creating.awaitingTap = false;
  }
  refreshNewlayButton();
  renderCreationPanel();
}

// ── AN APP HE JUST OPENED IS ALREADY A SLOT (owner request 2026-08-09, task
// 185) ──────────────────────────────────────────────────────────────────────
//
// He double-clicks an .xlsx through the stream, Excel opens, and the phone
// asks "layout with it?" (the chip lives in window-offer.js; the PC's side of
// the question is server/layout_popup.py). Saying yes lands HERE — in the
// creation panel he already knows, pre-seeded with that window, with the usual
// single/grid and portrait/landscape choices. There is no second wizard: the
// only thing task 185 adds to this file is a way IN that starts with a slot.
function startFromWindow(win) {
  if (!win || !win.hwnd) return;
  creating = newCreation("new");
  creating.slots.push({
    hwnd: win.hwnd, title: win.title || "", process: win.process || "",
    icon: win.icon || null, agents: win.agents || [], tab: null,
    x: 0.5, y: 0.5,
  });
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
  // THE FOOTER IS PINNED, THE LIST SCROLLS (owner report 2026-08-11, task 227a
  // — with a long window list Cancel/Create scrolled off-screen with it,
  // because `.lay-card` is one block that scrolls as a whole: the list's own
  // 38vh cap does not stop the CARD'S total content from exceeding 92vh once
  // a chosen row, the name field, the shape rows and a tall list all stand
  // above it). Every piece except Cancel/Create now lives in `.lc-scrollwrap`
  // (`box`/`listInto` point INTO it, never at `card` directly), which is the
  // one thing that scrolls; `actions` stays a direct child of `card`, appended
  // last, so it can never be scrolled past. `.lc-panel` makes the card itself
  // a fixed-height flex column instead of a single scrolling block — see
  // layout-create.css. The short-landscape multicol reflow (panels.css) turns
  // the wrap back into `display:contents` there, so the two-column
  // fragmentation this card also does is untouched.
  const scrollWrap = document.createElement("div");
  scrollWrap.className = "lc-scrollwrap";
  // A SCROLLING LIST MAY NOT LIVE INSIDE A COLUMNED CARD (found 2026-08-09 by
  // photographing this panel at 915x412 — the round's own verification). The
  // landscape reflow of task 172 made this card a `column-count: 2`
  // FRAGMENTAINER, and the list inside it is a scroll container: the fourth of
  // six rows came out sliced through the middle, 10 px above the "Shape:"
  // block in the same column, with rows five and six nowhere and no scrollbar
  // to say they existed. Measured in a real Chromium: a scroller inside a
  // multicol is not clipped by its own box at all — `overflow: hidden` does
  // not clip it either, and the same staging with twenty windows put fourteen
  // rows off the bottom of the screen entirely, unreachable, while the card
  // reported no scroll of its own to make.
  //
  // The columns are still RIGHT for this panel — it is the tallest the phone
  // has, and one column does not fit it in either landscape size (630 px of
  // content in a 377 px card at 915x412, 749 px in 734 px on a tablet), which
  // is BUG A with 155 px and 520 px of width standing idle. So the card keeps
  // two columns and stops being a fragmentainer: an explicit FLEX split, whose
  // children are ordinary boxes a scroller works inside. The list gets a whole
  // column of its own height instead of an arbitrary 38vh, its own header
  // finally stands above it (the multicol had left the caption in the LEFT
  // column, introducing a list on the right), and the actions row sits under
  // both columns so Create can never fall below a fold.
  //
  // ONLY the list source is split. A creation session with no list (the "Tap a
  // window" flow) is short, has nothing that scrolls, and keeps the measured
  // `card-columns` behaviour exactly — a split there would leave one column
  // empty, which is the opposite defect.
  const split = c.source === "list" && !!c.entries;
  card.className = (split ? "lay-card lc-split" : "lay-card card-columns") + " lc-panel";
  card.appendChild(scrollWrap);
  // Where the two halves go. Outside the split these are the scroll wrap
  // itself, so the order and the markup are byte-for-byte what they were.
  const cols = document.createElement("div");
  const side = document.createElement("div");
  const listBox = document.createElement("div");
  const box = split ? side : scrollWrap;
  const listInto = split ? listBox : scrollWrap;
  if (split) {
    cols.className = "lc-cols";
    side.className = "lc-side";
    listBox.className = "lc-main";
    cols.append(side, listBox);
    scrollWrap.appendChild(cols);
  }

  const h = document.createElement("h2");
  h.textContent = "New layout";
  box.appendChild(h);

  // chosen slots — tap one to remove it
  if (c.slots.length) {
    const sub = document.createElement("p");
    sub.className = "lay-sub";
    sub.textContent = `Chosen (${c.slots.length}/${cellsNeeded()}) — tap to remove:`;
    box.appendChild(sub);
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
    box.appendChild(row);
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
  box.append(nameLbl, nameIn);

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
  box.appendChild(modeRow);
  // …and the absence is EXPLAINED. A row that silently holds fewer chips than
  // last time reads as a bug; the number is the same one the cap is made of.
  if (avail !== null && avail < 4) {
    const capLbl = document.createElement("p");
    capLbl.className = "lay-sub";
    capLbl.textContent = avail <= 1
      ? "Only one window is open on the PC — a grid needs at least two."
      : `Only ${avail} windows and tabs are open on the PC — a bigger grid ` +
        "needs more of them.";
    box.appendChild(capLbl);
  }

  if (c.mode === "grid" && GRID_CELLS[c.grid] === 3) {
    const arrLbl = document.createElement("p");
    arrLbl.className = "lay-sub";
    arrLbl.textContent = "Where does the single window go?";
    const arrRow = document.createElement("div");
    arrRow.className = "lay-row";
    GRID_THREE.forEach((g) => arrRow.appendChild(
      gridChip(g, c.orient, c.grid === g, () => { c.grid = g; renderCreationPanel(); })));
    box.append(arrLbl, arrRow);
  }

  if (c.source === "list" && c.entries) {
    const hint = document.createElement("p");
    hint.className = "lay-sub";
    // The header carries the SAME number the cap is made of — what is on the
    // PC and what can actually go in a layout are different quantities (a
    // three-tab window is four rows and three members), and the panel says
    // the one the choice above is limited by.
    // "on the PC" is wrong the moment there are two groups: it sat directly
    // above a heading that says "In this layout", and an intro that
    // contradicts the first thing under it is worse than no intro. Found by
    // PHOTOGRAPHING the two-group state — the wording read fine in the diff
    // and only the picture put the two lines side by side.
    const what = c.inLayout ? "Windows and tabs" : "Windows and tabs on the PC";
    hint.textContent = avail === null
      ? `${what}:` : `${what} — ${avail} can go in a layout:`;
    listInto.appendChild(hint);
    // A minimized window enumerates NO tabs (Windows reports it as having no
    // size at all), so the list would silently show fewer rows for it than it
    // will after a restore. It says so on the row and here (owner 2026-08-09,
    // task 167) — a list that quietly changes shape is what this replaces.
    if (c.entries.some((e) => e.tabs_hidden)) {
      const note = document.createElement("p");
      note.className = "lay-sub";
      note.textContent = "A minimized window cannot show its tabs — restore " +
        "it on the PC to pick them.";
      listInto.appendChild(note);
    }
    const list = document.createElement("div");
    list.className = "lc-rows lc-scroll";
    // TWO GROUPS WHEN THE LIST WAS ASKED FOR FROM INSIDE A LAYOUT (owner
    // request 2026-08-13, his point 4B): the tabs of the layout he is in come
    // first, then the desktop. Driven by each entry's own `group` and not by
    // its position — an order is not something the page can verify, and a list
    // that quietly changes meaning is the failure task 167 was about. With no
    // layout focused the server sends one group and this emits no heading at
    // all, so the desktop list looks exactly as it always has.
    let group = null;
    c.entries.forEach((e) => {
      if (e.group && e.group !== group) {
        group = e.group;
        if (c.inLayout) {
          const head = document.createElement("p");
          head.className = "lay-sub lc-group";
          head.textContent = group === "layout"
            ? `In this layout — ${c.inLayout}:` : "Elsewhere on the PC:";
          list.appendChild(head);
        }
      }
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
    listInto.appendChild(list);
  } else if (c.source === "tap" && c.slots.length < cellsNeeded()) {
    const row = document.createElement("div");
    row.className = "lay-row";
    row.appendChild(layChip(`Tap window ${c.slots.length + 1} of ${cellsNeeded()}`,
                            false, armNextTap));
    box.appendChild(row);
  } else if (c.source === "new" && c.slots.length < cellsNeeded()) {
    // The New source can fill a grid too: each cell is another thing opened.
    // It is the SAME chip the tap source shows, so a half-built grid looks the
    // same however its members are being found.
    const row = document.createElement("div");
    row.className = "lay-row";
    row.appendChild(layChip(`Open window ${c.slots.length + 1} of ${cellsNeeded()}`,
                            false, openRecentsPanel));
    box.appendChild(row);
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
  box.append(orientLbl, orientRow);

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
    // LOADING: FULL — the server is extracting tabs and placing windows
    showLayLoading("Arranging the windows…", LOADING_FULL);
  });
  if (!ready) {
    create.classList.add("lc-off");
    create.setAttribute("aria-disabled", "true");
  }
  actions.appendChild(create);
  card.appendChild(actions);
  layPanel.appendChild(card);
}
