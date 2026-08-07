# Agents — Flow

**About:** [description](../__about/agents.md)

## The bridge, end to end

```
THE PC                                              THE PHONE
──────                                              ─────────
Get-CimInstance Win32_Process -Filter claude.exe
 │   → (pid, creation FILETIME, command line)  for each
 │
 ├─ "--claude-in-chrome-mcp"          ✗ an MCP helper, not a conversation
 │
 └─ every CONVERSATION process, resolved in three tiers:

    TIER 1  ~/.claude/sessions/<pid>.json          ← Claude Code's own record
              {pid, cwd, procStart, kind, …}
              pid alive?  procStart matches?  ──▶  "u:\…\Remote User"
                                                        └─ "remote user"
    TIER 2  "…\claude.exe --resume=0eb7cbe2-…"     ← an older CLI
              └─ ~/.claude/projects/<slug>/0eb7cbe2-….jsonl
                    └─ first lines carry "cwd"  ──▶  "remote user"
    TIER 3  the N most recently written projects   ← N = still unnamed
              (never more than that, never older than FRESH_S)

live_agents()  ->  {"claude": {"remote user", "uvuruna"}}
                                  │
window title "… - Remote User - Visual Studio Code [Administrator]"
                  └── title_folder() -> "remote user"  ──┘  match

layout_state.layouts[i].agents = ["claude"]  ───────────>  appSetMatches(s, lay)
layout_offer.entries[i].agents = ["claude"]  ───────────>  autoAppSets(slots)
```

Measured on the owner's PC, 2026-08-07: four `claude.exe` — two helpers
dropped, two conversations both named by tier 1, tiers 2 and 3 never reached.

## What decides an app set now, in order

```
appSetMatches(set, layout)              client/sets.js
 │                                      (the tick list that used to answer
 │                                       first was removed on 2026-08-07 —
 │                                       it outranked live detection forever)
 ├─ process does not match?             not this app → no
 ├─ set.agent set?                      ASK THE PC
 │     ├─ layout.agents has it          → YES  (the detection path)
 │     └─ no `agents` field at all      → fall back to the old title guess,
 │                                        for a server older than this one
 ├─ set has no `title`                  → YES  (the whole app: VSCode, Chrome…)
 └─ else                                → the word test on the window's title
```

## Cost

```
one PowerShell call            ~1.0 s cold          measured on the owner's PC
cached                         2 s                  CACHE_S
called from                    layout_state, layout_offer
worst case per state send      one scan, shared by every layout in it
```
