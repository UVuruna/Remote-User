# Theme — Flow

**About:** [description](../__about/theme.md)

## `TOKENS` — section / key tree

```
TOKENS
├─ Surfaces (elevation steps lighter, never flat gray)
│   ├─ surface0    #0F172A   (window background — matches client --surface-0)
│   ├─ surface1    #1E293B   (card background)
│   ├─ surface2    #273449   (control background)
│   └─ border      rgba(255,255,255,0.10)
├─ Text
│   ├─ text        #F5F5F5   (matches client --text-primary)
│   └─ text2       #A8B3C5   (matches client --text-secondary)
├─ Accent (one accent family — matches the client's --accent)
│   ├─ accent      #38BDF8
│   ├─ accentDark  #0EA5E9   (gradient stop — no client counterpart)
│   └─ accentDim   rgba(56,189,248,0.16)
├─ Semantic
│   ├─ success     #22C55E
│   ├─ warning     #F59E0B   (matches client --warning)
│   └─ error       #EF4444   (matches client --error)
└─ Shape
    ├─ radiusControl  8px
    └─ radiusCard     14px
```

`FONT_STACK` sits outside `TOKENS` (not a color/shape token) and is spliced in
at format time: `QSS.format(font=FONT_STACK, **TOKENS)`.

## `QSS` — rule blocks, in file order

```
QSS
├─ QWidget                        base background/text/font for the whole window
├─ QFrame#card                    the bento-card surface (surface1 + border + radiusCard)
├─ QLabel
│   ├─ (base)                     transparent background, no border
│   ├─ #h1                        20px / 700 weight — window title
│   ├─ #caption                   12px, text2 — subtitles/footer
│   ├─ #url                       12px, text2 — pairing URL
│   └─ #qr                        white background, rounded — QR image frame
├─ QLabel#pill                    status pill shell (radius 999px, bold, 12px)
│   ├─ [state="running"]          success green
│   ├─ [state="starting"]         warning amber
│   ├─ [state="stopped"]          neutral text2
│   └─ [state="failed"]           error red
├─ QPushButton
│   ├─ (base)                     surface2 + border + radiusControl
│   ├─ :hover / :pressed / :disabled
│   ├─ #primary                   accent→accentDark gradient (+ :hover/:disabled)
│   └─ #danger                    translucent error red (+ :hover)
├─ QComboBox
│   ├─ (base) / :hover
│   ├─ ::drop-down / ::down-arrow
│   └─ QAbstractItemView          popup list (accentDim selection)
├─ QMenu                          tray/context menu shell
│   └─ ::item / ::item:selected
└─ QToolTip
```

## Helper functions (not QSS-expressible)

    card_shadow(widget):
        attach QGraphicsDropShadowEffect(blur=28, offset=(0,6), color=black@55/255)

    repolish(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        # forces Qt to re-evaluate dynamic-property selectors (e.g. pill state)
