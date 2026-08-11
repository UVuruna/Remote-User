# Layout Popup — Flow

**About:** [description](../__about/layout_popup.md)

## Algorithm — a foreground window that is not a member

```mermaid
flowchart TB
    A["focus_guard._decide — a layout is focused,<br/>fg is NOT one of its members"] --> B{"fg already adopted?"}
    B -- yes --> C["re-measure: still inside the region?"]
    C --> Z["accept — the keyboard may sit on it"]
    B -- no --> D{"owner chain root is a member?<br/>(a dialog of a member)"}
    D -- yes --> P["ATTRIBUTED"]
    D -- no --> E{"was it standing when the phone connected?<br/>(the baseline)"}
    E -- yes --> X["STRANGER — the guard's refusal runs,<br/>focus goes back to the layout"]
    E -- no --> F{"same process as a member?"}
    F -- yes --> P
    F -- no --> G{"its process was started by a member's?<br/>(parent links, up to ANCESTRY_HOPS)"}
    G -- yes --> P
    G -- no --> X
    P --> Q{"already offered, or already declined?"}
    Q -- yes --> X
    Q -- no --> O["ONE CHIP on the phone:<br/>Show in layout / Leave on desktop"]
    O --> X
    T["his tap comes back — POST /window_offer → pick()"] --> U{"act"}
    U -- "layout" --> H["record in Layout.adopted — the ledger owes it a way down"]
    U -- "desktop / no answer / anything else" --> V["remembered as DECLINED — nothing moves, ever"]
    H --> C
```

**Nothing moves before he taps** (his amendment, 2026-08-11): until then the
window is an ordinary desktop window and the fence treats it as one — which is
also why the offer path returns "" and the guard's refusal runs, exactly as it
did before this feature existed. The chip goes out from `focus_guard.watch`
over the page's own socket ([Notify](../__about/notify.md)'s one-device slot); his answer
comes back over HTTP, because the socket's dispatcher belongs to `web.py`.

A window is judged **once**: after the decision it joins the baseline set, so a
stranger that fights for the foreground does not cost a process-table read four
times a second, and a popup we could not place is never re-read as a thief.

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
