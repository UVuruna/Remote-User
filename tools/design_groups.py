"""THE CATALOGUE — every tunable design value, in the words of what it does.

Split out of `tools/design_tokens.py` on 2026-08-19 (owner round 2). That file
is the ENGINE — where a value lives, how it is read, how it is written back —
and this one is the VOCABULARY: which knobs exist, in which group, and what
each one is FOR. Two different questions, two files, and neither is now within
sight of the structure wall.

THE OWNER'S ROUND-2 SENTENCE IS THE SPEC OF THIS FILE:

<!-- lang-ok-begin: the owner's own words, kept because they name the deliverable -->
    "Najvaznije lepse opise i pa cak i ako treba sa slicicom nekom ovaj levi
     panel koji definise sta radi koji setting. Nisam mogao da nadjem gde se
     podesava SHADOW COLOR koji je WHITE za BLACK LETTERS i BLACK LOGO kojih
     ima u 2 seta (Input i Claude Tools)"
<!-- lang-ok-end -->

Two failures in one sentence, and both are answered here rather than in the
page's CSS:

  1. A KNOB WITH NO SENTENCE IS A KNOB NOBODY TURNS. Every row carries `help`:
     one plain sentence saying what the number does and where on the phone it
     is seen. Not the token's name reworded — the token's name is already on
     the row and it is not an explanation.
  2. A VALUE THAT IS NOT IN THE LIST CANNOT BE FOUND, however carefully the
     list is grouped. The white shadow he went looking for lives in TWO
     places, and the first version of this file offered neither as a colour:
     `SHADOW_LIGHT` in client/theme.js (the coloured looks, decided per
     button) and `--ink-shadow` / `--lbl-shadow` in client/theme.css (the
     plain looks, decided per theme). Both are rows now, at the top of the
     group that owns the question.

THREE THINGS EVERY ROW CARRIES, and each is one way "what does this do" is
answered without reading the source:

  help — the sentence.
  pic  — the id of a mini diagram the page draws beside it (tools/design_pics.js).
         A number that means "how round", "how far apart" or "how big a halo"
         is a picture before it is a word.
  demo — a CSS selector INSIDE the specimen board (tools/preview.html). Hover
         the row and every element the value reaches is outlined in all eight
         frames at once. This is the answer to "which setting is this?" that
         no amount of prose gives: the page points at it.

A DEMO IS A PROMISE, so a row whose value nothing on the bench draws carries
NO demo and says where it is drawn instead. An independent grader found five
rows pointing at elements that never read their token — a pointer that lands
on the wrong thing is worse than no pointer, because it is believed.
"""

from __future__ import annotations

# ═══════════════════════════ WHAT A GATE PINS ═══════════════════════════
# token -> the sentence shown beside it in the page, and again in the save
# report. Naming the gate is the point: he should know before he drags the
# slider that a test is going to have an opinion.
PINNED = {
    "--ink-shadow": "tests/test_ink_shadow.py — his 2026-08-15 strength, and "
                    "the colour must stay the DARK theme's opposite ink",
    "--lbl-shadow": "tests/test_ink_shadow.py — his 2026-08-15 strength, and "
                    "the colour must stay the DARK theme's opposite ink",
    "--ink-shadow-x": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--ink-shadow-y": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--ink-shadow-blur": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--lbl-shadow-x": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--lbl-shadow-y": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "--lbl-shadow-blur": "tests/test_ink_shadow.py — his 0 / 1px, 1px blur (2026-08-15)",
    "SHADOW_DARK": "tests/test_ink_shadow.py — it must stay DARKER than the "
                   "0.179 crossover, or the shadow stops being the ink's opposite",
    "SHADOW_LIGHT": "tests/test_ink_shadow.py — it must stay LIGHTER than the "
                    "0.179 crossover, or the shadow stops being the ink's opposite",
    "--warning": "tests/test_layout_audit.py — 4.5:1 under the status pill's ink",
    "--error": "tests/test_layout_audit.py — #ef4444 measured 3.45:1 here (2026-08-08)",
    "--on-warning": "tests/test_layout_audit.py — the ink belongs to the fill",
    "--on-error": "tests/test_layout_audit.py — the ink belongs to the fill",
    "--ledger-yellow": "the 2026-08-17 grader — must not read as a shade of --warning",
    "--fill-solid": "his choice of 2026-08-08 — the fill axis must be VISIBLE",
}
# Every set colour answers to the same sweep, so the note is one sentence.
SET_PIN = ("tests/test_layout_audit.py — the contrast sweep, both themes, both "
           "fills · saturation <= 72%, lightness 26-54%")

# Said once, on the four rows it is true of. The coloured looks re-point these
# two variables per button (client/theme.css → `body[data-colored="true"]`), so
# what a plain-look row moves is the plain looks.
PLAIN_ONLY = ("The PLAIN looks only — a coloured control computes its own "
              "shadow per button from the two colours at the top of this group.")


# ═══════════════════════════ THE GROUPS ═══════════════════════════
# The order they appear in the page. A group is a JOB, not a file: what the
# page is made of, what the ink is, what a switched-on button does — so a
# question like "the ON ring is too tight" lands in one place, with the colour
# and the geometry of that ring side by side, however far apart the two live
# on disk.
#
# kinds:
#   theme   — one colour token, TWO values (dark + light), edited together
#   shape   — one number in client/style.css, with the range its slider spans
#   shadow  — a colour token that is ALSO a strength: the hue per theme and one
#             strength slider that lands in three places (both themes and the
#             JS constant the coloured looks compute with). It replaced an
#             "alpha" kind that offered the strength alone, which is how half
#             of his own question stayed unanswerable for a round.
#   jscolor — a COLOUR that is a rule in code (client/theme.js), one value for
#             both themes because the rule does not know about themes
#   derived — shown, never edited: the file computes it from another token
#   sets    — the whole set palette, one swatch per shipped set
GROUPS = [
    {
        "id": "shadows",
        "title": "Shadows — under the icon and the label",
        "note": "A control floats over whatever the PC is showing — a white "
                "document, a black editor, a photograph — so the icon and the "
                "label carry a shadow to keep their shape. THE COLOUR IS A "
                "RULE: it is always the opposite of the ink it sits under. It "
                "is decided in two different places, and both are here. On a "
                "COLOURED control it is decided PER BUTTON while it is painted "
                "(the first two rows); on a plain one the ink is simply the "
                "theme's, so the answer is one colour per theme (the two rows "
                "after them). A switched-on button draws NO shadow at all — "
                "its face is a known, opaque surface, so there is nothing to "
                "lift the ink off.",
        "rows": [
            {"kind": "jscolor", "token": "SHADOW_LIGHT",
             "label": "COLOURED controls · shadow under BLACK letters",
             "help": "The WHITE one. A coloured button whose ink came out "
                     "black gets this under it — hover the row and every such "
                     "specimen is outlined in whichever look is on screen. "
                     "Which sets those are depends on the LOOK, not on a list: "
                     "in the FULL fill it is the light colours (Attach, "
                     "Chrome, Explorer, Claude Tools today), and in the "
                     "OUTLINED fill on the light page it is very nearly all of "
                     "them, because there every set's ink is walked dark.",
             "pic": "shadow-light", "demo": ":dark-ink"},
            {"kind": "jscolor", "token": "SHADOW_DARK",
             "label": "COLOURED controls · shadow under WHITE letters",
             "help": "The BLACK one, and what almost everything wears: on the "
                     "dark page a set's ink is its own colour lifted PALE, so "
                     "a black shadow sits under it. Switch the frames to "
                     "light + coloured + outlined and this row goes quiet — "
                     "there nearly every set takes the white one above.",
             "pic": "shadow-dark", "demo": ":light-ink"},
            {"kind": "shadow", "token": "--ink-shadow",
             "label": "PLAIN controls · icon shadow",
             "help": "The colour and the strength of the shadow under the "
                     "ICON when the controls are not coloured — black on the "
                     "dark page, white on the light one, because that is where "
                     "the ink is. " + PLAIN_ONLY + " The strength is one knob "
                     "and three writes: both themes and the constant "
                     "client/theme.js computes the coloured looks with.",
             "pic": "shadow-dark", "demo": ".ctl svg",
             "min": 0, "max": 1, "step": 0.05},
            {"kind": "shadow", "token": "--lbl-shadow",
             "label": "PLAIN controls · label shadow",
             "help": "The same for the small word under the icon. It is "
                     "stronger than the icon's because a 9 px label is the "
                     "thing that has to stay readable. " + PLAIN_ONLY,
             "pic": "shadow-dark", "demo": ".ctl .lbl",
             "min": 0, "max": 1, "step": 0.05},
            {"kind": "shape", "token": "--ink-shadow-x", "label": "Icon shadow — sideways",
             "help": "How far right the icon's shadow is offset, in every "
                     "look. 0 keeps it straight under the shape.",
             "pic": "shift-x", "demo": ".ctl svg",
             "min": -4, "max": 4, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ink-shadow-y", "label": "Icon shadow — down",
             "help": "How far down the icon's shadow is offset. 1 px is a lift "
                     "off the screen; more starts to read as a drop shadow.",
             "pic": "shift-y", "demo": ".ctl svg",
             "min": -4, "max": 4, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ink-shadow-blur", "label": "Icon shadow — softness",
             "help": "How soft the icon's shadow edge is. Past about 2 px it "
                     "stops being a lift and starts being a glow — it was a "
                     "2 px blur that made his first report.",
             "pic": "blur", "demo": ".ctl svg",
             "min": 0, "max": 12, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--lbl-shadow-x", "label": "Label shadow — sideways",
             "help": "The same offset for the label's shadow.",
             "pic": "shift-x", "demo": ".ctl .lbl",
             "min": -4, "max": 4, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--lbl-shadow-y", "label": "Label shadow — down",
             "help": "The same offset for the label's shadow.",
             "pic": "shift-y", "demo": ".ctl .lbl",
             "min": -4, "max": 4, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--lbl-shadow-blur", "label": "Label shadow — softness",
             "help": "How soft the label's shadow edge is. On a 9 px word this "
                     "is the number that decides between crisp and smudged.",
             "pic": "blur", "demo": ".ctl .lbl",
             "min": 0, "max": 12, "step": 1, "unit": "px"},
        ],
    },
    {
        "id": "shape",
        "title": "Control shape — the button itself",
        "note": "One button: how big, how round, how large its icon, how much "
                "room its word may take. A label that wraps onto a second line "
                "is correct — nothing readable is ever cut off — so widen the "
                "label before shrinking the text.",
        "rows": [
            {"kind": "shape", "token": "--corner", "label": "Button size",
             "help": "The width and height of one control — and the page's "
                     "whole measuring stick, not just a button's: the two top "
                     "corner buttons, the D-pad's entire footprint, the layout "
                     "bar's margins and the floor every floating notice starts "
                     "below are all counted in it. This slider moves the page.",
             "pic": "size", "demo": ".ctl",
             "min": 36, "max": 96, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-radius", "label": "Corner radius",
             "help": "How round the four corners are. 0 is a square, half the "
                     "button size is a circle.",
             "pic": "radius", "demo": ".ctl",
             "min": 0, "max": 40, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-icon", "label": "Icon size",
             "help": "The drawn symbol inside the button — the mouse, the "
                     "microphone, the arrows.",
             "pic": "icon", "demo": ".ctl svg",
             "min": 10, "max": 44, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-gap", "label": "Icon to label",
             "help": "The air between the symbol and the word under it.",
             "pic": "gap", "demo": ".ctl .lbl",
             "min": 0, "max": 12, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-label", "label": "Label text size",
             "help": "How big the word under the icon is. This is the smallest "
                     "text the phone shows, so it is the one to raise first if "
                     "anything is hard to read.",
             "pic": "label", "demo": ".ctl .lbl",
             "min": 6, "max": 18, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-label-max", "label": "Label width",
             "help": "How wide the word may run before it wraps onto a second "
                     "line. Wider means fewer wraps and a broader button row.",
             "pic": "width", "demo": ".ctl .lbl",
             "min": 30, "max": 120, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--ctl-label-text", "label": "Chord button text",
             "help": "A key combination — Ctrl+Shift+P — has no icon, so its "
                     "text IS the whole face of the button and gets its own "
                     "size. Watch the chord specimen while you move it: too "
                     "large and a long combination breaks mid-word.",
             "pic": "label", "demo": ".ctl.text",
             "min": 8, "max": 24, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--cat-size", "label": "Set switcher — size",
             "help": "The smaller dashed button that jumps to another set. It "
                     "is deliberately not a full control: it does not do "
                     "anything to the PC.",
             "pic": "size", "demo": ".ctl.cat",
             "min": 24, "max": 72, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--cat-radius", "label": "Set switcher — radius",
             "help": "How round that smaller button's corners are.",
             "pic": "radius", "demo": ".ctl.cat",
             "min": 0, "max": 36, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--cat-icon", "label": "Set switcher — icon",
             "help": "The symbol inside the set switcher.",
             "pic": "icon", "demo": ".ctl.cat svg",
             "min": 8, "max": 32, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--cat-label", "label": "Set switcher — label",
             "help": "The set's name on that smaller button.",
             "pic": "label", "demo": ".ctl.cat .lbl",
             "min": 6, "max": 16, "step": 1, "unit": "px"},
            {"kind": "theme", "token": "--glass-fill", "label": "Button face — OUTLINED look",
             "help": "What fills a control when the look is outlined: a faint "
                     "tint, so the PC's screen shows through. In the FULL look "
                     "this token is re-pointed at the solid fill below, which "
                     "is why the outlined swatch stops mattering there.",
             "pic": "swatch", "demo": ".ctl"},
            {"kind": "theme", "token": "--fill-solid", "label": "Button face — FULL look",
             "help": "What an uncoloured control is filled with in the FULL "
                     "look. It reaches further than the button: the panel "
                     "chips and the wheel circles are re-pointed at it too, so "
                     "the whole page reads as filled and not just the D-pad.",
             "pic": "swatch", "demo": ".ctl"},
        ],
    },
    {
        "id": "on",
        "title": "ON state — a switch that is switched on",
        "note": "Keys held, scroll locked, dictation running. It is a "
                "LUMINANCE event and not a hue (his report of 2026-08-09): the "
                "face flips to the far end of the theme's range, so it reads "
                "as ON over any picture the PC happens to be showing. The ring "
                "around it is three stops — face, gap, ring — and it inverts "
                "with the page: bright-dark-bright on the dark one, "
                "dark-bright-dark on the light one.",
        "rows": [
            {"kind": "theme", "token": "--on-face", "label": "Flipped face",
             "help": "What the button's face becomes when it is on: near-white "
                     "on the dark page, near-black on the light one. The ring's "
                     "outer stop is drawn in this colour too.",
             "pic": "swatch", "demo": ".ctl.active"},
            {"kind": "theme", "token": "--on-face-ink", "label": "Ink on that face",
             "help": "The icon and the word once the face has flipped — the "
                     "opposite of the face, or the button says nothing.",
             "pic": "ink", "demo": ".ctl.active svg, .ctl.active .lbl"},
            {"kind": "theme", "token": "--on-glow", "label": "Glow colour",
             "help": "The halo around a switched-on button. It is what makes "
                     "ON visible from the corner of the eye.",
             "pic": "glow", "demo": ".ctl.active"},
            {"kind": "derived", "token": "--on-gap", "label": "Ring gap colour",
             "help": "The separating line between the flipped face and the "
                     "ring. Not editable: it is always the page's own floor, "
                     "so it is the dark stop on the dark page and the light "
                     "one on the light page — and that inversion is what makes "
                     "the ring read over any picture behind it.",
             "pic": "ring", "demo": ".ctl.active",
             "why": "always the page floor — the gap is what makes the ring "
                    "read over any picture the PC happens to be showing"},
            {"kind": "shape", "token": "--on-border", "label": "Border width",
             "help": "The button's own edge while it is on.",
             "pic": "edge", "demo": ".ctl.active",
             "min": 1, "max": 6, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--on-ring-gap", "label": "Ring — the gap stop",
             "help": "How thick the separating line around the face is.",
             "pic": "ring", "demo": ".ctl.active",
             "min": 0, "max": 8, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--on-ring-face", "label": "Ring — the outer stop",
             "help": "How far the ring itself reaches, measured from the "
                     "button's edge outwards.",
             "pic": "ring", "demo": ".ctl.active",
             "min": 0, "max": 14, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--on-glow-blur", "label": "Glow size",
             "help": "How far the halo spreads. Large values bleed into the "
                     "neighbouring buttons.",
             "pic": "glow", "demo": ".ctl.active",
             "min": 0, "max": 48, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--on-scale", "label": "Grows by",
             "help": "How much bigger the button gets when it is on. 1.00 is "
                     "no change; 1.06 is the six percent it grows today.",
             "pic": "scale", "demo": ".ctl.active",
             "min": 0.9, "max": 1.3, "step": 0.01, "unit": ""},
        ],
    },
    {
        "id": "held",
        "title": "Pressed — a finger on the button right now",
        "note": "The moment of touch, and nothing more: it lasts as long as "
                "the finger does. It must never be mistakable for the ON "
                "state, which is why this one stays a hue and shrinks INWARD "
                "while that one flips its face and grows. THE TWO SIZES BELOW "
                "MOVE THE PLAIN LOOKS ONLY — a coloured control's press is "
                "drawn by a rule of its own in client/theme.css that outranks "
                "them and carries its own 3 px ring and 22 px halo.",
        "rows": [
            {"kind": "theme", "token": "--accent-glow", "label": "Halo colour",
             "help": "The colour of the halo under the finger on a plain "
                     "control (a coloured one uses its set's own). The same "
                     "colour marks a focused field elsewhere on the page.",
             "pic": "glow", "demo": ".ctl.held"},
            {"kind": "shape", "token": "--held-ring", "label": "Ring",
             "help": "How thick the ring drawn while the finger is down is. "
                     "Plain looks only — see the note above.",
             "pic": "ring", "demo": ".ctl.held",
             "min": 0, "max": 8, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--held-glow", "label": "Glow size",
             "help": "How far the halo under the finger spreads. Plain looks "
                     "only — see the note above.",
             "pic": "glow", "demo": ".ctl.held",
             "min": 0, "max": 48, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--held-scale", "label": "Shrinks to",
             "help": "How far the button presses in. Below 1 it goes inward, "
                     "which is what makes it feel like a button.",
             "pic": "scale", "demo": ".ctl.held",
             "min": 0.8, "max": 1.1, "step": 0.01, "unit": ""},
            {"kind": "shape", "token": "--held-on-scale", "label": "Shrinks to, when also ON",
             "help": "The same, for a button that is already switched on — it "
                     "starts from bigger, so it presses to a different size.",
             "pic": "scale", "demo": ".ctl.active.held",
             "min": 0.8, "max": 1.1, "step": 0.01, "unit": ""},
        ],
    },
    {
        "id": "sets",
        "title": "Set palette — one colour per set",
        "note": "Mouse, Claude, Attach, Input… Each set owns one colour: the "
                "button's OUTLINE when the controls are outlined, its FILL "
                "when they are full. ONE table for both themes (his decision "
                "of 2026-08-08) — a set's colour is its identity, and an "
                "identity that changes with the sun/moon switch is not one. "
                "Every ink on top is computed from the colour you choose, so "
                "no colour here can make a label unreadable: a light colour "
                "simply gets black letters, and with them the white shadow at "
                "the top of this list.",
        "rows": [{"kind": "sets", "pic": "sets", "demo": ".ctl.cat",
                  "label": "The shipped sets",
                  "help": "One swatch per set. The wall at the bottom of every "
                          "frame shows all of them at once, in the look you "
                          "have chosen — which is where you see which ones "
                          "come out with black letters."}],
    },
    {
        "id": "surfaces",
        "title": "Surfaces — what the page is made of",
        "note": "Every one of these is a background something else is later "
                "read against, so a move here moves contrast everywhere. Set "
                "the frames' backdrop to a white document or a busy window "
                "before judging any of them. The two BUTTON faces are not "
                "here — they live with the button, in Control shape.",
        "rows": [
            {"kind": "theme", "token": "--surface-0", "label": "Page floor",
             "help": "The page behind everything, seen wherever the PC's own "
                     "screen is not. The ON ring's gap is this colour too.",
             "pic": "swatch", "demo": "body"},
            {"kind": "theme", "token": "--card", "label": "Panel card",
             "help": "The surface a chooser, a setting, a notice or the "
                     "ledger is drawn on.",
             "pic": "swatch", "demo": ".sets-card"},
            {"kind": "theme", "token": "--card-shadow", "label": "Card elevation",
             "help": "The soft shadow that lifts that card off the page. The "
                     "only shadow on this page that is about DEPTH rather than "
                     "about keeping ink legible, which is why it is here and "
                     "not in the Shadows group.",
             "pic": "shadow-dark", "demo": ".sets-card"},
            {"kind": "theme", "token": "--glass-strong", "label": "Wheel circle face",
             "help": "The fill of one circle in the ring of sets, in the "
                     "outlined look. In the FULL look the circles take the "
                     "solid fill instead.",
             "pic": "swatch", "demo": ".wheel-item"},
            {"kind": "theme", "token": "--border", "label": "Edge",
             "help": "The line around a control, a card and a chip.",
             "pic": "edge", "demo": ".ctl"},
            {"kind": "theme", "token": "--wheel-border", "label": "Edge, wheel circle",
             "help": "The line around one circle in the ring of sets.",
             "pic": "edge", "demo": ".wheel-item"},
            {"kind": "theme", "token": "--chip", "label": "Chip / input / list row",
             "help": "The small surfaces inside a panel — a text field, a row "
                     "in the layouts list, a chip. Not on this bench: they are "
                     "drawn in the layouts and ledger panels.",
             "pic": "swatch"},
            {"kind": "theme", "token": "--chip-2", "label": "Chip, second shade",
             "help": "The alternate chip shade, for a row that has to be told "
                     "apart from the one above it. Not on this bench either.",
             "pic": "swatch"},
            {"kind": "theme", "token": "--bar", "label": "Floating bar / banner",
             "help": "The strip the layout bar and the update banner sit on. "
                     "Not on this bench.",
             "pic": "swatch"},
            {"kind": "theme", "token": "--scrim", "label": "Modal backdrop",
             "help": "The dimming laid over the page while a panel is open. "
                     "Not on this bench — it covers the whole screen when it "
                     "is there at all.",
             "pic": "swatch"},
            {"kind": "theme", "token": "--scrim-soft", "label": "Wheel backdrop",
             "help": "The lighter dimming while the ring of sets is open — "
                     "lighter because the wheel is a glance, not a decision. "
                     "Not on this bench.",
             "pic": "swatch"},
            {"kind": "theme", "token": "--dim-out", "label": "Outside a region grab",
             "help": "What covers the part of the screen you are NOT selecting "
                     "while dragging out a region. Not on this bench.",
             "pic": "swatch"},
            {"kind": "theme", "token": "--opaque", "label": "Layout-building overlay",
             "help": "The full-screen cover shown while the PC arranges the "
                     "windows of a layout — the whole screen becomes that "
                     "animation. Not on this bench.",
             "pic": "swatch"},
        ],
    },
    {
        "id": "ink",
        "title": "Ink — the text itself",
        "note": "The colours letters are drawn in. An `--on-…` token is the "
                "ink ON a coloured fill and never a page ink: amber wants dark "
                "letters and red wants light ones, whichever theme is on, so "
                "they are their own values rather than a theme's.",
        "rows": [
            {"kind": "theme", "token": "--text-primary", "label": "Primary text",
             "help": "Everything you are meant to read: labels, titles, list "
                     "rows, the ledger's lines.",
             "pic": "ink", "demo": ".ctl .lbl, .ldg-line span"},
            {"kind": "theme", "token": "--text-secondary", "label": "Secondary text",
             "help": "The quieter second line — a hint, a caption, a state "
                     "word beside a row. Not on this bench: every caption you "
                     "can see on the board belongs to the bench itself.",
             "pic": "ink"},
            {"kind": "theme", "token": "--on-accent", "label": "Ink on the accent colour",
             "help": "Letters drawn on an accent-filled surface — the "
                     "connected pill, the setup wizard's primary button. Set "
                     "the Toast to `connected` to see it (it fades out by "
                     "design, so it is a colour more than a specimen).",
             "pic": "ink", "demo": "#status"},
            {"kind": "theme", "token": "--on-warning", "label": "Ink on amber",
             "help": "Letters on the amber warning pill. Set the Toast to "
                     "`connecting`.",
             "pic": "ink", "demo": "#status"},
            {"kind": "theme", "token": "--on-error", "label": "Ink on red",
             "help": "Letters on the red error pill — the one that says a "
                     "layout was refused. That is the Toast's default.",
             "pic": "ink", "demo": "#status"},
        ],
    },
    {
        "id": "accent",
        "title": "Accent — the one colour the page uses for itself",
        "note": "Selection, focus, the current circle in the wheel, a pressed "
                "plain control. It belongs to the PAGE, not to any set: a "
                "set's own colour comes from the palette further up. The halo "
                "it throws is tuned with the press, in the Pressed group.",
        "rows": [
            {"kind": "theme", "token": "--accent", "label": "Accent",
             "help": "The colour of the current circle in the wheel, a chosen "
                     "row's edge and hint, a focused field, and the ledger's "
                     "'done' dot.",
             "pic": "swatch",
             "demo": ".wheel-item.current, .sets-row.chosen, .ldg-blue"},
            {"kind": "theme", "token": "--accent-2", "label": "Accent, gradient end",
             "help": "The second stop where the accent is drawn as a gradient "
                     "rather than a flat colour — the connected pill and the "
                     "setup wizard's primary button, and nothing else.",
             "pic": "swatch", "demo": "#status"},
            {"kind": "theme", "token": "--accent-wash", "label": "Accent wash",
             "help": "The very faint accent tint used as a FILL: the region "
                     "rectangle you drag out, the aspect box, a chosen quality "
                     "segment. Not on this bench.",
             "pic": "swatch"},
        ],
    },
    {
        "id": "status",
        "title": "Status colours — what the phone tells you",
        "note": "The pill along the top and the dots in the ledger. This is "
                "semantic colour: it is the only thing that ever says a layout "
                "was refused or a window is gone, so every one of these "
                "carries a 4.5:1 floor against the ink on it (rules/DESIGN.md).",
        "rows": [
            {"kind": "theme", "token": "--success", "label": "Success",
             "help": "Connected, done, proven — the ledger's green dot.",
             "pic": "dot", "demo": ".ldg-green"},
            {"kind": "theme", "token": "--warning", "label": "Warning",
             "help": "Connecting, waiting, something needs an answer — the "
                     "amber pill and the ledger's orange dot.",
             "pic": "dot", "demo": ".ldg-orange, #status"},
            {"kind": "theme", "token": "--warning-2", "label": "Warning, gradient end",
             "help": "The second stop of the amber pill's gradient. Set the "
                     "Toast to `connecting` to see it.",
             "pic": "swatch", "demo": "#status"},
            {"kind": "theme", "token": "--error", "label": "Error",
             "help": "Disconnected, refused, failed — the loudest thing the "
                     "page can say, and the ledger's red dot.",
             "pic": "dot", "demo": ".ldg-red, #status"},
            {"kind": "theme", "token": "--error-2", "label": "Error, gradient end",
             "help": "The second stop of the red pill's gradient.",
             "pic": "swatch", "demo": "#status"},
            {"kind": "theme", "token": "--ledger-yellow", "label": "Ledger — waiting for you",
             "help": "The dot beside a task that is waiting on a person. It "
                     "must not read as a shade of the amber warning above.",
             "pic": "dot", "demo": ".ldg-yellow"},
            {"kind": "theme", "token": "--success-dim", "label": "Setup step — done, fill",
             "help": "The pale green behind a completed step of the first-run "
                     "setup. Not on this bench.",
             "pic": "swatch"},
            {"kind": "theme", "token": "--success-edge", "label": "Setup step — done, edge",
             "help": "The line around that same badge. Not on this bench.",
             "pic": "edge"},
        ],
    },
    {
        "id": "wheel",
        "title": "Wheel — the ring of sets",
        "note": "The circle of sets that opens under a long press. Its "
                "DIAMETER is measured live (a multi-word set name grows every "
                "circle at once, so nothing is ever cut off); what is tunable "
                "here is what one circle is made of.",
        "rows": [
            {"kind": "shape", "token": "--wheel-icon", "label": "Icon size",
             "help": "The symbol inside one circle of the ring.",
             "pic": "icon", "demo": ".wheel-item svg",
             "min": 10, "max": 40, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--wheel-gap", "label": "Icon to label",
             "help": "The air between that symbol and the set's name.",
             "pic": "gap", "demo": ".wheel-label",
             "min": 0, "max": 14, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--wheel-label", "label": "Label size",
             "help": "How big the set's name is inside the circle. Raising it "
                     "widens every circle, because the ring is measured from "
                     "the longest name.",
             "pic": "label", "demo": ".wheel-label",
             "min": 8, "max": 20, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--wheel-ring", "label": "Current set — ring",
             "help": "The ring around the set you are in right now.",
             "pic": "ring", "demo": ".wheel-item.current",
             "min": 0, "max": 8, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--wheel-glow", "label": "Current set — glow",
             "help": "The halo around that same circle.",
             "pic": "glow", "demo": ".wheel-item.current",
             "min": 0, "max": 48, "step": 1, "unit": "px"},
        ],
    },
    {
        "id": "rhythm",
        "title": "Page rhythm — spacing and round ends",
        "note": "How far apart things stand, and how round the pill-shaped "
                "ones are. The two spaces are used everywhere, so a small move "
                "here is a large move on screen.",
        "rows": [
            {"kind": "shape", "token": "--space-s", "label": "Small space",
             "help": "The gap between neighbours — two buttons, an icon and "
                     "its text, a dot and its line.",
             "pic": "space", "demo": ".bench-row",
             "min": 0, "max": 32, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--space-m", "label": "Medium space",
             "help": "The gap between groups — a row of controls and the next "
                     "row, a card and the page edge.",
             "pic": "space", "demo": ".board",
             "min": 0, "max": 48, "step": 1, "unit": "px"},
            {"kind": "shape", "token": "--radius-pill", "label": "Pill radius",
             "help": "How round a pill-shaped thing is: the status toast, a "
                     "chip. A number far larger than the height simply means "
                     "'fully round'.",
             "pic": "pill", "demo": "#status",
             "min": 0, "max": 999, "step": 1, "unit": "px"},
            {"kind": "derived", "token": "--topbar", "label": "Top bar floor",
             "help": "Where the top band ends and a floating notice may start. "
                     "Not editable: it is computed from the two spaces, the "
                     "button size and the keyboard's own offset, so a notice "
                     "can never land on the layout arrows — and it moves by "
                     "itself when the soft keyboard opens.",
             "pic": "space", "demo": "#status",
             "why": "computed from the spaces, the button size and the "
                    "keyboard offset — a notice that started above it would "
                    "sit on the layout arrows"},
        ],
    },
]
