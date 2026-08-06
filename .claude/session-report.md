# Final Report — Round 10 (2026-08-06)

Shipped as **v0.0.085**:
https://github.com/UVuruna/Remote-User/releases/tag/v0.0.085

| # | Task (owner's words) | Status | Evidence |
|---|---|---|---|
| 41 | "zašto mi se ne pokazuje Claude controls" | **FIXED** | Root cause probed live on his PC: the Claude tab is named after the CONVERSATION ('Ispravka UI dizajna meni…'), identical UIA class to `prompt.txt`, empty AutomationId/HelpText, 20-element tree with zero "claude" hits. Fixed by `Layout.app_sets` — his own tick. Guard case "the layout's own ticks win over the title guess" pins his real title. |
| 42 | "zašto mogu 9 opcija da uključim" — 8 is LAW | **FIXED** | Two sources: the cap ran only on a tap (now `enforceWheelCap()` normalizes stored state) and the SHIPPED actions.json ticked 9 (Cursor off by default). Desktop editor counts the same reserve. Self-test: re-enabling Cursor → "ticks 9 sets by default". |
| 43 | "hoću da bude štiklirano pored onoga koji je aktivan" | **FIXED** | "ON THE WHEEL NOW" badge on the app rows; phone audit measures the picker with two badges lit. Self-test: 210px badge padding → FAIL at both orientations. |
| 44 | "ni sistem notifikacija ne radi ???" | **FIXED** | Correct — `agent_hook.py` was never registered. Installed, and ROADMAP H2 closed with the Settings-card switch (reads the real state; handles frozen bundle + missing python honestly). |
| 45 | THE STRUCTURE LAW (controls.js hit 1000) | **FIXED** | `client/sets.js` + about/flow + client index + load-test order + docs tier. |
| 46 | Round close | **DONE** | APK 0.0.085, INPUT + PRESENCE + NOTIFY gates, PyInstaller smoke test, signed exe + installer, release published. |

## Gates on the released tree

guards 4/4 · APP-SET WHEEL 6/6 · INPUT GATE · PRESENCE GATE · NOTIFY GATE 13/13
· Qt layout audit 4/4 · phone layout audit 19/19 · client load test.

## Open on the owner's device

Install v0.0.085 → make the Claude layout → tick **Claude** in the creation
panel → the Claude set must ride beside VSCode. Then Settings → Sets: the
counter must read 8 of 8, never 9, and both live sets must wear the badge.

## Two-session note

The parallel session took 0.0.223 and shipped v0.0.084 mid-round, so my five
commits were renumbered to 0.0.230–0.0.235 before anything was pushed. Two
files that were not mine (`.claude/settings.json`, `e.txt`) were swept into a
`git add -A` and taken back out — staged files belong to whoever owns the
change.
