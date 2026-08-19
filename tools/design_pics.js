"use strict";
// THE MINI DIAGRAMS — one little picture per KIND of number.
//
// Owner round 2, 2026-08-19: "lepse opise i pa cak i ako treba sa slicicom".
// A sentence answers "what is this for"; a picture answers "which way does it
// move", and for a corner radius, a gap, a ring or a halo the picture is the
// faster of the two. Each row of tools/design_lab.js names one of these by id
// (`pic` in tools/design_groups.py) and the drawing is the same for every row
// that means the same thing — a gap is a gap whether it is under an icon or
// between two cards.
//
// THEY ARE THE LAB'S OWN CHROME, like everything else in this folder: two
// classes (`base` for the shape, `hot` for the quantity being tuned) styled in
// tools/design_lab.css, so a diagram cannot look like a specimen and a
// specimen cannot be mistaken for a diagram. The only literal colours in the
// file are in the two SHADOW pictures, where black and white ARE the subject —
// and both sit on a mid-grey card so neither disappears into the panel.

const PIC_BOX = '0 0 48 32';

const PICS = {
  // — the face —
  size: '<rect class="base" x="8" y="6" width="32" height="20" rx="4"/>' +
        '<path class="hot" d="M12 16h24M12 16l3-3M12 16l3 3M36 16l-3-3M36 16l-3 3"/>',
  radius: '<rect class="base" x="8" y="6" width="32" height="20" rx="8"/>' +
          '<path class="hot" d="M8 14a8 8 0 0 1 8-8"/>',
  icon: '<rect class="base" x="8" y="4" width="32" height="24" rx="4"/>' +
        '<rect class="hot" x="17" y="9" width="14" height="14" rx="3"/>',
  edge: '<rect class="hot" x="9" y="6" width="30" height="20" rx="5" stroke-width="3"/>',
  swatch: '<rect class="base" x="8" y="6" width="32" height="20" rx="5"/>' +
          '<rect class="fill" x="11" y="9" width="26" height="14" rx="3" opacity="0.55"/>',

  // — text —
  label: '<text class="hotfill" x="24" y="24" text-anchor="middle" ' +
         'font-family="system-ui, sans-serif" font-size="19" font-weight="600">Aa</text>',
  ink: '<text class="fill" x="24" y="24" text-anchor="middle" ' +
       'font-family="system-ui, sans-serif" font-size="19" font-weight="600">Aa</text>',
  width: '<rect class="base" x="8" y="8" width="32" height="12" rx="3"/>' +
         '<path class="hot" d="M8 27h32M8 27l3-3M8 27l3 3M40 27l-3-3M40 27l-3 3"/>',

  // — distance —
  gap: '<rect class="fill" x="12" y="4" width="24" height="8" rx="2"/>' +
       '<rect class="fill" x="12" y="22" width="24" height="6" rx="2"/>' +
       '<path class="hot" d="M24 12v10M24 12l-2 2M24 12l2 2M24 22l-2-2M24 22l2-2"/>',
  space: '<rect class="fill" x="4" y="8" width="14" height="16" rx="3"/>' +
         '<rect class="fill" x="30" y="8" width="14" height="16" rx="3"/>' +
         '<path class="hot" d="M18 16h12M18 16l3-3M18 16l3 3M30 16l-3-3M30 16l-3 3"/>',

  // — what happens around the shape —
  ring: '<rect class="base" x="15" y="10" width="18" height="12" rx="3"/>' +
        '<rect class="base" x="12" y="7" width="24" height="18" rx="5" opacity="0.5"/>' +
        '<rect class="hot" x="9" y="4" width="30" height="24" rx="7"/>',
  glow: '<rect class="hotfill" x="5" y="2" width="38" height="28" rx="11" opacity="0.16"/>' +
        '<rect class="hotfill" x="10" y="6" width="28" height="20" rx="8" opacity="0.28"/>' +
        '<rect class="base" x="15" y="10" width="18" height="12" rx="4"/>',
  scale: '<rect class="base" x="7" y="4" width="34" height="24" rx="5" stroke-dasharray="3 3"/>' +
         '<rect class="hot" x="14" y="9" width="20" height="14" rx="3"/>',

  // — the shadow's own three numbers —
  'shift-x': '<rect class="fill" x="20" y="8" width="18" height="16" rx="3" opacity="0.45"/>' +
             '<rect class="hot" x="12" y="8" width="18" height="16" rx="3"/>' +
             '<path class="hot" d="M30 28h8M38 28l-3-2M38 28l-3 2"/>',
  'shift-y': '<rect class="fill" x="14" y="11" width="20" height="17" rx="3" opacity="0.45"/>' +
             '<rect class="hot" x="14" y="4" width="20" height="17" rx="3"/>' +
             '<path class="hot" d="M40 21v7M40 28l-2-3M40 28l2-3"/>',
  blur: '<rect class="fill" x="11" y="5" width="26" height="22" rx="5" opacity="0.12"/>' +
        '<rect class="fill" x="14" y="8" width="20" height="16" rx="4" opacity="0.28"/>' +
        '<rect class="hot" x="17" y="11" width="14" height="10" rx="2"/>',
  strength: '<rect class="hotfill" x="7"  y="8" width="7" height="16" rx="2" opacity="0.22"/>' +
            '<rect class="hotfill" x="16" y="8" width="7" height="16" rx="2" opacity="0.48"/>' +
            '<rect class="hotfill" x="25" y="8" width="7" height="16" rx="2" opacity="0.74"/>' +
            '<rect class="hotfill" x="34" y="8" width="7" height="16" rx="2"/>',

  // THE TWO SHADOW COLOURS — the one place a literal black and a literal white
  // belong, because they ARE what the row is about. The mid-grey card is what
  // lets both of them be seen at once, whichever theme the lab is drawn in.
  'shadow-light':
    '<rect x="3" y="2" width="42" height="28" rx="5" fill="#8b93a5"/>' +
    '<text x="26" y="26" text-anchor="middle" fill="#ffffff" ' +
    'font-family="system-ui, sans-serif" font-size="24" font-weight="700">A</text>' +
    '<text x="23" y="23" text-anchor="middle" fill="#000000" ' +
    'font-family="system-ui, sans-serif" font-size="24" font-weight="700">A</text>',
  'shadow-dark':
    '<rect x="3" y="2" width="42" height="28" rx="5" fill="#8b93a5"/>' +
    '<text x="26" y="26" text-anchor="middle" fill="#000000" ' +
    'font-family="system-ui, sans-serif" font-size="24" font-weight="700">A</text>' +
    '<text x="23" y="23" text-anchor="middle" fill="#ffffff" ' +
    'font-family="system-ui, sans-serif" font-size="24" font-weight="700">A</text>',

  // — the small round things —
  dot: '<circle class="hotfill" cx="24" cy="16" r="8"/>',
  pill: '<rect class="hot" x="5" y="9" width="38" height="14" rx="7"/>',
  // Four squares meaning "several colours at once". Deliberately NOT the
  // shipped palette: an icon that quoted server/config.py would be a fifth
  // copy of those hexes and the one nobody updates.
  sets: '<rect x="5"  y="6"  width="16" height="9" rx="2" fill="#3b82f6"/>' +
        '<rect x="26" y="6"  width="16" height="9" rx="2" fill="#ef4444"/>' +
        '<rect x="5"  y="18" width="16" height="9" rx="2" fill="#f59e0b"/>' +
        '<rect x="26" y="18" width="16" height="9" rx="2" fill="#22c55e"/>',
};

/** The diagram for `id`, or null when a row asked for one that does not exist
 *  — a missing picture is a row without a picture, never a broken page. */
function pic(id) {
  const body = PICS[id];
  if (!body) return null;
  const el = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  el.setAttribute("viewBox", PIC_BOX);
  el.setAttribute("class", "pic");
  el.setAttribute("aria-hidden", "true");
  el.innerHTML = body;
  return el;
}
