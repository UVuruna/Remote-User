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

## Where it can end up with nothing to cover

```
flip_theme(name)
   QApplication.instance() is None ?   →  apply_theme(name) and return
      (a guard run, --selfcheck, an import with no GUI)
   no visible top-level window ?       →  covers == [], the swap still happens
```

The decoration is never allowed to be load-bearing.
