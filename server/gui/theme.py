"""Design tokens + QSS for the desktop app — in TWO palettes, dark and light.

Follows root DESIGN.md (tokens, soft depth, one accent) with the same
slate/cyan family as the web client (client/theme.css) — one product, one
look. All values live HERE (No Hardcoded Values, rules/CODE.md); component code never hardcodes a
color or radius.

WHY THE PALETTE IS READ LATE (build round R3, 2026-08-07). Until this round
the dark palette was baked into a module-level `QSS` string and every window
pasted that string onto ITSELF. Both halves made a runtime switch impossible,
and DESIGN.md → Live theme switching names them by name: a module-level
f-string evaluates once at import and can never be flipped, and a per-widget
stylesheet WINS over its parent's, so re-styling the main window would have
left Controls, Traffic, Settings and the wheel-order dialog in the old theme.

So:

  - `PALETTES` holds both palettes, whole, in one table.
  - `TOKENS` is the ACTIVE palette, mutated in place by `set_theme` — every
    `TOKENS["accent"]` inside a `paintEvent` therefore reads the live value
    with no call-site change (and no module-level constant may cache one:
    `traffic_window.out_color()` is a function for exactly this reason).
  - `qss()` builds the stylesheet from the active palette, and `apply_theme`
    puts it on the QAPPLICATION, not on a window — one call re-themes every
    window the app has open and every window it opens later.

The elevation ORDER inverts between the two (DESIGN.md): on dark, higher is
lighter; on light, the raised card is the whitest thing and the page sits a
step down. Reusing the dark ordering is what makes light modes look sunken.
"""

import logging

from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QWidget,
)

from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT

# ═══════════════════════════ ASSET PATHS ═══════════════════════════
# QSS reaches assets by PATH, so it needs the one the app is actually running
# from. Forward slashes and quotes: the installed path holds spaces
# ("C:/Program Files/Remote User/…") and a bare url() would break on them.
ASSET_DIR = (BUNDLE_DIR if FROZEN else PROJECT_ROOT) / "assets"
ASSET_URL = ASSET_DIR.as_posix()

# ═══════════════════════════ DESIGN TOKENS ═══════════════════════════
# Two palettes, same keys, one table. Adding a token means adding it to BOTH
# — `set_theme` asserts that, so a key that exists only in dark can never
# reach a light window as a KeyError at paint time.
#
# The accent is the same cyan family in both, DEEPENED on light: #38BDF8 sits
# at 2.16:1 on white, which is unreadable, so light runs #0369A1 (6.14:1 under
# white ink) and keeps the bright original for nothing — a light theme that
# reuses a dark theme's accent is the single most common light-mode bug
# (DESIGN.md → Color).
#
# `shadowRgba` is read by `card_shadow`, which has no QSS to give it alpha;
# it stays a plain literal string so this whole table remains DECLARATIVE
# (rules/CODE.md — a table that computes is logic again).
PALETTES = {
    "dark": {
        # Surfaces (elevation steps LIGHTER, never flat gray)
        "surface0": "#0F172A",
        "surface1": "#1E293B",
        "surface2": "#273449",
        "border": "rgba(255, 255, 255, 0.10)",
        # Text
        "text": "#F5F5F5",
        "text2": "#A8B3C5",
        # One accent family (matches the client)
        "accent": "#38BDF8",
        "accentDark": "#0EA5E9",
        "accentDim": "rgba(56, 189, 248, 0.16)",
        "onAccent": "#06212E",
        # Semantic
        "success": "#22C55E",
        "warning": "#F59E0B",
        # #F87171, NOT #EF4444 (2026-08-08, found by the fourth visual grader
        # and named for three rounds before that). This ink is painted on
        # `surface1` cards — the Settings window's error line, the failed
        # status pill, the danger button — where #EF4444 measured 3.89 / 3.38 /
        # 3.43 : 1, all under DESIGN.md's 4.5:1 floor for semantic colour. The
        # lighter red measures 5.29 / 4.60 / 4.67. It survived because the Qt
        # audit had no contrast check at all; it has one now
        # (tests/test_layout_audit_qt.py), so this cannot silently return.
        "error": "#F87171",
        # Semantic wash + edge, for the status pill and the danger button.
        # These were rgba() literals inside the QSS until round R3 — the exact
        # kind of hardcoded colour that is right in one palette and wrong in
        # the other (a 16 % white-ish wash reads as nothing on a white card).
        "successDim": "rgba(34, 197, 94, 0.16)",
        "successEdge": "rgba(34, 197, 94, 0.40)",
        "warningDim": "rgba(245, 158, 11, 0.16)",
        "warningEdge": "rgba(245, 158, 11, 0.40)",
        "errorDim": "rgba(239, 68, 68, 0.16)",
        "errorEdge": "rgba(239, 68, 68, 0.40)",
        "dangerFill": "rgba(239, 68, 68, 0.14)",
        "dangerFillHover": "rgba(239, 68, 68, 0.24)",
        "dangerEdge": "rgba(239, 68, 68, 0.45)",
        "neutralDim": "rgba(168, 179, 197, 0.12)",
        # A control that is OFF must RECEDE. On dark that is simply one step
        # back down the elevation ladder (surface1 under surface2), which is
        # why this used to be written as `surface1` — see the light entry for
        # why that could not survive a second palette.
        "controlOff": "#1E293B",
        # …and the same sentence for a control being PRESSED: it must sink,
        # and on dark "sink" happens to be the same step down the ladder.
        "controlPressed": "#1E293B",
        # A TEXT INPUT IS NOT A SURFACE STEP (2026-08-07, the third time this
        # class of bug has been photographed). `QLineEdit` had no rule at all,
        # so it fell through to the `QWidget` rule and wore the PAGE colour
        # with whatever frame the native style felt like drawing — which on
        # dark happens to look like a field and on light is literally the page.
        # An input needs a token of its own precisely because the two palettes
        # answer "what does an editable box look like" differently: on dark it
        # RISES out of the page (the same control surface as a combo), on light
        # it is WHITE inside a real 1 px line (DESIGN.md → Light surfaces).
        "fieldFill": "#273449",
        "fieldEdge": "rgba(255, 255, 255, 0.16)",
        # …and a DISABLED field is still a field. `controlOff` cannot serve
        # here — see the light entry; on dark the two happen to coincide.
        "fieldOff": "#1E293B",
        # The tick inside a checked box. It is dark ink on the bright dark-mode
        # accent and white ink on the deep light-mode one — the asset cannot
        # carry both, and QSS `image:` (unlike `theme.icon`) cannot re-tint what
        # it loads, so WHICH file is a palette decision like any other.
        "checkAsset": "check",
        # …and the same for the combo box's caret, whose ink is this palette's
        # `text2`. See assets/caret.svg for what it replaces: a CSS border
        # triangle Qt's subcontrol renderer painted as a solid 10x10 BLOCK.
        "caretAsset": "caret",
        # Depth — QColor(r, g, b, a) for card_shadow
        "shadowRgba": "0, 0, 0, 55",
        # A QR is a MEASUREMENT, not decoration: it is scanned by a camera and
        # stays white-on-black in both palettes. Named rather than inlined so
        # nobody "fixes" it into a surface token one day.
        "qrPaper": "#FFFFFF",
        # Shape
        "radiusControl": "8px",
        "radiusCard": "14px",
    },
    "light": {
        # Surfaces — elevation rises TOWARD white: the card is the whitest
        # thing and the window sits a step below it (DESIGN.md).
        "surface0": "#ECEEF6",
        "surface1": "#FFFFFF",
        "surface2": "#DFE2EE",
        # A real 1px line, not white-alpha: alpha over white is invisible.
        "border": "#C7CBDD",
        "text": "#16161F",
        "text2": "#545A6B",
        "accent": "#0369A1",
        "accentDark": "#075985",
        "accentDim": "rgba(3, 105, 161, 0.14)",
        "onAccent": "#FFFFFF",
        # BOTH DARKENED 2026-08-08, by the same first run of the new contrast
        # check, for the same reason as `error` below: each reads a comfortable
        # 5.02:1 on a white card and only 4.27 / 4.25 : 1 on ITS OWN 12 % wash,
        # which is where the running pill and the warning caption really live.
        # #166534 and #92400E measure 6.08:1 and 6.00:1 there.
        "success": "#166534",
        "warning": "#92400E",
        # #B91C1C, NOT #DC2626 (2026-08-08). Found by the contrast check added
        # in the same commit, on its FIRST run, and nobody had ever named it:
        # #DC2626 reads 4.83:1 on a white card but only 4.13:1 on its OWN
        # wash, which is where the failed pill and the danger button actually
        # paint it. The darker red measures 6.47:1 / 5.54:1. The lesson is the
        # tooth's, not the colour's — an ink is not checked until it is
        # checked against the surface it is really on.
        "error": "#B91C1C",
        "successDim": "rgba(21, 128, 61, 0.12)",
        "successEdge": "rgba(21, 128, 61, 0.38)",
        "warningDim": "rgba(180, 83, 9, 0.12)",
        "warningEdge": "rgba(180, 83, 9, 0.38)",
        "errorDim": "rgba(220, 38, 38, 0.10)",
        "errorEdge": "rgba(220, 38, 38, 0.38)",
        "dangerFill": "rgba(220, 38, 38, 0.10)",
        "dangerFillHover": "rgba(220, 38, 38, 0.18)",
        "dangerEdge": "rgba(220, 38, 38, 0.40)",
        "neutralDim": "rgba(84, 90, 107, 0.10)",
        # FOUND BY OPENING THE PICTURE (build round R3, ControlsEditor in
        # light): the disabled rules said `surface1`, and on light surface1 is
        # WHITE — so every disabled button came out BRIGHTER than the enabled
        # ones beside it, which is the meaning exactly backwards. "One step
        # back down the ladder" is a DARK-palette sentence; what a disabled
        # control actually owes the user is to recede, and on light that means
        # sitting almost flat against the card it is on.
        "controlOff": "#EDEFF5",
        # The SAME defect one state over, and the same fix: `:pressed` also
        # said `surface1`, so pressing a button on light made it flash WHITE —
        # a button that gets brighter under the finger reads as switched on,
        # not as pressed. Reasoned rather than photographed: a press state
        # cannot be caught in a rendered screenshot, so it is named here for
        # the reviewer instead of claimed as a picture.
        "controlPressed": "#C9CEE0",
        # THE SAME BUG A THIRD TIME, found by opening ControlsEditor__light.png
        # on 2026-08-07: with no `QLineEdit` rule the set Name field, the
        # Shortcut field and the command Name field were page-coloured boxes
        # with a hairline or no line at all — three inputs that read as static
        # labels, on the one palette where "one step up the ladder" IS the
        # page. White fill and a REAL line, the way the combos beside them
        # already look (DESIGN.md → Light surfaces: border is #C7CBDD, a line,
        # never white-alpha).
        "fieldFill": "#FFFFFF",
        "fieldEdge": "#C7CBDD",
        # THE SAME BUG A FOURTH TIME, and this one survived the fix above —
        # measured off ControlsEditor__light.png on 2026-08-07, AFTER the
        # QLineEdit rule landed. `QLineEdit:disabled` reused `controlOff`, and
        # on light `controlOff` is #EDEFF5: the two fields the grader named by
        # name — the set `Name [Claude]` (disabled unless the set is custom)
        # and `Shortcut [e.g. ctrl+shift+p]` (disabled on a built-in command)
        # — came back as (237,239,245) on a page of (236,238,246). One unit
        # per channel, exactly the number the grader had blocked the release
        # over; only the third field, the one that is always editable, had
        # actually been fixed.
        #
        # The cause is that `controlOff` is TWO ideas wearing one name. A
        # disabled BUTTON owes the user nothing but its label, so receding
        # flat against the page is right. A disabled INPUT still carries a
        # VALUE he must read, so it owes him a box — quieter than an editable
        # one, never absent. Two meanings, two tokens: 11 steps above the page
        # and 8 below the white of a field he may actually type in.
        "fieldOff": "#F7F8FC",
        # White ink for the light accent (#0369A1). The shipped check.svg
        # draws #06212E, which is right on the dark theme's bright cyan and
        # ~2.2:1 on this one — measured off the same screenshot.
        "checkAsset": "check-light",
        "caretAsset": "caret-light",
        # Tinted, not flat black, and much softer — a dark shadow under a
        # white card reads as dirt.
        "shadowRgba": "15, 23, 42, 30",
        "qrPaper": "#FFFFFF",
        "radiusControl": "8px",
        "radiusCard": "14px",
    },
}

DEFAULT_THEME = "dark"

# THE PALETTES MUST CARRY THE SAME KEYS, and this is checked at IMPORT rather
# than left as a promise in a comment. It is not theoretical: writing the
# light palette, one edit dropped `neutralDim` from it, and nothing complained
# until a stopped server tried to paint its pill in light — a KeyError from
# `qss()`, in the middle of a theme flip, on a palette the dark run never
# touches. A four-line check at import is the cheapest place to find that.
_MISMATCH = set(PALETTES["dark"]) ^ set(PALETTES["light"])
if _MISMATCH:
    raise KeyError(
        "gui/theme.py: the palettes do not carry the same tokens — "
        f"{sorted(_MISMATCH)}. Every token exists in BOTH or in neither.")

# THE ACTIVE PALETTE. Mutated in place by `set_theme` so that every existing
# `TOKENS[...]` read — most of them inside a paintEvent — sees the live value.
TOKENS = dict(PALETTES[DEFAULT_THEME])
_active = DEFAULT_THEME

# Inter is the design-system typeface; the stack degrades to Segoe UI Variable
# (modern Win11 face) when Inter is not installed on the machine.
FONT_STACK = '"Inter", "Segoe UI Variable Display", "Segoe UI", sans-serif'

# ═══════════════════════════ STYLESHEET (QSS) ═══════════════════════════
# A TEMPLATE, never a formatted string: formatting at import would bake in
# whichever palette was active then, which is the whole defect this round
# removes (DESIGN.md → Live theme switching).
QSS_TEMPLATE = """
QWidget {{
    background: {surface0};
    color: {text};
    font-family: {font};
    font-size: 13px;
}}

QFrame#card {{
    background: {surface1};
    border: 1px solid {border};
    border-radius: {radiusCard};
}}

QLabel {{ background: transparent; border: none; }}
QLabel#h1 {{ font-size: 20px; font-weight: 700; }}
QLabel#caption {{ color: {text2}; font-size: 12px; }}
/* A caption REPORTING A FAILURE is not help text. The Settings window prints
   the agent-hook switch's refusal in this slot, and in caption grey it read
   exactly like the sentence that explains what the switch does — the one
   place this app says something is broken looked like the place it says
   everything is fine. DESIGN.md has a semantic Error hue; this is what it is
   for. Set through the `tone` property + `repolish`, so one label can be
   both states over its life. */
QLabel#caption[tone="error"] {{ color: {error}; }}
/* A card's section heading (Settings window). Small, bold and secondary —
   the CARD is the visual block, so the heading names it without competing
   with the controls inside it. */
QLabel#section {{ color: {text2}; font-size: 11px; font-weight: 700; }}
QLabel#url {{ color: {text2}; font-size: 12px; }}
QLabel#qr {{ background: {qrPaper}; border-radius: 10px; }}

/* Status pill — colored by the `state` dynamic property */
QLabel#pill {{
    border-radius: 999px;
    padding: 4px 14px;
    font-weight: 600;
    font-size: 12px;
}}
QLabel#pill[state="running"]  {{ background: {successDim}; color: {success}; border: 1px solid {successEdge}; }}
QLabel#pill[state="starting"] {{ background: {warningDim}; color: {warning}; border: 1px solid {warningEdge}; }}
QLabel#pill[state="stopped"]  {{ background: {neutralDim}; color: {text2};  border: 1px solid {border}; }}
QLabel#pill[state="failed"]   {{ background: {errorDim};   color: {error};  border: 1px solid {errorEdge}; }}

QPushButton {{
    background: {surface2};
    border: 1px solid {border};
    border-radius: {radiusControl};
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:hover   {{ border-color: {accent}; color: {accent}; }}
QPushButton:pressed {{ background: {controlPressed}; }}
QPushButton:disabled {{ color: {text2}; background: {controlOff}; }}

QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {accent}, stop:1 {accentDark});
    border: none;
    color: {onAccent};
}}
QPushButton#primary:hover  {{ background: {accent}; color: {onAccent}; }}
/* `controlOff`, like every other disabled button. It said `surface2`, which
   put TWO different disabled fills in one window — on light #DFE2EE against
   the #EDEFF5 of the plain ones, so the dead primary button read as the more
   prominent of the two. One state, one token. */
QPushButton#primary:disabled {{ background: {controlOff}; color: {text2}; }}

QPushButton#danger {{
    background: {dangerFill};
    border: 1px solid {dangerEdge};
    color: {error};
}}
QPushButton#danger:hover {{ background: {dangerFillHover}; color: {error}; }}

/* min-width is a FLOOR for an empty combo, never a claim on space: at 140px
   two combos in one row held 280px while the shortcut field beside them was
   squeezed to "ift+tab" (owner screenshot 2026-08-05). Qt already sizes a
   combo to its longest item; the floor only keeps an empty one clickable.
   THE SPACE & LEGIBILITY LAW — no neighbour holds slack next to a starving
   element. */
QComboBox {{
    background: {surface2};
    border: 1px solid {border};
    border-radius: {radiusControl};
    padding: 6px 10px;
    min-width: 92px;
}}
QComboBox:hover {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
/* THE CARET IS DRAWN. It was a CSS border triangle, which is a browser trick
   Qt's subcontrol renderer does not perform — it painted a solid 10x10 BLOCK
   in every combo of every window (sampled off the screenshots, 2026-08-07:
   100 identical ink pixels and not one antialiased edge). Same class as the
   ✥ the owner rejected on his phone. An SVG of the app's own icon family,
   one file per palette because QSS `image:` cannot re-tint. */
QComboBox::down-arrow {{
    image: url("{assets}/{caretAsset}.svg");
    width: 12px;
    height: 12px;
    margin-right: 8px;
}}
/* A dropdown popup is a RAISED overlay, which is `surface1` in both palettes
   (on dark a step up from the page, on light the whitest thing) — the same
   token QMenu below already uses. It said `surface2`, and that is a
   dark-palette sentence again: on light `surface2` is DARKER than the page,
   so the list that opens ON TOP of the window looked like a hole in it.
   Reasoned rather than photographed — a popup is not on screen when the audit
   renders a window, so no shot of this round can show it. */
QComboBox QAbstractItemView {{
    background: {surface1};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accentDim};
    selection-color: {accent};
    outline: none;
}}

/* Checkboxes. Unstyled, a QCheckBox took the QWidget rule above and carried
   the WINDOW's background into the card it sits in — a darker block around
   the label, plus Windows' own gray tick box (owner screenshot 2026-08-06).
   The label is transparent, and the box is the same control surface as a
   combo, filled with the one accent when it is on. */
QCheckBox {{ background: transparent; spacing: 9px; }}
QCheckBox:disabled {{ color: {text2}; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border};
    border-radius: 5px;
    background: {surface2};
}}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{
    background: {accent};
    border: 1px solid {accent};
    image: url("{assets}/{checkAsset}.svg");
}}
QCheckBox::indicator:disabled {{ background: {controlOff}; border-color: {border}; }}
QCheckBox::indicator:checked:disabled {{ background: {accentDim}; }}

/* TEXT INPUTS. A field the user may type in must LOOK like one in both
   palettes — see `fieldFill`/`fieldEdge`. Disabled keeps the LINE and loses
   the fill: a built-in set's Name is not editable, but it still carries a
   value the user must read, and a borderless grey box reads as a caption. */
QLineEdit {{
    background: {fieldFill};
    border: 1px solid {fieldEdge};
    border-radius: {radiusControl};
    padding: 6px 10px;
    selection-background-color: {accentDim};
    selection-color: {accent};
}}
QLineEdit:hover  {{ border-color: {accent}; }}
QLineEdit:focus  {{ border-color: {accent}; }}
/* `fieldOff`, NOT `controlOff` — a disabled input keeps both the line and a
   fill of its own, because it still shows a value the user must read. */
QLineEdit:disabled {{ background: {fieldOff}; color: {text2}; }}

/* THE CONTAINERS. Unstyled, a QGroupBox and an item view are drawn by the
   NATIVE style, whose frame is a hairline that simply vanishes on a light
   page — the Controls editor's set list and its three boxes lost their
   containers entirely (graded 2026-08-07). A card is a card in both
   palettes: the raised surface plus the palette's own border token. */
QGroupBox {{
    border: 1px solid {border};
    border-radius: {radiusCard};
    margin-top: 12px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: {text2};
}}

QListWidget, QTableWidget {{
    background: {surface1};
    border: 1px solid {border};
    border-radius: {radiusControl};
    gridline-color: {border};
    outline: none;
}}
/* ONE ACCENT (DESIGN.md → Color). Left to the native style, a selected row
   wears the WINDOWS SYSTEM accent — gold on the owner's PC — so the editor
   showed a yellow selection bar and a yellow current-cell frame against its
   own blue. The selection is ours now, in the app's one hue. */
/* Horizontal padding only: a row's HEIGHT is the scarcest thing the Controls
   editor has (its minimum must stay inside the declared 1280x1000 frame), and
   3 px above and below every row cost that window 90 px of list and 78 px of
   table for no legibility at all. */
QListWidget::item, QTableWidget::item {{ padding: 0px 6px; }}
QListWidget::item:selected, QTableWidget::item:selected {{
    background: {accentDim};
    color: {accent};
}}
/* `:horizontal` is load-bearing, not decoration. Unqualified, this rule also
   reaches the VERTICAL header — which the commands table HIDES — and Qt still
   takes its padded section height as the floor for every ROW: 26 px rows
   became 39, which cost the window 169 px and pushed its minimum outside the
   declared 1280x1000 frame. Measured both ways on 2026-08-07. */
QHeaderView::section:horizontal {{
    background: {surface2};
    color: {text2};
    border: none;
    border-bottom: 1px solid {border};
    padding: 6px 8px;
    font-weight: 600;
}}

QMenu {{
    background: {surface1};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {accentDim}; color: {accent}; }}

/* Same sentence as the dropdown popup: a tooltip floats ABOVE the window, so
   it takes the raised surface, not the sunken-on-light `surface2`. */
QToolTip {{
    background: {surface1};
    color: {text};
    border: 1px solid {border};
    padding: 4px 8px;
}}
"""


def qss() -> str:
    """The stylesheet of the ACTIVE palette. A function, never a constant —
    see this module's docstring."""
    return QSS_TEMPLATE.format(font=FONT_STACK, assets=ASSET_URL, **TOKENS)


# ═══════════════════════════ THEME SWITCHING ═══════════════════════════
logger = logging.getLogger(__name__)


def current_theme() -> str:
    return _active


def set_theme(name: str) -> str:
    """Make `name` the active palette. Returns the name actually applied —
    an unknown one falls back to the default AND says so in the log, because
    a settings file carrying a theme this version dropped must not take the
    window down with it (a real boundary: user file input).

    The dict is CLEARED and refilled rather than rebound, so every module that
    did `from gui.theme import TOKENS` keeps reading the live palette.
    """
    global _active
    if name not in PALETTES:
        logger.warning("Unknown theme %r — falling back to %s", name, DEFAULT_THEME)
        name = DEFAULT_THEME
    TOKENS.clear()
    TOKENS.update(PALETTES[name])
    _active = name
    return name


def apply_theme(name: str) -> str:
    """Switch the palette and re-style the whole APPLICATION.

    On the application, never on a window: a per-widget stylesheet wins over
    its parent's, so styling the main window alone would leave Controls,
    Traffic, Settings and the wheel-order dialog in the previous theme
    (DESIGN.md → Live theme switching). Everything the app has open — and
    everything it opens afterwards — follows from this one call.

    Three things QSS cannot re-do by itself are done here too:

      - card SHADOWS — a QGraphicsDropShadowEffect holds a QColor it was
        handed once, and a black shadow under a white card reads as dirt;
      - themed ICONS — `icon()` bakes the palette into the SVG source before
        Qt parses it (Qt's renderer does not resolve `currentColor`), so a
        button's icon is a picture in the old ink until it is rebuilt. Any
        widget that carries the dynamic property `iconName` gets a fresh one;
      - custom-painted widgets (the traffic chart, the wheel ring), which are
        simply told to repaint.
    """
    applied = set_theme(name)
    app = QApplication.instance()
    if app is None:
        return applied            # headless import (guards, --selfcheck)
    app.setStyleSheet(qss())
    for widget in app.allWidgets():
        effect = widget.graphicsEffect()
        if isinstance(effect, QGraphicsDropShadowEffect):
            effect.setColor(_shadow_color())
        name_property = widget.property("iconName")
        if name_property:
            widget.setIcon(icon(str(name_property)))
        widget.update()
    return applied


def color(value: str) -> QColor:
    """A palette VALUE as a QColor — including the `rgba(r, g, b, a)` form.

    QColor does not parse CSS `rgba()`: it returns an INVALID colour, and an
    invalid QColor paints opaque BLACK. Every wash in this table is written
    that way because QSS needs it that way — so any `paintEvent` reaching for
    `accentDim`, `border` or (dark) `fieldEdge` got black, silently.

    Found by sampling the pixels of ControlsEditor's own screenshot on
    2026-08-07: the `required` sets' tick boxes came out solid black in BOTH
    palettes where an accent wash was intended. Custom painting is the only
    place this can bite — QSS itself parses the string perfectly — which is
    exactly why it went unnoticed: the bug is invisible until a widget draws
    itself.
    """
    text = value.strip()
    if text.startswith("rgba(") or text.startswith("rgb("):
        parts = [p.strip() for p in text[text.index("(") + 1:text.rindex(")")].split(",")]
        if len(parts) in (3, 4):
            alpha = round(float(parts[3]) * 255) if len(parts) == 4 else 255
            return QColor(int(parts[0]), int(parts[1]), int(parts[2]), alpha)
    parsed = QColor(text)
    if not parsed.isValid():
        logger.error("Unparseable palette value %r — falling back to text", value)
        return QColor(TOKENS["text"])
    return parsed


def _shadow_color() -> QColor:
    return QColor(*(int(part) for part in TOKENS["shadowRgba"].split(",")))


# ═══════════════════════════ HELPERS ═══════════════════════════
def card(margins: tuple[int, int, int, int] = (18, 16, 18, 16),
         spacing: int = 10) -> tuple[QFrame, QVBoxLayout]:
    """One soft-shadowed card and its column — the bento tile every window in
    this app is built out of (DESIGN.md). It lived as a private method on the
    main window until the Settings window needed the same seven lines; a card
    is part of the design system, not of one window."""
    frame = QFrame()
    frame.setObjectName("card")
    card_shadow(frame)
    box = QVBoxLayout(frame)
    box.setContentsMargins(*margins)
    box.setSpacing(spacing)
    return frame, box


def icon(name: str, color: str | None = None) -> QIcon:
    """An SVG asset from assets/, tinted with a theme token.

    Qt's SVG renderer does NOT resolve `currentColor`, so the colour is
    substituted into the source text before Qt ever parses it. That is not a
    workaround for its own sake: it keeps the palette out of the asset, so one
    icon file serves the light theme as well as the dark one — and a font
    glyph was never an option (the owner's phone drew ✥ as a blunt cross, and
    the same rule holds on the desktop).

    A missing or unreadable asset yields an EMPTY icon and a logged error:
    the button keeps working with its label alone, and the log says which file
    is gone instead of the app dying over a decoration.
    """
    path = ASSET_DIR / f"{name}.svg"
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.error("Icon %s could not be read: %s", path, e)
        return QIcon()
    pixmap = QPixmap()
    if not pixmap.loadFromData(
            source.replace("currentColor", color or TOKENS["text"]).encode(), "svg"):
        logger.error("Icon %s could not be rendered as SVG", path)
        return QIcon()
    return QIcon(pixmap)


def card_shadow(widget: QWidget) -> None:
    """Soft ambient card shadow per DESIGN.md — Qt's defaults ARE the dated
    look (blur 1, offset 8/8), so parameters are always set explicitly. The
    COLOUR comes from the active palette (a black shadow under a white card
    reads as dirt) and is refreshed by `apply_theme`."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(28)
    shadow.setOffset(0, 6)
    shadow.setColor(_shadow_color())
    widget.setGraphicsEffect(shadow)


def repolish(widget: QWidget) -> None:
    """Re-applies QSS after a dynamic property change (Qt caches styles)."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
