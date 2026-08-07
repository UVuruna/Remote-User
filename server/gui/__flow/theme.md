# Theme — Flow

**About:** [description](../__about/theme.md)

## `PALETTES` — the same keys, twice

```
PALETTES
├─ "dark"                                   │ "light"
│   Surfaces  (higher = LIGHTER)            │  (higher = WHITER, page a step down)
│   ├─ surface0    #0F172A                  │  #ECEEF6
│   ├─ surface1    #1E293B  (cards)         │  #FFFFFF   ← the raised card is whitest
│   ├─ surface2    #273449  (controls)      │  #DFE2EE
│   └─ border      rgba(255,255,255,0.10)   │  #C7CBDD   ← a REAL line; alpha on white is nothing
│   Text                                    │
│   ├─ text        #F5F5F5                  │  #16161F
│   └─ text2       #A8B3C5                  │  #545A6B
│   Accent  (one family, DEEPENED on light) │
│   ├─ accent      #38BDF8   2.16:1 on white│  #0369A1   6.1:1 under white ink
│   ├─ accentDark  #0EA5E9                  │  #075985
│   ├─ accentDim   rgba(56,189,248,0.16)    │  rgba(3,105,161,0.14)
│   └─ onAccent    #06212E                  │  #FFFFFF   ← ink ON the accent, not a surface
│   Semantic                                │
│   ├─ success     #22C55E                  │  #15803D
│   ├─ warning     #F59E0B                  │  #B45309
│   └─ error       #EF4444                  │  #DC2626
│   Semantic wash + edge (was rgba() INSIDE the QSS until round R3)
│   ├─ successDim/Edge, warningDim/Edge, errorDim/Edge
│   ├─ dangerFill / dangerFillHover / dangerEdge
│   └─ neutralDim
│   A control that is OFF / PRESSED  (a DARK sentence until it was tested)
│   ├─ controlOff     #1E293B               │  #EDEFF5
│   └─ controlPressed #1E293B               │  #C9CEE0
│   A TEXT INPUT  (2026-08-07 — QLineEdit had no rule at all and wore the PAGE)
│   ├─ fieldFill   #273449  (rises)         │  #FFFFFF   ← white inside a real line
│   ├─ fieldEdge   rgba(255,255,255,0.16)   │  #C7CBDD
│   └─ fieldOff    #1E293B                  │  #F7F8FC   ← DISABLED, and NOT
│      controlOff: a dead button owes the user nothing but its label, a dead
│      INPUT still shows a value he must read. Reusing controlOff here put the
│      set Name and the Shortcut field back at one unit from the light page —
│      the same defect, one state over (measured 2026-08-07, fourth time)
│   Marks the QSS loads as FILES (image: cannot re-tint what it loads)
│   ├─ checkAsset  check      (dark ink)    │  check-light  (white ink)
│   └─ caretAsset  caret      (text2 ink)   │  caret-light  (text2 ink)
│   Depth                                   │
│   └─ shadowRgba  0, 0, 0, 55              │  15, 23, 42, 30   ← tinted and softer
│   Fixed in both                           │
│   ├─ qrPaper     #FFFFFF   (a QR is scanned by a camera)
│   ├─ radiusControl 8px
│   └─ radiusCard    14px

TOKENS = the ACTIVE one, mutated IN PLACE:
    set_theme("light"):  TOKENS.clear(); TOKENS.update(PALETTES["light"])
    …so every TOKENS["accent"] already written inside a paintEvent
      reads the live value with no call-site change.
```

`FONT_STACK` and `ASSET_URL` sit outside the palettes (neither is a
colour/shape token) and are spliced in at format time:
`QSS_TEMPLATE.format(font=FONT_STACK, assets=ASSET_URL, **TOKENS)`.

## `apply_theme` — one call, the whole application

```
apply_theme("light")
   │
   ├─ set_theme("light")            unknown name → DEFAULT_THEME + a warning
   │                                (a settings file may name a theme this
   │                                 version dropped; that is a boundary)
   ├─ app = QApplication.instance()
   │     None?  →  return           headless: guards, --selfcheck
   │
   ├─ app.setStyleSheet(qss())      ← THE APPLICATION, never a window:
   │                                  a per-widget sheet WINS over its
   │                                  parent's, so a window-level call would
   │                                  strand every dialog in the old palette
   │
   └─ for widget in app.allWidgets():
          ├─ QGraphicsDropShadowEffect?  → setColor(shadowRgba)
          │      (an effect holds a QColor it was handed ONCE)
          ├─ property("iconName")?       → setIcon(icon(name))
          │      (Qt bakes the tint into the SVG SOURCE — an old icon is a
          │       picture in the old ink, not a recolourable glyph)
          └─ update()                    → the custom-painted widgets repaint
```

## `qss()` — rule blocks, in file order

```
QSS_TEMPLATE
├─ QWidget                        base background/text/font
├─ QFrame#card                    the bento-card surface (surface1 + border + radiusCard)
├─ QLabel
│   ├─ (base) / #h1 / #caption / #section / #url
│   └─ #qr                        qrPaper — white in BOTH palettes
├─ QLabel#pill                    status pill shell (radius 999px, bold, 12px)
│   └─ [running] successDim/Edge · [starting] warningDim/Edge
│      [stopped] neutralDim       · [failed]   errorDim/Edge
├─ QPushButton
│   ├─ (base) / :hover / :pressed / :disabled
│   ├─ #primary                   accent→accentDark gradient, onAccent ink
│   └─ #danger                    dangerFill + dangerEdge
├─ QComboBox                      (base) / :hover / ::drop-down
│   ├─ ::down-arrow               image: assets/{caretAsset}.svg  ← a DRAWING.
│   │                             It was a CSS border triangle, which Qt's
│   │                             subcontrol renderer does not perform: a
│   │                             solid 10x10 BLOCK in every combo of every
│   │                             window, both palettes (sampled 2026-08-07)
│   └─ QAbstractItemView          popup list (accentDim selection)
├─ QCheckBox                      transparent label (never the window's surface0)
│   └─ ::indicator [+ :checked / :disabled]  accent fill + {checkAsset}.svg
├─ QLineEdit                      fieldFill + fieldEdge; :disabled keeps the
│                                 LINE and loses the fill (a value the user
│                                 must read is still a field)
├─ QGroupBox [+ ::title]          a real border in both palettes
├─ QListWidget, QTableWidget      surface1 card + border + gridline
│   └─ ::item:selected            accentDim + accent ink — OURS, not the
│                                 Windows system accent (gold on this PC)
├─ QHeaderView::section:horizontal
│                                 `:horizontal` is load-bearing — unqualified
│                                 it also sizes the HIDDEN vertical header and
│                                 Qt takes that as every ROW's floor (26 -> 39 px)
├─ QMenu                          ::item / ::item:selected
└─ QToolTip
```

## Helper functions (not QSS-expressible)

    color(value) -> QColor:
        "rgba(56, 189, 248, 0.16)"  →  QColor(56, 189, 248, 41)
        "#273449"                   →  QColor("#273449")
        anything else               →  TOKENS["text"] + a logged error
        # QColor CANNOT parse the rgba() form — it returns an INVALID colour,
        # which paints opaque BLACK. QSS parses those strings perfectly, so
        # the bug is invisible until a widget paints ITSELF: the Controls
        # editor's `required` tick boxes came out black in both palettes.
        # Every custom paintEvent reads tokens through this.

    card_shadow(widget):
        QGraphicsDropShadowEffect(blur=28, offset=(0,6),
                                  color=QColor(*shadowRgba.split(",")))

    repolish(widget):
        widget.style().unpolish(widget); widget.style().polish(widget)
        # forces Qt to re-evaluate dynamic-property selectors (pill state)

## What proves both palettes

`tests/test_layout_audit_qt.py` runs its WHOLE window registry under each
palette (`use_palette` sets `SETTINGS.ui_theme` too, because MainWindow
applies it in its own constructor) and writes a second screenshot per window
with a `__light` suffix. A light theme is not a repaint of a dark one: a
translucent white border vanishes on white, a 16 %-alpha wash reads as nothing
on a card, and an icon whose ink was baked in at build time turns invisible —
none of which a dark-only run can see.
