# Layout API — Flow

**About:** [description](../__about/layout_api.md)

## Algorithm — creating a layout

```mermaid
flowchart TB
    A["layout_create {slots, mode, grid, orient, name?}"] --> B{"any slots?"}
    B -- no --> C["toast 'Nothing selected' + layout_state"]
    B -- yes --> D["for each slot: resolve_slot"]
    D --> E{"slot names a TAB?"}
    E -- no --> F["use the whole window's hwnd"]
    E -- yes --> G["uia.extract_tab — app command → Explorer path → SendInput drag"]
    G -- ok --> H["the NEW window's hwnd"]
    G -- fail --> I["toast 'could not separate' → fall back to the whole window"]
    F --> J["layout_progress {done, total} — one cube turn"]
    H --> J
    I --> J
    J --> K{"anything resolved?"}
    K -- no --> L["toast 'those windows are gone' + layout_state"]
    K -- yes --> M["registry.create — place every member, VERIFIED"]
    M --> N{"all members landed on their rects?"}
    N -- no --> O["toast 'a window would not take its exact spot'"]
    N -- yes --> P["layout_focus(index)"]
    O --> P
```

Every raise inside extraction is a **stage direction**, not membership: the
source window keeps its other tabs and the new window is not registered yet,
so both use `raise_window(..., topmost=False)`. A topmost raise there stranded
them — they belonged to no layout, so nothing could ever lower them again.

## Algorithm — focusing, and what leaves the topmost band

```mermaid
flowchart TB
    A["layout_focus {index}"] --> B{"index < 0?"}
    B -- yes --> C["registry.minimize_members() — the desktop shows only non-layout windows"]
    B -- no --> D["registry.focus(index, ratio, mon_rect)"]
    D --> E["prune() — CLOSED windows only, never merely cloaked"]
    E --> F["drop the topmost band from every layout that is not the target — BEFORE any early return"]
    F --> G{"target still there?"}
    G -- no --> H["toast 'that layout's window is gone'; conn.active = None"]
    G -- yes --> I{"device aspect / ratio / pos changed?"}
    I -- yes --> J["re-place every member (place_window, verified)"]
    I -- no --> K["leave them where they stand"]
    J --> L["raise_window(member) — TOPMOST, ledger entry"]
    K --> L
    L --> M["last_focus = (index, name) — where the next session resumes"]
    M --> N["region = the members' combined rect, monitor-normalized"]
    C --> O["send_layout_state"]
    H --> O
    N --> O
```

The drop pass runs **before** the early returns. It used to sit after them, so
focusing a layout whose window had been closed at the desk returned `None`
with the previous layout still nailed above everything — and the phone then
showed the desktop over it.
