# Layout creation — Flow

**About:** [description](../__about/layout-create.md) ·
**Living with layouts:** [Layouts flow](layouts.md)

## Algorithm — the two sources, and the one slot shape they both produce

```mermaid
flowchart TB
    PLUS[Layout + tapped] --> CHOOSE{Where do the windows come from?}
    CHOOSE -- From a list --> LIST[send layout_list<br/>overlay: 'Collecting windows and tabs…']
    LIST --> ENTRIES[layout_offer.entries<br/>windows already IN a layout are absent;<br/>tabs only from tab-capable apps]
    CHOOSE -- Tap a window --> ARM[layoutArm = true<br/>the NEXT canvas tap sends layout_pick]
    ARM --> OFFER[layout_offer.target + tab]
    ENTRIES --> SLOT[slotFromEntry]
    OFFER --> SLOT2[slotFromOffer]
    SLOT --> PANEL[slot panel: mode solo/grid,<br/>orientation, chosen slots, name]
    SLOT2 --> PANEL
    PANEL --> MORE{cellsNeeded reached?}
    MORE -- no, grid still hungry --> ARM
    MORE -- yes --> CREATE[Create → layout_create slots<br/>overlay: 'Arranging the windows…']
```

## The session, and every way it ends

```
creating = null                      nothing is being made
   │  + tapped
   ▼
creating = {source, slots: [], …}    the wizard is live, + is lit
   │
   ├── Create ─────────────► layout_create  →  creating = null
   ├── Cancel chip ────────► cancelCreation()      "Layout creation cancelled"
   ├── + tapped again ─────► cancelCreation()
   └── backdrop tap ───────► cancelCreation()   (layouts.js hands it over —
                                                 the list and aspect panels
                                                 just close, nothing was sent)
```

`cancelCreation` always clears `layoutArm` too. An armed tap that outlived its
session would turn the owner's next ordinary cursor move into a window pick.
