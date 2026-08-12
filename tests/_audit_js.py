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
    // TWO KINDS OF DELIBERATE ELLIPSIS, each declared on the element
    // itself rather than allow-listed here where no one editing the
    // product would ever see it:
    //   data-opens-more  — "there is more behind me" (More languages…)
    //   data-in-progress — "this is still happening" (2026-08-12). The
    //     loading overlay's label reads "Arranging the windows…", and its
    //     ellipsis is the whole message: the sentence is COMPLETE and the
    //     work is not. Found the day the overlay was first photographed —
    //     it had never been in the sweep at all, which is why this tooth
    //     had never met a progress ellipsis before.
    if (!el || el.closest('[data-opens-more], [data-in-progress]')) continue;
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

// KIN ROWS ARE THE SAME SIZE — A ROW IS ONE LINE, LIKE A BUTTON (owner
// 2026-08-09, task 163, with his screenshot: one layout row wrapped to FOUR
// lines beside a two-line sibling, because a VS Code window title is 63
// characters long). His rule, in translation: elements of one kin group are
// always the same size, and a long name is CUT — "the first two words, as many
// as fit — and three dots" — never wrapped.
//
// Why no existing instrument could catch it, which is the whole reason this
// one exists: every other measurement in this file judges a SINGLE element (is
// it clipped, can it be read, was its text cut before the DOM saw it), and four
// wrapped lines are none of those things — the row simply grew, legibly, and
// the card scrolled. This defect is a RELATION BETWEEN SIBLINGS, so it needs
// siblings; the panel was staged with ONE layout until today, which is how it
// shipped.
//
// It measures three relations and one fact:
//   - every row the same height WITHIN ITS OWN GROUP, and no row's name taller
//     than one line;
//   - the trailing buttons the same width COLUMN BY COLUMN (found by OPENING
//     the screenshot of the first fix: "Screen" on one row and "3:5" on the
//     next made the main button beside the narrow chip 32 px longer than its
//     neighbour's);
//   - every row's main button the same width, which is the two above seen
//     from the other side;
//   - and that the long title is REALLY elided — without that last one the
//     whole check would pass on a staging whose titles all happen to fit,
//     which is exactly how a one-row staging passed for years.
//
// A CHILD IS NOT IN ITS PARENT'S KIN GROUP (owner 2026-08-09, task 168 — the
// clause that made the creation list's indent legal in the first place:
// "pod-tab ne pripada istoj grupaciji kao njegov roditelj" / lang-ok: owner
// quote). The creation panel now draws a window's tabs as INDENTED rows under
// it, which are narrower than their parent BY DESIGN and may legitimately be
// a different height — a window row carries an app icon and a tab row carries
// none. Comparing across the indent would therefore have made his own drawing
// illegal, and the cheap way out — dropping the height check for these rows —
// would have left the six rows this round rewrote governed by nothing.
//
// So rows are grouped by their INDENT and every relation is measured inside a
// group. The key is the row's own left inset read LIVE (`.lc-kid` in
// client/layout-create.css is a 30 px margin; padding counts too, so a future
// indent spelled the other way still splits the groups) — never the row's
// absolute left edge, which a short-landscape card would split by COLUMN
// instead: `panels.css` reflows a card into two columns under 560 px of
// height, and the layout list's rows really do land in both of them while
// remaining one kin group.
window.__kinRows = (card) => {
  const bad = [];
  const cr = card.getBoundingClientRect();
  const w = (el) => Math.round(el.getBoundingClientRect().width);
  const rows = [...card.querySelectorAll('.lay-item')];
  if (rows.length < 3) {
    bad.push('only ' + rows.length + ' rows staged — a list of one cannot ' +
             'show a sibling of another height');
    return bad;
  }
  const indentOf = (r) => {
    const s = getComputedStyle(r);
    return Math.round((parseFloat(s.marginLeft) || 0) +
                      (parseFloat(s.paddingLeft) || 0));
  };
  const groups = new Map();
  for (const r of rows) {
    const k = indentOf(r);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(r);
  }
  const where = (k) => groups.size < 2 ? '' : ' indented ' + k + 'px';
  for (const [k, kin] of groups) {
    const h = kin.map((r) => Math.round(r.getBoundingClientRect().height));
    if (Math.max(...h) - Math.min(...h) > 1) {
      bad.push('sibling rows' + where(k) + ' differ in height: ' + h.join(' / '));
    }
    // BY COLUMN, since 2026-08-09 (task 164 put a THIRD trailing button on the
    // row — the layout's drawn shape). This used to measure one chip per row,
    // found by `querySelector`, which is whichever comes FIRST in the DOM: add
    // a button in front of it and the tooth silently changes what it is
    // watching and the old kin group stops being measured at all. Every column
    // is its own kin group now — shape against shape, pencil against pencil,
    // aspect against aspect — so a new trailing button joins the law instead
    // of dodging it.
    const chipRows = kin.map((r) => [...r.querySelectorAll('.lay-ratio')])
                        .filter((c) => c.length);
    const cols = chipRows.length
      ? Math.max(...chipRows.map((c) => c.length)) : 0;
    for (let j = 0; j < cols; j++) {
      const col = chipRows.map((c) => c[j]).filter(Boolean).map(w);
      if (col.length > 1 && Math.max(...col) - Math.min(...col) > 1) {
        bad.push('sibling row buttons' + where(k) + ' in column ' + (j + 1) +
                 ' differ in width: ' + col.join(' / '));
      }
    }
    // Only rows that CARRY trailing buttons: the layout list's Desktop row has
    // none, so its main button is legitimately the width of the whole row.
    const mains = kin.filter((r) => r.querySelector('.lay-ratio'))
                     .map((r) => w(r.querySelector('.lay-item-main')));
    if (mains.length > 1 && Math.max(...mains) - Math.min(...mains) > 1) {
      bad.push('sibling rows' + where(k) + ' end at different widths: ' +
               mains.join(' / '));
    }
  }
  for (const r of rows) {
    const span = r.querySelector('.lay-item-main span');
    const st = getComputedStyle(span);
    const line = parseFloat(st.lineHeight) || parseFloat(st.fontSize) * 1.2;
    if (span.getBoundingClientRect().height > line * 1.6) {
      bad.push('a row wrapped: "' + span.textContent.slice(0, 24) + '…"');
    }
    // …and nothing on the row was pushed off the card by a long name.
    for (const b of r.querySelectorAll('button')) {
      const br = b.getBoundingClientRect();
      if (br.right > cr.right + 1 || br.left < cr.left - 1) {
        bad.push('a row button leaves the card');
      }
    }
  }
  const long = rows.map((r) => r.querySelector('.lay-item-main span'))
                   .find((s) => s.textContent.length > 40);
  if (!long) {
    bad.push('no long title staged — the elision is untested');
  } else if (long.scrollWidth <= long.clientWidth + 1) {
    bad.push('the long title was not elided (it fits) — stage a longer one, ' +
             'or the rule is not being exercised');
  }
  return bad;
};

// THE NAME IS NOT THE LAST IN LINE FOR THE ROW'S WIDTH (independent grader,
// 2026-08-09, task 172, who opened the picture and wrote: "the starred row
// spends its width on two leading badges plus three trailing buttons and
// leaves the name 'Claude Cod…' — nine characters, one word, which cannot tell
// two Claude layouts apart, and that is the one job a title has").
//
// WHY THIS ASSERTION AND NOT A PIXEL FLOOR. Every check above judges the row
// as GEOMETRY — same height, nothing wrapped, nothing off the card — and the
// shipped row passed all of them while being useless: 48 px of name beside a
// 96 px chip that said "Screen" is perfectly legal, perfectly aligned and
// perfectly unreadable, which is precisely the gap THE SPACE & LEGIBILITY LAW
// exists to close. A pixel floor would close it too, but only until somebody
// asked where the number came from — a floor of "at least 90 px" is an opinion
// with no argument behind it, and the first row that needs 92 would be a
// negotiation instead of a defect.
//
// So the rule is a RELATION, in the row's own terms: the element carrying the
// row's one irreplaceable fact — which layout this is — may never be narrower
// than the widest button standing beside it. Nothing to tune, nothing that
// drifts with a font or a viewport, and it fails on exactly the row that was
// reported: 48 < 96 at 412 px, 57 < 96 at both landscape sizes, 88 < 96 on the
// tablet — every viewport, which is why it is the check that would have caught
// this before the picture was ever written.
//
// Rows with NO trailing button are skipped (the Desktop row's main button is
// the whole row, and the member chooser and creation list carry none at all),
// so this measures the layout list and says nothing it cannot see.
window.__nameRoom = (card) => {
  const bad = [];
  const w = (el) => Math.round(el.getBoundingClientRect().width);
  let judged = 0;
  for (const r of card.querySelectorAll('.lay-item')) {
    const chips = [...r.querySelectorAll('.lay-ratio')];
    if (!chips.length) continue;
    judged++;
    const span = r.querySelector('.lay-item-main span');
    const widest = chips.reduce((a, b) => (w(a) >= w(b) ? a : b));
    if (w(span) < w(widest)) {
      bad.push('"' + span.textContent.slice(0, 14) + '…" has ' + w(span) +
               'px of name beside a ' + w(widest) + 'px button — the row ' +
               'spends more on a control than on which layout it is');
    }
  }
  if (!judged) bad.push('no row with trailing buttons staged — untested');
  return bad;
};

// ⭐ ON THE TRUNK AND ON NOTHING ELSE (owner decision 2026-08-09, task 169).
// A layout gets a leading star when another layout's content was torn out of
// one of its windows, so closing it would take that other layout with it.
//
// It needs an instrument of its own because the two things that can go wrong
// are invisible to everything else in this file: the star lands on the WRONG
// ROW (a fact about which layout, not about pixels — no clip, contrast or fit
// check can see it), or a COLOUR EMOJI's own metrics lift the row it sits in
// above its siblings, which is task 163's kin defect arriving through a new
// door. `lays` is the page's own staged list, passed in rather than read off
// the window, so what is expected can never drift from what is staged.
window.__layoutStars = (lays) => {
  const bad = [];
  const rows = [...document.querySelectorAll('#layout-panel .lay-item')];
  if (rows.length !== lays.length + 1) {
    bad.push('the list is not Desktop + every layout');
    return bad;
  }
  if (rows[0].querySelector('.lay-star')) {
    bad.push('the Desktop row is starred — it is no layout');
  }
  let seen = 0;
  lays.forEach((lay, i) => {
    const star = rows[i + 1].querySelector('.lay-star');
    if (!!star !== !!lay.parent) {
      bad.push('"' + lay.name.slice(0, 16) + '" ' + (lay.parent
        ? 'is a parent and carries no star'
        : 'is starred and is not a parent'));
      return;
    }
    if (!star) return;
    seen++;
    const sr = star.getBoundingClientRect();
    const nm = rows[i + 1].querySelector('.lay-item-main span');
    const nr = nm.getBoundingClientRect();
    if (sr.width < 8 || sr.height < 8) {
      bad.push('the star did not render (' + Math.round(sr.width) + 'x' +
               Math.round(sr.height) + ')');
    }
    // Before the first letter of the name, on the name's own line.
    if (sr.right > nr.left + 1) bad.push('the star overlaps the name');
    if (Math.abs((sr.top + sr.bottom) / 2 - (nr.top + nr.bottom) / 2) > 4) {
      bad.push("the star does not sit on the name line");
    }
    // …and it is not part of the text, so the long name still elides.
    if (nm.scrollWidth <= nm.clientWidth + 1 && nm.textContent.length > 40) {
      bad.push('the starred row stopped eliding its long name');
    }
  });
  if (!seen) bad.push('no parent staged — the star is untested');
  return bad;
};

// HE PICKS THE WINDOW BY ITS POSITION (owner request 2026-08-09, task 165).
// The member chooser's whole premise is that every row draws the layout's grid
// with ITS OWN cell lit — a grid of four VS Code windows has four nearly
// identical titles, and only one of them is the top-left square. The lit cell
// is the LAST path of the drawing (the faint rest is drawn first), so two rows
// lighting the same square is a defect only the live page can report.
// Run beside `__kinRows`, which governs the same rows as rows.
window.__memberCells = (card) => {
  const bad = [];
  const lit = [...card.querySelectorAll('.lay-item')].map((r) => {
    const p = [...r.querySelectorAll('.lay-cell-ico path')];
    return p.length ? p[p.length - 1].getAttribute('d') : null;
  });
  if (!lit.length || lit.some((d) => !d)) {
    bad.push('a member row carries no cell drawing');
  } else if (new Set(lit).size !== lit.length) {
    bad.push('two member rows light the SAME cell — nothing on screen tells ' +
             'them apart');
  }
  return bad;
};

// A SCROLLING LIST MAY NOT LIVE INSIDE A COLUMNED CARD (found 2026-08-09 by
// photographing the creation panel at 915x412 — this round's own
// verification, and the reason this instrument exists).
//
// The landscape reflow of task 172 gives a card `column-count: 2`, which makes
// it a FRAGMENTAINER; the creation panel's window list inside it is a scroll
// container. The two do not compose, and the failure is not subtle once it is
// looked at: the fourth of six rows came out sliced through the middle, ten
// pixels above the "Shape:" block in the same column, with rows five and six
// nowhere and no scrollbar to say they existed. MEASURED in the real
// Chromium this audit runs: a scroller inside a multicol is not clipped by
// its own box at all — `overflow: hidden` does not clip it either, `column
// -span: all` does not fix it, and the same list with twenty windows put
// fourteen rows off the bottom of the screen while the card reported no
// scroll of its own to make.
//
// WHY A STRUCTURAL RULE AND NOT A PIXEL ONE. Every other instrument in this
// file measures a rendered box, and each of them was green on that panel:
// nothing overflowed the CARD, no text was cut before the DOM saw it, the
// contrast was fine, the rows were the same height. The defect is a
// COMPOSITION — two layout modes that are each correct alone — so what is
// checked is the composition. It has no number to tune and it generalises:
// any future panel that puts a scroller in a columned card is caught the day
// it is staged, instead of the day somebody opens its screenshot.
window.__scrollInColumns = (card) => {
  const bad = [];
  const cs = getComputedStyle(card);
  const cols = parseInt(cs.columnCount, 10);
  if (!(cols > 1)) return bad;          // not a fragmentainer — nothing to say
  const scrolls = (s) => s === 'auto' || s === 'scroll';
  for (const el of card.querySelectorAll('*')) {
    const s = getComputedStyle(el);
    if (!scrolls(s.overflowY) && !scrolls(s.overflowX)) continue;
    if (el.scrollHeight <= el.clientHeight + 1 &&
        el.scrollWidth <= el.clientWidth + 1) continue;   // holds nothing back
    bad.push('"' + (el.className || el.tagName) + '" scrolls (' +
             el.scrollHeight + ' in ' + el.clientHeight + ') inside a ' +
             cols + '-column card — a fragmentainer does not clip it, so its ' +
             'rows paint over whatever the next column holds');
  }
  return bad;
};

// HOW MUCH OF A CARD THE USER CANNOT SEE — the card's own scroll, or that of
// anything scrolling inside it (2026-08-09).
//
// `noScrollWithSlack` in test_layout_audit.py read `card.scrollHeight -
// card.clientHeight` and nothing else, which was the whole truth while every
// panel card was one scrolling block. The Sets picker stopped being one on
// this round: on a 915x412 phone it does not fit, so it pins its Done button
// and scrolls a `.sets-body` between the header and it — a better card, and
// one whose CARD reports no scroll at all. The number the rule exists to
// judge would have walked out of its reach on the day the layout improved,
// which is the same class of miss as measuring a JS variable instead of the
// geometry (task 149's Move handle). What is asked is therefore what the
// user experiences: how much of this panel is out of sight, wherever the
// scrollbar happens to live.
window.__hiddenPx = (card) => {
  let hidden = card.scrollHeight - card.clientHeight;
  for (const el of card.querySelectorAll('*')) {
    const s = getComputedStyle(el);
    if (s.overflowY === 'auto' || s.overflowY === 'scroll') {
      hidden = Math.max(hidden, el.scrollHeight - el.clientHeight);
    }
  }
  return hidden;
};

// WHAT ELSE DIES WITH THESE WINDOWS, SAID BEFORE HE TAPS (owner 2026-08-09,
// task 171). Closing a layout's windows destroys any OTHER layout whose
// content was torn out of one of them — the tab has no home to go back to —
// and until this round the ✕ chooser said nothing about it. The server names
// them (`layout_state.dependents`); this proves the phone puts those names on
// the irreversible option and on nothing else.
//
// It needs its own instrument for the reason `__layoutStars` does: WHICH
// option carries the warning is a fact about meaning, not about pixels, and a
// warning printed under the harmless act — or under both — is worse than none.
// `deps` is the page's own staged list, passed in, so what is expected can
// never drift from what is staged.
window.__closeWarning = (deps) => {
  const bad = [];
  const chips = [...document.querySelectorAll('#layout-panel .lay-source')];
  if (chips.length !== 2) {
    bad.push('the chooser is not two options');
    return bad;
  }
  const warned = chips.filter((c) => c.querySelector('.lay-warn'));
  if (!deps.length) {
    if (warned.length) bad.push('a layout with no dependents was warned about');
    return bad;
  }
  if (warned.length !== 1) {
    bad.push(warned.length + ' of the two options carry the warning — only ' +
             'the CLOSE one may');
    return bad;
  }
  // The one that closes windows is the one that must carry it. Identified by
  // what it SAYS it does, never by its position in the row.
  const label = (warned[0].textContent || '').toLowerCase();
  if (label.indexOf('close') < 0) {
    bad.push('the warning sits on the option that closes nothing');
  }
  const text = warned[0].querySelector('.lay-warn').textContent;
  for (const name of deps) {
    if (text.indexOf(name) < 0) {
      bad.push('"' + name + '" would be destroyed and is not named: "' +
               text.slice(0, 60) + '"');
    }
  }
  // …and it is READ, not merely present: it wraps, it is not cut, and it
  // stays inside the card like every other consequence line on it.
  const el = warned[0].querySelector('.lay-warn');
  const cr = document.querySelector('#layout-panel .lay-card')
    .getBoundingClientRect();
  const wr = el.getBoundingClientRect();
  if (el.scrollWidth > el.clientWidth + 1) bad.push('the warning is clipped');
  if (wr.left < cr.left - 1 || wr.right > cr.right + 1 ||
      wr.bottom > cr.bottom + 1) {
    bad.push('the warning leaves the card');
  }
  return bad;
};

// THE ⚙ SHEET OFFERS EXACTLY WHAT THIS LAYOUT CAN TAKE (owner 2026-08-09,
// task 175 — one common settings icon instead of one icon per act).
//
// The sheet IS its list of acts, so what has to be true of it is not a
// geometry: a SOLO layout has no window to throw out and no arrangement to
// choose, and offering either would be a control that cannot act — the same
// rule that makes a solo row's shape badge a plain <span> rather than a
// button. Nothing else in this file can see that: a row that does nothing is
// legible, unclipped, the right height and inside the card.
//
// The arrangement is the asymmetry of the owner's own sheet (2026-08-07): a 2
// and a 4 have one arrangement each and a 3 has four, so the chips are offered
// for a three and for nothing else. `members` is passed in from the staging,
// never read off the page, so the expectation cannot drift from what is
// staged.
window.__settingsSheet = (members) => {
  const bad = [];
  const card = document.querySelector('#layout-panel .lay-card');
  if (!card) { bad.push('the sheet did not open'); return bad; }
  const rows = [...card.querySelectorAll('.lay-item')];
  const labels = rows.map(
    (r) => (r.querySelector('.lay-item-main span') || {}).textContent || '');
  const has = (re) => labels.some((t) => re.test(t));
  if (!has(/rename/i)) bad.push('no Rename row');
  if (!has(/aspect/i)) bad.push('no Aspect ratio row');
  if (has(/window out/i) !== (members > 1)) {
    bad.push(members > 1
      ? 'a grid offers no way to take a window out'
      : 'a SOLO layout offers to take a window out of nothing');
  }
  // The rows are kin — one line each, the same height, inside the card.
  const h = rows.map((r) => Math.round(r.getBoundingClientRect().height));
  if (h.length && Math.max(...h) - Math.min(...h) > 1) {
    bad.push('the sheet rows differ in height: ' + h.join(' / '));
  }
  const cr = card.getBoundingClientRect();
  for (const b of card.querySelectorAll('button')) {
    const br = b.getBoundingClientRect();
    if (br.left < cr.left - 1 || br.right > cr.right + 1) {
      bad.push('a control leaves the card: "' +
               (b.textContent || '').slice(0, 18) + '"');
    }
  }
  // Orientation is always offered (his second half of the task — a layout
  // built portrait used to need deleting to become landscape) and exactly one
  // of the two is lit.
  const orient = [...card.querySelectorAll('.lay-chip.lay-shape')];
  if (orient.length !== 2) {
    bad.push(orient.length + ' orientation chips, expected 2');
  } else if (orient.filter((c) => c.classList.contains('sel')).length !== 1) {
    bad.push('the current orientation is not the lit one');
  }
  const arr = [...card.querySelectorAll('.lay-chip.lay-grid:not(.lay-shape)')];
  const wantArr = members === 3 ? 4 : 0;
  if (arr.length !== wantArr) {
    bad.push(arr.length + ' arrangement chips for ' + members +
             ' windows, expected ' + wantArr);
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

# THE PICTURE NEVER GOES BLANK (task 151, 2026-08-10 — 3b7b477 restored onto
# the new client/live-clock.js mechanism). Paints the canvas a known colour
# once before any frame has ever been drawn (clearing IS correct there) and
# once after (a gap must leave the last picture alone) — the generic-blue
# failure the owner photographed live at max settings.
LIVE_CLOCK_BLANK_JS = """() => {
  const realBg = canvasBg;
  streamMode = 'h264';
  everDrew = false;
  canvasBg = '#010203';
  redraw();
  const before = ctx.getImageData(1, 1, 1, 1).data;
  const bad = [];
  if (!(before[0] === 1 && before[1] === 2 && before[2] === 3)) {
    bad.push('a session with no frame yet did not paint the page colour');
  }
  everDrew = true;
  canvasBg = '#0a0b0c';
  redraw();
  const after = ctx.getImageData(1, 1, 1, 1).data;
  if (after[0] === 10 && after[1] === 11 && after[2] === 12) {
    bad.push('a gap in the stream wiped the last picture');
  }
  canvasBg = realBg;
  everDrew = false;
  return bad;
}"""

# THE TRUTH TABLE MATCHES HIS SIX CASES (task 151 — a9db36b restored onto
# client/live-clock.js's `liveAction`). The pure module has its own gate
# (tests/test_live_clock.py, driven whole in node); this is the WIRING half —
# the live page must answer the same cases through the real globals it runs
# with (LIVE_MAX_BEHIND_S / LIVE_STARVED_S, client/state.js).
LIVE_CLOCK_DRIFT_JS = """() => [
  ['healthy 0.20s', liveAction(0.20, LIVE_MAX_BEHIND_S, LIVE_STARVED_S), 'live'],
  ['at the edge 0.49', liveAction(0.49, LIVE_MAX_BEHIND_S, LIVE_STARVED_S), 'live'],
  ['drifted 0.80s', liveAction(0.80, LIVE_MAX_BEHIND_S, LIVE_STARVED_S), 'seek_forward'],
  ['his freeze -11.1s', liveAction(-11.1, LIVE_MAX_BEHIND_S, LIVE_STARVED_S), 'starved'],
  ['just past zero -0.05s', liveAction(-0.05, LIVE_MAX_BEHIND_S, LIVE_STARVED_S), 'live'],
  ['starved -0.5s', liveAction(-0.5, LIVE_MAX_BEHIND_S, LIVE_STARVED_S), 'starved'],
].filter(([, got, want]) => got !== want)"""


# ── WHAT A PANEL CARD MUST SATISFY, measured on the live page ─────────────
# Moved here from tests/test_layout_audit.py on 2026-08-10: this file owns
# HOW a truth about pixels is computed, that one owns WHICH screen is opened
# and what is asserted — the split both files' docstrings already state. It
# moved when the free-width correction of tasks 215/217 took the audit past
# THE STRUCTURE LAW's 1,000 lines, and the boundary it moved across was
# already the right one.
PANEL_FIT_JS = """(sel) => {
          const card = document.querySelector(sel);
          const r = card.getBoundingClientRect();
          // INSIDE THE VIEWPORT, OR INSIDE A PANEL THAT SCROLLS IT (corrected
          // 2026-08-10, task 217). Before that fix a card could never be taller
          // than the screen, because a capped multicol silently fragmented
          // sideways instead — so "is it in the viewport" and "can he reach all
          // of it" were the same question. They are not: a genuinely long card
          // (the dictation list of a phone with fourteen languages) is now
          // taller than a 412 px screen ON PURPOSE and its panel scrolls. What
          // must still hold is that no part of it is unreachable, which is
          // exactly `left/right` inside the viewport and `top/bottom` inside
          // the panel's own scroll extent.
          const pan = card.parentElement;
          const pr = pan.getBoundingClientRect();
          const scrolls = /(auto|scroll)/.test(getComputedStyle(pan).overflowY);
          const inView = r.left >= 0 && r.right <= innerWidth + 1 &&
            (scrolls
              ? r.top >= pr.top + pan.scrollTop - 1 &&
                r.height <= pan.scrollHeight + 1
              : r.top >= 0 && r.bottom <= innerHeight + 1);
          const noPageScroll =
            document.scrollingElement.scrollWidth <= innerWidth + 1;
          // WHICH element, not merely "something": "noClip: False" alone costs
          // a whole probe run to localise (2026-08-09).
          const clipped = [];
          for (const el of card.querySelectorAll('button, .q-row, .sets-row, input')) {
            if (el.scrollWidth > el.clientWidth + 2) {
              clipped.push((el.className || el.tagName) + ' ' +
                           el.scrollWidth + '>' + el.clientWidth);
            }
          }
          const noClip = !clipped.length &&
                         card.scrollWidth <= card.clientWidth + 1;
          // BUG A of THE SPACE & LEGIBILITY LAW, measured (2026-08-07): "a
          // visible scrollbar with unused space in the same window is a bug,
          // not a style choice". Not "the card never scrolls" — rung 4 is
          // legal once the screen is full — but "it never scrolls while width
          // stands idle beside it", which is what landscape did to seven of
          // these ten panels: 420 px of card in a 915 px screen, by up to
          // 256 px. Counted over the card AND whatever scrolls INSIDE it
          // (`__hiddenPx` — a pinned footer must not hide that number).
          const hidden = __hiddenPx(card);
          // FREE WIDTH IS WHAT THE CARD COULD STILL TAKE, never what the
          // SCREEN has left over (corrected 2026-08-10, tasks 215/217): the
          // old `innerWidth - r.width` counted the panel's own mandatory
          // gutter (2 x --space-m = 32px, over the 24px tolerance) as idle
          // space, and convicted every full-width portrait card of BUG A for
          // having a margin — invisible until a card was finally staged long
          // enough to SCROLL upright. A card cannot grow into its panel's
          // padding, so rung 1 really is exhausted there.
          const ps = getComputedStyle(card.parentElement);
          const freeW = card.parentElement.getBoundingClientRect().width
            - parseFloat(ps.paddingLeft || 0) - parseFloat(ps.paddingRight || 0)
            - r.width;
          const noScrollWithSlack = !(hidden > 1 && freeW > 24);
          return { inView, noPageScroll, noClip, noScrollWithSlack, clipped,
                   hiddenPx: hidden, freeWidthPx: Math.round(freeW),
                   contrast: __contrast(card),
                   // …and the cut this file could not see until 2026-08-07:
                   // a string JavaScript shortened before the DOM existed.
                   truncated: __truncated(card) };
        }"""
