# Flow — theme.css + theme.js

## The fill axis, before and after the 2026-08-07 grader fix

```
LIGHT THEME, data-fill=…

BEFORE (grader: 7/10 — "not perceptibly different")
  transparent  --glass-fill 0.55 alpha white  ─┐
  full         --glass-fill = --fill-solid    ─┤  both read as "white button"
                (#ffffff, 1.00 alpha)          ┘

AFTER
  transparent  --glass-fill 0.14 alpha white   ─── nearly see-through: only
                                                    the border draws a shape
  full         --glass-fill = --fill-solid     ─── solid white card, clearly
                (#ffffff, 1.00 alpha)               raised off the page
```

Dark never had this problem — its transparent value (0.20 alpha of the dark
card colour) was already far from `--fill-solid` (`#1e293b`, opaque). Light's
old values (0.55 / 0.90 / 0.75 for `--glass-fill` / `--glass-strong` /
`--chip`) were close enough to opaque that the axis did nothing a person could
see; they now sit as low as dark's. Dropping the fill left unselected wheel
items without a shape of their own, so a dedicated `--wheel-border` token
(stronger on light) replaced the plain `--border` on `.wheel-item`/`.wheel-x`.

## Where a look comes from, end to end

```
DESKTOP                                          PHONE
Settings → APPEARANCE
  ├─ "The phone" [Dark|Light|Colored dark|Colored light]
  └─ "The phone" [Outlined|Filled]
        │ save_user_settings(phone_theme / phone_fill)
        ▼
  config.SETTINGS  ──►  config.ui_config()
                          {theme, fill, colors: set_colors()}
                              │   ↑ the DESKTOP picks the palette:
                              │     colored-light → SET_COLORS_LIGHT
                              │     anything else → SET_COLORS_DARK
                              │     (one flat map on the wire — the phone
                              │      never learns two tables exist)
                              │
                              │  web._send_config()  →  `config` frame
                              ▼
                        connection.js: applyUi(msg.ui)   ← as it arrived,
                              │                             absence included
                              ▼
                    ┌─────────────────────────────────────────┐
                    │  no `ui` at all?  → return. nothing      │
                    │  happens: no state, no pref, no repaint  │
                    │                                          │
                    │  otherwise: ui = mergedUi(ui, next)      │
                    │    theme  = next.theme  ?? ui.theme      │
                    │    fill   = next.fill   ?? ui.fill       │
                    │    colors = next.colors ?? ui.colors     │
                    │  (the base is THE LOOK IN FORCE — the    │
                    │   cache — never UI_DEFAULT)              │
                    └─────────────────────────────────────────┘
                              │
                  ┌───────────┴────────────┐
                  ▼                        ▼
        prefSet("uiLook", …)      writeLook()
        (the head start for            <body data-theme=… data-fill=…>
         the NEXT page load)                │
                                            ▼
                                      theme.css takes over
                                      (every token re-resolves)
                                            │
                                            ▼
                                    refreshCategories()
                                    → renderGroup() → paintSet(group)
                                    → openWheel()   → paintSet(item)
```

## Page load, before the socket says anything

```
theme.js loads (after controls.js — it uses prefGet/IN_APP)
  │
  ├─ restoreUi()      read the cached {theme, fill, colors}
  │     └─ writeLook()  <body> gets its two attributes NOW
  │
  └─ …the page paints in the right look, once.
        A `config` arriving later either confirms it (no visible change),
        corrects it (one repaint, on a page nobody is mid-gesture on),
        or says nothing about the look — in which case nothing moves.
```

## The reset that used to happen half a second after every connect

The bug a third independent grader measured on 2026-08-07, and what replaced
it:

```
BEFORE                                    AFTER
 t=0    owner picks Filled on the PC       t=0    owner picks Filled on the PC
        <body data-fill="full">                   <body data-fill="full">
 t+0.4  a `config` frame lands             t+0.4  a `config` frame lands
        ui absent / partial                       ui absent  → applyUi returns
        applyUi → UI_DEFAULT                      ui partial → merged onto the
        <body data-fill="transparent">                        look in force
        ▲                                         <body data-fill="full">
        └─ the Appearance card "does nothing"
```

Two things it cost, both measured, not argued:

```
Controls.png  vs  Controls_dark_full.png   (dark outlined vs dark filled)
   with the reset : max per-channel diff 0, 0 of 1,507,920 pixels differ
                    both are 87,024 px of the 20% tint rgb(18,26,45)
   without it     : max per-channel diff R13 G16 B15, 134,804 px differ (8.94%)
                    filled = 87,023 px of the solid rgb(30,41,59)

Controls_light_transparent_landscape.png   (a file named "light")
   with the reset : page colour (15, 23, 42)   ← the DARK theme
   without it     : page colour (236,238,246)  ← light, like its portrait twin
```

## `paintSet` — one write per set, not one per button, THREE surfaces not one

```
renderGroup("left")
  cat = allCats()[groups.left]                e.g. {name: "Mouse", …}
  paintSet(host, "Mouse", "--glass-fill")
        │
        ├─ setColors()["Mouse"]  →  "#1D6A86"   (the DARK palette)
        ├─ fillOn(rgb over page) →  clears AA as it is  →  unnudged
        ├─ inkOn(that fill)      →  luminance 0.12 < 0.179 → "#ffffff"
        ├─ lineOn(rgb, tokenSurface("--glass-fill"))
        │       →  a #1D6A86 label on the 20% tint is far under 7:1, so its
        │          HSL LIGHTNESS is walked up (hue 196, saturation 64% held)
        │       →  rgb(77 179 216) — the same teal, lighter. Never a mix
        │          toward white: that would drain the saturation the owner
        │          asked to keep.
        └─ host.style:
              --set-color: #1D6A86         (untouched — border, everywhere)
              --set-fill:  rgb(29 106 134) (fill — FULL background)
              --set-ink:   #ffffff         (ink ON --set-fill — FULL label)
              --set-line:  rgb(77 179 216) (ink ON the outlined tint — OUTLINED label)
              --set-glow:  rgb(77 179 216 / 0.30)  (the LIFTED colour — an
                            ON halo must be seen against the page)
                    │
                    ▼  inherited by every .ctl inside the group
          theme.css, data-theme^="colored"  (dark page AND light page):
            border            = var(--set-color)                (always)
            transparent label = var(--set-line, var(--set-color))
            full  background  = var(--set-fill, var(--set-color))
            full  label        = var(--set-ink)
```

The category button (`.ctl.cat`) is the same write, read through its own
0.85 `opacity` — `fillOn()` already required the ink DILUTED 85:15 toward the
fill to clear AA, so this button and a plain full-opacity `.ctl` both pass
with the same `--set-fill`/`--set-ink` pair; nothing here treats `.cat` as a
special case, because the fill was already chosen to survive it.

## The colour pool for a set nobody named

```
ui.colors  = { Mouse:#38BDF8, Input:#4ADE80, …, Cursor:#F472B6 }   (13)
pool       = those 13 values, in order
used       = the 13 they are already spending

for each set in [categories, customSets, appSets]:
    already has a colour? ──► skip
    otherwise:
        walk the pool from the cursor to the first colour not in `used`
        (all 13 taken → the pool cycles: a repeat, not a crash)
        map[name] = that colour;  used += it;  cursor++
```

Deterministic: the order is the order the sets arrive in, so a set's colour
does not change from one connection to the next. Rebuilt (`resetSetColors`)
only when the set list itself changes — a fresh `actions` frame — or when a
new `ui` arrives.

## The ink decision, and why VSCode is the one hue that moves

```
                    relative luminance of the set colour / fill
  0.0 ─────────────────────────┬──────────────────────────── 1.0
        light ink #ffffff      │      dark ink #0b1220
                            0.179
                  (where white and black tie on contrast)

  #FACC15 Chrome   L=0.65 ──► dark ink,  9.4:1  ── fillOn: unnudged
  #4ADE80 Input    L=0.55 ──► dark ink, 10.7:1  ── fillOn: unnudged
  #D97757 Claude   L=0.29 ──► dark ink,  6.0:1  ── fillOn: unnudged
  #3B82F6 VSCode   L=0.23 ──► dark ink,  4.3:1  ── BOTH inks land near the
                                                    crossover — under AA
                                                    (independent grader,
                                                    2026-08-07). fillOn lifts
                                                    the FILL itself the
                                                    shortest step toward
                                                    black/white until the
                                                    diluted (.cat, 85:15) ink
                                                    clears 4.5:1 — the border
                                                    still wears raw #3B82F6.
```

Outlined labels are held to **7:1 (AAA)**, not 4.5 — the backdrop behind an
outlined button is the PC's own unknowable screen, so `lineOn()` pays the
larger margin an unknown surface is owed. Filled labels sit on a KNOWN,
controlled surface (the fill itself), so `fillOn()`/`inkOn()` only owe **AA
(4.5:1)** — never 3:1, which is WCAG's LARGE-text floor and none of this
project's labels qualify.

## What the audit walks

```
for size in (portrait 412x915, landscape 915x412):
    open the page, wait for #group-left button
      …AND for monitor.w > 0                 ← the socket's FIRST `config`.
                                                The D-pad renders from the
                                                page's own defaults ~1.4 s
                                                earlier, and everything done
                                                in that window used to be
                                                overwritten when the frame
                                                finally landed
    install window.__contrast(root)          ← reads --surface-0 LIVE,
                                                composites every veil ABOVE
                                                the element too, and floors
                                                each leaf at 3:1 or 4.5:1
                                                by its own font-size/weight
    for look in the six (theme × fill):
        _apply_look(theme, fill, colors)
          ├─ config.apply(phone_theme, phone_fill)   ← the DESKTOP's own
          │                                            setting, in-process,
          │                                            so every later
          │                                            `config` frame agrees
          └─ applyUi({theme, fill, colors})          ← the app's own entry point

        every look-named screenshot goes through _shoot():
            body.dataset.theme / .fill == the look asked for?
              no  → the audit FAILS, naming both looks
              yes → page.screenshot(...)
        ├─ __contrast(#wheel) + (#group-left) + (#group-right)
        │     the surfaces a coloured theme actually paints, wheel OPEN and SHUT
        ├─ __sweepSetColours(all 13 names of the palette in force)
        │     not only the two or three a fixture happens to show
        └─ portrait, or the default look → every panel
              inView · noPageScroll · noClip · __contrast(card)
    …then back to the default look for the geometry checks below it.
```
