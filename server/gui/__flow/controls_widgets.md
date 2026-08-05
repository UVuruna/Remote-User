# Controls Editor — Widgets — Flow

**About:** [description](../__about/controls_widgets.md)

## Who owns what after the split (THE STRUCTURE LAW, 2026-08-05)

```
controls_editor.py  (dialog)          controls_widgets.py  (pieces)
├─ user/shipped actions.json paths    ├─ icon_for()      svg fragment → QIcon
├─ load_client_icons/builtins()       ├─ button_id()     command identity
├─ active_buttons()                   ├─ DPAD_SLOTS / LAND_SLOTS / PORT_SLOTS
├─ merge_shipped_pools()              ├─ ChordRecorder   records a chord
└─ ControlsEditor                     ├─ SlotDelegate    rich-text rows
     assembles ▼                      ├─ SlotList        height = its rows
                                      ├─ OrderList       slot ladder + Up/Down
                                      ├─ CommandDetail   one field per row
                                      └─ CommandTable    the pool + ticks
        imports ───────────────────────────▶ (one direction only)
```

## OrderList — a move changes the COMMAND order, never the ladder

```
item i    data(INDEX_ROLE) = index into the ACTIVE four   (what order() returns)
          data(LABEL_ROLE) = the name the phone prints    (never re-read from text)

set_order(labels, order)
 ├─ order valid (a permutation) ? use it : identity
 ├─ one item per slot, both roles set
 └─ _relabel()

↑ / ↓  _move(±1)
 ├─ takeItem(i) → insertItem(j)        the COMMAND travels
 ├─ setCurrentRow(j)                   selection follows the command
 └─ _relabel()                         ◀── the fix: the ladder is redrawn
                                            from the row numbers, so
                                            Top·Left·Right·Bottom (landscape)
                                            and 1ˢᵗ…4ᵗʰ (portrait) stand still

_relabel()
 for slot in rows:  text = SLOTS[slot] + " · " + escape(label)
                            ▲ position          ▲ HTML-escaped: labels come
                              (may hold <sup>)    from the owner's actions.json
```

Before the fix (owner screenshot 2026-08-05): the slot name was baked into
the item's text, so raising `Bottom · Next tab` produced

```
Top     · Sidebar          Top     · Sidebar
Left    · Terminal    →    Left    · Terminal
Right   · Preview          Bottom  · Next tab   ◀ the NAME came along
Bottom  · Next tab         Right   · Preview
```

## SlotDelegate — one row, drawn twice

```
sizeHint(option, index)                 paint(painter, option, index)
 ├─ initStyleOption → opt.text = HTML    ├─ doc = HTML in the row's font
 ├─ doc.idealWidth() + 10                ├─ opt.text = ""  ← Qt draws the
 └─ doc.size().height() + 6              │   background/selection only
        ▲                                ├─ palette.Text = HighlightedText
        └─ the item-view guard reads      │   while the row is selected
           THIS, so a rich-text row is    └─ doc.documentLayout().draw()
           measured by what is drawn          at SE_ItemViewItemText
```

## CommandDetail — what is editable, and what is only shown

```
show_button(btn, editable)
 ├─ btn.action  → kind = that action, name+icon from the client's BUILTINS
 ├─ btn.key     → kind = Special key,  shortcut = key
 ├─ btn.chord   → kind = Shortcut,     shortcut = chord
 └─ _kind_changed()
      ├─ built-in row  → every field disabled, real values shown (greyed)
      └─ custom set    → all fields live; Record… → ChordRecorder

dump()  → {"action": …} | {"label": …, "chord"|"key": …, "icon"?: …} | None
          (None = an unusable row — an empty shortcut is never written)
```
