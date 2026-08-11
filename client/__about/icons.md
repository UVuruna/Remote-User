# Icons

**Script:** [icons.js](../icons.js)

## Purpose

The icon set the phone draws — `const ICONS`, one 24×24 stroke fragment per
name — and the **single source of truth for two consumers**: the client
(`svg(name)` in [Controls](controls.md) wraps a fragment in its `<svg>`) and
the desktop **Controls editor**, which parses this very file
(`load_client_icons()`) so its icon combo offers exactly the faces the phone
will draw. An icon added here needs no second edit anywhere.

Split out of `controls.js` on 2026-08-05, when the owner accepted an icon for
every pool command that had none: the table alone had grown past a third of
that module (THE STRUCTURE LAW).

## House style

Every entry obeys it, and a new one must too:

- `viewBox 0 0 24 24`, `stroke-width 2`, round caps and joins — the wrapper in
  `svg()` sets these once, so a fragment never repeats them;
- **no fill unless the fill carries meaning** — the pressed mouse button, the
  occupied half of the screen in `snapl`/`snapr`, the dot of an info box;
- the shape must read at **23 px**, which is how large it lands on a D-pad
  button, and it is always accompanied by the button's text label — the icon
  speeds recognition up, it never carries the meaning alone;
- reuse before invention: `Rename` is the `edit` pencil, Explorer's `New tab`
  is Chrome's `newtab` (owner's own call, 2026-08-05 — one concept, one
  picture).

## Families

| Family | Names |
|--------|-------|
| Mouse | `mouse` `click` `right` `middle` `btn4` `btn5` `drag` `scroll` |
| Input | `keyboard` `mic` `enter` `esc` `newrow` `input` |
| Attach | `attach` `gallery` `shot` `snap` `image` `folder` `region` |
| Edit | `selall` `copy` `cut` `paste` `pasteplain` `undo` `redo` `save` `del` |
| Navigate / Cursor | `nav` `tab` `tabback` `find` `findnext` `arrowl` `arrowr` `arrowu` `arrowd` `wordl` `wordr` `linestart` `lineend` `totop` `tobottom` `pageup` `pagedown` `leftright` |
| Media | `play` `volup` `voldown` `mute` `stop` |
| Windows | `grid` `desktop` `switchwin` `tasks` `maxwin` `minwin` `snapl` `snapr` `run` `x` `newwin` |
| Apps | `sidebar` `palette` `terminal` `preview` `gotofile` `comment` `newtab` `closetab` `address` `reopen` `reload` `newdir` `folderup` `copypath` `details` |
| Claude | `claude` `usage` `model` `thinking` `cmode` `compact` `newchat` `rewind` |
| App faces | `vscode` `chrome` `explorer` |
| System / panels | `settings` `monitor` `monitor2` `gauge` `globe` `list` `aspect` `move` |

## Connections

### Used by
- [Controls](controls.md) — `svg(name)`, every D-pad button and wheel entry
- [Panels](panels.md), [Layouts](layouts.md), [Region](region.md) — same helper
- `server/gui/controls_editor.py` → `load_client_icons()` parses this file

### Design Decisions

- **The editor parses the file, it does not duplicate it.** A copied table
  would drift, and the owner would pick an icon the phone cannot draw.
- **`move` is drawn, never a character** (owner 2026-08-05): the `✥` glyph
  came out a blunt cross on his phone. Nothing user-visible may depend on a
  device's font coverage.
- **A missing name is not an error**: `svg()` returns an empty `<svg>`, and a
  button with no usable icon falls back to a text face (`.ctl.text`).
- **An app-aware set wears its own app's face** (owner 2026-08-06): VSCode,
  Chrome and Explorer all shared the generic `newwin` window, so the wheel
  and the desktop set list said "some app set" instead of naming the app.
  Drawn in the same stroke language as everything else — recognisable at
  24 px, never a bitmap logo. `claude` (the asterisk) was already there.

## The two Hide modes (owner 2026-08-09, task 159)

`hideauto` is the plain eye — the controls come BACK by themselves the moment
anything is touched. `hidestay` is the crossed eye under a padlock — hidden is
hidden until Hide is pressed again. They name the two states of the mini radial
the Hide button opens ([Chrome](chrome.md)); drawn geometry like everything
else here, never a font glyph.
