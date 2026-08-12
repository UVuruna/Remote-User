// Settings → Appearance: how THIS DEVICE looks.
//
// ── WHY THIS CARD EXISTS (owner ballot 2026-08-12) ─────────────────────────
// His verdict, approved on the ballot: "appearance is also per device, not
// global, so it belongs on the phone / tablet."
//
// The three axes — theme, whether the controls wear each set's colour, and
// whether they are outlined or filled — lived in the PC's Settings window and
// rode the `config` frame to every handset. That was the 2026-08-07 answer to
// P4 (one source of truth, no menu on the phone), and it was right that there
// must be ONE answer and wrong about where it lives: he uses a tablet AND a
// phone, held at different distances in different light, and one desktop
// dropdown could only ever describe one of them. Two devices could not look
// different, which is exactly what he asked for.
//
// So the PC's values are now the DEFAULT and this card is the choice. Nothing
// on the wire changed: `config.ui` still carries all three (server/config.py →
// `ui_config`), client/theme.js still applies it, and a handset that never
// opens this card wears the PC's values byte for byte. What is new is a second,
// PARTIAL store on the device — `uiChoice`, through the shell's
// SharedPreferences bridge, the sets-picker's mechanism and never bare
// localStorage (that is keyed by ORIGIN, and the shell alternates between the
// LAN and Tailscale addresses — the "picker rotates" bug of 2026-08-05).
//
// ── EVERY ROW OFFERS THE PC BACK ───────────────────────────────────────────
// The first step of each row is "PC (…)", and the brackets NAME what the PC is
// currently set to. Two reasons, and the second is the one that matters: a
// per-device override with no way home is a trap — he would have to remember
// what the PC said and re-pick it by hand, and he would then be PINNED to that
// value instead of following the PC again. Choosing "PC" deletes the axis from
// this device's store, so the axis resumes following the desktop for as long as
// he leaves it alone. Naming the value in the label is what makes that step a
// decision rather than a gamble.
//
// Loaded after panels.js (ghostClickArmor, segRow) and theme.js (the axis
// store); reached from the Settings set like Quality, Language and Phone.

"use strict";

const appearancePanel = document.getElementById("appearance-panel");
const appearanceOpened = { t: 0 };
ghostClickArmor(appearancePanel, appearanceOpened);

// Value used by the FIRST step of every row: "hand this axis back to the PC".
// A string nothing else can be — `theme` is dark/light, `fill` is
// transparent/full, `colored` is a boolean — so one sentinel serves all three.
const UI_FOLLOW_PC = "pc";

// One row per axis. `values` are what gets stored, `name` turns a stored value
// into the word the PC's own step shows in its brackets.
const APPEARANCE_ROWS = [
  {
    axis: "theme",
    title: "Theme",
    values: ["dark", "light"],
    labels: ["Dark", "Light"],
    name: (v) => (v === "light" ? "Light" : "Dark"),
  },
  {
    axis: "colored",
    title: "Controls",
    values: [true, false],
    labels: ["Coloured", "Plain"],
    name: (v) => (v ? "Coloured" : "Plain"),
  },
  {
    axis: "fill",
    title: "Buttons",
    values: ["transparent", "full"],
    labels: ["Outlined", "Filled"],
    name: (v) => (v === "full" ? "Filled" : "Outlined"),
  },
];

function appearanceRow(row) {
  // The stored pick, or the sentinel while this axis still follows the PC.
  const current = uiFollowsPc(row.axis) ? UI_FOLLOW_PC : uiLook()[row.axis];
  return segRow(
    row.title,
    [UI_FOLLOW_PC, ...row.values],
    [`PC (${row.name(uiPcValue(row.axis))})`, ...row.labels],
    current,
    (v) => {
      if (v === UI_FOLLOW_PC) clearUiAxis(row.axis);
      else setUiAxis(row.axis, v);
      // Re-render rather than trust the strip's own highlight: choosing "PC"
      // can change what the OTHER steps look like on screen, and the brackets
      // of every row are read from live state.
      openAppearancePanel();
    }
  );
}

function openAppearancePanel() {
  appearancePanel.innerHTML = "";
  const card = document.createElement("div");
  // `card-split` for the Sets picker's reason (task 217): a multicol card is a
  // fragmentainer and answers "I do not fit" by growing a column off the side
  // of a sideways phone. Three rows fit comfortably today — the class is what
  // keeps that true the next time a row is added.
  card.className = "sets-card card-split";
  card.innerHTML = `<h2>Appearance</h2>
    <p class="sets-sub">How the app looks on THIS device — your other phone or
       tablet keeps its own answer, and nothing here changes the PC.</p>`;

  const body = document.createElement("div");
  body.className = "sets-body";
  card.appendChild(body);

  APPEARANCE_ROWS.forEach((row) => body.appendChild(appearanceRow(row)));

  const note = document.createElement("p");
  note.className = "sets-sub";
  note.textContent =
    "Coloured gives every set its own colour; Filled paints the buttons in, "
    + "Outlined leaves them see-through. PC (…) follows the Vibe Coder window "
    + "on the computer, so this device changes with it.";
  body.appendChild(note);

  const done = document.createElement("button");
  done.type = "button";
  done.className = "sets-done";
  done.textContent = "Done";
  keepFocus(done, closeAppearancePanel);
  card.appendChild(done);

  appearancePanel.appendChild(card);
  appearancePanel.hidden = false;
  appearanceOpened.t = performance.now();
}

function closeAppearancePanel() {
  appearancePanel.hidden = true;
  appearancePanel.innerHTML = "";
}

appearancePanel.addEventListener("pointerdown", (e) => {
  if (e.target === appearancePanel) closeAppearancePanel(); // backdrop = done
});
