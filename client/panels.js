// Overlay panels opened from the Settings set: the Sets picker and the
// Quality panel. Split out of controls.js (THE STRUCTURE LAW) — controls.js
// owns the D-pad groups, wheel and button actions; this module owns the
// full-screen card overlays those actions open. Loaded after controls.js
// (uses its prefs helpers, wheel state and keepFocus); controls.js calls
// openSetsPanel/openQualityPanel only at runtime, after every script loaded.

// --- Sets picker (Settings → Sets, owner 2026-08-05) ----------------------
// Chooses WHICH sets ride in the wheel on THIS phone: the required built-ins
// are always on; the rest toggle up to wheelCap() total (creation on the
// desktop — creation never happens here) plus the app-shortcuts toggle.
// Stored per device via the prefs bridge, overriding the desktop defaults.

// ── WHICH BUILT-IN OPENS WHICH CARD ────────────────────────────────────────
// One table, and it lives HERE because this module is the one that owns the
// full-screen overlays (module docstring above): controls.js builds the D-pad
// button and knows only that a `kind` may name a card. It used to be one
// `else if` per kind in `makeActionButton`, which was fine while there were
// two and was the thing standing between controls.js and THE STRUCTURE LAW's
// 1,000-line ceiling by the time Settings → Voice needed a seventh
// (2026-08-12).
//
// Every entry is WRAPPED in an arrow rather than named directly: the openers
// live in five different modules — this one, quality.js, phone-panel.js,
// region.js, notify.js, chrome.js — and several of those load AFTER this file.
// A bare reference would be read at load time and throw; the arrow is read at
// tap time, by which point every script is in.
const PANEL_KINDS = {
  sets: () => openSetsPanel(),
  region: () => openRegionPanel(),
  quality: () => openQualityPanel(),
  dictation: () => openDictationPanel(),
  phone: () => openPhonePanel(),
  notifyvoice: () => openNotifyVoicePanel(),
  // HOW THIS DEVICE LOOKS (owner ballot 2026-08-12) — theme, coloured or
  // plain controls, outlined or filled. It left the PC's Settings window
  // because he uses a tablet AND a phone: client/appearance-panel.js.
  appearance: () => openAppearancePanel(),
  // WHEN this phone listens for notices (owner 2026-08-12) — only while the
  // app is open in the background, or always: client/notify.js.
  notices: () => openNoticeModePanel(),
  // The "anywhere access" banner appears once per device (owner 2026-07-26) —
  // this button is the permanent way back into the wizard.
  anywhere: () => openWizard(),
  // Session Ledger (T111, 2026-08-17) — client/ledger-panel.js.
  ledger: () => openLedgerPanel(),
};

const setsPanel = document.getElementById("sets-panel");

// Ghost-click armor (owner bug report 2026-08-05 — "the picker rotates"):
// the tap that OPENS a panel can still deliver a late synthetic click, which
// then lands on whichever row the panel happened to open under the finger —
// silently toggling it. Swallow every click in the first moments after
// opening; no human re-taps that fast.
const GHOST_CLICK_MS = 400;

function ghostClickArmor(panel, openedAt) {
  panel.addEventListener(
    "click",
    (e) => {
      if (performance.now() - openedAt.t < GHOST_CLICK_MS) {
        e.preventDefault();
        e.stopPropagation();
      }
    },
    true
  );
}

const setsOpened = { t: 0 };
ghostClickArmor(setsPanel, setsOpened);

function setsRow(s, locked) {
  const row = document.createElement("label");
  row.className = "sets-row";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = locked || setOn(s);
  cb.disabled = locked;
  if (!locked) {
    cb.addEventListener("change", () => {
      // Both tick paths ask the SAME question the same way (owner 2026-08-06):
      // write the choice, then measure — the two used to disagree (this one
      // measured before saving with >=, the app one after saving with >), and
      // a rule the code states twice is a rule the code will break once.
      const p = setsPrefs();
      const was = p.state[s.name];
      p.state[s.name] = cb.checked;
      saveSetsPrefs(p);
      if (cb.checked && visibleCount() > wheelCap()) {
        cb.checked = false;
        if (was === undefined) delete p.state[s.name]; else p.state[s.name] = was;
        saveSetsPrefs(p);
        showToast(`The wheel holds ${wheelCap()} sets — untick one first`);
        return;
      }
      refreshCategories();
      refreshSetsMeta();  // the counter and the live badges follow every tick
    });
  }
  const ic = document.createElement("span");
  ic.className = "sets-ic";
  ic.innerHTML = svg(s.icon && ICONS[s.icon] ? s.icon : "grid");
  row.append(cb, ic, document.createTextNode(s.name + (locked ? " — always on" : "")),
             setsEditButton(s));
  return row;
}

// THE DOOR INTO ONE SET'S OWN EDITOR (owner 2026-08-04, task 218b): from the
// same panel where the sets are ticked on and off, he configures the
// individual set — which buttons ride and where. A REQUIRED set is locked
// against the tick and fully editable here: "always on the wheel" says nothing
// about what is on its D-pad, and Mouse and Input are the two he arranges most.
//
// A button inside a <label> would otherwise toggle that label's checkbox on
// its way past, which would tick a set off every time he opened its editor. The
// click is swallowed in the capture phase — `keepFocus` acts on pointerup, so
// the action has already run by the time the click is cancelled.
function setsEditButton(s) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "sets-edit";
  b.innerHTML = svg("edit");
  b.setAttribute("aria-label", `Edit the ${s.name} buttons`);
  b.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); }, true);
  keepRowTap(b, () => {
    closeSetsPanel();
    openSetEditor(s);
  });
  return b;
}

// One app-aware set (VSCode, Claude, Chrome, Explorer). It costs a wheel slot
// like any other set, and it also carries a LIVE badge: which of them is on
// the wheel right now, for the layout currently focused (owner 2026-08-06 —
// "hoću da bude štiklirano pored onoga koji je aktivan, da bude uočljivo").
// Ticked means allowed; the badge means actually riding this second.
function appSetRow(s) {
  const row = document.createElement("label");
  row.className = "sets-row app";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = appSetOn(s);
  cb.addEventListener("change", () => {
    const p = setsPrefs();
    const was = p.appState[s.name];
    p.appState[s.name] = cb.checked;
    saveSetsPrefs(p);
    // An app set costs a wheel slot like any other (owner 2026-08-06) — and
    // VSCode + Claude cost two, because a Claude tab shows both. Refuse the
    // tick that would overflow instead of letting the wheel drop a set the
    // owner already chose, and say why.
    if (cb.checked && visibleCount() > wheelCap()) {
      cb.checked = false;
      if (was === undefined) delete p.appState[s.name]; else p.appState[s.name] = was;
      saveSetsPrefs(p);
      showToast(`The wheel holds ${wheelCap()} sets — untick one first`);
      return;
    }
    refreshCategories();
    refreshSetsMeta();
  });
  const ic = document.createElement("span");
  ic.className = "sets-ic";
  ic.innerHTML = svg(s.icon && ICONS[s.icon] ? s.icon : "newwin");
  const badge = document.createElement("span");
  badge.className = "sets-live";
  badge.dataset.set = s.name;
  badge.textContent = "on the wheel now";
  row.append(cb, ic, document.createTextNode(s.name), badge, setsEditButton(s));
  return row;
}

// The two things that change without a re-render: the counter line and which
// app sets are live. Updated in place — rebuilding the card would re-arm the
// ghost-click armor and swallow the owner's next tick.
function refreshSetsMeta() {
  const count = setsPanel.querySelector(".sets-count");
  if (count) {
    const reserve = appSetReserve();
    count.textContent = `${visibleCount()} of ${wheelCap()} used`
      + (reserve ? ` — ${reserve} held for app shortcuts` : "");
  }
  const live = new Set(visibleAppSets().map((s) => s.name));
  for (const b of setsPanel.querySelectorAll(".sets-live")) {
    b.classList.toggle("on", live.has(b.dataset.set));
  }
}

// ── ONE SEGMENTED ROW, SHARED BY EVERY CARD THAT ASKS A SMALL CHOICE ───────
// Born in quality.js as `qualitySegRow` and lifted here on 2026-08-11 when the
// Phone card (task 161) needed the same row: a caption on the left, a strip of
// mutually exclusive buttons on the right, one of them lit. Its `.q-row` /
// `.q-seg` classes keep their names — they are already styled, already audited
// and already photographed, and renaming measured CSS buys nothing.
//
// `disabled(v)` marks a step that exists but is out of reach here (the quality
// panel's fps above what the PC allows) — inert AND visibly so, never simply
// missing, because a step that vanished cannot explain itself.
function segRow(title, values, labels, current, onPick, disabled) {
  const row = document.createElement("div");
  row.className = "q-row";
  const cap = document.createElement("span");
  cap.className = "q-cap";
  cap.textContent = title;
  const seg = document.createElement("div");
  seg.className = "q-seg";
  values.forEach((v, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = labels[i];
    b.classList.toggle("on", v === current);
    if (disabled && disabled(v)) {
      b.classList.add("out");
      b.disabled = true;
    } else {
      b.addEventListener("click", () => {
        seg.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
        b.classList.add("on");
        onPick(v);
      });
    }
    seg.appendChild(b);
  });
  row.append(cap, seg);
  return row;
}

// One tick per orientation for the D-pad shape (owner 2026-08-09, task 177).
// `asked` is the shape THIS row asks for; unticking hands the orientation back
// to `auto` — the default — rather than to the opposite shape, so a device
// that ticked and unticked reads exactly like one that was never asked.
//
// The rows themselves moved to the PHONE card on 2026-08-11 (task 218a) — the
// builder stays here beside the other row builders, its callers do not.
function padShapeRow(orient, asked, text) {
  const row = document.createElement("label");
  row.className = "sets-row apps";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = padShape(orient) === asked;
  cb.addEventListener("change", () =>
    setPadShape(orient, cb.checked ? asked : "auto"));
  row.append(cb, document.createTextNode(text));
  return row;
}

// THIS CARD DECLARES ITS OWN COLUMNS — it is NOT a fragmentainer (defect found
// by the phone audit 2026-08-09, the round that added the two shape rows). The
// landscape reflow of task 172 gives a card `column-count: 2`, and a multicol
// with a definite height has exactly one answer when its content no longer
// fits: it makes ANOTHER column. Two rows more and this card grew a THIRD one,
// 273 px off the right edge of a 915 px screen, carrying the app-shortcuts row
// and the Done button with it — measured scrollWidth 1129 in a 758 px card.
// Nothing was clipped, nothing scrolled, and the primary button was simply not
// on the screen. So the card takes the mechanism the creation panel took for
// the same reason (`.lc-split`, client/layout-create.css): the columns are
// DECLARED — a grid on the LISTS, which are what is tall, and which are rows
// of short items — and the card itself is an ordinary block that scrolls when
// it must. A grid cannot invent a third column, and `card-split` is a class of
// this card's own so the four other `.sets-card` panels keep the reflow they
// were measured with.
//
// THE FOOTER IS PINNED for the same reason the spill mattered: on a 915x412
// phone this card genuinely does not fit (504 px of content in 377), and a
// Done button below the fold is the same failure by a slower route. The header
// and the button stay; `.sets-body` between them is what scrolls.
function openSetsPanel() {
  setsPanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card card-split";
  const reserve = appSetReserve();
  // The count rides on the TITLE's line (2026-08-09). It is one short phrase
  // and it was spending a whole row of a card that, on a phone held sideways,
  // has 377 px for ten rows — the cheapest 25 px in the panel, and the title
  // row reads better for it at every size.
  card.innerHTML = `<div class="sets-head"><h2>Wheel sets</h2>
    <span class="sets-sub sets-count">${visibleCount()} of ${wheelCap()} used${reserve ? ` — ${reserve} held for app shortcuts` : ""}</span></div>
    <p class="sets-sub">Mouse, Input and Settings are always in the wheel. Pick the rest — up to ${wheelCap()} in total, app shortcuts included. New sets are made on the PC (Vibe Coder window → Controls…).</p>`;

  // Everything between the header and Done. In portrait it is a plain block
  // and changes nothing; in landscape it is the part that scrolls.
  const body = document.createElement("div");
  body.className = "sets-body";
  card.appendChild(body);

  const list = document.createElement("div");
  list.className = "sets-list";
  categories.forEach((s) => list.appendChild(setsRow(s, !!s.required)));
  customSets.forEach((s) => list.appendChild(setsRow(s, false)));
  body.appendChild(list);

  // App sets are ticked ONE BY ONE (owner 2026-08-05, when Claude joined
  // VSCode on the same window): a single master switch could only say "all
  // app shortcuts or none", and two sets riding the same process is exactly
  // the case where you want one of them gone. The master switch stays as the
  // heading's own checkbox — it still turns the whole group off in one tap.
  const appHead = document.createElement("label");
  appHead.className = "sets-row apps";
  const appCb = document.createElement("input");
  appCb.type = "checkbox";
  appCb.checked = setsPrefs().apps;
  appCb.addEventListener("change", () => {
    const p = setsPrefs();
    p.apps = appCb.checked;
    saveSetsPrefs(p);
    refreshCategories();
    openSetsPanel();  // the per-app rows below follow the master switch
  });
  appHead.append(appCb, document.createTextNode(
    "App shortcuts while a layout is focused — they take wheel slots too"));
  body.appendChild(appHead);

  if (setsPrefs().apps) {
    const appList = document.createElement("div");
    appList.className = "sets-list apps";
    appSets.forEach((s) => appList.appendChild(appSetRow(s)));
    body.appendChild(appList);
  }

  // THE D-PAD SHAPE TICKS LEFT THIS CARD on 2026-08-11 (task 218a). They asked
  // about the shape of the CONTROL GROUPS on this handset and sat in a card
  // titled "Wheel sets", which is about which sets ride the wheel — the owner
  // named the misplacement himself, and this round's Phone card is the home
  // task 160's comment above already promised them. Not copied: MOVED (see
  // client/phone-panel.js), because a switch with two doors is two states to
  // keep in step.

  const done = document.createElement("button");
  done.type = "button";
  done.className = "sets-done";
  done.textContent = "Done";
  keepRowTap(done, closeSetsPanel);
  card.appendChild(done);

  setsPanel.appendChild(card);
  setsPanel.hidden = false;
  refreshSetsMeta();
  setsOpened.t = performance.now();
}

function closeSetsPanel() {
  setsPanel.hidden = true;
  setsPanel.innerHTML = "";
}

setsPanel.addEventListener("pointerdown", (e) => {
  if (e.target === setsPanel) closeSetsPanel(); // backdrop tap = done
});

// The quality panel moved to client/quality.js (owner 2026-08-05) — it edits
// the quality prefs and now reads the PC's base, so it belongs with them.

// --- Command chooser (owner idea 2026-08-05) -------------------------------
// His question, and it is the better design: *"jel ne možemo u centar da
// prikažemo opcije pa korisnik odabere a program automatski odradi selekciju"*.
//
// Some commands are not an ACTION but a CHOICE — `/effort` takes a level, so
// sending it alone only prints its usage, and the first version left Claude's
// own menu on screen for the finger to pick from. That worked, but it made the
// phone depend on another app's menu staying where it is. A button with
// `options` now shows the choices HERE, on the phone, and sends the finished
// command in one go: `/effort` + `high` → `paste_text "/effort high"`.
//
// Any future command of this shape gets it for free — it is a property of the
// button, not a special case for Claude.

const choicePanel = document.getElementById("choice-panel");
const choiceOpened = { t: 0 };
ghostClickArmor(choicePanel, choiceOpened);

function openChoicePanel(btn) {
  const options = (btn.options || []).map((o) =>
    (typeof o === "string" ? { label: o, value: o } : o));
  if (!options.length) return;

  choicePanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card card-columns";
  const title = btn.label || btn.text;
  card.innerHTML = `<h2>${title}</h2>` +
    `<p class="sets-sub">Pick one — the PC types it and runs it.</p>`;

  const list = document.createElement("div");
  list.className = "sets-list";
  for (const option of options) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "sets-row choice";
    row.textContent = option.label;
    // The one he already chose is marked — and marked as SAVED, never as
    // "active" (owner 2026-08-08 asked for a tick; honesty asks for the right
    // word). A `/model` button reads `saved.model`, `/effort` reads
    // `saved.effort`; a command we know nothing about marks nothing.
    const key = btn.text === "/model" ? "model"
      : btn.text === "/effort" ? "effort" : null;
    if (key && claudeSaved[key] === option.value) {
      row.classList.add("chosen");
      row.setAttribute("aria-current", "true");
      const tag = document.createElement("span");
      tag.className = "sets-hint";
      tag.textContent = "saved";
      row.appendChild(tag);
    }
    keepRowTap(row, () => {
      // `enter` is DATA-DRIVEN (owner round 30, 2026-08-09): this used to be
      // hardcoded true, which made the `enter` field in actions.json dead
      // code for every options-based command — a menu-standing command (one
      // whose finished argument still needs a SECOND app to react, e.g.
      // opening a picker) could never say so. Precedence: the OPTION's own
      // `enter` wins, else the BUTTON's, else true — so every command written
      // before this existed keeps sending Enter exactly as it did.
      const enter = option.enter !== undefined ? option.enter
        : (btn.enter !== undefined ? btn.enter : true);
      send({
        type: "paste_text",
        text: `${btn.text} ${option.value}`.trim(),
        enter,
        // Passed through like the plain typed button's (controls.js): a
        // command that must land in a named box says so in its own data, and
        // the generic chooser must not be the one place that drops it.
        ...(btn.focus ? { focus: btn.focus } : {}),
      });
      showToast(`${title}: ${option.label}`);
      closeChoicePanel();
    });
    list.appendChild(row);
  }
  card.appendChild(list);

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "sets-done";
  cancel.textContent = "Cancel";
  keepRowTap(cancel, closeChoicePanel);
  card.appendChild(cancel);

  choicePanel.appendChild(card);
  choicePanel.hidden = false;
  choiceOpened.t = performance.now();
}

function closeChoicePanel() {
  choicePanel.hidden = true;
  choicePanel.innerHTML = "";
}

choicePanel.addEventListener("pointerdown", (e) => {
  if (e.target === choicePanel) closeChoicePanel(); // backdrop tap = cancel
});
