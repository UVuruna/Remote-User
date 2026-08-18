# Popup Contain - Flow

**About:** [description](../__about/popup_contain.md)

WHOSE window this is has already been decided when anything here runs -
that half is [Layout Popup - Flow](layout_popup.md).

## Algorithm — where it is put

```mermaid
flowchart TB
    A["region = union of the members' REAL frame rects<br/>(measured now, never remembered)"] --> B{"already inside it?"}
    B -- yes --> Y["nothing to do"]
    B -- no --> C{"tries exhausted?"}
    C -- yes --> W["leave it, logged by name"]
    C -- no --> D{"its frame FITS the region?"}
    D -- yes --> E["place centered inside the region, at its own size"]
    E -- landed --> Y
    D -- no --> F["ask it to TAKE the region"]
    F -- landed --> Y
    F -- refused (minimum size) --> G["full screen: the work area of the members' monitor"]
    G -- landed --> Y
    G -- refused --> W
```

Every branch goes through `window_manager.place_window`, which **verifies**
where the window really stands — the refusal is what decides the full-screen
branch, and the ledger entry (constraint 10) is made on the way.

## Algorithm — the way back down

```mermaid
flowchart LR
    A["another layout focused"] --> R["Layout.release_adopted()"]
    B["Desktop chosen (minimize_members)"] --> R
    C["the layout removed / merged away"] --> R
    D["the popup closed at the desk (prune)"] --> R
    E["the phone hung up (clear_topmost → release_all)"] --> L["the LEDGER, which needs no list"]
    R --> N["out of the topmost band, animation back,<br/>NOT moved, NOT minimized, NEVER closed"]
```
