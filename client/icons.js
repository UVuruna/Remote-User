// The icon set the phone draws — one 24x24 stroke fragment per name, and the
// single source of truth for BOTH the client and the desktop Controls editor
// (which parses `const ICONS` out of THIS file to offer the same faces in its
// icon combo). Split out of controls.js on 2026-08-05, when the owner
// approved an icon for every pool command that had none and the table alone
// outgrew a third of that module (THE STRUCTURE LAW).
//
// House style, kept by every entry: viewBox 0 0 24 24, stroke 2, round caps
// and joins, no fill unless the fill CARRIES meaning (the pressed mouse
// button, the occupied half of the screen in Snap, the dot of an info box).
// Loads before controls.js, which defines svg() over this table.
// See client/__about/icons.md.
"use strict";

const ICONS = {

  mouse: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 7v4"/>',
  right: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 3v7"/><path d="M12 3h2a4 4 0 0 1 4 4v3h-6z" fill="currentColor" stroke="none"/>',
  drag: '<polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><polyline points="15 19 12 22 9 19"/><polyline points="19 9 22 12 19 15"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/>',
  scroll: '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
  // Click = mirror of `right` (owner-approved icon set 2026-08-04); Middle =
  // the filled wheel (variant A of the approved proposals).
  click: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 3v7"/><path d="M12 3h-2a4 4 0 0 0-4 4v3h6z" fill="currentColor" stroke="none"/>',
  middle: '<rect x="6" y="3" width="12" height="18" rx="6"/><rect x="10.6" y="6" width="2.8" height="6" rx="1.4" fill="currentColor" stroke="none"/>',
  // Side buttons (owner 2026-08-05): the same mouse body with the thumb pad
  // filled — rear (Btn 4) and front (Btn 5). The button also carries its
  // label, so the pad's position only has to be recognisable, not readable.
  btn4: '<rect x="7" y="3" width="11" height="18" rx="5.5"/><rect x="3.6" y="11.4" width="3" height="4" rx="1.4" fill="currentColor" stroke="none"/><path d="M12.5 6.5v3.5"/>',
  btn5: '<rect x="7" y="3" width="11" height="18" rx="5.5"/><rect x="3.6" y="6.6" width="3" height="4" rx="1.4" fill="currentColor" stroke="none"/><path d="M12.5 6.5v3.5"/>',
  mic: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><line x1="12" y1="18" x2="12" y2="22"/>',
  enter: '<path d="M20 5v6a3 3 0 0 1-3 3H5"/><path d="m9 10-4 4 4 4"/>',
  esc: '<path d="M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5"/><path d="M15 4h5v5"/><path d="m20 4-8 8"/>',
  // wrap-text: a line breaking onto the next row (the New row button)
  newrow: '<line x1="3" y1="6" x2="21" y2="6"/><path d="M3 12h13a3 3 0 0 1 0 6h-4"/><polyline points="14 16 12 18 14 20"/><line x1="3" y1="18" x2="7" y2="18"/>',
  // Navigate / Cursor sets (owner 2026-08-05)
  nav: '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88" fill="currentColor" stroke="none"/>',
  tab: '<line x1="20" y1="6" x2="20" y2="18"/><path d="M4 12h11"/><path d="m11 8 4 4-4 4"/>',
  tabback: '<line x1="4" y1="6" x2="4" y2="18"/><path d="M20 12H9"/><path d="m13 8-4 4 4 4"/>',
  leftright: '<polyline points="9 7 4 12 9 17"/><polyline points="15 7 20 12 15 17"/>',
  arrowl: '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 5 5 12 12 19"/>',
  arrowr: '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
  // Media set
  play: '<polygon points="5 4 15 12 5 20"/><line x1="19" y1="5" x2="19" y2="19"/>',
  volup: '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19"/><line x1="15" y1="12" x2="21" y2="12"/><line x1="18" y1="9" x2="18" y2="15"/>',
  voldown: '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19"/><line x1="15" y1="12" x2="21" y2="12"/>',
  mute: '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19"/><line x1="15" y1="9" x2="21" y2="15"/><line x1="21" y1="9" x2="15" y2="15"/>',
  attach: '<path d="M21.44 11.05 12.25 20.24a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
  gallery: '<rect x="7" y="3" width="14" height="14" rx="2"/><circle cx="11" cy="7" r="1.5"/><path d="m21 12-3-3-7 7"/><path d="M3 7v11a3 3 0 0 0 3 3h11"/>',
  shot: '<path d="M9 4H6a2 2 0 0 0-2 2v3"/><path d="M15 4h3a2 2 0 0 1 2 2v3"/><path d="M20 15v3a2 2 0 0 1-2 2h-3"/><path d="M4 15v3a2 2 0 0 0 2 2h3"/><circle cx="12" cy="12" r="3"/>',
  folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
  selall: '<rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="3 3.2"/><rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor" stroke="none"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  cut: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/>',
  paste: '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M12 10v7"/><path d="m9 14 3 3 3-3"/>',
  monitor2: '<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/><path d="m10 7.5-3 3 3 3"/><path d="m14 7.5 3 3-3 3"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  redo: '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
  find: '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.2" y2="16.2"/>',
  del: '<path d="M9 5 2.6 12 9 19h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2z"/><line x1="17" y1="9.5" x2="12" y2="14.5"/><line x1="12" y1="9.5" x2="17" y2="14.5"/>',
  keyboard: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M18 13h.01M9 13h6"/>',
  monitor: '<rect x="2" y="4" width="14" height="10" rx="2"/><path d="M9 18h7"/><path d="M9 14v4"/><path d="m17 9 4 3-4 3"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-4.5-4.5L5 21"/>',
  snap: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  x: '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.09a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.09a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>',
  list: '<rect x="4" y="2.5" width="16" height="19" rx="2"/><rect x="9" y="1" width="6" height="3.5" rx="1"/><path d="m7.5 9 1.2 1.2L11 7.8"/><line x1="13" y1="9" x2="17" y2="9"/><path d="m7.5 14 1.2 1.2L11 12.8"/><line x1="13" y1="14" x2="17" y2="14"/><line x1="13" y1="18" x2="17" y2="18"/>',
  input: '<rect x="2" y="6" width="20" height="12" rx="2"/><line x1="6" y1="10" x2="6" y2="14"/><path d="m14 10 3 2-3 2"/>',
  gauge: '<path d="M12 20a8 8 0 1 1 8-8"/><path d="m12 12 5-3"/><path d="M17 17l3 3"/>',
  newwin: '<rect x="3" y="4" width="18" height="16" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><circle cx="6" cy="6.5" r="0.5" fill="currentColor"/><circle cx="8.5" cy="6.5" r="0.5" fill="currentColor"/><line x1="12" y1="11.5" x2="12" y2="17.5"/><line x1="9" y1="14.5" x2="15" y2="14.5"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
  // region inside the screen — the layout aspect-ratio panel
  aspect: '<rect x="2.5" y="4" width="19" height="16" rx="2"/><rect x="7" y="8" width="10" height="8" rx="1"/>',
  desktop: '<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
  // Four-way move (the aspect panel's Move handle). A drawn icon, not the
  // "✥" character: that glyph is whatever the device's font makes of it, and
  // on the owner's phone it came out a blunt cross with no arrowheads
  // (owner 2026-08-05).
  move: '<path d="M12 3.5v17"/><path d="M3.5 12h17"/><path d="m9 6.5 3-3 3 3"/><path d="m9 17.5 3 3 3-3"/><path d="m6.5 9-3 3 3 3"/><path d="m17.5 9 3 3-3 3"/>',

  // ── Approved 2026-08-05 (the owner took the whole proposal page) ─────────
  // Edit reserves
  save: '<path d="M19.5 21h-15a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2H16l5.5 5.5V19a2 2 0 0 1-2 2z"/><path d="M7 21v-7h10v7"/><path d="M7 3v5h7"/>',
  pasteplain: '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M9.5 12.5h5"/><path d="M12 12.5v5.5"/>',
  // Navigate reserves
  findnext: '<circle cx="10.5" cy="10.5" r="6.5"/><line x1="21" y1="21" x2="15.2" y2="15.2"/><path d="M8 10.5h4.6"/><path d="m10.8 8.7 1.8 1.8-1.8 1.8"/>',
  totop: '<line x1="4" y1="4" x2="20" y2="4"/><line x1="12" y1="21" x2="12" y2="9"/><polyline points="6.5 14.5 12 9 17.5 14.5"/>',
  tobottom: '<line x1="4" y1="20" x2="20" y2="20"/><line x1="12" y1="3" x2="12" y2="15"/><polyline points="6.5 9.5 12 15 17.5 9.5"/>',
  pageup: '<polyline points="6 12 12 6 18 12"/><polyline points="6 19 12 13 18 19"/>',
  pagedown: '<polyline points="6 5 12 11 18 5"/><polyline points="6 12 12 18 18 12"/>',
  // Cursor reserves — arrowu/arrowd complete the existing arrowl/arrowr pair,
  // the doubled chevrons are word jumps, the walls are line start / line end
  arrowu: '<line x1="12" y1="20" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>',
  arrowd: '<line x1="12" y1="4" x2="12" y2="19"/><polyline points="5 12 12 19 19 12"/>',
  wordl: '<polyline points="11 6 5 12 11 18"/><polyline points="19 6 13 12 19 18"/>',
  wordr: '<polyline points="13 6 19 12 13 18"/><polyline points="5 6 11 12 5 18"/>',
  linestart: '<line x1="4" y1="5" x2="4" y2="19"/><line x1="20" y1="12" x2="8" y2="12"/><polyline points="13 7 8 12 13 17"/>',
  lineend: '<line x1="20" y1="5" x2="20" y2="19"/><line x1="4" y1="12" x2="16" y2="12"/><polyline points="11 7 16 12 11 17"/>',
  // Media
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  // Windows set
  switchwin: '<rect x="2.5" y="8" width="12" height="10.5" rx="2"/><path d="M9.5 5.5h10a2 2 0 0 1 2 2v9"/>',
  tasks: '<rect x="2.5" y="5" width="10" height="14" rx="2"/><rect x="15" y="5" width="6.5" height="6" rx="1.5"/><rect x="15" y="13" width="6.5" height="6" rx="1.5"/>',
  maxwin: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 15.5v-2.5h2.5"/><path d="M16 8.5v2.5h-2.5"/><line x1="8" y1="15.5" x2="11.5" y2="12"/><line x1="16" y1="8.5" x2="12.5" y2="12"/>',
  minwin: '<rect x="3" y="4.5" width="18" height="11" rx="2"/><line x1="7.5" y1="19.5" x2="16.5" y2="19.5"/><polyline points="9.5 8 12 10.5 14.5 8"/>',
  snapl: '<path d="M4.5 4.5H12v15H4.5a2 2 0 0 1-2-2v-11a2 2 0 0 1 2-2z" fill="currentColor" stroke="none"/><rect x="2.5" y="4.5" width="19" height="15" rx="2"/><line x1="12" y1="4.5" x2="12" y2="19.5"/>',
  snapr: '<path d="M12 4.5h7.5a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H12z" fill="currentColor" stroke="none"/><rect x="2.5" y="4.5" width="19" height="15" rx="2"/><line x1="12" y1="4.5" x2="12" y2="19.5"/>',
  run: '<rect x="2.5" y="5.5" width="19" height="13" rx="2"/><line x1="2.5" y1="9.5" x2="21.5" y2="9.5"/><line x1="6" y1="14" x2="12.5" y2="14"/><path d="m15 12 2 2-2 2"/>',
  // VSCode app set
  sidebar: '<rect x="2.5" y="4.5" width="19" height="15" rx="2"/><line x1="9" y1="4.5" x2="9" y2="19.5"/><line x1="4.8" y1="8.5" x2="7" y2="8.5"/><line x1="4.8" y1="12" x2="7" y2="12"/><line x1="4.8" y1="15.5" x2="7" y2="15.5"/>',
  palette: '<rect x="2.5" y="4.5" width="19" height="15" rx="2"/><rect x="5.5" y="7.3" width="13" height="3.4" rx="1.7"/><line x1="5.5" y1="14" x2="15" y2="14"/><line x1="5.5" y1="17" x2="12" y2="17"/>',
  terminal: '<rect x="2.5" y="4.5" width="19" height="15" rx="2"/><polyline points="6.5 9.5 9.5 12 6.5 14.5"/><line x1="12" y1="15" x2="17.5" y2="15"/>',
  preview: '<rect x="2.5" y="4.5" width="19" height="15" rx="2"/><line x1="12" y1="4.5" x2="12" y2="19.5"/><line x1="5" y1="9" x2="9" y2="9"/><line x1="5" y1="12" x2="9" y2="12"/><line x1="5" y1="15" x2="7.5" y2="15"/><rect x="14.5" y="8" width="5" height="2.2" rx="1.1" fill="currentColor" stroke="none"/><line x1="14.5" y1="13" x2="19" y2="13"/><line x1="14.5" y1="16" x2="17.5" y2="16"/>',
  gotofile: '<path d="M13.5 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.5z"/><polyline points="13.5 3 13.5 8.5 19 8.5"/><circle cx="11.3" cy="14" r="2.6"/><line x1="15.6" y1="18.3" x2="13.2" y2="15.9"/>',
  comment: '<path d="M21 14.5a2 2 0 0 1-2 2H8.5L4 21V5.5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z"/><line x1="8" y1="8.5" x2="17" y2="8.5"/><line x1="8" y1="12" x2="14" y2="12"/>',
  // Chrome / Explorer app sets — newtab and closetab serve both
  newtab: '<rect x="2.5" y="6" width="19" height="14" rx="2"/><line x1="2.5" y1="10" x2="21.5" y2="10"/><line x1="12" y1="12.8" x2="12" y2="17.6"/><line x1="9.6" y1="15.2" x2="14.4" y2="15.2"/>',
  closetab: '<rect x="2.5" y="6" width="19" height="14" rx="2"/><line x1="2.5" y1="10" x2="21.5" y2="10"/><line x1="9.6" y1="12.8" x2="14.4" y2="17.6"/><line x1="14.4" y1="12.8" x2="9.6" y2="17.6"/>',
  address: '<rect x="2.5" y="7" width="19" height="10" rx="5"/><line x1="6.5" y1="12" x2="14" y2="12"/><circle cx="17.6" cy="12" r="1.2" fill="currentColor" stroke="none"/>',
  reopen: '<path d="M3.5 12a8.5 8.5 0 1 1 2.9 6.4"/><polyline points="3.5 6.8 3.5 12 8.7 12"/>',
  reload: '<path d="M20.5 12a8.5 8.5 0 1 1-2.6-6.1"/><polyline points="20.5 4.2 20.5 9.4 15.3 9.4"/>',
  newdir: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11.5" x2="12" y2="17.5"/><line x1="9" y1="14.5" x2="15" y2="14.5"/>',
  folderup: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><polyline points="9 15.5 12 12.5 15 15.5"/><line x1="12" y1="12.5" x2="12" y2="18.5"/>',
  copypath: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/><line x1="12" y1="14" x2="18" y2="14"/><line x1="12" y1="17.5" x2="16" y2="17.5"/>',
  details: '<rect x="3" y="3" width="18" height="18" rx="2.5"/><line x1="12" y1="11" x2="12" y2="16.5"/><circle cx="12" cy="7.8" r="1.15" fill="currentColor" stroke="none"/>',
  // Region (Attach, owner 2026-08-05): a free rectangle with grab handles —
  // dashed, because nothing is captured until you send it
  region: '<rect x="3.2" y="6" width="17.6" height="12" rx="1" stroke-dasharray="3.2 3"/><rect x="1.6" y="4.4" width="3.2" height="3.2" rx="0.9" fill="currentColor" stroke="none"/><rect x="19.2" y="4.4" width="3.2" height="3.2" rx="0.9" fill="currentColor" stroke="none"/><rect x="1.6" y="16.4" width="3.2" height="3.2" rx="0.9" fill="currentColor" stroke="none"/><rect x="19.2" y="16.4" width="3.2" height="3.2" rx="0.9" fill="currentColor" stroke="none"/>',
  // Claude app set (owner 2026-08-05): the set's face is the asterisk; the
  // rest are its commands — usage bars, a model swap, the thinking dial, the
  // mode shield, compact arrows, a fresh conversation, rewind.
  claude: '<path d="M12 2.5v19"/><path d="M2.5 12h19"/><path d="M5.3 5.3 18.7 18.7"/><path d="M18.7 5.3 5.3 18.7"/>',
  usage: '<line x1="5" y1="20" x2="5" y2="12.5"/><line x1="12" y1="20" x2="12" y2="5"/><line x1="19" y1="20" x2="19" y2="15.5"/><line x1="3" y1="20" x2="21" y2="20"/>',
  model: '<circle cx="6.5" cy="7.5" r="3.2"/><circle cx="17.5" cy="16.5" r="3.2"/><path d="M10 7.5h7"/><path d="M14 16.5H7"/><polyline points="14.5 5 17 7.5 14.5 10"/><polyline points="9.5 14 7 16.5 9.5 19"/>',
  thinking: '<path d="M12 20.5a8.5 8.5 0 1 1 8.5-8.5"/><path d="M12 12 16 8.5"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/><line x1="16.5" y1="17.5" x2="21.5" y2="17.5"/><line x1="19" y1="15" x2="19" y2="20"/>',
  cmode: '<path d="M12 3 5 6.2v5.4c0 4.2 2.9 7.7 7 8.6 4.1-.9 7-4.4 7-8.6V6.2z"/><polyline points="9 12 11.2 14.2 15 10"/>',
  compact: '<polyline points="8 8.5 12 4.5 16 8.5"/><polyline points="8 15.5 12 19.5 16 15.5"/><line x1="4" y1="12" x2="20" y2="12"/>',
  newchat: '<path d="M21 14.5a2 2 0 0 1-2 2H8.5L4 21V5.5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z"/><line x1="12.5" y1="7" x2="12.5" y2="13"/><line x1="9.5" y1="10" x2="15.5" y2="10"/>',
  rewind: '<path d="M3.5 12a8.5 8.5 0 1 1 3 6.5"/><polyline points="3.5 6.8 3.5 12 8.7 12"/><path d="M12 8v4.3l3 1.8"/>',
};
