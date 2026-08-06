# Controls Editor — Flow

**About:** [description](../__about/controls_editor.md)

## Dialog layout

The command LIST replaced the four fixed button rows (owner 2026-08-05: a set
may hold more commands than a D-pad shows), and the per-command fields moved
into their own full-width rows — which is also what removed the two SPACE &
LEGIBILITY violations the owner photographed.

```
┌─ Controls — sets on the phone ──────────────────────────────────────────┐
│ Sets                 │ Name [Navigate.....]        Icon [▾ nav]         │
│ ┌──────────────────┐ │ [x] Shown in the wheel by default (≤ 8 sets)     │
│ │ STANDARD         │ │ ┌ Commands — tick the 4 on the D-pad ─────────┐  │
│ │  Mouse           │ │ │ On │ Name         │ Does     │ Shortcut     │  │
│ │  Input           │ │ │ [x]│ Esc          │ built-in │ esc          │  │
│ │  …               │ │ │ [x]│ Prev         │ chord    │ shift+tab    │  │
│ │ APP-AWARE        │ │ │ [x]│ Next         │ chord    │ tab          │  │
│ │  VSCode (code)   │ │ │ [x]│ Find         │ chord    │ ctrl+f       │  │
│ │  Claude (code·…) │ │ │ [ ]│ Back         │ chord    │ alt+left     │  │
│ │  Chrome (chrome) │ │ │ [ ]│ Find next    │ chord    │ f3      ↕    │  │
│ │ CUSTOM           │ │ │ [Add command][Remove]      4 of 4 on D-pad  │  │
│ │  My set          │ │ └────────────────────────────────────────────┘  │
│ └──────────────────┘ │                                                 │
│ [New set] [Delete]   │                                                 │
│                      │ ┌ The selected command ──────────────────────┐   │
│                      │ │ Does     [Shortcut (chord) ▾]              │   │
│                      │ │ Shortcut [shift+tab.............][Record…] │   │
│                      │ │ Name     [Prev..........................]  │   │
│                      │ │ Icon     [▾ tabback]                       │   │
│                      │ └────────────────────────────────────────────┘   │
│                      │ ┌ Arrangement ───────────────────────────────┐   │
│                      │ │ D-pad (landscape) │ Stack (portrait)       │   │
│                      │ │ [list + ↑ ↓]      │ [list + ↑ ↓]           │   │
│                      │ │                                  [Default] │   │
│                      │ └────────────────────────────────────────────┘   │
│ [Open the file]                                    [Save] [Cancel]      │
└─────────────────────────────────────────────────────────────────────────┘
   ▲ list asks for its widest entry   ▲ the table takes ALL the free height
```

## Where the space goes (SPACE & LEGIBILITY LAW)

```
free height ──▶ the command table            (the only stretched widget)
set list    ──▶ sizeHintForColumn(0)         "Explorer   (app · explorer)"
order lists ──▶ exactly their 4 rows         SlotList.sizeHint = rows + frame
detail form ──▶ one field per row, column 1 stretched, Record fixed
window min  ──▶ _computed_minimum()          measured strings, never a round number
```

## Data flow

```
open
 ├─ user_actions_path()          seed %LOCALAPPDATA% copy (installed) + config.apply
 ├─ load_client_icons()          client/controls.js → {name: svg}
 ├─ load_client_builtins()       client/controls.js → {action: (label, icon)}
 ├─ json.loads(actions.json)     → self.data (categories + custom_sets + app_sets)
 ├─ merge_shipped_pools()        built-in pools ← the SHIPPED file
 │                               (owner's active / order_* / enabled survive)
 └─ _reload_list() ─▶ _computed_minimum()    measure the filled widgets

select set S (currentRowChanged → _row_selected → _select)
 ├─ _rows[row]                   list ROW → entry index (None = a heading)
 ├─ _store_current()             previous set: screen → self.data (RAM)
 ├─ table.fill(pool, active…)    every pool command, four ticked
 └─ widgets ← S                  built-in / app: pool + arrangement only
                                 custom: name/icon/enabled/commands too

tick a command (itemChanged)
 ├─ >4 ticked → refuse the fifth, say "A D-pad holds 4 — untick one first"
 └─ else       → active = [button_id(...)], arrangement reset to shipped order

select a row (currentCellChanged)
 ├─ _store_command()             the previous row: form → pool (custom only)
 └─ detail.show_button(btn, editable)

Record… ──▶ ChordRecorder.keyPressEvent
             modifiers (ctrl/win/alt/shift) + main key → "ctrl+shift+p"
             Esc alone = cancel; unknown keys keep listening

Save
 ├─ _store_current()
 ├─ warn: custom sets with zero finished buttons
 ├─ clamp: shown-by-default sets > WHEEL_MAX → non-required extras enabled=false
 │         (app sets are never counted — they ride with a focused layout)
 └─ write actions.json (indent=2)  ──▶ phone re-reads on next connection
```

## Pool semantics

```
buttons     = the whole POOL of a set        (4 or more commands)
active      = ["click", "right", …]          IDs of the ≤4 on the D-pad
              missing  → the first four      (pre-pool files keep working)
button_id   = id | action | chord | key | label
order_land[slot] = index into ACTIVE         slots: 0=top 1=left 2=right 3=bottom
order_port[slot] = index into ACTIVE         slots: column top → bottom
identity order   = key removed               (shipped default needs no JSON)
invalid order    = ignored by client         (falls back to default)
```
