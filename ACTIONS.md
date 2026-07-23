# actions.json — Control Categories

The two D-pad groups on the tablet are defined entirely by [actions.json](actions.json) in the project root. Edit it on the PC, refresh the tablet page, and the buttons change — no server restart (it is re-read on every connection).

## Layout on the tablet

- **Two groups**, one bottom-left and one bottom-right. Each shows one **category** of up to 4 buttons.
- **Landscape:** each group is a D-pad cross (up / left / right / down) around a small centre button.
- **Portrait:** the four buttons stack in a column.
- The small **centre button** (dashed) opens the **category wheel**: tap it, tap the category you want, or tap the centre **✕** to cancel. Each group switches independently.
- Top-left **Move** (pan the view, no click) and top-right **Hide** (hide all controls) are fixed, not part of the categories.

## Format

```json
{
  "left": 0,
  "right": 2,
  "categories": [
    {
      "name": "Mouse",
      "icon": "mouse",
      "buttons": [
        { "action": "click" },
        { "action": "right" },
        { "action": "drag" },
        { "action": "scroll" }
      ]
    },
    {
      "name": "Edit",
      "icon": "edit",
      "buttons": [
        { "label": "Copy", "chord": "ctrl+c" }
      ]
    }
  ]
}
```

- **left / right** — index of the category each group shows on connect.
- **name** — the category label (centre button + wheel).
- **icon** — one of: `mouse`, `edit`, `keyboard`, `monitor`, `grid`, `snap`, `click`, `right`, `drag`, `scroll`, `settings`, `target`.
- **buttons** — up to 4, placed in order **up · left · right · down**.

## Button kinds

A button is one of:

- **Built-in action** — `{ "action": "<name>" }`, where `<name>` is:
  - `click` — **the left click**: presses at the current cursor position (the finger only steers the cursor); press it twice fast for a double click.
  - `right`, `drag`, `scroll` — **mouse modes** (toggle on/off, only one active at a time, together with `Move`): the mode decides what one finger on the screen does — tap → right-click / drag with left held / wheel. Default (no mode) = the finger only moves the PC cursor, it never clicks. Two fingers always pinch-zoom.
  - `keyboard` — toggle the phone keyboard; what you type/dictate lands in the focused box on the PC screen itself (no mirror bar). The keyboard's ↵ makes a new row (never "send"); the real Enter is its own button (see `key`).
  - `upload` — pick an image from the phone (gallery/camera); the server pastes it into the focused box on the PC by itself.
  - `monitor` — switch the streamed monitor.
  - `snap` — screenshot the PC monitor into the PC clipboard (available in config; not in the default layout).
  - `calibrate` — re-measure your fingertip so the on-screen pointer sits at a comfortable, always-visible offset from it. Tap it, then tap the screen a few times; a toast confirms when it locks. Shipped as the first item of the **Settings** category.
- **Chord** — `{ "label": "Copy", "chord": "ctrl+c" }` — fires a key combination (see below).
- **Special key** — `{ "label": "Esc", "key": "escape" }` — a single structural key.

## Chord syntax

`modifier+…+key` — modifiers held while the last key is tapped.

- **Modifiers:** `ctrl`, `alt`, `shift`, `win`
- **Keys:** letters, digits, `f1`–`f24`, or named: `enter`, `esc`, `tab`, `space`, `backspace`, `delete`, `insert`, `home`, `end`, `pageup`, `pagedown`, `left`, `up`, `right`, `down`

Examples: `ctrl+c` · `alt+tab` · `ctrl+win+alt+1` · `shift+enter` · `win`

An unrecognised chord is logged on the server and does nothing — never a half-pressed key.

## Your custom categories

The shipped `Zones` category maps `ctrl+win+alt+1..4` (FancyZones presets). The shipped `Settings` category holds `calibrate` (finger calibration) — the home for future on-device options. Add or rearrange categories freely — this file is yours to hand-edit; to move a button between categories, just move its JSON entry.
