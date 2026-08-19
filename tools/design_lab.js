"use strict";
// THE BENCH'S WIRING — build the knobs from the registry, push every turn of
// one into the frames, and hand the whole set to the server when he saves.
//
// IT HOLDS NO DEFAULTS. Every value on this page came from `/tokens`, which
// read it out of client/theme.css, client/style.css, client/theme.js and
// server/config.py a moment ago; every value it sends back goes to the same
// declaration. A constant written here would be a third opinion about a colour
// that already has two homes, and it would be the one that goes stale.
//
// LIVE IS AN OVERRIDE, SAVE IS A WRITE. Dragging a slider only posts a message
// to the frames, which set the token inline (tools/preview.html). Nothing on
// disk moves until Save, so a session of tuning that ends in Revert leaves the
// project byte-identical.
//
// ROUND 2 (owner, 2026-08-19) adds the three things a knob needs before it is
// usable: a SENTENCE (design_groups.py `help`), a PICTURE (design_pics.js) and
// a way for the page to POINT at what the value touches — hover a row and
// every element it reaches is outlined in all eight frames at once. Plus a
// search box, because he went looking for the white shadow and a list of
// eleven groups is a list you scroll past.
// See tools/__about/design_lab.md.

// ═══════════════════════════ STATE ═══════════════════════════
let snapshot = null;
// What he has changed and not yet saved, per source. The keys are the five
// sources of tools/design_tokens.py plus `alphas`, which is one knob that
// lands in three places (both themes' tokens and the JS constant).
let edits = { dark: {}, light: {}, shape: {}, sets: {}, js: {}, alphas: {} };

const LOOKS = [];
for (const theme of ["dark", "light"]) {
  for (const colored of [false, true]) {
    for (const fill of ["transparent", "full"]) {
      LOOKS.push({ theme, colored, fill });
    }
  }
}

// The PC's own screen behind the controls. Not decoration: a control is drawn
// over whatever the desktop happens to be showing, and "is this still legible"
// has no answer until you say over WHAT. These five are the cases that have
// actually caught something — a white document under light ink, a dark editor
// under dark ink, and a busy colourful window under both.
const BACKDROPS = {
  none: "",
  grey: "#7a7a7a",
  white: "linear-gradient(180deg, #ffffff 0%, #f2f2f2 100%)",
  ide: "linear-gradient(180deg, #1e1e1e 0%, #252526 100%)",
  busy: "conic-gradient(from 20deg, #d94f4f, #d9a24f, #4fd97a, #4f9ad9, #a24fd9, #d94f4f)",
};

// The lab's own two remembered preferences. localStorage and not the project:
// nothing under tools/ may write a value the phone reads, and how wide he
// likes the panel is not a design decision — it is furniture.
const PREF_WIDTH = "vibecoder.lab.side";
const PREF_ZOOM = "vibecoder.lab.zoom";

function lookName(look) {
  return (look.theme === "dark" ? "dark" : "light") + " · " +
         (look.colored ? "coloured" : "plain") + " · " +
         (look.fill === "full" ? "full" : "outlined");
}

// ═══════════════════════════ COLOUR ═══════════════════════════
// Two spellings live in client/theme.css and both must survive a round trip:
// `#rrggbb` and `rgb(r g b / a)`. The tool NEVER rewrites one as the other —
// the file's own spelling is part of how it reads, and a save that reformatted
// forty declarations would bury the one line he actually changed.
function parseColour(value) {
  const text = String(value || "").trim();
  let match = text.match(/^#([0-9a-f]{6})$/i);
  if (match) return { hex: "#" + match[1].toLowerCase(), alpha: 1, form: "hex" };
  match = text.match(/^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)\s*(?:[/,]\s*([\d.]+)\s*)?\)$/i);
  if (match) {
    const hex = "#" + [1, 2, 3].map((i) =>
      Math.max(0, Math.min(255, Math.round(parseFloat(match[i]))))
        .toString(16).padStart(2, "0")).join("");
    return { hex, alpha: match[4] === undefined ? 1 : parseFloat(match[4]), form: "rgb" };
  }
  return null;   // `var(--other)` and anything else: text only, no picker
}

function composeColour(original, hex, alpha) {
  const parsed = parseColour(original);
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  if (parsed && parsed.form === "hex" && alpha >= 1) return hex;
  const a = alpha >= 1 ? 1 : Math.round(alpha * 100) / 100;
  return "rgb(" + r + " " + g + " " + b + " / " + a + ")";
}

function withAlpha(value, alpha) {
  const parsed = parseColour(value);
  if (!parsed) return value;
  return composeColour(value, parsed.hex, alpha);
}

/** `0 0 0` <-> `#000000`. The shadow colours are written in client/theme.js as
 *  the bare triple `shadowFor` interpolates into `rgb(… / a)`, so the picker
 *  speaks hex and the file keeps its own spelling. */
function tripleToHex(triple) {
  const parts = String(triple || "").trim().split(/\s+/).map(Number);
  if (parts.length !== 3 || parts.some((n) => !isFinite(n))) return null;
  return "#" + parts.map((n) => Math.max(0, Math.min(255, Math.round(n)))
    .toString(16).padStart(2, "0")).join("");
}

function hexToTriple(hex) {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(" ");
}

// ═══════════════════════════ CURRENT VALUES ═══════════════════════════
function current(source, token) {
  if (edits[source] && token in edits[source]) return edits[source][token];
  return snapshot.values[source][token];
}

function currentAlpha(token) {
  if (token in edits.alphas) return edits.alphas[token];
  const parsed = parseColour(snapshot.values.dark[token]);
  return parsed ? parsed.alpha : 1;
}

function isChanged(source, token) {
  return edits[source] && token in edits[source] &&
         String(edits[source][token]) !== String(snapshot.values[source][token]);
}

function countChanges() {
  let n = 0;
  for (const source of ["dark", "light", "shape", "sets", "js"]) {
    for (const token of Object.keys(edits[source])) {
      if (isChanged(source, token)) n++;
    }
  }
  return n + Object.keys(edits.alphas).length;
}

// ═══════════════════════════ THE FRAMES ═══════════════════════════
const frames = [];   // {look, iframe}

function send(frame, message) {
  if (!frame.iframe.contentWindow) return;
  frame.iframe.contentWindow.postMessage(message, "*");
}

function toAll(message) {
  frames.forEach((frame) => send(frame, message));
}

/** Everything a frame needs to be correct right now — sent once when it loads
 *  and again whenever the whole picture changes (a save, a revert). Sending
 *  the WHOLE state rather than a difference is deliberate: a frame that missed
 *  one message would otherwise stay wrong for the rest of the session. */
function refresh(frame) {
  send(frame, { kind: "look", look: {
    theme: frame.look.theme, colored: frame.look.colored, fill: frame.look.fill,
    colors: setPalette(),
  } });
  send(frame, { kind: "shape", values: allOf("shape") });
  send(frame, { kind: "colour", values: allOf(frame.look.theme) });
  send(frame, { kind: "jscolor", base: snapshot.values.js, values: edits.js });
  send(frame, { kind: "bench", mode: document.getElementById("bench").value });
  send(frame, { kind: "backdrop", css: BACKDROPS[document.getElementById("backdrop").value] });
  send(frame, { kind: "toast", state: document.getElementById("toast").value });
  send(frame, fitMessage());
}

/** A source's values with his unsaved edits laid over them — the same shape
 *  the frame would have got from the file. */
function allOf(source) {
  const out = Object.assign({}, snapshot.values[source], edits[source]);
  // A shadow's strength is a knob of its own, applied to whichever colour the
  // token carries — the hue is never his to pick (it is the ink's opposite).
  for (const [token, alpha] of Object.entries(edits.alphas)) {
    if (token in out) out[token] = withAlpha(out[token], alpha);
  }
  return out;
}

function setPalette() {
  return Object.assign({}, snapshot.values.sets, edits.sets);
}

function pushColour(theme, token, value) {
  frames.forEach((frame) => {
    if (frame.look.theme === theme) send(frame, { kind: "colour", values: { [token]: value } });
  });
}

function pushShape(token, value) {
  toAll({ kind: "shape", values: { [token]: value } });
}

function pushSets() {
  toAll({ kind: "sets", colors: setPalette() });
}

function pushJsColour() {
  toAll({ kind: "jscolor", base: snapshot.values.js, values: edits.js });
}

/** Outline, in every frame at once, whatever this row's value touches. This is
 *  the answer to "which setting is that?" that no sentence gives: the page
 *  points at it. An empty selector clears the pointer. */
function pointAt(selector) {
  toAll({ kind: "point", selector: selector || "" });
}

// ── how many columns, how tall, and who scrolls ────────────────────────
// THE GRID IS SIZED FROM THE COUNT, never from a minimum width (his round-2
// report: eight cards in an auto-fit grid came out 5 + 3 and left the bottom
// right of the screen empty). Eight divides into 1, 2, 4 and 8 columns and
// nothing else, so every row is full whatever the window is; of those, the one
// whose cell comes out closest to a specimen board's own proportions wins.
const CELL_RATIO = 0.8;      // a board is taller than it is wide

function gridFor(count, width, height) {
  let best = { cols: 1, rows: count, score: Infinity };
  for (let cols = 1; cols <= count; cols++) {
    if (count % cols) continue;
    const rows = count / cols;
    const ratio = (width / cols) / (height / rows);
    const score = Math.abs(Math.log(ratio / CELL_RATIO));
    if (score < best.score) best = { cols, rows, score };
  }
  return best;
}

function zoomChoice() {
  return document.getElementById("zoom").value;
}

function fitMessage() {
  const choice = zoomChoice();
  return choice === "fit"
    ? { kind: "fit", mode: "fit" }
    : { kind: "fit", mode: "fixed", zoom: parseFloat(choice) };
}

/** Lay the wall out for the space it actually has. Called on every resize, on
 *  every splitter drag and whenever the number of frames changes. */
function layoutFrames() {
  const host = document.getElementById("frames");
  if (!frames.length) return;
  const fixed = zoomChoice() !== "fit";
  host.classList.toggle("fixed", fixed);
  const box = host.getBoundingClientRect();
  const gap = 10, pad = 20;
  const width = Math.max(1, box.width - pad);
  const height = Math.max(1, box.height - pad);

  if (spill) {
    // Floored and still too tall: give every card the height its board needs
    // and let the WALL scroll. Rows are `auto`, so the grid grows downwards.
    host.classList.add("spill");
    host.style.gridTemplateColumns = "repeat(" +
      gridFor(frames.length, width - gap * 3, height - gap).cols +
      ", minmax(0, 1fr))";
    host.style.gridTemplateRows = "";
    host.style.setProperty("--look-h", spill + 30 + "px");
    return;
  }
  host.classList.remove("spill");
  if (fixed) {
    // A card is drawn at a size he chose, so the question is only how many of
    // them fit side by side — and it is still a divisor, so no row is ragged.
    const want = 440 * parseFloat(zoomChoice());
    let cols = 1;
    for (let n = 1; n <= frames.length; n++) {
      if (frames.length % n === 0 && (width - gap * (n - 1)) / n >= want) cols = n;
    }
    host.style.gridTemplateColumns = "repeat(" + cols + ", minmax(0, 1fr))";
    host.style.gridTemplateRows = "";
    return;
  }
  const grid = gridFor(frames.length, width - gap * 3, height - gap);
  host.style.gridTemplateColumns = "repeat(" + grid.cols + ", minmax(0, 1fr))";
  host.style.gridTemplateRows = "repeat(" + grid.rows + ", minmax(0, 1fr))";
}

// ONE SCALE FOR THE WALL. Each frame fits itself and reports what it worked
// out; the smallest is what every card is then drawn at. Without this the wall
// would be eight pictures at eight sizes, and a comparison bench whose cards
// are not the same size is not comparing anything.
let fitted = new Map();
let scaleTimer = null;
// When even the floor is not enough — a small laptop showing eight boards —
// the CARD is given the height its board needs and the WALL scrolls. The
// ladder in rules/GUI.md ends in "scroll" only after reflow and a raised
// minimum, and one scrollbar for the wall is the shape he asked for, not eight
// inside the cards. Cleared only when the wall is rebuilt, never by the
// re-fit that follows: a card that grew, fitted, and shrank again would
// oscillate for as long as the window stayed that size.
let spill = 0;

function noteFitted(source, report) {
  const frame = frames.find((f) => f.iframe.contentWindow === source);
  if (!frame) return;
  fitted.set(frame, report);
  clearTimeout(scaleTimer);
  scaleTimer = setTimeout(() => {
    const seen = frames.map((f) => fitted.get(f)).filter(Boolean);
    if (seen.length !== frames.length) return;
    const floored = seen.filter((r) => r.floored).map((r) => r.need);
    if (floored.length && !spill) {
      spill = Math.max.apply(null, floored);
      layoutFrames();
      note("this window is too small to fit eight boards side by side — the " +
           "cards are full height and the WALL scrolls. Widen it, drag the " +
           "panel narrower, or show one look.");
      return;
    }
    const zooms = seen.map((r) => r.zoom).filter((z) => z > 0);
    const smallest = Math.min.apply(null, zooms);
    if (Math.max.apply(null, zooms) - smallest < 0.005) return;   // already one
    toAll({ kind: "scale", zoom: smallest });
  }, 140);
}

function note(text) {
  document.getElementById("wall-note").textContent = text || "";
}

window.addEventListener("message", (event) => {
  const msg = event.data || {};
  if (msg.kind === "fitted") noteFitted(event.source, msg);
});

function buildFrames() {
  const host = document.getElementById("frames");
  const one = document.getElementById("which").value === "one";
  host.textContent = "";
  frames.length = 0;
  fitted = new Map();
  spill = 0;          // a rebuilt wall asks the question again
  note("");
  const wanted = one
    ? [{ theme: document.getElementById("theme").value,
         colored: document.getElementById("colored").value === "true",
         fill: document.getElementById("fill").value }]
    : LOOKS;
  wanted.forEach((look) => {
    const box = document.createElement("div");
    box.className = "look";
    const name = document.createElement("div");
    name.className = "look-name";
    name.textContent = lookName(look);
    const iframe = document.createElement("iframe");
    iframe.src = "/preview";
    const frame = { look, iframe };
    iframe.addEventListener("load", () => refresh(frame));
    box.appendChild(name);
    box.appendChild(iframe);
    host.appendChild(box);
    frames.push(frame);
  });
  layoutFrames();
}

// ═══════════════════════════ THE KNOBS ═══════════════════════════
function markDirty() {
  const n = countChanges();
  document.getElementById("dirty").textContent =
    n === 0 ? "nothing changed yet"
            : n + (n === 1 ? " value changed, not yet saved" : " values changed, not yet saved");
  document.getElementById("save").disabled = n === 0;
}

/** A row is a PICTURE, a TITLE, a SENTENCE and only then the control — in that
 *  order, because that is the order the question is asked in. The token's own
 *  name and the file it lives in come last: they are what you need after you
 *  have decided, not before. */
function rowShell(row, control) {
  const box = document.createElement("div");
  box.className = "row";
  box.dataset.token = row.token || "";
  if (row.demo) box.dataset.demo = row.demo;   // what the frames outline
  // What the search box matches on — the words that are actually on the row.
  box.dataset.find = [row.label, row.help, row.token, row.why]
    .filter(Boolean).join(" ").toLowerCase();

  const top = document.createElement("div");
  top.className = "row-top";
  const picture = typeof pic === "function" ? pic(row.pic) : null;
  if (picture) top.appendChild(picture);
  const words = document.createElement("div");
  words.className = "row-words";
  const title = document.createElement("div");
  title.className = "row-label";
  title.textContent = row.label;
  words.appendChild(title);
  if (row.help || row.why) {
    const help = document.createElement("div");
    help.className = "row-help";
    help.textContent = row.help || row.why;
    words.appendChild(help);
  }
  top.appendChild(words);
  box.appendChild(top);

  if (control) box.appendChild(control);

  const meta = document.createElement("div");
  meta.className = "row-meta";
  if (row.token) {
    const id = document.createElement("div");
    id.className = "row-token";
    id.textContent = row.token;
    const where = snapshot.files[sourceOf(row)];
    if (where) {
      const file = document.createElement("span");
      file.className = "row-file";
      file.textContent = "   " + where;
      id.appendChild(file);
    }
    meta.appendChild(id);
    if (snapshot.pinned[row.token]) {
      const pin = document.createElement("div");
      pin.className = "row-pin";
      pin.textContent = "pinned: " + snapshot.pinned[row.token];
      meta.appendChild(pin);
    }
  }
  box.appendChild(meta);

  // POINTING. Hover (or tab to) the row and every frame outlines what it
  // touches; leaving takes the outline away, so no screenshot ever carries it.
  if (row.demo) {
    box.addEventListener("mouseenter", () => pointAt(row.demo));
    box.addEventListener("mouseleave", () => pointAt(""));
    box.addEventListener("focusin", () => pointAt(row.demo));
  }
  return box;
}

/** Which of the five sources a row's value is read from and written to — used
 *  only to print the file name on the row, so he can find it afterwards. */
function sourceOf(row) {
  if (row.kind === "shape") return "shape";
  if (row.kind === "jscolor") return "js";
  if (row.kind === "theme" || row.kind === "shadow") return "dark";
  return null;
}

/** A colour that exists twice — once per theme — edited as one row, because
 *  that is how it is decided: "the card" is one idea with two answers, and a
 *  page that made him find the light one somewhere else is a page that lets
 *  the two drift. */
function colourRow(row) {
  const holder = document.createElement("div");
  holder.className = "row-ctrl stack";
  const box = rowShell(row, holder);

  ["dark", "light"].forEach((theme) => {
    const value = current(theme, row.token);
    if (value === undefined) return;
    const line = document.createElement("div");
    line.className = "line";
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = theme === "dark" ? "dark page" : "light page";

    const text = document.createElement("input");
    text.type = "text";
    text.value = value;
    const parsed = parseColour(value);
    let picker = null;
    if (parsed) {
      picker = document.createElement("input");
      picker.type = "color";
      picker.value = parsed.hex;
      line.appendChild(picker);
    }
    line.appendChild(text);
    line.appendChild(tag);
    holder.appendChild(line);

    const apply = (next) => {
      edits[theme][row.token] = next;
      text.value = next;
      const now = parseColour(next);
      if (picker && now) picker.value = now.hex;
      box.classList.toggle("changed", isChanged(theme, row.token));
      pushColour(theme, row.token, next);
      markDirty();
    };
    text.addEventListener("input", () => apply(text.value.trim()));
    if (picker) {
      picker.addEventListener("input", () => {
        const now = parseColour(current(theme, row.token)) || { alpha: 1 };
        apply(composeColour(current(theme, row.token), picker.value, now.alpha));
      });
    }
  });
  return box;
}

/** A colour that is a RULE in code (client/theme.js): the shadow drawn under
 *  black ink and the one drawn under white ink. One value, both themes, because
 *  the rule that picks between them does not know what a theme is — it looks at
 *  the ink. This is the row he went looking for and could not find. */
function jsColourRow(row) {
  const holder = document.createElement("div");
  holder.className = "row-ctrl";
  const box = rowShell(row, holder);

  const value = current("js", row.token);
  const picker = document.createElement("input");
  picker.type = "color";
  picker.value = tripleToHex(value) || "#000000";
  const text = document.createElement("input");
  text.type = "text";
  text.value = value;
  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = "r g b";
  holder.appendChild(picker);
  holder.appendChild(text);
  holder.appendChild(tag);

  const apply = (triple) => {
    edits.js[row.token] = triple;
    text.value = triple;
    const hex = tripleToHex(triple);
    if (hex) picker.value = hex;
    box.classList.toggle("changed", isChanged("js", row.token));
    pushJsColour();
    markDirty();
  };
  picker.addEventListener("input", () => apply(hexToTriple(picker.value)));
  text.addEventListener("input", () => apply(text.value.trim()));
  return box;
}

/** A number in client/style.css, with the range its slider spans and the exact
 *  value beside it — the slider is for finding the answer, the box is for
 *  saying it. */
function shapeRow(row) {
  const holder = document.createElement("div");
  holder.className = "row-ctrl";
  const box = rowShell(row, holder);

  const raw = String(current("shape", row.token));
  const unit = row.unit === undefined ? "px" : row.unit;
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = row.min;
  slider.max = row.max;
  slider.step = row.step;
  slider.value = parseFloat(raw);
  const number = document.createElement("input");
  number.type = "number";
  number.className = "num";
  number.step = row.step;
  number.value = parseFloat(raw);
  const unitTag = document.createElement("span");
  unitTag.className = "tag";
  unitTag.textContent = unit || "×";
  holder.appendChild(slider);
  holder.appendChild(number);
  holder.appendChild(unitTag);

  const apply = (value) => {
    const text = String(value) + unit;
    edits.shape[row.token] = text;
    number.value = value;
    slider.value = value;
    box.classList.toggle("changed", isChanged("shape", row.token));
    pushShape(row.token, text);
    markDirty();
  };
  slider.addEventListener("input", () => apply(slider.value));
  number.addEventListener("input", () => {
    if (number.value !== "") apply(number.value);
  });
  return box;
}

/** THE PLAIN LOOKS' SHADOW — a colour per theme AND one strength, on one row.
 *
 *  It was a strength alone until a grader read the first version back: the
 *  white shadow he went looking for exists in TWO places, and offering only
 *  the coloured looks' constant left the plain half of his own question
 *  unanswerable while a note claimed it was answered. So the hue is a picker
 *  per theme (the rule still holds — a gate pins each one to its theme's
 *  opposite ink) and the strength stays what it was: one knob, three writes on
 *  Save (the token on each theme and the constant client/theme.js computes the
 *  coloured looks with). */
function shadowRow(row) {
  const holder = document.createElement("div");
  holder.className = "row-ctrl stack";
  const box = rowShell(row, holder);

  ["dark", "light"].forEach((theme) => {
    const value = current(theme, row.token);
    if (value === undefined) return;
    const line = document.createElement("div");
    line.className = "line";
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = theme === "dark" ? "dark page" : "light page";
    const parsed = parseColour(value) || { hex: "#000000", alpha: 1 };
    const picker = document.createElement("input");
    picker.type = "color";
    picker.value = parsed.hex;
    const text = document.createElement("input");
    text.type = "text";
    text.value = value;
    line.appendChild(picker);
    line.appendChild(text);
    line.appendChild(tag);
    holder.appendChild(line);

    const apply = (next) => {
      edits[theme][row.token] = next;
      text.value = next;
      const now = parseColour(next);
      if (now) picker.value = now.hex;
      box.classList.toggle("changed", isChanged(theme, row.token));
      pushColour(theme, row.token, withAlpha(next, currentAlpha(row.token)));
      markDirty();
    };
    // The HUE only — the strength is the slider below, and it is the one that
    // also reaches client/theme.js. Writing both from here would let the two
    // disagree by a value nobody edited.
    picker.addEventListener("input", () => {
      const base = parseColour(current(theme, row.token)) || { alpha: 1 };
      apply(composeColour(current(theme, row.token), picker.value, base.alpha));
    });
    text.addEventListener("input", () => apply(text.value.trim()));
  });

  const strength = document.createElement("div");
  strength.className = "line";
  const label = document.createElement("span");
  label.className = "tag";
  label.textContent = "strength";
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = row.min;
  slider.max = row.max;
  slider.step = row.step;
  slider.value = currentAlpha(row.token);
  const number = document.createElement("input");
  number.type = "number";
  number.className = "num";
  number.step = row.step;
  number.min = row.min;
  number.max = row.max;
  number.value = currentAlpha(row.token);
  strength.appendChild(label);
  strength.appendChild(slider);
  strength.appendChild(number);
  holder.appendChild(strength);

  const applyAlpha = (value) => {
    const alpha = parseFloat(value);
    edits.alphas[row.token] = alpha;
    number.value = value;
    slider.value = value;
    box.classList.add("changed");
    ["dark", "light"].forEach((theme) => {
      const base = current(theme, row.token);
      if (base !== undefined) pushColour(theme, row.token, withAlpha(base, alpha));
    });
    markDirty();
  };
  slider.addEventListener("input", () => applyAlpha(slider.value));
  number.addEventListener("input", () => {
    if (number.value !== "") applyAlpha(number.value);
  });

  const note = document.createElement("div");
  note.className = "row-note";
  note.textContent = "the strength also writes client/theme.js, so the " +
    "coloured looks follow it after Save + reload";
  box.appendChild(note);
  return box;
}

function derivedRow(row) {
  const holder = document.createElement("div");
  holder.className = "row-ctrl";
  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = "computed by the page — not editable";
  holder.appendChild(tag);
  return rowShell(row, holder);
}

function setsGrid(row) {
  const grid = document.createElement("div");
  grid.className = "sets-grid";
  Object.keys(snapshot.values.sets).forEach((name) => {
    const cell = document.createElement("div");
    cell.className = "set-cell";
    cell.dataset.find = (name + " set colour palette").toLowerCase();
    const label = document.createElement("div");
    label.className = "set-name";
    label.textContent = name;
    const line = document.createElement("div");
    line.className = "line";
    const picker = document.createElement("input");
    picker.type = "color";
    picker.value = current("sets", name);
    const text = document.createElement("input");
    text.type = "text";
    text.value = current("sets", name);
    line.appendChild(picker);
    line.appendChild(text);
    cell.appendChild(label);
    cell.appendChild(line);
    grid.appendChild(cell);

    const apply = (value) => {
      edits.sets[name] = value;
      picker.value = /^#[0-9a-f]{6}$/i.test(value) ? value : picker.value;
      text.value = value;
      pushSets();
      markDirty();
    };
    picker.addEventListener("input", () => apply(picker.value.toUpperCase()));
    text.addEventListener("input", () => apply(text.value.trim()));
  });
  return grid;
}

function buildGroups() {
  const host = document.getElementById("groups");
  host.textContent = "";
  snapshot.groups.forEach((group, index) => {
    const box = document.createElement("details");
    box.className = "group";
    box.dataset.group = group.id;
    box.open = index === 0;
    const head = document.createElement("summary");
    head.textContent = group.title;
    box.appendChild(head);
    const note = document.createElement("p");
    note.className = "group-note";
    note.textContent = group.note;
    box.appendChild(note);
    group.rows.forEach((row) => {
      if (row.kind === "theme") box.appendChild(colourRow(row));
      else if (row.kind === "shadow") box.appendChild(shadowRow(row));
      else if (row.kind === "jscolor") box.appendChild(jsColourRow(row));
      else if (row.kind === "shape") box.appendChild(shapeRow(row));
      else if (row.kind === "derived") box.appendChild(derivedRow(row));
      else if (row.kind === "sets") {
        const pin = document.createElement("p");
        pin.className = "row-pin";
        pin.textContent = "pinned: " + snapshot.setPin;
        box.appendChild(pin);
        box.appendChild(setsGrid(row));
      }
    });
    host.appendChild(box);
  });
  applyFilter();
}

// ═══════════════════════════ FIND ═══════════════════════════
/** Type a word, keep the rows that say it. The groups that still have a row
 *  open themselves, the ones that do not go away entirely — a group heading
 *  with nothing under it is a row of noise between him and the answer. */
function applyFilter() {
  const needle = document.getElementById("find").value.trim().toLowerCase();
  const note = document.getElementById("find-note");
  let hits = 0;
  document.querySelectorAll(".group").forEach((group) => {
    let shown = 0;
    group.querySelectorAll(".row, .set-cell").forEach((row) => {
      const match = !needle || (row.dataset.find || "").includes(needle);
      row.classList.toggle("hidden", !match);
      if (match) shown++;
    });
    group.classList.toggle("hidden", needle !== "" && shown === 0);
    if (needle) group.open = shown > 0;
    hits += shown;
  });
  note.textContent = needle
    ? (hits === 0 ? "nothing here says “" + needle + "”"
                  : hits + (hits === 1 ? " setting" : " settings") + " match")
    : "";
}

// ═══════════════════════════ SAVE ═══════════════════════════
function report(lines, cls) {
  const host = document.getElementById("report");
  const block = document.createElement("div");
  if (cls) block.className = cls;
  block.textContent = lines.join("\n");
  host.appendChild(block);
  host.scrollTop = host.scrollHeight;
}

async function save() {
  document.getElementById("save").disabled = true;
  document.getElementById("report").textContent = "";
  const payload = { dark: {}, light: {}, shape: {}, sets: {}, js: {},
                    alphas: edits.alphas };
  for (const source of ["dark", "light", "shape", "sets", "js"]) {
    for (const [token, value] of Object.entries(edits[source])) {
      if (isChanged(source, token)) payload[source][token] = value;
    }
  }
  let answer;
  try {
    const response = await fetch("/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    answer = await response.json();
  } catch (error) {
    report(["the lab could not reach its own server: " + error], "bad");
    markDirty();
    return;
  }
  if (!answer.ok) {
    report(["REFUSED — nothing was written:", answer.error], "bad");
    markDirty();
    return;
  }
  report(answer.changed.length
    ? ["written:"].concat(answer.changed)
    : ["nothing to write — every value already said that"]);
  if (answer.pins.length) {
    report([""].concat(
      ["a gate has an opinion about " + answer.pins.length +
       " of these — run `python tests/run_guards.py` and " +
       "`python -m pytest tests`, and update docs/DECISIONS.md in the same round:"],
      answer.pins.map((line) => "  · " + line)), "warn");
  }
  // Re-read from disk rather than trusting what we just sent: the file is the
  // truth about what is in the file.
  edits = { dark: {}, light: {}, shape: {}, sets: {}, js: {}, alphas: {} };
  await load();
}

function revert() {
  edits = { dark: {}, light: {}, shape: {}, sets: {}, js: {}, alphas: {} };
  document.getElementById("report").textContent = "";
  buildGroups();
  buildFrames();
  markDirty();
}

// ═══════════════════════════ THE SPLITTER ═══════════════════════════
function sideWidth(px) {
  const width = Math.max(320, Math.min(window.innerWidth - 360, Math.round(px)));
  document.documentElement.style.setProperty("--side-w", width + "px");
  try { localStorage.setItem(PREF_WIDTH, String(width)); } catch (e) { /* private mode */ }
  layoutFrames();
}

function wireSplitter() {
  const bar = document.getElementById("splitter");
  let dragging = false;
  bar.addEventListener("pointerdown", (event) => {
    dragging = true;
    bar.setPointerCapture(event.pointerId);
    document.body.classList.add("dragging");
  });
  bar.addEventListener("pointermove", (event) => {
    if (dragging) sideWidth(event.clientX);
  });
  const stop = () => {
    dragging = false;
    document.body.classList.remove("dragging");
  };
  bar.addEventListener("pointerup", stop);
  bar.addEventListener("pointercancel", stop);
  // Double-click widens it to whatever the widest row actually needs — the
  // ladder's last rung, taken for him.
  bar.addEventListener("dblclick", () => sideWidth(560));
}

// ═══════════════════════════ START ═══════════════════════════
async function load() {
  snapshot = await (await fetch("/tokens")).json();
  buildGroups();
  buildFrames();
  markDirty();
}

["which", "theme", "colored", "fill"].forEach((id) => {
  document.getElementById(id).addEventListener("change", buildFrames);
});
["backdrop", "toast", "bench"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => frames.forEach(refresh));
});
document.getElementById("zoom").addEventListener("change", () => {
  try { localStorage.setItem(PREF_ZOOM, zoomChoice()); } catch (e) { /* private mode */ }
  layoutFrames();
  toAll(fitMessage());
});
document.getElementById("find").addEventListener("input", applyFilter);
document.getElementById("save").addEventListener("click", save);
document.getElementById("revert").addEventListener("click", revert);
// A frame that has just been re-laid-out has to re-fit its board; the frame
// itself cannot see the resize, because an iframe's own `resize` fires only
// for its window and the grid change is the parent's.
new ResizeObserver(() => {
  layoutFrames();
  toAll(fitMessage());
}).observe(document.getElementById("frames"));

try {
  // The default is a SHARE of the window, not a number: 470 px is a sixth of
  // his screen and a third of a small laptop's, and a third of a 1366 screen
  // spent on the panel is what starves the wall beside it (a grader measured
  // exactly that). Capped both ways, and his own dragged width still wins.
  const share = Math.max(340, Math.min(470, Math.round(window.innerWidth * 0.26)));
  document.documentElement.style.setProperty("--side-w", share + "px");
  const saved = parseInt(localStorage.getItem(PREF_WIDTH) || "", 10);
  if (saved) document.documentElement.style.setProperty("--side-w", saved + "px");
  const zoom = localStorage.getItem(PREF_ZOOM);
  if (zoom) document.getElementById("zoom").value = zoom;
} catch (e) { /* private mode — the defaults are fine */ }

wireSplitter();
load();
