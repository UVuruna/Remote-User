# client/sets.js — flow

## 1. The sets arrive

```
server  ──`actions` frame──▶  connection.js
                                 │  categories / appSets / customSets  ←  actions.json
                                 │
                                 ▼
                          enforceWheelCap()            ← sets.js
                                 │
                    over 8? ─────┴───── no ──▶ refreshCategories()
                        │
                       yes
                        │
                        ▼
                  capVictim() picks ONE                 ┌──────────────────────┐
                        │                               │ 1. app set in the    │
                        │  writes prefs, loops          │    CHARGING group    │
                        │                               │ 2. last optional     │
                        ▼                               │    basic             │
                 toast: "switched off Claude"           │ 3. last app set      │
                                                        └──────────────────────┘
```

The loop is bounded (64 turns) and stops the moment nothing droppable is
left — required sets are never touched, so a pathological file lands on
"three sets and a warning", never on a spin.

## 2. Which app sets ride, right now

```
layout focus changes ──▶ refreshCategories() ──▶ allCats()
                                                    │
                                                    ├── categories (required | ticked)
                                                    ├── visibleAppSets()
                                                    │      │
                                                    │      ├─ master switch off? → none
                                                    │      ├─ no layout focused? → none
                                                    │      └─ appSetMatches(s, lay) && appSetOn(s)
                                                    │              │
                                                    │              ├─ lay.app_sets exists?
                                                    │              │     └─▶ the OWNER'S TICKS decide, alone
                                                    │              └─ else: process match, then title word test
                                                    └── customSets (ticked)
```

`allCats()` still trims from the end as a last resort, but after
`enforceWheelCap()` it has nothing left to trim — which is the point: the
picker's counter and the wheel now say the same number.

## 3. A tick in the Sets picker

```
panels.js  setsRow / appSetRow
      │
      │  write the choice  ──▶  saveSetsPrefs()
      │  measure           ──▶  visibleCount() > 8 ?
      │                              │
      │                     yes ─────┴───── no
      │                      │               │
      │            revert + toast      refreshCategories() + refreshSetsMeta()
      ▼
prefs bridge (Android SharedPreferences via state.js — NOT localStorage,
which is per-ORIGIN and split the state between the LAN and Tailscale
addresses: the "picker rotates" bug of 2026-08-05)
```

Both rows now write-then-measure. They used to disagree — the basic row
measured *before* saving with `>=`, the app row *after* saving with `>` — and
a rule the code states twice is a rule the code will break once.

`refreshSetsMeta()` updates the counter line and the **on-the-wheel-now**
badges in place. It deliberately does not rebuild the card: re-rendering
re-arms the ghost-click armor (`GHOST_CLICK_MS`) and would swallow the
owner's next tick.

## Related

- [sets](../__about/sets.md) — the rules and why they exist
- [panels flow](../__about/panels.md) — the picker's own structure
