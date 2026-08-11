# VERIFICATION — everything delivered on 2026-08-11, and every point the owner checks

One big list, as ordered ("implementiraj sve pa cu ja posle da testiram sve
... ostavi neku listu sta je sve uradjeno i sta ja sve treba da proverim" —
lang-ok: owner quote). Four releases: **v0.0.108, v0.0.109, v0.0.110,
v0.0.111** — install the newest ([Releases](https://github.com/UVuruna/Remote-User/releases))
on the PC and BOTH phones, then walk the checklist. Every item names the task
it closes; a broken item is a repeat — report it with what you saw.

## A. Layouts

- [ ] **Creation panel** (227): open Layout (+) → List with many windows —
  Cancel/Create are ALWAYS visible; a finger drag over the rows SCROLLS the
  list, only a real tap selects.
- [ ] **Four sources** (186/184/228): the Layout button opens a centered ring
  with Tap / List / New / Recent. New opens something not yet running
  (Explorer Quick Access, VS Code recents). Recent re-creates a layout you
  made before in one tap and NAMES any window that is not open.
- [ ] **Bar geometry** (223/237): TOP — the name takes the row, slim arrows
  tight against the frame; BOTTOM on the TABLET (portrait) — the bar sits in
  the bottom row BETWEEN the button columns, same size as at top; BOTTOM on
  the PHONE — the bar takes its own row (too narrow between the columns);
  LANDSCAPE — Bottom is honored and the bar is centered, never full-width.
  Swipe on the bar steps layouts.
- [ ] **Grid self-heals** (231): move a member window with the mouse at the
  desk, enter the grid — if a placement is refused you get a toast and the
  grid snaps right within ~1.5 s, without leaving and re-entering.
- [ ] **⚙ sheet** (195/197/233): Add a window / Split into windows / Take one
  window out — each with its OWN icon; grow works to four, split leaves one
  solo layout per member.
- [ ] **List reorder** (196 — still unconfirmed on your device): drag a row
  BETWEEN two others; report whether the drop takes.

## B. The window that opens while you work

- [ ] **New process** (239): from a focused layout, open something that
  launches a NEW app — the "layout with it?" / "Show in layout" chip appears
  within ~1–4 s WITHOUT leaving the layout.
- [ ] **Already-running browser** (240): click a link that opens a NEW WINDOW
  of an already-open Chrome — the chip appears too (within ~5 s of your
  click). A new TAB in an existing window stays invisible — that is a known,
  recorded limit, not a bug.
- [ ] **Notification tap** (236): while a DIFFERENT layout is focused, tap an
  agent-finished notification — it takes you to THAT agent's layout. If it
  ever does not, the server log now names the exact reason.

## C. Controls, wheel, Hide

- [ ] **Wheel modes** (181 — you already confirmed): drop-out default, cap 10,
  picker says N of 10; Fixed in the desktop Controls editor.
- [ ] **Landscape wheel** (238): sideways, the wheel shows EVERY riding set.
- [ ] **Hide hold** (229): hold Hide ~0.4 s with a normal finger — the two
  modes (Comes back / Stays hidden) appear; a swipe across the button does
  nothing.
- [ ] **Set editor on the phone** (218b — you already found it): Settings →
  Sets → pencil.

## D. Notifications and channels

- [ ] **Channels** (226a): Settings → This phone — three switches (banner /
  speak / tone) per device; muting all three still leaves the banner.
- [ ] **The voice** (224): a notice speaks only "project — title", the banner
  keeps the full text.
- [ ] **Both devices** (209): tablet and phone each get every notice once,
  with the app closed.

## E. Desktop

- [ ] **Advanced card** (226b): Settings — port, H.264 on/off, JPEG quality,
  QR image toggle, at the bottom.
- [ ] **2560 offer** (226c): with your saved 3840/60, the next start shows a
  ONE-TIME banner offering 2560; either answer sticks and it never returns.
- [ ] **Apply & restart** (234): no ~10 s hang on restart.
- [ ] **Controls editor** (232): fits a 1280-wide screen — three columns,
  nothing cut, the full command pool visible.

## F. Performance (from v0.0.108, still on your list)

- [ ] **60 fps without freezing** (130/131/151): lower Resolution once or take
  the phone's ↑ Native — the picture must move at 60 fps.
- [ ] **Excursion return** (203): gallery and back — seconds, not a minute.
- [ ] **Bitrate Apply** (193): change bitrate + Apply — nothing dies.
- [ ] **Orientation lock** (204): portrait layout, turn the tablet, leave and
  return — never rotates.
- [ ] **Clipboard both ways** (182), **quality raise panel** (131), **quality
  edits through the phone** (218b) — as listed in the v0.0.108 report.

## G. Open questions that are YOURS

- **Rotation** (176): my critique stands — the lock is a consequence of the
  region's shape on the PC; a tablet rotating a portrait layout would only
  letterbox it. One word from you overrules it.
- **New-tab chip** (240 limit): covering a new TAB of an existing browser
  window is not possible by window identity; if you want it, that is a
  different investigation (browser-side signals), say so.

---
Everything above shipped through the full gate chain (fail-closed build
gates, phone + Qt audits in both palettes, independent visual grading) —
but per FIXED = VERIFIED, only your eyes close these boxes.
