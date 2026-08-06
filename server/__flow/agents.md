# Agents — Flow

**About:** [description](../__about/agents.md)

## The bridge, end to end

```
THE PC                                              THE PHONE
──────                                              ─────────
Get-CimInstance Win32_Process -Filter claude.exe
 │
 ├─ "…\claude.exe --resume=0eb7cbe2-… --debug …"
 │        │
 │        └─ session id
 │             └─ ~/.claude/projects/<slug>/0eb7cbe2-….jsonl   ← the file exists
 │                   └─ first lines carry  "cwd": "u:\…\Remote User"
 │                         └─ folder name  "remote user"
 │
 └─ (a session with no --resume: a NEW conversation)
          └─ projects whose *.jsonl were written in the last 30 min

live_agents()  ->  {"claude": {"remote user", "uvuruna", "domy watch"}}
                                  │
window title "… - Remote User - Visual Studio Code [Administrator]"
                  └── title_folder() -> "remote user"  ──┘  match

layout_state.layouts[i].agents = ["claude"]  ───────────>  appSetMatches(s, lay)
layout_offer.entries[i].agents = ["claude"]  ───────────>  autoAppSets(slots)
```

## What decides an app set now, in order

```
appSetMatches(set, layout)              client/sets.js
 ├─ layout.app_sets is a list?          the owner ticked it himself → obey, stop
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
