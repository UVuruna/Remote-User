"use strict";
// THE BENCH'S WIRING — build the knobs from the registry, push every turn of
// one into the frames, and hand the whole set to the server when he saves.
//
// IT HOLDS NO DEFAULTS. Every value on this page came from `/tokens`, which
// read it out of client/theme.css, client/style.css and server/config.py a
// moment ago; every value it sends back goes to the same declaration. A
// constant written here would be a third opinion about a colour that already
// has two homes, and it would be the one that goes stale.
//
// LIVE IS AN OVERRIDE, SAVE IS A WRITE. Dragging a slider only posts a message
// to the frames, which set the token inline (tools/preview.html). Nothing on
// disk moves until Save, so a session of tuning that ends in Revert leaves the
// project byte-identical.
// See tools/__about/design_lab.md.

// ═══════════════════════════ STATE ═══════════════════════════
let snapshot = null;
// What he has changed and not yet saved, per source. The keys are the four
// sources of tools/design_tokens.py plus `alphas`, which is one knob that
// lands in three places (both themes' tokens and the JS constant).
let edits = { dark: {}, light: {}, shape: {}, sets: {}, alphas: {} };

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
  for (const source of ["dark", "light", "shape", "sets"]) {
    for (const token of Object.keys(edits[source])) {
      if (isChanged(source, token)) n++;
    }
  }
  return n + Object.keys(edits.alphas).length;
}

// ═══════════════════════════ THE FRAMES ═══════════════════════════
const frames = [];   // {look, iframe, ready}

function send(frame, message) {
  if (!frame.iframe.contentWindow) return;
  frame.iframe.contentWindow.postMessage(message, "*");
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
  send(frame, { kind: "backdrop", css: BACKDROPS[document.getElementById("backdrop").value] });
  send(frame, { kind: "toast", state: document.getElementById("toast").value });
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
  frames.forEach((frame) => send(frame, { kind: "shape", values: { [token]: value } }));
}

function pushSets() {
  frames.forEach((frame) => send(frame, { kind: "sets", colors: setPalette() }));
}

function buildFrames() {
  const host = document.getElementById("frames");
  const one = document.getElementById("which").value === "one";
  host.classList.toggle("single", one);
  host.textContent = "";
  frames.length = 0;
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
}

// ═══════════════════════════ THE KNOBS ═══════════════════════════
function markDirty() {
  const n = countChanges();
  document.getElementById("dirty").textContent =
    n === 0 ? "nothing changed yet"
            : n + (n === 1 ? " value changed, not yet saved" : " values changed, not yet saved");
  document.getElementById("save").disabled = n === 0;
}

function rowShell(row, label, token, extra) {
  const box = document.createElement("div");
  box.className = "row";
  box.dataset.token = token || "";
  const name = document.createElement("div");
  name.className = "row-label";
  name.textContent = label;
  box.appendChild(name);
  box.appendChild(extra);
  if (token) {
    const id = document.createElement("div");
    id.className = "row-token";
    id.textContent = token;
    box.appendChild(id);
    if (snapshot.pinned[token]) {
      const pin = document.createElement("div");
      pin.className = "row-pin";
      pin.textContent = "pinned: " + snapshot.pinned[token];
      box.appendChild(pin);
    }
  }
  if (row && row.why) {
    const why = document.createElement("div");
    why.className = "row-why";
    why.textContent = row.why;
    box.appendChild(why);
  }
  return box;
}

/** A colour that exists twice — once per theme — edited as one row, because
 *  that is how it is decided: "the card" is one idea with two answers, and a
 *  page that made him find the light one somewhere else is a page that lets
 *  the two drift. */
function colourRow(row) {
  const pair = document.createElement("div");
  pair.className = "pair stack";   // one theme per line — see design_lab.css
  const box = rowShell(row, row.label, row.token, pair);

  ["dark", "light"].forEach((theme) => {
    const value = current(theme, row.token);
    if (value === undefined) return;
    const wrap = document.createElement("div");
    wrap.className = "pair";
    const tag = document.createElement("span");
    tag.textContent = theme === "dark" ? "D" : "L";
    wrap.appendChild(tag);

    const text = document.createElement("input");
    text.type = "text";
    text.value = value;
    const parsed = parseColour(value);
    let picker = null;
    if (parsed) {
      picker = document.createElement("input");
      picker.type = "color";
      picker.value = parsed.hex;
      wrap.appendChild(picker);
    }
    wrap.appendChild(text);
    pair.appendChild(wrap);

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

/** A number in client/style.css, with the range its slider spans and the exact
 *  value beside it — the slider is for finding the answer, the box is for
 *  saying it. */
function shapeRow(row) {
  const holder = document.createElement("div");
  holder.className = "pair";
  const box = rowShell(row, row.label, row.token, holder);

  const raw = String(current("shape", row.token));
  const unit = row.unit === undefined ? "px" : row.unit;
  const number = document.createElement("input");
  number.type = "number";
  number.className = "num";
  number.step = row.step;
  number.value = parseFloat(raw);
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = row.min;
  slider.max = row.max;
  slider.step = row.step;
  slider.value = parseFloat(raw);
  const unitTag = document.createElement("span");
  unitTag.textContent = unit || "×";
  holder.appendChild(number);
  holder.appendChild(unitTag);
  box.appendChild(slider);

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

/** The strength of a shadow whose COLOUR is not a choice. One knob, three
 *  writes on Save (the token on each theme and the constant client/theme.js
 *  computes the coloured looks with). */
function alphaRow(row) {
  const holder = document.createElement("div");
  holder.className = "pair";
  const box = rowShell(row, row.label, row.token, holder);

  const number = document.createElement("input");
  number.type = "number";
  number.className = "num";
  number.step = row.step;
  number.min = row.min;
  number.max = row.max;
  number.value = currentAlpha(row.token);
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = row.min;
  slider.max = row.max;
  slider.step = row.step;
  slider.value = currentAlpha(row.token);
  holder.appendChild(number);
  box.appendChild(slider);

  const note = document.createElement("div");
  note.className = "row-why";
  // Said out loud rather than hidden: the coloured looks compute their shadow
  // in client/theme.js from a constant that is only read when the file loads,
  // so what moves live here is the plain looks. Claiming otherwise would be
  // exactly the kind of "it works" this project does not accept.
  note.textContent = "live in the plain looks; the coloured ones recompute " +
    "from client/theme.js and follow after Save + reload";
  box.appendChild(note);

  const apply = (value) => {
    const alpha = parseFloat(value);
    edits.alphas[row.token] = alpha;
    number.value = value;
    slider.value = value;
    box.classList.add("changed");
    ["dark", "light"].forEach((theme) => {
      const base = snapshot.values[theme][row.token];
      if (base !== undefined) pushColour(theme, row.token, withAlpha(base, alpha));
    });
    markDirty();
  };
  slider.addEventListener("input", () => apply(slider.value));
  number.addEventListener("input", () => {
    if (number.value !== "") apply(number.value);
  });
  return box;
}

function derivedRow(row) {
  const holder = document.createElement("div");
  holder.className = "pair";
  const tag = document.createElement("span");
  tag.textContent = "computed";
  holder.appendChild(tag);
  return rowShell(row, row.label, row.token, holder);
}

function setsGrid() {
  const grid = document.createElement("div");
  grid.className = "sets-grid";
  Object.keys(snapshot.values.sets).forEach((name) => {
    const cell = document.createElement("div");
    cell.className = "set-cell";
    const picker = document.createElement("input");
    picker.type = "color";
    picker.value = current("sets", name);
    const label = document.createElement("label");
    label.textContent = name;
    const text = document.createElement("input");
    text.type = "text";
    text.value = current("sets", name);
    text.style.width = "92px";
    cell.appendChild(picker);
    cell.appendChild(label);
    cell.appendChild(text);
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
      else if (row.kind === "shape") box.appendChild(shapeRow(row));
      else if (row.kind === "alpha") box.appendChild(alphaRow(row));
      else if (row.kind === "derived") box.appendChild(derivedRow(row));
      else if (row.kind === "sets") {
        const pin = document.createElement("p");
        pin.className = "row-pin";
        pin.textContent = "pinned: " + snapshot.setPin;
        box.appendChild(pin);
        box.appendChild(setsGrid());
      }
    });
    host.appendChild(box);
  });
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
  const payload = { dark: {}, light: {}, shape: {}, sets: {}, alphas: edits.alphas };
  for (const source of ["dark", "light", "shape", "sets"]) {
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
  edits = { dark: {}, light: {}, shape: {}, sets: {}, alphas: {} };
  await load();
}

function revert() {
  edits = { dark: {}, light: {}, shape: {}, sets: {}, alphas: {} };
  document.getElementById("report").textContent = "";
  buildGroups();
  buildFrames();
  markDirty();
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
["backdrop", "toast"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => frames.forEach(refresh));
});
document.getElementById("save").addEventListener("click", save);
document.getElementById("revert").addEventListener("click", revert);

load();
