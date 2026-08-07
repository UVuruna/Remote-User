# Style — Flow

**About:** [description](../__about/style.md)

## `:root` — design tokens

```
:root
├─ Surfaces
│   ├─ --surface-0    #0f172a               page background
│   ├─ --glass-fill   rgb(30 41 59 / 0.20)  see-through button fill
│   └─ --border       rgb(255 255 255 / 0.20)
├─ Live viewport (written by render.js's updateViewport() from
│  visualViewport — not static)
│   ├─ --kb     0px   soft-keyboard height — lifts the D-pad groups clear of it
│   └─ --vtop   0px   visualViewport top offset — keeps top corners visible
├─ Text
│   ├─ --text-primary    #f5f5f5
│   └─ --text-secondary  #a8b3c5
├─ Accent (one accent family)
│   ├─ --accent        #38bdf8
│   ├─ --accent-2      #8b5cf6
│   └─ --accent-glow   rgb(56 189 248 / 0.25)
├─ Semantic
│   ├─ --warning   #f59e0b
│   └─ --error     #ef4444
└─ Shape / Spacing
    ├─ --radius-pill  999px
    ├─ --space-s      8px
    ├─ --space-m      16px
    └─ --topbar       bottom edge of the top panel (corners + layout bar) —
                      every floating notice starts BELOW this line so it can
                      never cover the layout name / arrows
```

## Rule blocks, in file order

```
style.css
├─ * (reset)                    margin/padding/box-sizing
├─ html, body                   full-size, no scroll/overscroll/selection,
│                               touch-action:none
├─ #screen                      the canvas — full-size, touch-action:none
├─ #status                      connection + toast pill, fixed top-center,
│                               top: --topbar (under the top panel)
│   ├─ .connecting              warning→amber gradient
│   ├─ .connected               accent gradient, opacity:0 (fades out once live)
│   ├─ .disconnected            error→red gradient
│   └─ .fade                    opacity:0 keeping the current colour — how an
│                               expiring toast leaves the screen without
│                               flashing a blue "Connected" pill
├─ #kb                          keyboard-capture textarea — full-width 42px
│                               strip, transparent text/caret/background,
│                               pointer-events:none (real-size + transparent,
│                               never display:none/opacity:0 — see the file's
│                               own comment for why)
├─ #filepick                    display:none (phone→PC upload input)
├─ #vid                         offscreen H.264/MSE decode surface — pushed
│                               off the left edge rather than display:none,
│                               so the browser keeps decoding
├─ Buttons (.ctl)               see-through fill, no backdrop blur
│   ├─ .ctl                     58×58, rounded, icon+label column
│   ├─ .ctl svg / .ctl .lbl     icon and label, drop-shadowed for legibility
│   │                           over the live stream
│   ├─ .ctl.text .lbl           chord buttons: no icon, label fills the face
│   ├─ .ctl.active              accent glow + scale(1.06)
│   └─ .ctl.cat                 the smaller category-wheel opener (dashed
│                               border, 42×42)
├─ Corners (.corner)            fixed top, offset by --vtop
│   ├─ .corner-tl                 left (Move)
│   └─ .corner-tr                 right (Hide)
├─ D-pad groups (.group)        fixed bottom, above --kb + safe-area-inset-bottom
│   ├─ .group.left / .group.right
│   ├─ grid-template-areas       ". up . / left center right . down ."
│   │                           (landscape — CSS grid cross)
│   └─ @media (orientation: portrait)
│                               column stack: up / left / center / right / down
├─ Category wheel (#wheel)      full-screen tap-to-open overlay (display:none
│                               until .open)
│   ├─ .wheel-item               circular category button, positioned
│   │                           absolutely (coordinates set by controls.js's
│   │                           openWheel)
│   ├─ .wheel-item.current       accent glow — marks the active category
│   └─ .wheel-x                  the ✕ cancel button, screen center
├─ "Access from anywhere" banner + wizard
│   ├─ #anywhere-banner          pill, bottom-center, above --kb
│   ├─ #update-banner            pill, below #status — in-app update offer
│   ├─ #wizard / .wiz-card       full-screen modal, scrollable card
│   ├─ #wiz-close                ✕ dismiss, top-right of the card
│   ├─ .wiz-step / .wiz-num / .wiz-body / .wiz-btn(.primary)
│   └─ .wiz-step.done            green success state (step 3 — Tailscale
│                               joined)
└─ Hide-all mode
    └─ body.hidden-controls      hides .group, #wheel, #anywhere-banner,
                                  .corner-tl (Move) — .corner-tr (Hide) stays
                                  reachable so the mode can be toggled back.
                                  #update-banner is ALSO hidden in this mode,
                                  but that rule is declared next to
                                  #update-banner's own block, not gathered
                                  here with the rest (noted for accuracy, not
                                  changed — see the folder's Design Decisions)
```

## Build round R3 (2026-08-07) — themes

```
theme.css   :root                      every colour, dark by default
            body[data-theme="light"]   surfaces invert, accent deepens,
                                       ink shadows flip black -> white
            body[data-theme="colored"] dark surfaces + per-set --set-color
            body[data-fill="full"]     --glass-fill/--chip -> --fill-solid
      |
      v  (loaded first)
style.css   :root   --kb --vtop --topbar --corner --radius-pill --space-*
            ...every rule below reads a colour token and names none.
      |
      v
layouts.css ...the same, for the layout feature's own surfaces.
```
