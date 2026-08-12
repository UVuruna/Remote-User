// The CATEGORY WHEEL: the ring a group's dashed centre button opens, the item
// a tap picks, and the geometry that keeps the ring on the screen.
//
// Split out of controls.js on 2026-08-13, when the rotation fix pushed that
// file past THE STRUCTURE LAW's 1,000 lines. The seam is a real one: the wheel
// is one coherent thing with its own state (which side is open), its own
// geometry, and its own lifecycle — it was never a paragraph of "everything
// that drives the PC". It DOES drive the PC in the end (a pick changes which
// commands the D-pad sends), which is why it is here and not in chrome.js,
// whose stated boundary is that nothing in it ever reaches the PC.
//
// Loads AFTER controls.js (uses `keepFocus`, `svg`, `renderGroup`, `groups`,
// `paintSet`) and after chrome.js (`wheelLayout`, `wheelItemSize`,
// `wheelLabelHtml`). `sets.js` supplies `wheelCats`/`placedCat`/`rememberGroup`
// and `allCats`. See client/__about/wheel.md.
"use strict";

const wheelEl = document.getElementById("wheel");
// The ring's GEOMETRY lives in client/chrome.js — `wheelLayout` beside
// `miniRingPoints`, plus `setWheelSide`/`layoutWheel`, which re-run it when the
// screen changes shape under an OPEN ring (owner report 2026-08-13). Furniture
// with no PC-facing side effect; here we only open, fill and close.

function openWheel(side) {
  wheelEl.innerHTML = "";
  setWheelSide(side);
  const screen = { width: window.innerWidth, height: window.innerHeight };
  // wheelCats(side), not allCats() — task 181's drop-out wheel: no duplicate
  // of the other side's placed set, and drop-out also sheds this side's own
  // (sets.js). Renderer unchanged otherwise — it draws whatever list it gets.
  const cats = wheelCats(side);
  const currentCat = placedCat(side);
  // ONE call decides BOTH the face size and the points: the ring may shrink its
  // circles when the screen cannot hold the gap, so `wheelItemSize` alone would
  // put an 86px circle on a 70px plan. `layoutWheel` re-runs exactly this.
  const { size: faceSize, points } = wheelLayout(cats.length, screen, wheelItemSize(cats));
  wheelEl.style.setProperty("--wheel-item-size", `${faceSize}px`);
  cats.forEach((cat, i) => {
    const item = document.createElement("div");
    item.className = "wheel-item" + (cat === currentCat ? " current" : "");
    item.innerHTML = svg(cat.icon) + wheelLabelHtml(cat.name);
    // The wheel is where the colours SAY what they are — and a wheel item is
    // painted with `--glass-strong` (0.85), a different surface from a D-pad
    // button's 0.20 tint, so it gets its own ink.
    paintSet(item, cat.name, "--glass-strong");
    item.style.left = `${points[i].x}px`;
    item.style.top = `${points[i].y}px`;
    keepFocus(item, () => {
      groups[side] = allCats().indexOf(cat); // index into the FULL list
      rememberGroup(side, cat.name); // outlives the next excursion (sets.js)
      renderGroup(side);
      closeWheel();
    });
    wheelEl.appendChild(item);
  });

  const x = document.createElement("div");
  x.className = "wheel-x";
  x.innerHTML = svg("x");
  keepFocus(x, closeWheel);
  wheelEl.appendChild(x);

  wheelEl.addEventListener("pointerdown", backdropCancel);
  wheelEl.classList.add("open");
  // The dimming veil is a layer of its own, under our chrome and over the
  // stream (client/style.css → body.wheel-open::before) — see the note there.
  document.body.classList.add("wheel-open");
}

function backdropCancel(e) {
  if (e.target === wheelEl) {
    e.preventDefault();
    closeWheel();
  }
}

function closeWheel() {
  setWheelSide(null);
  wheelEl.classList.remove("open");
  document.body.classList.remove("wheel-open");
  wheelEl.removeEventListener("pointerdown", backdropCancel);
  wheelEl.innerHTML = "";
}

