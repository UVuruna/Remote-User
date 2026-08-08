"""The measuring instruments the phone audit injects into the live page.

Split out of tests/test_layout_audit.py on 2026-08-08, when the status pill's
own contrast check pushed that file past THE STRUCTURE LAW's 1,000 lines. The
boundary is a real one: this file is HOW a truth about pixels is measured —
compositing, luminance, WCAG floors, per-set repaints — while the audit itself
decides WHICH screens are opened and what is asserted about them. The two
change for entirely different reasons, and only this one has to be right about
colour maths.

Everything here is a JavaScript source string, installed once per page via
`page.add_init_script` / `page.evaluate`. Nothing in it imports anything.
"""

# CONTRAST - the check that was missing (owner screenshot 2026-08-06: six
# white bars with near-white labels on them, and every geometric check green).
# Text that cannot be read is not a style opinion, it is unreadable content,
# and the law's whole subject is content the user must read. A <button> with
# no background of its own inherits the WebView's light default while the
# theme keeps its light text - which is exactly how it happened.
#
# ALPHA IS COMPOSITED, never ignored: this project's own selected states are
# translucent accent over a card, and reading that as solid accent under
# accent text reports 1.00:1 on a button that is perfectly readable. A guard
# that cries wolf gets switched off, so it measures what the eye gets: every
# layer painted over the one below it.
#
# THE FLOOR IS READ, NOT ASSUMED (build round R3). It was the literal
# [15, 23, 42] - the dark theme's --surface-0 - which would have quietly
# scored every LIGHT-theme panel against a dark page that is not there, and
# passed unreadable combinations. It now comes from the live variable, so the
# same check is honest in all eight looks.
#
# Installed ONCE per page as `window.__contrast(root)` so the panels, the
# D-pad and the wheel are all judged by the same function instead of by three
# copies of it (rules/CODE.md - No Duplicate Code).
#
# WHAT IS PAINTED *OVER* IT COUNTS TOO (independent grader, 2026-08-07 — the
# hole that let a 2.66:1 label through this check green). The walk below only
# ever looked DOWNWARD, through the element's own ancestors, so a full-screen
# overlay lying ON TOP of the element was invisible to it: the category wheel
# used to paint `--scrim-soft` (0.55 navy) across the whole viewport at z-index
# 35, above the D-pad at 20, and the tooth kept scoring those labels against
# the un-veiled surface — 8.05:1 where a person reading the screenshot measures
# 2.66:1. The same class of miss would hit any future overlay. So every visible
# fixed full-viewport layer with a higher z-index than the element is now
# composited over BOTH the ink and its background, exactly as a camera sees it.
#
# ANCESTOR OPACITY COUNTS TOO: `.ctl.cat` is drawn at 0.85, which the old check
# ignored because it read `opacity` only on the text leaf itself.
CONTRAST_JS = """
window.__contrast = (root) => {
  const parse = (c) => {
    const m = (c || '').match(/[\\d.]+/g);
    if (!m || m.length < 3) return null;
    return [+m[0], +m[1], +m[2], m.length > 3 ? +m[3] : 1];
  };
  const over = (top, bottom) =>
    [0, 1, 2].map((i) => top[i] * top[3] + bottom[i] * (1 - top[3]));
  const PAGE = parse(getComputedStyle(document.body).backgroundColor) ||
               [15, 23, 42];
  // Every layer this page paints across the WHOLE viewport, with the z-index
  // it paints at. Real elements and body's ::before pseudo alike — the veil
  // this round moved under the controls is a pseudo, and a check that could
  // not see it would prove nothing about the fix.
  const veils = [];
  const addVeil = (el, pseudo) => {
    const s = getComputedStyle(el, pseudo || null);
    if (s.display === 'none' || s.visibility === 'hidden') return;
    if (pseudo && (s.content === 'none' || s.content === 'normal')) return;
    if (s.position !== 'fixed') return;
    if (['top', 'left', 'right', 'bottom'].some((k) => s[k] !== '0px')) return;
    const c = parse(s.backgroundColor);
    if (!c || c[3] === 0) return;
    const z = parseInt(s.zIndex, 10);
    if (!isFinite(z)) return;
    veils.push({ z: z, c: c });
  };
  for (const el of document.body.children) addVeil(el);
  addVeil(document.body, '::before');
  addVeil(document.body, '::after');
  // Where the element itself sits in that stack, and how much of it survives
  // its ancestors' opacity.
  const stackOf = (el) => {
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const z = parseInt(getComputedStyle(n).zIndex, 10);
      if (isFinite(z)) return z;
    }
    return 0;
  };
  const alphaOf = (el) => {
    let a = 1;
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const o = parseFloat(getComputedStyle(n).opacity);
      if (isFinite(o)) a *= o;
    }
    return a;
  };
  const bgOf = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (!c || c[3] === 0) continue;
      layers.push(c);
      if (c[3] === 1) break;
    }
    let base = PAGE.slice(0, 3);
    for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
    return base;
  };
  const veiled = (rgb, z) => {
    let base = rgb;
    for (const v of veils.slice().sort((a, b) => a.z - b.z)) {
      if (v.z > z) base = over(v.c, base);
    }
    return base;
  };
  const lumOf = (rgb) => {
    const [r, g, b] = rgb.map((v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const bad = [];
  for (const el of root.querySelectorAll('*')) {
    const text = (el.textContent || '').trim();
    if (!text || el.children.length) continue;   // leaf text only
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    const alpha = alphaOf(el);
    if (alpha < 0.5) continue;  // deliberately inert
    const ink = parse(style.color);
    if (!ink || ink[3] === 0) continue;
    const z = stackOf(el);
    const bgRgb = bgOf(el);
    // ink -> its own background -> the element's inherited opacity -> every
    // veil painted above it. The order a compositor uses, and the order a
    // photograph of the phone records.
    let fgRgb = over(ink, bgRgb);
    if (alpha < 1) fgRgb = over([...fgRgb, alpha], bgRgb);
    const fg = lumOf(veiled(fgRgb, z));
    const bg = lumOf(veiled(bgRgb, z));
    const ratio = (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
    // THE FLOOR IS PER-ELEMENT, NOT ONE NUMBER FOR EVERYTHING (independent
    // grader, 2026-08-07 — measured 2.66:1 on a 13 px D-pad label and named
    // this check itself as the reason it shipped: "widen that check to
    // measure what these numbers measure, or it will come back"). WCAG's 3:1
    // floor is for LARGE text ONLY — 24px normal weight, or 18.66px (14pt) at
    // bold (>=700) — and every label this project draws is smaller than
    // that (D-pad .lbl is 9px, wheel-item text 12px, panel body 13-16px).
    // Everything else is held to 4.5:1, the number the grader actually cited.
    const px = parseFloat(style.fontSize) || 0;
    const weight = parseInt(style.fontWeight, 10) || 400;
    const isLarge = px >= 24 || (px >= 18.66 && weight >= 700);
    const floor = isLarge ? 3.0 : 4.5;
    if (ratio < floor) {
      bad.push(text.slice(0, 20) + ' [' + el.tagName.toLowerCase() + '.' +
               (el.className || '-') + '] ' + style.color + ' on ' +
               ratio.toFixed(2) + ':1 (needs ' + floor.toFixed(1) + ':1)');
    }
  }
  return bad;
};

// TEXT CUT BEFORE THE DOM EVER SEES IT (independent grader, 2026-08-07 — the
// hole that let the owner's OWN complaint pass three rounds green). Every
// clip test in this file measures the DOM: `scrollWidth > clientWidth`, a
// card wider than its viewport, a label outside its button. A string that
// JavaScript shortened BEFORE creating the node defeats all of them by
// construction — `client/layouts.js` did `s.title.slice(0, 29) + "…"`, so the
// element fitted perfectly, `scrollWidth === clientWidth`, and the audit could
// only ever report PASS while 225 device px stood idle on the same row and
// the owner was writing "a pun naziv se na tom ekranu ne vidi nigde".
//
// The tell such a cut leaves behind is the ellipsis IN THE TEXT ITSELF, so
// that is what this measures: any text node that ends in "…" (or "...") while
// there is free width to its right on its own row. CSS elision leaves no
// ellipsis in the text — that case is the scrollWidth check's, and the two
// together cover both ways a string can be shortened.
//
// The one deliberate ellipsis this app draws ("More languages (2)…", which
// means "there is more behind me") declares itself with `data-opens-more` in
// client/panels.js. An allow-list of strings HERE would have been the same
// thing written where nobody editing the product would see it.
window.__truncated = (root) => {
  const bad = [];
  const cs = getComputedStyle(root);
  const rr = root.getBoundingClientRect();
  // The right edge of the column the text is laid out in — the card's own
  // content box, which is exactly what the grader measured by hand (chip ends
  // at 523, the column runs to 748).
  //
  // Honest limit: on a SHORT landscape screen the card is a two-column
  // multicol (style.css), so an element in the first column is measured
  // against the second column's right edge and looks freer than it is. That
  // errs toward FAILING, never toward passing, which is the only direction a
  // tooth may err in.
  const colRight = rr.right - (parseFloat(cs.paddingRight) || 0) -
                              (parseFloat(cs.borderRightWidth) || 0);
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const t = (n.nodeValue || '').replace(/\\s+$/, '');
    if (!/(\\u2026|\\.\\.\\.)$/.test(t)) continue;
    const el = n.parentElement;
    if (!el || el.closest('[data-opens-more]')) continue;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    const rects = [...range.getClientRects()].filter((r) => r.width > 0);
    if (!rects.length) continue;
    const last = rects[rects.length - 1];
    const free = Math.round(colRight - last.right);
    if (free > 24) {
      bad.push('"' + t.trim().slice(-30) + '" [' + el.tagName.toLowerCase() +
               '.' + (el.className || '-') + '] was cut with ' + free +
               ' CSS px still free on its row');
    }
  }
  return bad;
};

// EVERY COLOUR IN THE TABLE, not merely the three the fixture happens to show
// (independent grader, 2026-08-07: "that tooth is the only safety net for
// `colored` when the owner retunes his palette"). tests/fixtures/actions.json
// ships Mouse / Input / Edit, so ten of the desktop's thirteen set colours had
// never been measured on any surface at all — a set whose colour the owner
// darkens tomorrow would reach his phone unreadable with every check green.
// `paintSet` is the product's own entry point and takes a NAME, so the real
// D-pad and the real wheel items are repainted with each colour in turn and
// measured through the same `__contrast` as everything else.
window.__sweepSetColours = (names) => {
  const bad = [];
  const group = document.getElementById('group-left');
  for (const name of names) {
    paintSet(group, name, '--glass-fill');
    for (const t of __contrast(group)) bad.push(name + ' D-pad: ' + t);
  }
  openWheel('left');
  const items = [...document.querySelectorAll('#wheel .wheel-item')];
  for (const name of names) {
    items.forEach((it) => paintSet(it, name, '--glass-strong'));
    for (const t of __contrast(document.getElementById('wheel')))
      bad.push(name + ' wheel: ' + t);
  }
  closeWheel();
  renderGroup('left');   // the real set's own colour goes back
  return bad;
};

// THE STATUS PILL — EVERY TOAST THIS APP SHOWS (fix of 2026-08-08).
//
// It needs its own check, and the reason is the whole finding. `__contrast`
// reads `backgroundColor` up the ancestor chain; the pill's fill is a
// linear-GRADIENT, so its backgroundColor is transparent and the walk scores
// the ink against the PAGE behind it. The element that carries every notice
// this product gives — "Layout refused: a window would not land where it was
// commanded" — was therefore invisible to the one tooth that would have
// caught it, and shipped at 1.97:1 through four visual rounds.
//
// A gradient has no single background, so the STOPS are measured: they bound
// every pixel between them. Read live from the page's own tokens, so a retune
// of the palette fails this instead of quietly re-opening the hole.
window.__pillContrast = () => {
  const css = getComputedStyle(document.documentElement);
  const hex = (v) => {
    const s = css.getPropertyValue(v).trim();
    const m = s.match(/^#([0-9a-f]{6})$/i);
    if (m) return [0, 2, 4].map((i) => parseInt(m[1].substr(i, 2), 16));
    const n = (s.match(/[\\d.]+/g) || []).map(Number);
    return n.length >= 3 ? n.slice(0, 3) : null;
  };
  const lum = (rgb) => {
    const [r, g, b] = rgb.map((v) => {
      const c = v / 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const bad = [];
  // `.connected` is deliberately absent: it is the pill's RESTING state and
  // it is painted at opacity 0. Nobody reads it, so it is not a surface.
  for (const [ink, fills, what] of [
    ['--on-warning', ['--warning', '--warning-2'], 'toast'],
    ['--on-error', ['--error', '--error-2'], 'disconnected'],
  ]) {
    const fg = hex(ink);
    if (!fg) { bad.push(what + ': ' + ink + ' is not defined'); continue; }
    for (const fill of fills) {
      const bg = hex(fill);
      if (!bg) { bad.push(what + ': ' + fill + ' is not defined'); continue; }
      const a = lum(fg), b = lum(bg);
      const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      // 14px at weight 600 — not large text by WCAG, so the 4.5:1 floor.
      if (ratio < 4.5) {
        bad.push(what + ': ' + ink + ' on ' + fill + ' = ' +
                 ratio.toFixed(2) + ':1 (needs 4.5:1)');
      }
    }
  }
  return bad;
};
"""
