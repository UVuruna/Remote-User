# Lost Windows — Flow

**About:** [description](../__about/lost_windows.md)

## Algorithm — is this window reachable, and how does it come back

```mermaid
flowchart TB
    S["focus_guard.watch tick<br/>(desktop OR layout — no gate)"] --> R{"phone away or left?"}
    R -- yes --> Z["nothing: those windows belong to his desk"]
    R -- no --> T{"LOST_EVERY_S since the last sweep?"}
    T -- no --> Z
    T -- yes --> E["wm.list_windows — every top-level app window"]
    E --> M{"a member or adopted window<br/>of any layout?"}
    M -- yes --> Z2["skip: the layout put it there and can move it"]
    M -- no --> I{"minimized?"}
    I -- yes --> P["rect = GetWindowPlacement.rcNormalPosition<br/>(where it would COME BACK to)"]
    I -- no --> F["rect = DWM frame bounds"]
    P --> G
    F --> G{"is at least GRAB_WIDTH_PX x TITLE_HEIGHT_PX<br/>of the TITLE STRIP inside ONE work area?"}
    G -- yes --> Z3["reachable — he can grab it"]
    G -- no --> A{"already asked, or declined<br/>on this connection?"}
    A -- yes --> Z
    A -- no --> C["ONE CHIP on the phone:<br/>'X is off the screen' —<br/>Bring it back / Leave it"]
```

## His tap comes back

```mermaid
flowchart TB
    T["POST /window_offer → layout_popup.pick(id, act)"] --> K{"act"}
    K -- "anything but 'rescue'" --> L["remembered in lost_left —<br/>nothing moves, ever"]
    K -- "rescue" --> M["mon_rect() — asked NOW,<br/>never the value from chip time"]
    M --> N["freeze_transitions<br/>(no slide for the phone to watch)"]
    N --> O{"minimized?"}
    O -- yes --> Q["ShowWindow(SW_RESTORE)"]
    O -- no --> Q2{"hidden?"}
    Q2 -- yes --> Q3["ShowWindow(SW_SHOW)"]
    Q --> P["place_window(_target(rect, work area))<br/>own size where it fits, centered"]
    Q2 -- no --> P
    Q3 --> P
    P --> R["raise_window(topmost=FALSE) — constraint 10:<br/>a rescued window is a normal window"]
    R --> S{"placement took?"}
    S -- yes --> U["logged: rescued from → to"]
    S -- no --> V["ERROR logged, returns False —<br/>the next sweep asks again"]
```

**The order in the second diagram is the fix, not a detail.** Placing before
restoring writes the geometry into a minimized window's stored placement
without bringing it back: it returns success and he sees nothing change. The
gate pins the order (`tests/test_lost_windows.py` → *restore comes before the
placement*), proven by planting the swap.
