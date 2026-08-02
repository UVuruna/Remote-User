# UIA Tab Layer — Flow

**About:** [description](../__about/uia.md)

## Algorithm

```mermaid
flowchart TB
    A[extract_tab: pick point + target window] --> B{TabItem under point?}
    B -- no --> N[return None → whole window]
    B -- yes --> C[raise target window]
    C --> D{process?}
    D -- explorer.exe --> E[click tab to select →<br>read path from Address band]
    E --> F{path exists?}
    F -- yes --> G[explorer.exe path →<br>wait new window →<br>Ctrl+W closes original tab]
    F -- no --> H
    D -- other --> I[right-click tab →<br>find menu item containing<br>'new window' → click it]
    I --> J{new window appeared?}
    G --> J
    J -- yes --> R[return new hwnd]
    J -- no --> H[drag tear-off: held SendInput<br>slow grab + travel →<br>drop on taskbar strip]
    H --> K{new window appeared?}
    K -- yes --> R
    K -- no --> N
```

Pseudocode (language-neutral):

    tab ← TabItem under the pick point (walk ancestors, ≤6 levels)
    IF no tab → None (caller uses the whole window)
    raise the target window
    snapshot ← same-process top-level windows
    IF process is Explorer:
        click tab (select) → read Address-band path → open new window there
        IF new window appeared → Ctrl+W on original tab → DONE
    ELSE:
        right-click tab → menu item with "new window" in its name → click
        IF new window appeared → DONE
    drag tab (held SendInput, slow 40px grab, then travel)
        to the taskbar strip (outside every window rect) → release
    IF new window appeared → DONE, ELSE → None

Waiting for the new window = polling the same-process window set against the
snapshot, 0.25 s steps, 6 s ceiling.
