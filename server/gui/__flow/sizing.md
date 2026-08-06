# Sizing — Flow

**About:** [description](../__about/sizing.md)

## The settle, step by step

```
settle_minimum(window, floor, keep)
 │
 ├─ size := floor                     the window's own measured-strings estimate
 │                                    (_computed_minimum(): longest real row)
 └─ up to SETTLE_ROUNDS passes:
      ├─ window.setMinimumSize(size)  a dialog follows its minimum…
      ├─ window.resize(size)          …a window follows its size
      ├─ layout().activate()          lay out AT that width
      ├─ needs := required_size(window)
      │     ├─ hint   := window.minimumSizeHint()          width comes from here
      │     └─ height := max(hint.height(),                ← THE FIX
      │                      column.heightForWidth(content.width()) + chrome)
      ├─ grown := max(size, needs) componentwise
      └─ grown == size ? stop : size := grown              (converges in 2-3)

 ├─ window.setMinimumSize(size)       the DECLARED minimum the law asks for
 └─ window.resize(max(keep, size))    never shrink the owner's own window
                                      (skipped while maximized / full screen)
```

## Why the height line is the whole module

```
a column holding a WRAPPING label
 ├─ minimumSizeHint().height()   → the label at ONE line          ← the lie
 └─ heightForWidth(width)        → the label at THIS width        ← the truth

short by 48 px
 └─ Qt does not clip a short layout — it OVERLAPS it
      ├─ every widget still reports its full size   → size checks stay GREEN
      └─ the pairing link is drawn across the QR    → the owner's screenshot
```

## Who calls it, and when

```
MainWindow      __init__ (floor, keep = 0x0)     window is born
                showEvent (first show)           real metrics arrive
                _resettle()                      content changed since the
                                                 last measure — update button
                                                 appeared, notify caption grew
                                                 (skipped while in the tray:
                                                 a hidden window measures small)
ControlsEditor  showEvent (once)                 after the parent's QSS lands
TrafficWindow   showEvent (once)                 same, then resize to 760x520
```
