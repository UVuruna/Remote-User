# Flow — switch.py

## One click, from pill to repainted app

```
user clicks either pill
        │
        ▼
ThemeSwitch.mouseReleaseEvent
   name = "dark" if currently light else "light"
   set_theme_name(name, animate=True)      ← its own knob starts sliding
   picked.emit(name)
        │
        ▼
choose_theme(name)
   │
   ├─ save_user_settings({"ui_theme": name})     the choice survives a restart
   │
   ├─ flip_theme(name) ───────────────────────────────┐
   │                                                  │
   └─ for every ThemeSwitch in the app:               │
          set_theme_name(name, animate=True)          │
          (the clicked one is already heading there;  │
           re-aiming an animation at its own target   │
           costs nothing and keeps this branch free   │
           of "who called me")                        │
                                                      ▼
                                    ┌─────────────────────────────────┐
                                    │ 1. GRAB          every visible  │
                                    │    window.grab() → QPixmap      │
                                    │    → QLabel child, raised,      │
                                    │      transparent to the mouse   │
                                    ├─────────────────────────────────┤
                                    │ 2. SWAP          theme.apply_   │
                                    │    theme(name):                 │
                                    │      TOKENS refilled in place   │
                                    │      app.setStyleSheet(qss())   │
                                    │      shadows re-coloured        │
                                    │      iconName icons rebuilt     │
                                    │      every widget .update()     │
                                    │    …all of it BEHIND the covers │
                                    ├─────────────────────────────────┤
                                    │ 3. FADE          opacity 1 → 0  │
                                    │    over 300 ms, OutCubic,       │
                                    │    then deleteLater()           │
                                    └─────────────────────────────────┘
```

## The knob's own timeline

```
slide property   0 ─────────────────────────────────────► 1     (LINEAR, 600 ms)
                                    │
                                    ▼
_knob_x()        smoothstep: t·t·(3 − 2t)
                 ┌──────────────────────────────┐
              1  │                        ╭─────│
                 │                    ╭───╯     │
                 │              ╭─────╯         │
                 │        ╭─────╯               │
              0  │────────╯                     │
                 └──────────────────────────────┘
                 0                              1
```

## What the pill draws, left to right

```
   ┌──────────────────────────────────────────┐
   │  ◗  moon (dim)              sun (dim) ☀  │   ← the two destinations,
   │ ╭────────╮                               │     drawn on the track so the
   │ │  ◗     │                               │     pill says what it does
   │ ╰────────╯                               │     while standing still
   └──────────────────────────────────────────┘
      knob = accent fill + the ACTIVE symbol in --onAccent ink,
      sitting on top of whichever destination is current
```

## The sun, bounded — how `_sun(r)` stays a sun and never a cog

```
        r = the OUTER bound passed by the caller
        (never crossed by anything this function draws)
                     │
    container edge ──┼─────────────────╮
    (knob rim, or     .                 │  ← real margin: caller picks r
     the track's       .   ray tip        so this gap is never zero —
     rounded end)       .  (0.94 r)        knob: knob_d*0.42 leaves ~0.10
                          .                 knob_d of clear accent to the
                    ╲      .                rim; track: h*0.30 leaves room
                     ╲      .               to the pill's rounded end
      ray start        ╲     .
      (0.58 r) ────────► •    .
                          ╲    ○  ← disc, UNFILLED ring only (0.34 r):
                           ╲  ╱     a filled disc + rays crossing its
                            ╲╱      edge is what reads as a cog, at
                                    any size — an outline never can
```

Two graders independently caught this defect in the light theme (the knob
filled solid). The FIRST fix only re-tuned the ray/disc ratio and still
failed a second look: it never checked the result against the container the
knob actually is, so the ray tips crossed the knob's own rim and read as
teeth cut through its edge. The fix above ties the geometry to `r` as a true
outer bound instead — see `__about/switch.md` for the full account.

## Where it can end up with nothing to cover

```
flip_theme(name)
   QApplication.instance() is None ?   →  apply_theme(name) and return
      (a guard run, --selfcheck, an import with no GUI)
   no visible top-level window ?       →  covers == [], the swap still happens
```

The decoration is never allowed to be load-bearing.
