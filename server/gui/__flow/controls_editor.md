# Controls Editor — Flow

**About:** [description](../__about/controls_editor.md)

## Dialog layout

The command LIST replaced the four fixed button rows (owner 2026-08-05: a set
may hold more commands than a D-pad shows), and the per-command fields moved
into their own full-width rows — which is also what removed the two SPACE &
LEGIBILITY violations the owner photographed.

```
┌─ Controls — sets on the phone ──────────────────────────────────────────┐
│ Sets — ticked = on   │ Name [Navigate.....]        Icon [▾ nav]         │
│ the phone's wheel    │ [x] Shown in the wheel by default (≤ 8 sets)     │
│ ┌──────────────────┐ │ ┌ Commands — tick the 4 on the D-pad ─────────┐  │
│ │ STANDARD         │ │ │ On │ Name         │ Does     │ Shortcut     │  │
│ │  Mouse         ✓ │ │ │ [x]│ Esc          │ built-in │ esc          │  │
│ │  Input         ✓ │ │ │ [x]│ Prev         │ chord    │ shift+tab    │  │
│ │  Cursor          │ │ │ [x]│ Next         │ chord    │ tab          │  │
│ │ APP-AWARE        │ │ │ [x]│ Find         │ chord    │ ctrl+f       │  │
│ │  VSCode (code)   │ │ │ [ ]│ Back         │ chord    │ alt+left     │  │
│ │  Claude (code·…) │ │ │ [ ]│ Find next    │ chord    │ f3      ↕    │  │
│ │ CUSTOM           │ │ │ [Add command][Remove]      4 of 4 on D-pad  │  │
│ │  My set        ✓ │ │ │ [ ]│ Focus        │ chord    │ ctrl+esc     │  │
│ └──────────────────┘ │ │ [Add command][Remove]      4 of 4 on D-pad  │  │
│ [New set][Delete]    │ └────────────────────────────────────────────┘  │
│ [Wheel order]        │ ┌ The selected command ──────────────────────┐   │
│ ┌ Arrangement ─────┐ │ │ Does     [Shortcut (chord) ˅]              │   │
│ │ D-pad  │ Stack   │ │ │ Shortcut [shift+tab.............][Record]  │   │
│ │ [list] │ [list]  │ │ │ Name     [Prev..........................]  │   │
│ │ [↑][↓] │ [↑][↓]  │ │ │ Icon     [˅ tabback]                       │   │
│ │            [Def] │ │ └────────────────────────────────────────────┘   │
│ └──────────────────┘ │            [Open the file]     [Save] [Cancel]   │
└─────────────────────────────────────────────────────────────────────────┘
   ▲ LEFT = which set, and how it rides     ▲ RIGHT = which commands
     (list states its own rows AND width)     (the table takes the free height)
```

## Where the space goes (SPACE & LEGIBILITY LAW)

The Arrangement box moved into the LEFT column on 2026-08-07 — ladder step 2,
after two independent graders measured the same hole: three of thirteen pool
rows behind a scrollbar with ~253 px of idle set list beside them. Both
columns now STATE what they need, which is what makes the minimum honest.

```
left column  ──▶ caption + set list + [New set][Delete][Wheel order] + Arrangement
right column ──▶ Name/Icon form + the pool table + the selected command + actions
window min   ──▶ max(left, right)            _computed_minimum() is only the FLOOR;
                                             settle_minimum grows it to the truth
set list     ──▶ _fit_set_list()             its widest entry + MARK (the tick's
                                             reserved 22 px column) AND its real
                                             row height, capped at ROWS_SHOWN = 15
pool table   ──▶ _fit_rows()                 all 13 rows of the largest shipped pool
free height  ──▶ the pool table              the right column is the shorter one,
                                             so its stretch lands here
order lists  ──▶ exactly their 4 rows        SlotList.sizeHint = rows + frame
detail form  ──▶ one field per row, column 1 stretched, Record fixed
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

Wheel order… ──▶ _open_wheel_order (build round R5, 2026-08-07)
 ├─ effective_wheel_order(self.data)   saved order + unmentioned sets, appended at the end
 ├─ natural_order(self._shipped)       the dialog's own Default target
 └─ WheelOrderDialog(current, default, self).exec()
       accepted → self.data["wheel_order"] = dlg.order_names()   (RAM only —
                                              Save below writes it to disk)
       cancelled → self.data untouched
    See [Controls Order — Flow](controls_order.md) for the dialog's own diagram.

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
