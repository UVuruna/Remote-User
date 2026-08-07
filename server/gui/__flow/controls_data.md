# Controls Editor — Data — Flow

**About:** [description](../__about/controls_data.md)

## Who owns what after the round R5 split

```
controls_data.py   (data)              controls_widgets.py (command widgets)
├─ user/shipped actions.json paths     ├─ ChordRecorder, CommandDetail,
├─ load_client_icons/builtins()        │  CommandTable, icon_for()
├─ button_id() / active_buttons()      controls_order.py   (order widgets)
├─ merge_shipped_pools()               ├─ SlotList/SlotDelegate/OrderList
├─ natural_order()                     ├─ WheelRing, WheelOrderDialog
└─ effective_wheel_order()             controls_editor.py  (the window)
        ▲ imported by all three ◀──────────────── assembles the above
```

## merge_shipped_pools — THE OWNERSHIP RULE, key by key

The owner's actions.json is seeded ONCE at install and never replaced, so this
is the only path a later version has into it. The decision is per KEY, and it
is a rule — never a list of today's field names (2026-08-07: a hardcoded list
is what kept `agent` out of his Claude set through four releases).

```
                        ┌──────────────── is the key HIS? ────────────────┐
                        │  set:  active · order_land · order_port ·       │
                        │        enabled          (+ button `label`)      │
                        │  top:  wheel_order · left · right · custom_sets │
                        └───────────────────────┬────────────────────────-┘
                                 yes ◀──────────┴──────────▶ no  (= OURS)
                                  │                          │
                    he has it? ───┤                          │
                      yes → KEEP exactly as he left it       │
                      no  → SEED it from shipped ────────────┤
                            (wheel_order lands here)         │
                                                             ▼
                                              value ← shipped, ALWAYS
                                              not in shipped → DELETE
                                              (works for fields nobody
                                               has invented yet)

merge_shipped_pools(data, shipped)
 1. every TOP-LEVEL key of shipped, by the rule above
 2. for key in ("categories", "app_sets"):     ◀── MERGED_SECTIONS
      for each shipped set S, matched by NAME:
        owner has no such set → append S's own copy (newly shipped)
        owner has it          → _merge_set(his, S):
                                  every key by the rule above
                                  renames carried by COMMAND ID
                                  stale `active` → dropped
 3. custom_sets — never touched, at any depth
    a set HE has that we no longer ship — left alone (it may have moved)
```

Gate: `tests/test_actions_migration.py` — starts from his REAL older file
shape and plants an invented field name, because every earlier guard built its
"user file" out of the SHIPPED file and so could not fail.

## natural_order / effective_wheel_order

```
natural_order(data)
 = [s.name for key in ("categories","app_sets","custom_sets")
           for s in data[key]]        ◀── "today's order" — the shipped
                                          actions.json's own wheel_order

effective_wheel_order(data)
 names  = natural_order(data)
 saved  = [n for n in data.get("wheel_order", []) if n in names]
 saved += [n for n in names if n not in saved]   ◀── unmentioned → END
 return saved                                     (never mutates data)
```
