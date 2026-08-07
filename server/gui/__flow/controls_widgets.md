# Controls Editor — Command Widgets — Flow

**About:** [description](../__about/controls_widgets.md)

## Who owns what after the round R5 split (2026-08-07)

```
controls_editor.py  (dialog)          controls_widgets.py  (COMMAND widgets)
├─ (imports from the other three)     ├─ icon_for()      svg fragment → QIcon
└─ ControlsEditor                     ├─ ChordRecorder   records a chord
     assembles ▼                      ├─ CommandDetail   one field per row
                                      └─ CommandTable    the pool + ticks

controls_data.py    (data)            controls_order.py    (ORDER widgets)
├─ button_id()     command identity   ├─ SlotDelegate/SlotList/OrderList
├─ DPAD_SLOTS / WHEEL_MAX              ├─ WheelRing / WheelOrderDialog
└─ merge_shipped_pools() etc.          (see [Controls Order — Flow](controls_order.md)
        ▲ imported by all three ◀──────────────── for the OrderList diagram)
```

`SlotList`/`SlotDelegate`/`OrderList` and their flow diagram moved to
[Controls Order — Flow](controls_order.md) in build round R5 (2026-08-07);
`button_id()` moved to [Controls Data](controls_data.md) the same round.

## CommandDetail — what is editable, and what is only shown

```
show_button(btn, editable)
 ├─ btn.action        → kind = that action, name+icon from the client's BUILTINS
 ├─ btn.key           → kind = Special key,  shortcut = key
 ├─ btn.text present  → kind = Types (paste text), text = btn.text, enter = btn.enter
 ├─ btn.chord (else)  → kind = Shortcut,     shortcut = chord
 └─ _kind_changed()
      ├─ shows _shortcut_row  (Shortcut field + Record)   when kind is chord/key
      ├─ shows _text_row      (Text field + Press Enter)  when kind is Types
      │    — exactly ONE of the two rows is ever visible (build round R6,
      │      2026-08-07 — this exclusivity IS the fix: before it, a typed
      │      command showed an empty Shortcut row under a table that already
      │      said "types · /usage")
      ├─ built-in row  → every field disabled, real values shown (greyed)
      └─ custom set    → all fields live; Record… → ChordRecorder

dump()  → {"action": …}
        | {"label": …, "text": …, "enter": bool, "icon"?: …}   (Types)
        | {"label": …, "chord"|"key": …, "icon"?: …}
        | None   (None = an unusable row — an empty shortcut/text is never written)
```

## Build round R3 (2026-08-07) — themes

```
icon_for(body)
   stroke = icon_stroke()          <- TOKENS["text2"], read NOW (was "#cbd5e1")
   <svg stroke="{stroke}"> + body.replace("currentColor", stroke) </svg>
   -> QSvgRenderer -> 48x48 QPixmap -> QIcon
```
