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
              pid alive?  procStart matches?  ──▶  "u:\…\Vibe Coder"
                                                        └─ "remote user"
    TIER 2  "…\claude.exe --resume=0eb7cbe2-…"     ← an older CLI
              └─ ~/.claude/projects/<slug>/0eb7cbe2-….jsonl
                    └─ first lines carry "cwd"  ──▶  "remote user"
    TIER 3  the N most recently written projects   ← N = still unnamed
              (never more than that, never older than FRESH_S)

live_agents()  ->  {"claude": {"remote user", "uvuruna"}}
                                  │
Layout.project()   ← MEASURED every frame, never stored
  1. the member's OWN title    "Visual Studio Code"      -> no folder
  2. the SOURCE window's title  (the tab was torn out of it, still alive)
       "… - Vibe Coder - Visual Studio Code [Administrator]"
                  └── title_folder() -> "remote user"  ──┘  match
  3. the folder read at creation  ← last resort, source closed
                                    (a FOLDER, never an answer)

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

## What the conversation is running now (`claude_state`, task 208)

```
the focused layout ──▶ Layout.project()  ──▶  "remote user"
                                                   │
              newest_transcript(folder)            │
                ~/.claude/projects/*/               │
                  └─ folder_of(slug) == folder ?   ◀┘   (cwd, never the slug name)
                  └─ newest *.jsonl of the winners
                             │
              _tail_records(path)   last 256 KB, first (torn) line dropped
                             │      unparsable lines skipped in silence
                             ▼
              walk the records BACKWARDS, taking the first of each:

                 {"type":"assistant", "effort":"high",        ─▶ effort
                  "message":{"model":"claude-opus-5[1m]"}}    ─▶ model_id
                        │  (tool-call records carry both — nothing is skipped)
                        └─ model_family()  strips "[1m]"      ─▶ model  "opus"

                 the first record that HAS "permissionMode"   ─▶ mode  "plan"
                        (a tool RESULT is type:"user" and has none;
                         {"type":"mode"} reads "normal" always — not the source)

              claude_settings()  ~/.claude/settings.json      ─▶ saved
                             │
                             ▼
   {"type":"claude_state", model, model_id, effort, mode, saved}  ───▶  the phone
```

Nothing in that column raises: every step that finds nothing contributes
`None`, and the frame is sent with the fields it could fill. The desktop (no
focused layout) asks for the empty folder and lands on the same answer — only
`saved` stands there, because there is no one conversation to describe.
