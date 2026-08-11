# client/sets.js — which sets ride the wheel

Split out of `controls.js` on 2026-08-06 (THE STRUCTURE LAW — controls.js hit
1 000 lines). The division is by responsibility, not by size:

- `controls.js` owns the D-pad groups, the wheel, and what a button DOES.
- **`sets.js` owns the question "which sets exist on this phone right now, and
  may they all fit"** — the per-device preferences, the app-aware matching,
  and the cap.

`panels.js` (the Sets picker) is the UI on top of it; `connection.js` fills
the three arrays when the `actions` frame arrives.

## The three sources

| source | where from | when it appears |
|--------|-----------|-----------------|
| `categories` | `actions.json`, shipped | always (`required`) or per tick |
| `customSets` | `actions.json`, made in the desktop Controls editor | per tick |
| `appSets` | `actions.json` → `app_sets` | only while a layout is focused |

## THE CAP OF 8 (owner 2026-08-06)

`WHEEL_MAX = 8` counts all three together, and it is a **law over the stored
state**, not a check that runs on a tap. That distinction is the whole reason
this section exists: the cap used to be tested only at the moment of a tick, so
any state that arrived another way walked straight past it. The owner found
**nine sets ticked by default** on his own phone — the picker printed
`9 of 8 used` while `allCats()` silently dropped the last two off the wheel.

Two sources fed that nine, and both are fixed:

1. the shipped `actions.json` had seven categories on by default and the two
   `code` app sets reserve two more — nine. `tests/test_app_set_wheel.py` now
   refuses a shipped file that ticks past the cap;
2. prefs saved before app sets started charging (v0.0.213) survived untouched.
   `enforceWheelCap()` normalizes them when the actions arrive, and
   `connection.js` toasts what had to give way.

**Which set gives way** is the owner's own rule — *"ako samo 7 osnovnih onda
mora jedan od claude i vscode da bude iskljucen"*: the app-aware set goes
first, because the basics are the ones he ticked on purpose. Only a set in the
**charging group** can free a slot — unticking Chrome while VSCode and Claude
hold two between them changes nothing at all, which is why `capVictim()` picks
from the largest per-process group rather than from the end of the list.

## The reserve

`appSetReserve()` is **not** "how many app sets are ticked". Chrome, Explorer
and VSCode can never match at the same moment, so ticking all three costs one
slot. VSCode + Claude cost two, because a Claude window shows both. The charge
is therefore the **largest group of ticked sets that can appear together**,
which is the group per process.

## How an app set knows it belongs (owner 2026-08-06, corrected 2026-08-07/08)

`appSetMatches()` asks **the PC**, and nobody ticks anything. A set carrying
`agent` is answered by `lay.agents` — the agent tools the server found RUNNING
in this layout's project, sent fresh on every `layout_state`. An empty array is
a definitive NO; the `titleMatches()` guess below it survives only for a server
too old to send the field at all.

A tick list (`lay.app_sets`, written at creation) existed for one day and was
deleted on 2026-08-07: it outranked the live answer forever, so one miss froze
his Claude layout on the VS Code wheel while `agents` said `claude` two lines
away in the same frame. **Never store an answer the PC can read** — and on
2026-08-08 the same rule had to be applied one layer deeper, to the window
TITLE the server derives `agents` from (see
[Window Manager](../../server/__about/window_manager.md) → the section on
`Layout.project`): an extracted VS Code tab can be born titled bare `Visual
Studio Code`, so the layout keeps the source window's HANDLE and re-reads it,
instead of freezing whatever string existed at creation.

The detection exists because the title guess was **proven impossible**.
Probing the owner's own PC while a Claude Code conversation was open found:

```
WIN 'Ispravka UI dizajna meni… - Vibe Coder - Visual Studio Code [Administrator]'
     TAB 'Ispravka UI dizajna meni…, Window 2: Editor Group 1'   ← Claude
     TAB 'prompt.txt, Editor Group 1'                            ← a file
```

Claude Code names its tab after the **conversation**. The word "claude" is
nowhere in it; the UIA `ClassName` is identical to the file tab's beside it;
`AutomationId` and `HelpText` are empty; and a full walk of the extracted
window's tree (20 elements) finds no occurrence of "claude" or "anthropic",
because VSCode does not expose webview content to accessibility. No string
test can ever identify it — the **process table** can, and that is what
`server/agents.py` reads.

The older `titleMatches()` still guards the fallback: the test is a **word**,
never a substring, and a title that looks like a document (`CLAUDE.md`,
`notes.txt — Visual Studio Code`) never matches. Without that rule the
fallback would put the Claude wheel on every open copy of the constitution.

## The owner's WHEEL ORDER (build round R5, 2026-08-07)

`wheelOrder` — a list of set NAMES from `actions.json`'s `wheel_order`,
written by the desktop Controls editor's "Wheel order…" dialog — decides
what ORDER `allCats()` hands to `controls.js`. Position 1 is the desktop
list's TOP, which `openWheel()` already draws at 12 o'clock (`angle = -PI/2
+ i * 2*PI/n`, i=0 straight up, increasing i sweeping CLOCKWISE); sorting the
array is the whole feature, nothing about the drawing changed.

`sortByWheelOrder(list)` runs on the list `allCats()` has ALREADY filtered
to whatever is actually going to ride — a set the owner mentions but that is
currently off (unticked, or an app set whose layout is not focused) was
never in that list, so the ring closes up with no hole where it would have
sat. A set the order does not mention (a future version's addition) sorts to
the END, in its ORIGINAL relative order among the other unmentioned sets
(stable sort — never dropped arbitrarily into the middle of the owner's own
arrangement). Missing/empty `wheelOrder` is a no-op — `allCats()` returns
exactly what it always did, which is what "a user who never opens the new
list sees no change" means in code.

The cap trim (above) runs AFTER the sort, unchanged — it still drops
non-required sets from the array's own end, which after sorting means it
drops the LAST set in the owner's own arrangement, never an arbitrary one.

## Related

- [sets flow](../__flow/sets.md) — the order things happen in
- [panels](panels.md) — the Sets picker that renders these rules
- [controls](controls.md) — the wheel and the D-pad groups
- [layouts](layouts.md) — where the per-layout ticks are chosen
- [Controls Order](../../server/gui/__about/controls_order.md) — the desktop
  side that writes `wheel_order`
- `tests/test_app_set_wheel.py` — the guard, twelve rules (four of them the
  wheel order)
