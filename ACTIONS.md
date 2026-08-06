# actions.json — Control Categories

The two D-pad groups on the tablet are defined entirely by [actions.json](actions.json) in the project root. Edit it on the PC, refresh the tablet page, and the buttons change — no server restart (it is re-read on every connection).

## Layout on the tablet

- **Two groups**, one bottom-left and one bottom-right. Each shows one **category** of up to 4 buttons.
- **Landscape:** each group is a D-pad cross (up / left / right / down) around a small centre button.
- **Portrait:** the four buttons stack in a column.
- The small **centre button** (dashed) opens the **category wheel**: tap it, tap the category you want, or tap the centre **✕** to cancel. Each group switches independently.
- Top-left **Layout (+)** (pick a window for a new layout) and top-right **Hide** (hide all controls) are fixed, not part of the categories.

## Shipped categories (owner set 2026-08-04)

- **Mouse** — Click / Right / Middle (CLICK/HOLD buttons, see below) + Scroll (mode toggle).
- **Input** — Keys (keyboard toggle) / Enter / New row / Mic (direct voice input). New row replaced Esc in the defaults (owner 2026-08-04 — dictation has no keyboard, so line breaks need a button; Esc stays available as `{ "action": "esc" }` for hand-edited files).
- **Attach** — Gallery / Shot (PC screenshot of the viewed region) / Camera / Files — every source ends as a paste on the PC. **Region** waits in the pool (owner 2026-08-05): a frame you size and move, captured and pasted like the rest.
- **Edit** — All / Copy / Cut / Paste (chords with icons).
- **Navigate** — Esc / Prev (Shift+Tab) / Next (Tab) / Find (Ctrl+F) — moving between and closing UI elements (owner 2026-08-05: Esc proved essential in live use).
- **Cursor** — Undo / ← / → / Redo — text-caret steps and edit history.
- **Media** *(off by default)* — Play·Pause / Vol− / Vol+ / Mute (real media keys).
- **Windows** *(off by default)* — Alt+Tab / Win / Desktop (Win+D) / Tasks (Win+Tab).
- **Settings** — Monitor switch / Sets (the wheel picker) / quality / dictation (the Language card — owner 2026-08-05, replacing `anywhere` in the defaults; `next_input` and `anywhere` left the defaults 2026-08-05, both still available as actions).

## The wheel (owner spec 2026-08-05, revised the same day)

- **Mouse, Input and Settings are `"required"`** — always in the wheel, never
  hideable (mouse + typing + the recovery/picker path must survive anything).
- Every other shipped set (Edit, Attach, Navigate, Cursor, Media, Windows)
  and every custom set is **toggleable**: `"enabled"` in the file is the
  desktop default (`false` = off), the phone's **Settings → Sets** picker
  overrides it per device.
- **Custom sets** are created in the desktop app (**Controls…** button; end
  users never hand-edit files), stored under `"custom_sets"` — same shape as
  a category plus `"enabled"`.
- The **app sets** ride along while a matching layout is focused — and they
  DO charge against the count (owner 2026-08-06): what they hold is the
  largest group that can appear together, so VSCode + Claude reserve two
  slots and leave six for the rest. See App-aware sets below.
- Hard cap **8** in the wheel: over the cap, non-required sets are bumped
  from the END (they return when the app set goes away).

Any set (shipped or custom) may carry `"order_land"` / `"order_port"` — the
button arrangement per orientation (indices into the ACTIVE four; landscape
slots are top·left·right·bottom, portrait is the column top→bottom). The
shipped order is the default; the desktop editor's **Default** button
restores it. That editor calls the two lists **D-pad (landscape)** and
**Stack (portrait)** (owner's names, 2026-08-06).

## Pools and reserves (owner 2026-08-05)

A set's `"buttons"` list is its **POOL** — it may hold **more than four**
commands. The four that actually sit on the D-pad are named by
`"active"`, a list of command IDs:

```json
{
  "name": "Navigate",
  "icon": "nav",
  "buttons": [ … 11 commands … ],
  "active": ["esc", "shift+tab", "tab", "ctrl+f"]
}
```

- **ID** of a command = its `"id"` if it has one, else its `action`, `chord`,
  `key` or `label` — unique inside one set. IDs and not indices, so a later
  version inserting a command into the pool can never silently re-point your
  choice.
- **No `"active"` key = the first four** — every file written before pools
  keeps working unchanged.
- You pick the four in the desktop app (**Controls…**): tick a command, untick
  another. A fifth tick is refused with the reason on screen — a D-pad has
  four positions.
- **Any button may be RENAMED, in every set** (owner 2026-08-05): what a
  button DOES stays ours, what it is CALLED is yours. `Btn 4` / `Btn 5` carry
  whatever your mouse driver put on the side buttons, so the face has to be
  able to say `Back` or `Undo`. Clear the name field to fall back to ours; a
  new version's pool refresh keeps your names (matched by command, not by
  position).
- The pools of built-in and app sets are **ours** — you choose from them, and
  a new version's reserves are merged into your own copy of the file on the
  next opening of the editor (the reason `Anywhere` used to linger in Settings
  after an update). Your **custom sets** are fully editable, pool and all.

Shipped reserves, off until you tick them:

| Set | On the D-pad | Reserves in the pool |
|-----|--------------|----------------------|
| Mouse | Click · Right · Middle · Scroll | Drag · **Btn 4** · **Btn 5** (the side buttons) |
| Input | Keys · Enter · New row · Mic | Esc · Next box · Language |
| Attach | Gallery · Shot · Camera · Files | **Region** · Snap (Image was dropped 2026-08-05 — it was a single-picture Gallery) |
| Edit | All · Copy · Cut · Paste | Undo · Redo · Save · Paste plain · Delete |
| Navigate | Esc · Prev · Next · Find | Back · Forward · Find next · Top · Bottom · Page up · Page down |
| Cursor | Undo · ← · → · Redo | Up · Down · Word ← · Word → · Home · End |
| Media | Play · Vol− · Vol+ · Mute | Next · Prev · Stop |
| Windows | Alt+Tab · Win · Desktop · Tasks | Close · Max · Min · Snap ← · Snap → · Explorer · Run |
| Settings | Monitor · Sets · Quality · Language | Anywhere (owner 2026-08-05: Next box and Snap left this pool — Next box lives in Input, Snap in Attach) |
| **VSCode** | Sidebar · Palette · Terminal · Find | **Preview (ctrl+shift+v)** · **Next tab** · **Prev tab** · Save · Go to file · Comment |
| **Chrome** | New tab · Close · Next tab · Address | **Prev tab** · Reopen · Reload · Back · Forward · Find |
| **Explorer** | Rename · New dir · Delete · Up | **Next tab** · **Prev tab** · New tab · Back · Forward · Copy path · Details · Search |
| **Claude** | Usage · Model · **Thinking** · Stop | Menu · Mode · Compact · New chat · Rewind · Context · Agents · Resume · Focus |

**Thinking asks, it does not run** (owner correction 2026-08-05, with the
screenshot — then his better idea the same evening): `/effort` takes a level
(`low|medium|high|xhigh|max|auto`), so sending it alone only prints its usage.
The first fix typed `/effort` and stopped, leaving Claude's own menu on screen
for the finger. The shipped answer is his: the button carries `options`, the
PHONE shows the levels in the middle of the screen, and one tap sends the
finished `/effort xhigh` + Enter. Anything whose answer is a small fixed set
belongs in that shape — `options`, not a half-typed line.

`Zones` is no longer shipped — zone chords are a **custom** category the owner
adds when wanted (this file is hand-editable; a future desktop editor will
manage names/icons/shortcuts per zone).

## Format

```json
{
  "left": 0,
  "right": 1,
  "categories": [
    {
      "name": "Mouse",
      "icon": "mouse",
      "buttons": [
        { "action": "click" },
        { "action": "right" },
        { "action": "middle" },
        { "action": "scroll" }
      ]
    },
    {
      "name": "Edit",
      "icon": "edit",
      "buttons": [
        { "label": "Copy", "icon": "copy", "chord": "ctrl+c" }
      ]
    }
  ],
  "app_sets": [
    {
      "process": "code",
      "name": "VSCode",
      "icon": "vscode",
      "buttons": [ { "label": "Sidebar", "chord": "ctrl+b" } ]
    }
  ]
}
```

- **left / right** — index of the category each group shows on connect.
- **name** — the category label (centre button + wheel).
- **icon** — any name from the client's icon set, which lives in one place: [client/icons.js](client/icons.js) (100 of them: the owner's 2026-08-05 round of 97, plus `vscode` / `chrome` / `explorer` on 2026-08-06, so an app-aware set wears its own app's face instead of a generic window). The desktop **Controls…** editor reads that same file, so its icon combo always offers exactly what the phone can draw. Families and house style: [client/__about/icons.md](client/__about/icons.md).
- **buttons** — the set's POOL (see Pools above); the four on the D-pad are placed in order **up · left · right · down**.
- **title** *(app sets only, owner 2026-08-05)* — an extra match against the layout window's OWN title, so a set can single out an app that shares another's process: `Claude` is `{"process": "code", "title": ["claude code", "claude"]}` and rides beside `VSCode`, which matches the process alone. The title is the window's, never the layout's (owner-chosen) name, so renaming a layout never changes which set appears. A **list** names several spellings of the same thing. The match is a **whole word**, and a title that looks like a FILE never matches at all (owner 2026-08-06): the Claude set belongs to the Claude conversation, not to an open `CLAUDE.md`, a transcript, or any other document that happens to carry the word.

## App-aware sets (`app_sets`)

Sets that exist **only in layout focus** (owner decision 2026-08-04): when the
focused layout's app matches `process` (case-insensitive substring of the
process name, e.g. `"code"` → `Code.exe`), the set appears as an **extra
category in the wheel** — nothing switches by itself, and it vanishes when the
layout focus ends. Shipped: **VSCode** (Sidebar, Palette, Terminal, Find),
**Chrome** (New tab, Close, Next tab, Address), **Explorer** (Rename, New dir,
Delete, Up) and **Claude** (Usage, Model, Thinking, Stop) — each with a pool of
reserves behind them (see Pools above). Buttons use the same chord/key/icon
format as categories, plus the **typed text** kind the Claude set needs, and
app sets are editable in the desktop Controls editor like any other set.

**Two sets may match the same window** (owner 2026-08-05). Claude Code runs
INSIDE VSCode — same process, `Code.exe` — so `Claude` adds a `"title"` match
on top of the process and both sets ride together while that layout is
focused — this is the ONE case where two app sets are on the wheel at once,
and both are wanted: Claude's commands are there while the editor's own
shortcuts stay reachable.
The title is read when the layout is CREATED (it is the window's own title,
not the layout's name), which is also why nothing switches by itself later —
the same rule the app sets have followed since 2026-08-04. Each app set is
ticked separately in the phone's **Settings → Sets**, so hiding Claude while
keeping VSCode is one tap.

**And an app set costs a wheel slot** (owner 2026-08-06). They used to be
free, which let the Sets picker promise eight while the wheel silently
dropped two. What is charged is not "how many are ticked" but the largest
group that can appear TOGETHER — grouped by `process`, because Chrome,
Explorer and VSCode can never be on screen at the same moment. So:

| Ticked app sets | Slots held | Left for everything else |
|---|---|---|
| Chrome + Explorer + VSCode | 1 | 7 |
| VSCode + Claude | 2 | **6** |
| none (or the master switch off) | 0 | 8 |

The picker states it — `N of 8 used — M held for app shortcuts` — and refuses
the tick that would overflow instead of letting the wheel drop a set you
already chose.

## Button kinds

A button is one of:

- **Built-in action** — `{ "action": "<name>" }`, where `<name>` is:
  - `click`, `right`, `middle` — **CLICK/HOLD mouse buttons** (owner 2026-08-04, like a real mouse): a tap is a click at the current cursor position (the finger only steers the cursor); **keeping the finger on the button holds the PC button down** — steer with the other hand to drag/select, lift to release. Press twice fast for a double click.
  - `x1`, `x2` — the **side buttons** of a 5-button mouse (owner 2026-08-05): Btn 4 (rear) and Btn 5 (front), Windows' XBUTTON1/XBUTTON2 — Back/Forward in most apps. Same CLICK/HOLD behaviour; they sit in the Mouse pool as reserves, so tick one in place of another when you want it.
  - `scroll`, `drag` — **mouse modes** (toggle on/off, one active at a time): the mode decides what one finger on the screen does. Default (no mode) = the finger only moves the PC cursor. Two fingers always pinch-zoom. (`drag` is redundant with holding `click` and is not shipped.)
  - `keyboard` — toggle the phone keyboard; typing/dictation lands in the focused box on the PC. **A tap on the stream switches it OFF by itself** (owner 2026-08-04). The keyboard's ↵ makes a new row (never "send"); the real Enter is its own button.
  - `enter`, `esc` — press the real Enter/Escape **and switch keyboard + mic OFF first** (owner 2026-08-04). `esc` left the default layout (New row took its slot) but stays available here.
  - `newrow` — Shift+Enter (a new line that never "sends"). Deliberately does NOT switch the mic/keyboard off — break the line mid-dictation and keep talking.
  - `mic` — **direct voice input** (no keyboard detour): the app listens via Android speech recognition and types what you say into the focused PC box. A toggle like the keyboard; only one of mic/keyboard is ever ON; a tap on the stream switches it off. First use asks the microphone permission once.
  - `gallery` — pick image(s) from the phone gallery (more than one allowed). One image pastes as a picture; several paste as **files**.
  - `camera` — open the camera, take a shot, paste it on the PC.
  - `files` — pick any file(s) (PDF…); pasted on the PC as **real files** (like Copy in Explorer).
  - `pcshot` — **Shot**: screenshot of exactly the REGION the phone is viewing (zoomed part / focused layout — never the whole desktop), pasted into the focused PC box.
  - `region` — **Region** (owner 2026-08-05): a frame you size and move anywhere on the screen; Send captures what is inside it and pastes it on the PC. Snipping Tool's rectangle, from the phone. Unlike a layout's region it is bound to no edge and keeps no ratio.
  - `upload` — legacy single-image pick (kept for hand-edited files; `gallery` replaces it).
  - `monitor` — switch the streamed monitor (shipped in **Settings**).
  - `snap` — full-monitor screenshot into the PC clipboard only (no paste; not in the default layout).
  - `next_input` — jump keyboard focus to the NEXT text-input box (dictation workflow). Full desktop = every visible window; layout focus = only that layout's. Out of the defaults since 2026-08-05 (Sets took the slot).
  - `sets` — open the phone's wheel picker: which custom sets are shown on THIS device (max 3) and whether app sets appear. Shipped in **Settings**.
  - `quality` — open the stream-quality panel (fps / resolution / bitrate + auto-save on mobile data — owner 2026-08-05, replacing the old cycle). Shipped in **Settings**.
  - `dictation` — open the dictation-language card (choose the language you speak; model download guided). Shipped in **Settings** (owner 2026-08-05).
  - `anywhere` — open the "use from anywhere" wizard (Tailscale setup). NOT in the defaults since 2026-08-05 (the first-contact banner still guides new phones); stays in the pool for custom sets.
  - `calibrate` — retired (the pointer sits exactly under the finger since 2026-08-02).
- **Chord** — `{ "label": "Copy", "chord": "ctrl+c" }` — fires a key combination (see below). An optional `"icon"` from the list above gives it an icon face.
- **Special key** — `{ "label": "Esc", "key": "escape" }` — a single structural key; `"icon"` works here too.
- **Typed text** — `{ "label": "Usage", "text": "/usage", "enter": true }` (owner 2026-08-05) — the PC pastes the text into whatever box has focus and presses Enter. Built for the **Claude** set, whose commands are not shortcuts at all but slash commands written into the app's own prompt. The paste goes through the clipboard (one atomic insert; a character-by-character type races the autocomplete menu that re-filters on every keystroke). `"enter": false` leaves the line standing — that is the `Menu` button, which types `/` and lets you pick from the list with the cursor.

## Chord syntax

`modifier+…+key` — modifiers held while the last key is tapped.

- **A choice** — `{ "label": "Thinking", "text": "/effort", "options": ["low", "medium", "high", "xhigh", "max", "auto"] }` (owner idea 2026-08-05). Some commands are not an action but a QUESTION: `/effort` takes a level, so sending it alone only prints its usage. A button with `options` shows the choices ON THE PHONE, in the middle of the screen, and one tap sends the finished command (`/effort xhigh` + Enter). It beats leaving another app's menu open for the finger to poke at, because it does not depend on that menu staying where it is. Options may be plain strings or `{ "label": …, "value": … }` when the two differ.
- **Modifiers:** `ctrl`, `alt`, `shift`, `win`
- **Keys:** letters, digits, `f1`–`f24`, `` ` `` (backquote), `/` (`slash`), or named: `enter`, `esc`, `tab`, `space`, `backspace`, `delete`, `insert`, `home`, `end`, `pageup`, `pagedown`, `left`, `up`, `right`, `down`, `minus`, `plus`, and the media keys `playpause`, `mute`, `volup`, `voldown`, `medianext`, `mediaprev`, `mediastop`

Examples: `ctrl+c` · `alt+tab` · `ctrl+win+alt+1` · `shift+enter` · `win` · ``ctrl+` ``

An unrecognised chord is logged on the server and does nothing — never a half-pressed key.

## Your custom categories

Add or rearrange categories freely — this file is yours to hand-edit; to move a button between categories, just move its JSON entry. Old favourites that left the defaults (`Alt+Tab`, `Win`, zone chords) are one JSON entry away.
