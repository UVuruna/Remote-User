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

## How an app set knows it belongs (owner 2026-08-06)

`appSetMatches()` answers from `lay.app_sets` — **the ticks the owner made
when he created the layout** — whenever that list exists. The process/title
guess below it survives only for layouts made before this version.

The tick exists because the guess was **proven impossible**. Probing the
owner's own PC while a Claude Code conversation was open found:

```
WIN 'Ispravka UI dizajna meni… - Remote User - Visual Studio Code [Administrator]'
     TAB 'Ispravka UI dizajna meni…, Window 2: Editor Group 1'   ← Claude
     TAB 'prompt.txt, Editor Group 1'                            ← a file
```

Claude Code names its tab after the **conversation**. The word "claude" is
nowhere in it; the UIA `ClassName` is identical to the file tab's beside it;
`AutomationId` and `HelpText` are empty; and a full walk of the extracted
window's tree (20 elements) finds no occurrence of "claude" or "anthropic",
because VSCode does not expose webview content to accessibility. No string
test can ever identify it — so the owner marks it, once, with one tap.

The older `titleMatches()` still guards the fallback: the test is a **word**,
never a substring, and a title that looks like a document (`CLAUDE.md`,
`notes.txt — Visual Studio Code`) never matches. Without that rule the
fallback would put the Claude wheel on every open copy of the constitution.

## Related

- [sets flow](../__flow/sets.md) — the order things happen in
- [panels](panels.md) — the Sets picker that renders these rules
- [controls](controls.md) — the wheel and the D-pad groups
- [layouts](layouts.md) — where the per-layout ticks are chosen
- `tests/test_app_set_wheel.py` — the guard, six rules
