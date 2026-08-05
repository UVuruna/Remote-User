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
- **Attach** — Gallery / Shot (PC screenshot of the viewed region) / Camera / Files — every source ends as a paste on the PC.
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
- The **app set** rides along while a matching layout is focused, and does
  not charge against the picker's count.
- Hard cap **8** in the wheel: over the cap, non-required sets are bumped
  from the END (they return when the app set goes away).

Any set (shipped or custom) may carry `"order_land"` / `"order_port"` — the
button arrangement per orientation (indices into `buttons`; landscape slots
are top·left·right·bottom, portrait is the column top→bottom). The shipped
order is the default; the desktop editor's "Reset arrangement" restores it.

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
      "icon": "newwin",
      "buttons": [ { "label": "Sidebar", "chord": "ctrl+b" } ]
    }
  ]
}
```

- **left / right** — index of the category each group shows on connect.
- **name** — the category label (centre button + wheel).
- **icon** — one of: `mouse`, `edit`, `keyboard`, `monitor`, `monitor2`, `grid`, `snap`, `click`, `middle`, `right`, `drag`, `scroll`, `settings`, `target`, `globe`, `mic`, `enter`, `esc`, `attach`, `gallery`, `shot`, `folder`, `selall`, `copy`, `cut`, `paste`, `undo`, `redo`, `find`, `del`, `newwin`, `image`, `input`, `gauge`.
- **buttons** — up to 4, placed in order **up · left · right · down**.

## App-aware sets (`app_sets`)

Sets that exist **only in layout focus** (owner decision 2026-08-04): when the
focused layout's app matches `process` (case-insensitive substring of the
process name, e.g. `"code"` → `Code.exe`), the set appears as an **extra
category in the wheel** — nothing switches by itself, and it vanishes when the
layout focus ends. Shipped: **VSCode** (Sidebar, Palette, Terminal, Find),
**Chrome** (New tab, Close, Next tab, Address), **Explorer** (Rename, New dir,
Delete, Up). Buttons use the same chord/key/icon format as categories.

## Button kinds

A button is one of:

- **Built-in action** — `{ "action": "<name>" }`, where `<name>` is:
  - `click`, `right`, `middle` — **CLICK/HOLD mouse buttons** (owner 2026-08-04, like a real mouse): a tap is a click at the current cursor position (the finger only steers the cursor); **keeping the finger on the button holds the PC button down** — steer with the other hand to drag/select, lift to release. Press twice fast for a double click.
  - `scroll`, `drag` — **mouse modes** (toggle on/off, one active at a time): the mode decides what one finger on the screen does. Default (no mode) = the finger only moves the PC cursor. Two fingers always pinch-zoom. (`drag` is redundant with holding `click` and is not shipped.)
  - `keyboard` — toggle the phone keyboard; typing/dictation lands in the focused box on the PC. **A tap on the stream switches it OFF by itself** (owner 2026-08-04). The keyboard's ↵ makes a new row (never "send"); the real Enter is its own button.
  - `enter`, `esc` — press the real Enter/Escape **and switch keyboard + mic OFF first** (owner 2026-08-04). `esc` left the default layout (New row took its slot) but stays available here.
  - `newrow` — Shift+Enter (a new line that never "sends"). Deliberately does NOT switch the mic/keyboard off — break the line mid-dictation and keep talking.
  - `mic` — **direct voice input** (no keyboard detour): the app listens via Android speech recognition and types what you say into the focused PC box. A toggle like the keyboard; only one of mic/keyboard is ever ON; a tap on the stream switches it off. First use asks the microphone permission once.
  - `gallery` — pick image(s) from the phone gallery (more than one allowed). One image pastes as a picture; several paste as **files**.
  - `camera` — open the camera, take a shot, paste it on the PC.
  - `files` — pick any file(s) (PDF…); pasted on the PC as **real files** (like Copy in Explorer).
  - `pcshot` — **Shot**: screenshot of exactly the REGION the phone is viewing (zoomed part / focused layout — never the whole desktop), pasted into the focused PC box.
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

## Chord syntax

`modifier+…+key` — modifiers held while the last key is tapped.

- **Modifiers:** `ctrl`, `alt`, `shift`, `win`
- **Keys:** letters, digits, `f1`–`f24`, `` ` `` (backquote), or named: `enter`, `esc`, `tab`, `space`, `backspace`, `delete`, `insert`, `home`, `end`, `pageup`, `pagedown`, `left`, `up`, `right`, `down`, and the media keys `playpause`, `mute`, `volup`, `voldown`

Examples: `ctrl+c` · `alt+tab` · `ctrl+win+alt+1` · `shift+enter` · `win` · ``ctrl+` ``

An unrecognised chord is logged on the server and does nothing — never a half-pressed key.

## Your custom categories

Add or rearrange categories freely — this file is yours to hand-edit; to move a button between categories, just move its JSON entry. Old favourites that left the defaults (`Alt+Tab`, `Win`, zone chords) are one JSON entry away.
