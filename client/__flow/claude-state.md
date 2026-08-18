# Claude state — Flow

**About:** [description](../__about/claude-state.md)

## Who asks, who answers, who may claim what

```
    tap on Model / Thinking / Mode
                │
                ▼
      openClaudePanel(btn)            client/claude-panels.js
                │
        ┌───────┴────────┐
        ▼                ▼
 requestClaudeState()   render() ──── draws NOW, with unknowns
        │                              (the card is on screen in the
        │                               SAME frame as the tap)
        ▼
   send {type:"claude_state"}
                │
                │   ...the PC may never answer.  That is ORDINARY:
                │      an older server has no such handler.
                ▼
      ┌─────────────────────┐          ┌──────────────────────────┐
      │ answer within 2 s   │          │ no answer (CLAUDE_ASK_MS)│
      └──────────┬──────────┘          └────────────┬─────────────┘
                 ▼                                  ▼
        onClaudeState(msg)                   claudePending = false
        claudeState = {...}                          │
        claudeSaved = msg.saved                      │
                 └──────────────┬─────────────────────┘
                                ▼
                        renderClaudePanel()
                     (in place — the ghost-click
                      armor's clock is not restarted)
```

## What each chip is allowed to say

```
                     PC answered?          value present?
                          │                      │
   ┌──────────────────────┴───────┐              │
   ▼                              ▼              ▼
 kind "fact"                 kind "fact"    text = the label
 SAVED  (config `saved`)     NOW            ────────────────
 NOW    (claude_state)       unknown        else text = "unknown"
                                            and value = null
   ▼
 kind "memory"   LAST SENT — this phone's own record.
                 NEVER lit like a fact:  no fill, dashed edge,
                 secondary ink  (task 208 in one rule).
```

**Nothing ever falls through from one chip to another.** `claudeEffortChips`
with a live answer missing reports `now = unknown` even when `saved.effort`
is known, because those are two different facts and conflating them IS the
208 report.

## Marking a row

```
MODEL     claude_state.model  "opus"          ── a FAMILY
                │
                ▼  claudeNowModel()
          CLAUDE_MODELS.find(m => m.family === family)
                │
        ┌───────┴────────┐
        ▼                ▼
   row "opus[1m]"     null  ── unknown family, or none.
   marked "now"             Default is NOT a catch-all: it
                            resolves per account, so no row
                            may claim it.

THINKING  only claude_state.effort lights a row.
          NOT claudeLastEffort(), NOT claudeSaved.effort —
          those are the chips, in their own words.
          (His screenshot: "Medium" lit under a PC on Max.)
```

## The Mode ring

```
                Shift+Tab
   default ─────► acceptEdits ─────► plan ──┐
      ▲                                     │
      └─────────────────────────────────────┘

 claudeModePresses(current, target)
        │
   current known? ── no ──► null
        │ yes
        ▼
   (to - at + 3) % 3        0 = already there (say so, press nothing)
```

```
 claudeSendMode(target)                     client/claude-panels.js
        │
   presses === null ?
        │ yes ──► ONE chord {shift+tab}
        │         toast: "stepped once — the PC did not say which
        │                 mode it was on"
        │
        │ no ───► N x chord {shift+tab}     (ordered: the server's
        ▼                                    receive loop awaits each)
   re-request claude_state after 1.5 s
   (sooner reads the state from BEFORE the tap)
```

**Why plain `chord` is safe enough to ship without a focus contract of its
own:** `chord` is in the server's `TYPING_KINDS`, so every press passes
through `focus_guard.typist()` exactly like `/usage` and `/compact` beside it
(`docs/DECISIONS.md` constraint 11). The Mode button is no more exposed than the buttons
it sits with. The gate holds that membership
(`check_the_mode_presses_ride_the_guarded_chord_path`) — if `chord` ever
leaves `TYPING_KINDS`, this button's presses stop being fenced and the gate
goes red.

## Sending a command

```
 tap an option
     │
     ├─ /effort only: prefSet("claudeLastEffort", value)   ← the memory
     ▼
 send {type:"paste_text", text:"/model opus[1m]", enter:true}
     │
 toast · close · re-request claude_state after 1.5 s
```
