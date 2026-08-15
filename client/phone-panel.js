// Settings → Phone: the switches that describe THIS DEVICE and nothing else.
//
// ── WHY THIS CARD EXISTS (owner 2026-08-11, task 161, ordered again in 218a)
// Every switch below already shipped, and every one of them shipped in the
// wrong room. The D-pad shape ticks lived in the "Wheel sets" picker, which is
// about which SETS ride the wheel; the layout bar's Top/Bottom chips lived on
// the layout list, which is about LAYOUTS; the Hide mode lived only behind a
// hold on the Hide button, where nothing announced it. His words about the
// lang-ok: owner quote, the report this card answers
// first of those — "to se sada nalazi gde se podešavaju setovi" — name the
// defect exactly: a control carrying one concept parked in a section named for
// another (ALG-9 SECTION TAXONOMY, rules/GUI.md → Zubi v2).
//
// The subject that gathers them is THE PHONE. Each one is a per-device
// preference stored through the SharedPreferences bridge, each one changes how
// this handset behaves and nothing on the PC, and none of them belongs to any
// other card in the product. So they are one card, reached from the Settings
// wheel like Quality and Language are, and their old homes gave them up in the
// same round — a switch with two doors is two states to keep in step.
//
// THE DICTATION BEEPS STAYED WHERE THEY ARE, deliberately: that switch is read
// and written by the Android speech engine through `Android.voiceMuteBeeps`,
// it only makes sense beside the language it mutes, and it already sits on the
// dictation card. This card carries a POINTER to it instead of a second copy.
//
// Loaded after panels.js (ghostClickArmor, segRow) and quality.js; it reads
// layouts.js's bar-position helpers at RUNTIME only, which is why it may load
// before that file.

"use strict";

const phonePanel = document.getElementById("phone-panel");
const phoneOpened = { t: 0 };
ghostClickArmor(phonePanel, phoneOpened);

function openPhonePanel() {
  phonePanel.innerHTML = "";
  const card = document.createElement("div");
  // NOT `card-columns` — a MULTICOL card is a fragmentainer, and a capped one
  // answers "I do not fit" by growing a column off the side of the screen
  // instead of scrolling (task 217). `card-split` is the Sets picker's answer
  // and the right one here: the card SPENDS the width a sideways phone gives
  // it (915x412 leaves 123 px idle beside a 760 px card — BUG A of THE SPACE
  // & LEGIBILITY LAW, and the phone audit measured exactly that on this card's
  // first run), the `.sets-body` between the header and Done is what scrolls,
  // and the primary button stays on screen.
  card.className = "sets-card card-split";
  card.innerHTML = `<h2>This phone</h2>
    <p class="sets-sub">Settings for the device in your hand — nothing here
       changes the PC, and your other device keeps its own answers.</p>`;

  const body = document.createElement("div");
  body.className = "sets-body";
  card.appendChild(body);

  // WHERE THE LAYOUT BAR STANDS (owner 2026-08-09, task 160 — moved here from
  // the layout list, task 218a). Top is where it has always been; Bottom puts
  // it within a thumb's reach on a tall phone.
  body.appendChild(segRow("Layout bar", LAY_BAR_POSITIONS, ["Top", "Bottom"],
    layBarPos(), (v) => {
      setLayBarPos(v);
      openPhonePanel();          // the row re-lights its choice
    }));

  // WHAT HIDE MEANS (owner 2026-08-09, task 159). He named both costs himself:
  // "comes back" makes the buttons' corner unusable for the mouse, "stays
  // hidden" leaves the Hide button's own corner covered until he presses it
  // again. Neither is better, which is why both ship and the choice is his.
  body.appendChild(segRow("When hidden", HIDE_MODES,
    ["Comes back", "Stays hidden"], hideMode(), (v) => {
      setHideMode(v);
      openPhonePanel();
    }));

  // THE SHAPE OF THE TWO CONTROL GROUPS, ONE TICK PER ORIENTATION (owner
  // 2026-08-09, task 177 — moved here from the sets picker, task 218a).
  // Upright, a 412 px phone has no room for two crosses with the picture
  // between them and a 10" tablet has plenty; sideways, a 16:9 picture leaves
  // a finger-wide band down each side that holds a column perfectly. Neither
  // tick changes a default: each starts on the shape this orientation renders
  // TODAY, and ticking writes the explicit choice that outranks it.
  const shape = document.createElement("div");
  shape.className = "sets-shape";
  shape.appendChild(padShapeRow(
    "portrait", "cross",
    "Held upright: the D-pad cross instead of the column — for a wide screen"));
  shape.appendChild(padShapeRow(
    "landscape", "column",
    "Held sideways: upright columns instead of the D-pad cross — they stand "
    + "in the empty bands beside the picture"));
  body.appendChild(shape);

  // NOTIFICATION CHANNELS (task 226, owner ballot verdict). Per-device mute
  // switches for the three carriers `notify.js` already reads and never had
  // a door to write: `notifyPrefs()`/`saveNotifyPrefs()` there, persisted
  // through the SAME prefGet/prefSet SharedPreferences bridge as every other
  // row on this card — never bare localStorage (that split state across the
  // LAN and Tailscale origins once already, 2026-08-05).
  //
  // THE LAST-RESORT RULE (documented once, here, where he reads it): muting
  // all three never means "send nothing" — the banner is the one carrier
  // that needs no sound and still reaches him with the screen off, so an
  // all-off state is answered as banner-only by `effectiveNotifyPrefs()` in
  // notify.js. The banner switch says so in its own label instead of
  // depending on him having read this comment.
  // Task 233 (grader flag d): the banner row's own label used to carry the
  // last-resort rule inline and wrapped 5-6 lines in this card's narrow
  // column. The rule is said ONCE, above the three rows, so no row's label
  // has to be a sentence — each stays a short name, ~2 lines at most.
  const notifyNote = document.createElement("p");
  notifyNote.className = "sets-sub";
  notifyNote.textContent = "Muting all three still reaches you: the banner "
    + "is the last resort and stays on until you turn it off yourself.";
  body.appendChild(notifyNote);

  const notify = document.createElement("div");
  notify.className = "sets-shape";
  const np = notifyPrefs();
  const chanRow = (key, label) => segRow(label, [true, false], ["On", "Off"],
    np[key], (v) => {
      const next = { ...notifyPrefs(), [key]: v };
      saveNotifyPrefs(next);
      openPhonePanel();
    });
  notify.appendChild(chanRow("banner", "Notification banner"));
  notify.appendChild(chanRow("speak", "Speak the notice aloud"));
  notify.appendChild(chanRow("tone", "Notification tone"));
  body.appendChild(notify);

  // The pointer, not a copy. It says where the switch lives and takes him
  // there in one tap — the dictation card owns it because the engine that
  // reads it is the one that beeps.
  const beeps = document.createElement("button");
  beeps.type = "button";
  beeps.className = "sets-row dict-more";
  beeps.textContent = "Dictation beeps and language — on the dictation card…";
  beeps.dataset.opensMore = "";   // the audit's declared "there is more" marker
  keepRowTap(beeps, () => {
    closePhonePanel();
    openDictationPanel();
  });
  body.appendChild(beeps);

  const done = document.createElement("button");
  done.type = "button";
  done.className = "sets-done";
  done.textContent = "Done";
  keepRowTap(done, closePhonePanel);
  card.appendChild(done);

  phonePanel.appendChild(card);
  phonePanel.hidden = false;
  phoneOpened.t = performance.now();
}

function closePhonePanel() {
  phonePanel.hidden = true;
  phonePanel.innerHTML = "";
}

phonePanel.addEventListener("pointerdown", (e) => {
  if (e.target === phonePanel) closePhonePanel();   // backdrop tap = done
});
