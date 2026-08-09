# Layouts — Flow

**About:** [description](../__about/layouts.md)

## Layout — the on-screen pieces this file owns

```
📱 viewport
  ┌───────────────────────────────────────────────────────────┐
  │ [+] #btn-newlay      #layout-bar            #btn-hide [👁] │
  │                 ⟨ ‹ ⟩ ┌──────────────┐ ⟨ › ⟩  ✕           │
  │                 SVG   │ 🗔  Chrome    │ SVG                │
  │                 32px  └──────────────┘                     │
  │                        tap → layout list                   │
  └───────────────────────────────────────────────────────────┘
  🗂 #layout-panel   — the ONE overlay card, several contents:
        · source chooser / creation panel   (creating ≠ null)
        · layout list (Desktop + every layout: icon ⭐ name shape ⚙)
        · the ⚙ SHEET, and the panels it opens — rename, aspect
          (W : H + preview, aspecting ≠ null), the member chooser
        · the ✕ chooser (remove / close, + what a close destroys)
  🧊 #lay-loading    — opaque full-screen cube overlay (class `open`)
```

## Where a window's FULL title is readable

A title is the only thing that tells two windows of one app apart, so it is
never shortened in JS — but since task 163 (2026-08-09) a ROW is one line and
the cut is made by CSS. The full title therefore lives ONE TAP AWAY, in a
field that wraps, and every row that elides one has such a field behind it.

```
creation panel                        layout list                 layout bar
┌──────────────────────────────────┐  ┌──────────────────────┐   ┌──────────┐
│ Chosen (1/2) — tap to remove:    │  │ 🗔 Claude Code - R…  │   │ 🗔 Claude│
│ ┌──────────────────────────────┐ │  │ 🗔 Downloads         │   │ Code -   │
│ │ 🗔 Claude Code - Remote Us…  │ │  │ 🗔 Reading           │   │ Remote…  │
│ └──────────────────────────────┘ │  └──────────────────────┘   └──────────┘
│ Name:  ┌───────────────────────┐ │  one line each, cut by      2 rows, then
│        │ Claude Code - Remote  │ │  CSS — the ⚙ opens the      clamped — the
│        │ User - Visual Studio  │ │  sheet, whose Rename card   list is one
│        │ Code [Administrator]  │ │  wraps the whole name       tap away
│        └───────────────────────┘ │
└──────────────────────────────────┘
  ▲ the WRAPPING field is the durable copy, prefilled with the window's
    own title (owner 2026-08-06 — the full name must be readable
    somewhere on that screen). The rows above it are kin: same height,
    one line, and a tab is INDENTED under its window rather than made
    a member of its group (owner 2026-08-09, task 168)
```

Every row on both lists shares ONE treatment — `.lay-item-main span`: take the
free width, then elide. (The wrapping title pill that predated it, `titleChip`
/ `.lay-chip.lay-title`, was deleted on 2026-08-09 when its last caller became
rows.) The top bar is the single exemption in the project, written into
`layouts.css` beside the rule: it owns one row of the phone screen, and one
tap opens the list.

## Algorithm — how long the loading animation lasts

```mermaid
flowchart TB
    START[layout created / switched / reshaped] --> SHOW[showLayLoading:\nnext cube face, fade in, spin]
    SHOW --> WAIT[server works\n layout_progress → cubeNext momentum burst]
    WAIT --> STATE[layout_state arrives\n= server is done]
    STATE --> ARM[settleLayLoading:\nstart sampling 64x36 thumbnails]
    ARM --> TICK{three samples\nnearly identical?}
    TICK -- no --> AGE{past SETTLE_MAX_MS\nafter the answer?}
    AGE -- no --> TICK
    AGE -- yes --> HIDE
    TICK -- yes --> MIN{overlay up\n> LOADING_MIN_MS?}
    MIN -- no --> TICK
    MIN -- yes --> HIDE[hideLayLoading:\nfade out, keep spinning\nthrough the fade]
    SHOW -.-> BACKSTOP[LOADING_MAX_MS 40s\nserver never answered] -.-> HIDE
```

Pseudocode:

    showLayLoading(text):
        cubeView = (cubeView + 1) % 6        # top → left → back → right → front → bottom
        cube tilt/angle = CUBE_VIEWS[cubeView]
        overlay.classList.add("open")        # CSS cross-fades in
        spin loop starts (rAF), backstop timer = LOADING_MAX_MS

    settleLayLoading():                      # called by the layout_state handler
        every SETTLE_SAMPLE_MS:
            draw the live frame source into a 64x36 canvas
            still = mean |Δrgb| vs the previous sample < SETTLE_DIFF
            hits = still ? hits + 1 : 0
            IF past the settle deadline OR (hits >= SETTLE_STABLE_HITS AND up > LOADING_MIN_MS):
                hideLayLoading()

## Algorithm — where a tap on a row goes (owner 2026-08-09, task 175)

Every act on a layout that ALREADY EXISTS is behind one ⚙, and Cancel is
always ONE step back — the chain is the same in both directions. The row's
shape badge is a SHORTCUT into it (task 165), so backing out of the member
chooser lands on that layout's sheet, not on the list.

```mermaid
flowchart TB
    BAR[layout bar: tap the framed name] --> LIST[layout list
icon ⭐ name shape ⚙]
    LIST -- tap the row --> FOCUS[layout_focus index]
    LIST -- hold + drag --> MERGE[layout_merge / layout_reorder]
    LIST -- tap the SHAPE --> MEM[member chooser
layout_member_remove]
    LIST -- tap the ⚙ --> SHEET[⚙ settings sheet]
    SHEET -- Rename --> REN[rename card → layout_rename]
    SHEET -- Aspect ratio --> ASP[aspect panel → layout_aspect]
    SHEET -- Take one window out --> MEM
    SHEET -- Orientation chip --> GRID[layout_grid index, grid, orient
the tap IS the command]
    SHEET -- Arrangement chip --> GRID
    REN -- Cancel --> SHEET
    ASP -- Cancel --> SHEET
    MEM -- Cancel --> SHEET
    SHEET -- Back --> LIST
```

`layout_grid` re-places real windows on the PC, so the loading cube covers it
and the phone's rotation lock follows the `layout_state` that comes back
(`applyOrientationLock`). The server needed nothing new for it: the message has
existed since 2026-08-07 for a three's arrangement — what it did not have was a
gate, and `tests/test_layout_shape.py` is it.

## Algorithm — the aspect ratio panel

```mermaid
flowchart TB
    OPEN[tap a layout's ratio button] --> DEV[devicePair orient → devA = W/H\nthe phone's own shape as one number]
    DEV --> STATE[state a = devA\nor the layout's stored ratio]
    STATE --> EDIT[drag anywhere in the preview — continuous\nOR type either W / H field]
    EDIT --> CLAMP[clampAspect: shrink-only side\nportrait a ≥ devA · wide a ≤ devA\nfloor ASP_MIN_FRAC]
    CLAMP --> PREV[preview only —\nnothing moves on the PC\nfields show ratioPair a]
    PREV --> APPLY[Apply] --> SEND[send layout_aspect index,\nround a×1000 : 1000 + pos 0–1000\nfull screen → 0,0]
    SEND --> LOAD[showLayLoading 'Reshaping the layout…']
    PREV --> RESET[Screen] --> DEFAULT[a = devA\nApply sends 0,0 = no override]
```

The rule the panel enforces, and the server enforces again
([Window Manager](../../server/__about/window_manager.md) → `layout_region`):
the region is the largest rect of the chosen W:H **inside** the box the
phone's own shape gives — it can only ever shrink, never grow past the screen.

    portrait:   width  = phone's width   (pinned)   height ≤ phone's height
    landscape:  height = phone's height  (pinned)   width  ≤ phone's width

`pos` (the Move handle) travels the same message but acts on the PHONE
(owner decree 2026-08-09): the server stores it, echoes it in `layout_state`,
and always centres the windows on the monitor; the picture is anchored by
[View Anchor](../__about/view-anchor.md) when the reply's `layout_state`
triggers `resetViewHome()`.

## Algorithm — creation sources

```mermaid
flowchart TB
    PLUS[Layout +] --> CHOOSE{source}
    CHOOSE -- From a list --> LIST[send layout_list\noverlay: 'Collecting windows and tabs…']
    LIST --> ENTRIES[layout_offer.entries\nwindows already IN a layout are absent;\ntabs only from tab-capable apps]
    CHOOSE -- Tap a window --> ARM[layoutArm = true\nthe next canvas tap sends layout_pick]
    ARM --> OFFER[layout_offer.target + tab]
    ENTRIES --> SLOTS[slot panel: mode solo/grid,\norientation, chosen slots]
    OFFER --> SLOTS
    SLOTS --> CREATE[Create → layout_create slots\noverlay: 'Arranging the windows…']
```
