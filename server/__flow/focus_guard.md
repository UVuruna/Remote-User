# Focus Guard — Flow

**About:** [description](../__about/focus_guard.md)

## Algorithm — every message that TYPES passes here first

```mermaid
flowchart TB
    A["key_text / key_special / chord / paste_text / screenshot"] --> B["guard(layouts, conn)"]
    B --> C["fg = GetForegroundWindow()<br/>root = owner chain of fg"]
    C --> D{"a layout is focused?"}
    D -- yes --> E{"fg is a member?"}
    E -- yes --> F["accept — layout.last_member = fg"]
    E -- no --> G{"root is a member?<br/>(Save As… of a member)"}
    G -- yes --> H["accept the dialog — the MEMBER stays the target"]
    G -- no --> I["LOG the thief (exe + title)<br/>raise_window(target, topmost=True)"]
    I --> J["target = conn.pin, else layout.last_member, else member[0]"]
    D -- no --> K{"pin stale / missing / dead?"}
    K -- yes --> L["arm: pin = fg — this is the burst's window"]
    K -- no --> M{"fg == pin?"}
    M -- yes --> F
    M -- no --> N{"root == pin?"}
    N -- yes --> H
    N -- no --> O["LOG the thief<br/>raise_window(pin, topmost=False)"]
    F --> P["inject the keys"]
    H --> P
    J --> P
    L --> P
    O --> P
```

`topmost=False` on the desktop path is not a detail: that window belongs to no
layout, and a topmost raise would strand it above the owner's desk for the rest
of the Windows session (owner decree 2026-08-05 — see
[Window Manager](../__about/window_manager.md)).

## Algorithm — what re-arms the target

```mermaid
flowchart LR
    A["pointer_down / click / press"] --> R["retarget(conn) — pin_stale = True"]
    B["next_input (UIA moves focus on purpose)"] --> R
    C["layout_focus / monitor_switch"] --> R
    R --> D["the NEXT typed message re-reads the foreground and arms it"]
    G["a chord, AFTER it fired"] --> R
    E["a focus thief"] -. "sends no message" .-> F["arms nothing — the fence holds"]
```

A chord is guarded on the way IN (Ctrl+V must land in his box) and re-arms on
the way OUT: it may itself move the window — Alt+Tab, Win+arrow, Ctrl+W — and
the next keystroke must not drag focus back to where the chord just left. In a
LAYOUT the fence still wins: the phone shows those windows and no others.

## Algorithm — the keyboard member across an excursion

```mermaid
sequenceDiagram
    participant P as Phone
    participant S as Server
    participant L as Layout (2 members)
    P->>S: key_text (dictation)
    S->>L: guard → member B accepted, last_member = B
    Note over P,S: picker / permission dialog → page hides → socket closes
    P->>S: new connection, layout_focus (client's layoutRestore)
    S->>L: focus() raises A, then B LAST
    Note over L: B holds the keyboard again — dictation continues where it was
```

Before this, `focus()` raised members in list order, so the keyboard went to
whichever window sat last in the grid — one excursion moved the owner's
dictation into the other pane.

## Gate
`tests/test_focus_guard.py` (FOCUS GATE, step 0e of [build.py](../../setup/build.py)) —
11 checks, no Windows and no browser: the fence, the fresh-connection case,
the followed move, the dialog, the desktop pin, what re-arms it, the named
thief, the raise order, the prune, and the whole path through the real
`web._receive_input` dispatcher.
