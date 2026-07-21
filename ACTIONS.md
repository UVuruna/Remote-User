# actions.json — Custom Shortcut Sets

The radial wheels on the tablet are defined entirely by [actions.json](actions.json) in the project root. Edit this file on the PC, refresh the tablet page, and the new buttons appear — no server restart needed (it is re-read on every connection).

## Format

```json
{
  "sets": [
    {
      "name": "Edit",
      "buttons": [
        { "label": "Copy", "chord": "ctrl+c" }
      ]
    }
  ]
}
```

- **set** → one launcher pill on the tablet (bottom-left). Hold it to open its wheel.
- **name** → the pill's text and the wheel's centre label. Keep it short.
- **buttons** → the wheel's entries; aim for ≤ 8 per set so the sectors stay thumb-sized.
- **label** → the text on the wheel item. Short (1–4 chars reads best).
- **chord** → what gets pressed on the PC.

## Chord syntax

`modifier+modifier+…+key` — every token but the last is a modifier held down while the last key is tapped, then released in reverse.

- **Modifiers:** `ctrl`, `alt`, `shift`, `win`
- **Keys:** any letter (`a`–`z`), digit (`0`–`9`), function key (`f1`–`f24`), or a named key: `enter`, `esc`, `tab`, `space`, `backspace`, `delete`, `insert`, `home`, `end`, `pageup`, `pagedown`, `left`, `up`, `right`, `down`
- A modifier alone is valid (`win` taps the Windows key).

Examples: `ctrl+c` · `ctrl+shift+v` · `alt+tab` · `ctrl+win+alt+1` · `alt+f4` · `win`

An unrecognised chord is logged on the server and simply does nothing — it never sends a half-pressed key.

## Owner's custom sets

The shipped `Zones` set maps `ctrl+win+alt+1..4` — the FancyZones layout presets. Extend or replace it freely; this file is yours to hand-edit.
