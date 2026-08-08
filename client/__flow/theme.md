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

## The axis correction, 2026-08-08 — one theme name split into two fields

```
BEFORE (build round R3, 2026-08-07)             AFTER (owner correction)

  phone_theme: "dark" | "light" |                phone_theme:   "dark" | "light"
               "colored" | "colored-light"       phone_colored: True | False
  phone_fill:  "transparent" | "full"            phone_fill:    "transparent" | "full"

  4 theme values x 2 fills = 8 looks              2 x 2 x 2 = 8 looks, SAME EIGHT,
  ("colored"/"colored-light" fold the             but colour is now the CONTROLS'
   colour question into the PAGE's theme)         own switch, not a page theme

  <body data-theme="colored-light"                <body data-theme="light"
        data-fill="full">                               data-colored="true"
                                                          data-fill="full">
```

His words: *"teme postoje samo dve, svetla i tamna … a ove komande … on može
da bude obojen, neobojen, i može da bude transparentan ili pun."* Same eight
renderings, correct model: two themes (the sun/moon switcher) and two
switches that belong to the D-pad groups and the radial wheel.

## The palette correction, the SAME DAY — two tables became one

```
BEFORE (owner-approved 2026-08-07)           AFTER (owner correction 2026-08-08)

  set_colors(theme):                           set_colors(theme):
    theme == "light" → SET_COLORS_LIGHT           `theme` accepted, IGNORED
    else              → SET_COLORS_DARK           → always SET_COLORS
                                                    (SET_COLORS_DARK/_LIGHT
                                                     kept as aliases of the
                                                     SAME dict — an old
                                                     import cannot resurrect
                                                     a second table)

  Mouse on the dark page:  #1D6A86             Mouse on the dark page:  #186B89
  Mouse on the light page: #186B89             Mouse on the light page: #186B89
```

His words: *"nema dve verzije za obojene setove. Oni ce uvijek imati ove
jake upecatljive boje. ono sto se menja su ostali elementi light ili dark
temi ali kontrole i setovi ce biti obojeni."* A set's colour is its
IDENTITY — it does not move when the sun/moon switch does; the theme moves
everything ELSE around it. This is a DIFFERENT correction from the axis one
above (that fixed how the look is SPELLED; this fixes what the coloured look
SHOWS), made the same day. The surviving table is the one he had tuned as
the classic strong ink (HSL lightness 26–54%, saturation capped at 72%) —
the `paintSet` walkthrough below uses its real values.

## Where a look comes from, end to end

```
DESKTOP                                          PHONE
Settings → APPEARANCE
  ├─ "The phone" [Dark|Light]
  ├─ "The phone" [Coloured|Plain]
  └─ "The phone" [Outlined|Filled]
        │ save_user_settings(phone_theme / phone_colored / phone_fill)
        ▼
  config.SETTINGS  ──►  config.ui_config()
                          {theme, colored, fill, colors: set_colors()}
                              │   ↑ ONE table, always (owner correction
                              │     2026-08-08 — the two-table split of a day
                              │     earlier is gone): set_colors(theme) takes
                              │     `theme` and IGNORES it, returning the same
                              │     SET_COLORS dict whichever theme, and
                              │     whichever `colored` state, is in force —
                              │     one flat map on the wire, the phone never
                              │     learns there used to be two tables
                              │
                              │  web._send_config()  →  `config` frame
                              ▼
                connection.js: applyUi(msg.ui)   ← as it arrived,
                              │                     absence included
                              ▼
                    ┌─────────────────────────────────────────┐
                    │  no `ui` at all?  → return. nothing      │
                    │  happens: no state, no pref, no repaint  │
                    │                                          │
                    │  otherwise: next = legacyTheme(msg.ui)   │
                    │             ui = mergedUi(ui, next)      │
                    │    theme   = next.theme   ?? ui.theme    │
                    │    colored = next.colored ?? ui.colored  │
                    │             (explicit-undefined check —  │
                    │              a boolean "false" is real)  │
                    │    fill    = next.fill    ?? ui.fill     │
                    │    colors  = next.colors  ?? ui.colors   │
                    │  (the base is THE LOOK IN FORCE — the    │
                    │   cache — never UI_DEFAULT)               │
                    └─────────────────────────────────────────┘
                              │
                  ┌───────────┴────────────┐
                  ▼                        ▼
        prefSet("uiLook", …)      writeLook()
        (the head start for            <body data-theme=…
         the NEXT page load)                  data-colored=…
                                               data-fill=…>
                                            │
                                            ▼
                                      theme.css takes over
                                      (every token re-resolves)
                                            │
                                            ▼
                                    refreshCategories()
                                    → renderGroup() → paintSet(group)
                                    → openWheel()   → paintSet(item)
```

## Backward compatibility — the OLD four-value `theme`, translated not reset

```
legacyTheme(next):
    next.theme == "colored"       → { ...next, theme:"dark",  colored: next.colored ?? true }
    next.theme == "colored-light" → { ...next, theme:"light", colored: next.colored ?? true }
    anything else                 → next, unchanged

Called from INSIDE mergedUi(), the single point every incoming `ui` object
passes through — so both paths that can still hand this file the old shape
go through the SAME translation:

  1. A server not yet rebuilt        →  msg.ui  (the `config` frame)
  2. THIS DEVICE'S OWN cache          →  prefGet("uiLook"), read by
     (written by an older page,          restoreUi() at load — BEFORE any
      before this build ever ran)        socket exists, so a server-side
                                          translation alone could never
                                          reach it
```

The server side of the same correction is `config._migrate_legacy_ui()` —
runs on every `load_user_settings()` AND on `save_user_settings()`'s own
re-read of the current file, so a `settings.json` written under the old model
self-heals on its very next save. Neither path resets the owner's choice —
"colored-light" meant light-page-with-colour, and that is exactly
`{theme:"light", colored:true}` spelled with two fields instead of one.

## Page load, before the socket says anything

```
theme.js loads (after controls.js — it uses prefGet/IN_APP)
  │
  ├─ restoreUi()      read the cached {theme, colored, fill, colors}
  │     └─ mergedUi(UI_DEFAULT, cached)  ← legacyTheme() runs here too
  │     └─ writeLook()  <body> gets its three attributes NOW
  │
  └─ …the page paints in the right look, once.
        A `config` arriving later either confirms it (no visible change),
        corrects it (one repaint, on a page nobody is mid-gesture on),
        or says nothing about the look — in which case nothing moves.
```

## The reset that used to happen half a second after every connect

The bug a third independent grader measured on 2026-08-07, and what replaced
it (unchanged by the 2026-08-08 axis correction — `colored` follows the exact
same ignore-or-merge rule `theme` and `fill` already had):

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
  paintSet(host, "Mouse", "--glass-fill")      (worked here for the DARK page
                                                — the light page starts the
                                                lineOn walk from ITS OWN
                                                --glass-fill surface, but from
                                                the exact same raw #186B89:
                                                one table, not two)
        │
        ├─ setColors()["Mouse"]  →  "#186B89"   (the ONE table, same on both
        │                                         themes since 2026-08-08;
        │                                         painted onto the element
        │                                         whether or not data-colored
        │                                         is true — theme.css only
        │                                         READS it under
        │                                         data-colored="true")
        ├─ fillOn(rgb over page) →  the diluted (.cat, 85:15) ink already
        │                            clears AA at 4.83:1  →  unnudged
        ├─ inkOn(that fill)      →  luminance 0.13 < 0.179 → "#ffffff"
        ├─ lineOn(rgb, tokenSurface("--glass-fill"))
        │       →  a #186B89 label on the dark page's 20% tint
        │          (rgb(18 27 45)) sits under 7:1, so its HSL LIGHTNESS is
        │          walked up (hue 196, saturation held) 14 steps
        │       →  rgb(62 179 221), 7.14:1. Never a mix toward white: that
        │          would drain the saturation the owner asked to keep.
        └─ host.style:
              --set-color: #186B89         (untouched — border, everywhere)
              --set-fill:  rgb(24 107 137) (fill — FULL background, unnudged)
              --set-ink:   #ffffff         (ink ON --set-fill — FULL label)
              --set-line:  rgb(62 179 221) (ink ON the outlined tint — OUTLINED label)
              --set-glow:  rgb(62 179 221 / 0.30)  (the LIFTED colour — an
                            ON halo must be seen against the page)
                    │
                    ▼  inherited by every .ctl inside the group
          theme.css, data-colored="true"  (whichever theme is in force):
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
    for look in the eight (theme x colored x fill):
        _apply_look(theme, colored, fill)
          ├─ config.apply(phone_theme, phone_colored, phone_fill)
          │      ← the DESKTOP's own setting, in-process, so every later
          │        `config` frame agrees
          └─ applyUi({theme, colored, fill, colors})  ← the app's own entry point

        every look-named screenshot goes through _shoot():
            body.dataset.theme / .colored / .fill == the look asked for?
              no  → the audit FAILS, naming both looks
              yes → page.screenshot(...)
        ├─ __contrast(#wheel) + (#group-left) + (#group-right)
        │     the surfaces a coloured look actually paints, wheel OPEN and SHUT
        ├─ __sweepSetColours(all 13 names of the palette in force)
        │     not only the two or three a fixture happens to show
        └─ portrait, or the default look → every panel
              inView · noPageScroll · noClip · __contrast(card)
    …then back to the default look for the geometry checks below it.
```
