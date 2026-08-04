# Controls Editor — Flow

**About:** [description](../__about/controls_editor.md)

## Dialog layout

```
┌─ Controls — sets on the phone ─────────────────────────────────┐
│ Sets                │ Name [........]        Icon [▾ preview]  │
│ ┌─────────────────┐ │ [x] Shown in the wheel by default (≤3)   │
│ │ Mouse (built-in)│ │ ┌ Buttons ───────────────────────────┐   │
│ │ Input (built-in)│ │ │ Top    [kind▾][label][icon▾][chord][Record…] │
│ │ …               │ │ │ Left   …                            │   │
│ │ My VSCode       │ │ │ Right  …                            │   │
│ └─────────────────┘ │ │ Bottom …                            │   │
│ [New set] [Delete]  │ └─────────────────────────────────────┘   │
│                     │ ┌ Arrangement ───────────────────────┐    │
│                     │ │ Landscape T·L·R·B │ Portrait ↑→↓   │    │
│                     │ │ [list + ↑ ↓]      │ [list + ↑ ↓]   │    │
│                     │ │              [Reset arrangement]   │    │
│                     │ └────────────────────────────────────┘    │
│ [Open the file]                              [Save] [Cancel]    │
└────────────────────────────────────────────────────────────────┘
```

## Data flow

```
open
 ├─ user_actions_path()          seed %LOCALAPPDATA% copy (installed) + config.apply
 ├─ load_client_icons()          client/controls.js → {name: svg}
 └─ json.loads(actions.json)     → self.data (categories + custom_sets)

select set S (currentRowChanged)
 ├─ _store_current()             previous set: screen → self.data (RAM)
 └─ widgets ← S                  built-in: only arrangement enabled
                                 custom: name/icon/enabled/buttons too

Record… ──▶ ChordRecorder.keyPressEvent
             modifiers (ctrl/win/alt/shift) + main key → "ctrl+shift+p"
             Esc alone = cancel; unknown keys keep listening

Save
 ├─ _store_current()
 ├─ warn: custom sets with zero finished buttons
 ├─ clamp: shown-by-default sets > WHEEL_MAX → non-required extras enabled=false
 └─ write actions.json (indent=2)  ──▶ phone re-reads on next connection
```

## Arrangement semantics

```
order_land[slot] = button index      slots: 0=top 1=left 2=right 3=bottom
order_port[slot] = button index      slots: column top → bottom
identity order   = key removed       (shipped default needs no JSON)
invalid order    = ignored by client (falls back to default)
```
