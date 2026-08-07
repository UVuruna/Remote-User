# switch.py — the sun/moon theme pill, and the cover it changes under

Build round **R3** (owner-approved 2026-08-07). Ported to Qt from the owner's
own PromptPainter switch (`Gadgets/PromptPainter/gui/switch.py`), keeping the
two things that make that one feel deliberate rather than jumpy.

## What is in it

| Name | What it is |
|---|---|
| `ThemeSwitch` | the pill widget: a track, a sliding knob, a moon on the left and a sun on the right |
| `flip_theme(name)` | change the palette under a snapshot of every open window |
| `choose_theme(name)` | what a click actually does: persist → flip → move every switch |
| `TRACK_W` / `TRACK_H` | the pill's size, imported by the two windows that MEASURE their minimum |

## The knob slides on a smoothstep over ~600 ms

Slow enough to read as a gesture, eased so it neither starts nor stops with a
jerk. The animation is driven **linearly** (`QPropertyAnimation` on a `slide`
property) and shaped in `_knob_x` with `t*t*(3-2t)`. Qt's easing enum has no
smoothstep, and a custom-curve callback is a per-frame trip into Python for a
curve that is three characters of arithmetic.

## The theme change itself is never SEEN

A live re-style puts every window through a repaint cascade — cards lose and
regain their shadow colour, item delegates re-measure, the traffic chart
repaints. Watching that happen looks like a bug.

So `flip_theme` grabs a picture of **every open top-level window** first, lays
each over its own window, changes the palette underneath, and fades the stale
pictures out over ~300 ms. The user sees one cross-fade.

The cover is a **child `QLabel` with a `QGraphicsOpacityEffect`**, deliberately
not a translucent frameless top-level: rules/GUI.md bans those (they take
move/resize away from DWM), and a child cannot fall out of sync with the
window it covers. It is `WA_TransparentForMouseEvents`, so a click during the
fade reaches the real control underneath, and it deletes itself when the
animation finishes.

If there is no window to cover — a headless guard run, the app starting up —
the palette simply changes. **The flip never depends on the decoration.**

## Two switches, one setting

One pill sits in the main window's top bar after the RUNNING pill; the other
is a row in Settings → APPEARANCE. Neither remembers a state of its own: both
are TOLD the current theme with `set_theme_name`, and both connect their
`picked` signal to `choose_theme`, which saves the setting, flips, and then
walks `QApplication.allWidgets()` moving every `ThemeSwitch` it finds.

A switch that remembered its own position would drift from its twin, and
"who called me" is not information either of them should have to carry. The
walk costs one pass over the widget list on a click the user makes a few times
a year.

## The sun and the moon are DRAWN

QPainter, never a font glyph — the same rule the phone's Move handle earned on
2026-08-05, when ✥ came out a blunt cross on the owner's device. The crescent
is a filled disc with a second disc painted over its edge in whatever the
crescent is sitting ON (the track, or the knob); a clip path per frame would
be the other way, and two ellipses read identically at this size.

### The sun read as a COG, twice, and why the second fix is different

Two independent graders caught the SAME defect in the light palette: the
active knob's sun, filled solid, read as "a solid blue disc with a hole in
the middle and short slots cut through its ring" — indistinguishable at a
glance from the real gear icon on the Settings button two rows below. The
first attempt (thinner rays, further out) did not survive a second look
because it tuned the ray/disc *ratio* without checking it against the
*container* — the knob call site passed a radius whose ray tips landed past
the knob's own edge, so the white rays crossed the blue knob's rim and read
as teeth cut through a disc, exactly the report's words.

`_sun(painter, centre, r, color)` now treats `r` as a true OUTER bound: every
proportion inside it (disc radius, ray start, ray end) is a fixed fraction of
`r`, so nothing it draws can reach past `r` itself. Two changes, not one:

1. **The disc is an unfilled ring**, never a filled blob. A filled disc plus
   rays crossing its silhouette is what a cog looks like, at any size, in any
   fill state — an outline never collapses into that reading.
2. **Every caller passes `r` verified against its own container**, with a
   real margin: the track's dim sun (`h * 0.30`, plenty of room against the
   pill's rounded end) and the knob's active sun (`knob_d * 0.42`, leaving
   ~0.10·knob_d — about 2 px at this pill's size — of solid accent between
   the last ray and the knob's own rim). That margin is exactly what the
   first fix never checked.

The moon keeps its filled crescent — a completely different silhouette from
a gear, so it never had this problem.

## Why it may carry a hard size

`sizeHint`/`minimumSizeHint` plus a Fixed size policy — **not**
`setFixedSize`, which `tests/test_layout_law.py` bans outright because it also
freezes text-bearing widgets. The pill carries no text, so a fixed size is
correct here; declaring it through the size hints keeps the ban meaningful.
`TRACK_W` is imported by `main_window.py` and `settings_window.py` so their
measured minimums can never drift from what is actually on the row.

## Colour tokens through `_token_color`

Read LIVE from `gui.theme.TOKENS`, never cached in a module constant — the
whole point of round R3. `rgba(r, g, b, a)` is parsed by hand because QColor
understands `#rrggbb` and CSS names but not the QSS `rgba()` form the tokens
use for translucent values.

## Related

- [theme.py](theme.md) — the two palettes and `apply_theme`
- [main_window.py](main_window.md) — the top-bar pill
- [settings_window.py](settings_window.md) — the APPEARANCE row
- [Flow](../__flow/switch.md)
