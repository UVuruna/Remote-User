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

## …and the other half: back onto the screen

```
clamp_to_screen(window)                    called where the geometry is FINAL
 │
 ├─ geo    := window.frameGeometry()       the TITLE BAR counts — it is what
 │                                         goes missing off the top edge
 ├─ screen := QGuiApplication.screenAt(geo.centre())  ← never QWidget.screen():
 │            or primaryScreen()              that binding crashes the Qt audit
 │            or return                       (dangling QScreen, access
 │                                             violation in the NEXT window)
 ├─ avail  := screen.availableGeometry()   not geometry — the taskbar is not
 │                                         readable screen
 ├─ x := min( max(geo.x, avail.x),  max(avail.x, avail.right - geo.w) )
 └─ y := min( max(geo.y, avail.y),  max(avail.y, avail.bottom - geo.h) )
       └─ the inner max is the tie-break for a window BIGGER than the screen:
          the TOP-LEFT stays reachable, because that is where the title bar
          and the first card are
```

```
why it is needed at all
 ├─ Qt places a child from the size it had BEFORE the show
 ├─ settle_minimum then GROWS it in place  → all growth on bottom + right
 └─ a parent sitting high on the screen    → the dialog's TOP is off-screen
                                              (owner's screenshot 2026-08-12)
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
                                                 NOT clamped — the owner placed
                                                 this window himself
ControlsEditor  showEvent (once)      settle → clamp_to_screen
TrafficWindow   showEvent (once)      settle → resize 760x560 → clamp_to_screen
SettingsWindow  showEvent (once)      settle, then singleShot _resettle
                _resettle()           settle → clamp_to_screen   ← geometry final
```
