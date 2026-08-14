# Traffic Window

**Script:** [Traffic Window (script)](../traffic_window.py)

## Purpose
The desktop window that shows what this PC actually sends to and receives from
the phone, over time. Opened from the main window's **Traffic…** button, next
to Controls… — the owner asked for it by name (2026-08-05) so that "does the
app keep running when I lock the phone" could be answered by a reading instead
of by another assurance.

Modeless on purpose: he watches this window WHILE he locks the phone in his
other hand.

## What it draws
- **PC → phone** and **phone → PC**, in bytes per second, as two filled lines
  (the AVERAGE of the visible span); on the two long spans (below) a faint
  dotted hairline above each also traces the bucket MAX, so a spike a wide
  bucket's average would otherwise erase stays visible.
- **A grey band wherever no client was connected.** That band is the point of
  the window: a locked phone must show a flat zero line *inside* the grey
  band, and if it ever shows traffic there, this is the evidence.
- **A real Y axis** — 4–5 gridlines on the 1/2/5 × 10^n round-value ladder
  (`_y_ticks`), each labeled in whatever unit fits (kB/s, MB/s), instead of a
  bare max-and-zero. **X-axis time labels** scale their format to the span:
  `HH:MM:SS` under an hour, `HH:MM` under a day, `MMM DD` beyond that.
- **A hover crosshair + readout card** (`setMouseTracking(True)`): the
  pointer snaps to the nearest point and a small card states the time to the
  second, both rates (plus the bucket peak when it meaningfully exceeds the
  average), and the connection state — `"nobody connected"` inside the grey
  band, `"1 client connected"` / `"N clients connected"` otherwise (English —
  see Translation Policy, below). The card is confined to the chart and
  **flips to the other side of the crosshair** whenever the default side
  would run it off the widget (THE SPACE & LEGIBILITY LAW — it may never
  leave the window).
- **A legend of DRAWN marks, not glyph characters** (`_LegendMark`, a small
  `QPainter` widget): a filled+lined swatch in each series' own live colour
  (`out_color()` / `in_color()`) for the two directions, a shaded rect for
  the idle band, a dashed line for the peak hairline. Laid out as a 2×2 GRID
  of atomic (mark, label) items — never a wrapping sentence — with the
  explanation ("a locked phone must show a flat line inside the grey band")
  moved to its own caption below, free to wrap on its own. Fixed 2026-08-07
  after an independent grade (6/10, both palettes): the old legend was one
  `QLabel` with literal `"■"`/`"▨"`/`"····"` characters painted in caption
  grey, so the two series — this window's whole subject — were visually
  identical, worst on light where both squares came out the same dark grey;
  and the sentence wrapped mid-item, orphaning "grey band" onto its own line
  between two keys.
- **The chart's plot area is a PANEL**, filled with `surface1` and outlined
  with a hairline border, not left at the window's own `surface0` — the
  independent grade's confirmed-but-mild finding (both palettes): a plot
  filled with the window's own colour reads as a flat region instead of a
  bounded chart.
- **"Recording to file" is a coloured DOT + status line**, not a disabled
  checkbox. Nothing in this window ever lets the owner turn recording on or
  off — only a disk write failure does (`traffic.py`'s `_append_csv`) — so a
  clickable-looking control that cannot be clicked was the wrong affordance;
  the same drawn-mark rule as the legend (`_LegendMark`, kind `"dot"`,
  success/error token) makes it an honest reading instead.
- **Header lines** — live rate and session total per direction, client count;
  the phone's own counters since it connected (Android `TrafficStats`: this
  app, and the whole device); and the line that settles the battery question —
  *what this app spent while it was away*, measured by the phone across the gap
  it was gone.
- **Footer** — the span picker: **Last 2 minutes / 10 minutes / hour** (the
  live in-memory ring buffer), plus **Since start** (this server process's
  whole life) and **All (from file)** (the complete recording) — both read
  off the UI thread from `traffic.csv` via
  [Traffic History](../../__about/traffic_history.md) (BUILD ROUND R4,
  owner-approved 2026-08-07). The recording status dot and path, **Open the
  recording**, **Reset counters** sit alongside.

The peak label has a 1 kB/s floor so an idle graph reads as a flat line along
the bottom instead of magnified noise.

Everything is `QPainter` on a plain `QWidget` — no new dependency for a
diagnostic window, and the chart takes every spare pixel (`Expanding`), so it
grows with the window instead of leaving slack beside it.

## The two long spans
Selecting **Since start** or **All (from file)** starts a `traffic_history.
HistoryJob` on a background thread — never the UI thread, since either span
can mean reading a file with ~4 months of one-second rows. While the first
read for a freshly-picked span is still running the chart shows "Reading
traffic.csv…" instead of a stale or empty graph; once loaded it re-reads
every `SETTINGS.traffic_history_refresh_s` (30 s) so a long watch still sees
new samples land, without re-scanning the file on every 1 s GUI tick. A
window **resize never re-reads the file** — `traffic_history` already bounds
its output to `SETTINGS.traffic_history_max_buckets`, comfortably above any
real window width, and the chart's own `_coalesce` does the final,
cheap, in-memory downsample to the exact current plot width on every paint
(so the on-screen "never more than one point per pixel" guarantee holds
regardless of window size, without touching disk again).

## THE SPACE & LEGIBILITY LAW
The minimum is **measured**, and measured on first `showEvent`, not in
`__init__` — the theme's font only resolves when Qt polishes the widget, and
measuring before that under-shoots every string by roughly a tenth (the
2026-08-05 lesson that cost the Controls editor a second release). Width comes
from the control row, which cannot wrap; the long text (legend, recording path)
wraps instead of widening the window. Registered in the Qt layout audit
(`tests/test_layout_audit_qt.py`) in its FULLEST state — a phone connected,
counters reported and an away-gap present, so the longest sentence is what gets
measured.

A refresh failure is logged, never raised: a diagnostic window may not be the
thing that takes the app down.

## Translation Policy (rules/GUI.md)
Every string in this window is ENGLISH — the language decision made explicit
in build round R6, below, after an independent grader found a mix (the two
long-span combo entries in Serbian, the hover card's connection state in
Serbian). Development is English-only; a bundle's Serbian coverage is a
translation session's job, never a partial slip inside a feature round.

## Build round R6 (2026-08-07) — the independent grade's six findings

An independent grader (not this window's author) failed TrafficWindow 6/10 in
BOTH palettes. What changed, one line per finding:

1. **Legend colour-blindness fixed.** The two series were literal `"■"`
   characters inside one caption-grey `QLabel` — on light they were two
   identical dark squares, and the window's whole subject is telling two
   directions apart. `_LegendMark` (a small `QPainter` widget) now draws
   each swatch in the series' own live colour (`out_color()` / `in_color()`).
2. **Legend orphaning fixed.** The legend is a 2×2 GRID of atomic
   (mark, label) items now, not a wrapping sentence — nothing can split
   mid-item. The explanation sentence moved to its own caption below, free
   to wrap on its own.
3. **Glyph marks replaced with drawn marks.** Every legend/status mark in
   this window (`_LegendMark`) is `QPainter` output — colour always from a
   theme token or the chart's own colour functions, never a font character.
4. **Serbian removed.** The two long spans ("Od starta" / "Sve (iz fajla)")
   are "Since start" / "All (from file)"; the hover card's connection state
   ("niko povezan" / "N klijenata povezano") is "nobody connected" /
   "N clients connected". See Translation Policy, above.
5. **"Record to file" is an honest status line.** It was a `QCheckBox` set
   `Enabled(False)` — a control that looks clickable but is not. Nothing in
   this window ever toggles recording; only a disk write failure does. It is
   now a coloured dot (`_LegendMark`, kind `"dot"`, success/error token) plus
   a label that reads "Recording to file" / "Recording stopped".
6. **The plot reads as a panel.** Filled with `surface1` and outlined with a
   hairline border, instead of the window's own `surface0` — the grader's
   own words: "confirmed but mild ... nowhere near the real problems." Fixed
   because it was cheap, not because it was the priority.

Re-shot and re-opened in both palettes after the fix; `tests/test_layout_
audit_qt.py` passes in both. A dedicated hover-state screenshot (real,
varying, non-zero data — the audit's own fixture is 0 B/s throughout, so the
series colours, the idle band and the peak hairline were never visible in
any previously graded picture) was produced from a run outside the audit,
confirming the crosshair card's edge-flip still holds.

## Connections
### Uses
- [Traffic Meter](../../__about/traffic.md) — `history()`, `snapshot()`, `reset()`, `PROCESS_START`
- [Traffic History](../../__about/traffic_history.md) — `HistoryJob`, `Point` — the two long spans
- [Theme](theme.md) — tokens and the card shadow (chart chrome — gridlines,
  idle band, crosshair, hover card — reads `TOKENS` at paint time, alpha-blended
  via the local `_alpha()` helper, never a hardcoded hex)
- [Config](../../__about/config.md) — the recording path, `traffic_history_max_buckets`, `traffic_history_refresh_s`

### Used by
- [Main Window](main_window.md) — the **Traffic…** button

### Flow
- [Traffic Window — Flow](../__flow/traffic_window.md)

## Per-device colour (owner request 2026-08-13, corrected 2026-08-14 — T75)

Both series can colour by DEVICE instead of by direction: each run of
consecutive points sharing one `Point.device` is drawn in that device's own
colour (`gui.theme.device_color(traffic_devices.REGISTRY.index_for(device))`),
so a smaller-resolution phone's lighter cost is visible against a tablet's.
An unattributed point (`device == ""` — nobody connected, or a pre-`device`-
column CSV row) draws `device_color(-1)`, the neutral "unknown" grey — never a
real device's colour and never the plain direction colour either, since
neither claim ("this is device X" / "this is the ordinary single-device
picture") is true of it.

**T75 correction (owner report 2026-08-14, from his own screenshot):** the
predicate deciding whether to colour by device at all used to be "does the
VISIBLE SPAN hold more than one device" — computed from the points on screen.
His screenshot showed why that is wrong: the legend already listed two
devices seen (persisted across the session) while the visible 2-minute span
held only the phone, so the chart fell back to the plain direction colour
(blue) for that span — the SAME blue the legend's own swatch had already
given the phone as its device colour. One colour, two meanings, in one
window. The predicate is now **"has this PC EVER seen more than one
device"** — `len(traffic_devices.REGISTRY.all()) > 1`, read fresh at every
paint from the registry that already persists across restarts (the entire
reason the "Devices seen" list can show a device that sent nothing in the
visible span). Once true, it stays true for the rest of this PC's life; it
never depends on which points happen to be on screen.

**Direction vs identity, once colour means device:** with both series
coloured by device, colour alone can no longer say which direction a segment
is (a device that talks both ways would draw the same colour twice, looking
like one line). Direction is told apart by PEN STYLE instead — PC→phone
stays the plain solid line this chart has always drawn; phone→PC becomes
DASHED whenever per-device colouring is active. No new legend layout (kept
deliberately simple, per the task): the legend's "phone → PC" item text notes
the dash, and its swatch stays a plain solid mark showing the direction
colour, since the swatch is a KEY to the direction, not a live preview of
every segment's device colour.

Gate: `tests/test_traffic_devices.py` → RENDERED PIXELS, two checks added for
this correction — a real pixel readback proving a device the registry has
ever seen (but that sent nothing in the visible span) still draws its OWN
colour, and a companion check proving a revert to the old visible-span-only
predicate makes that same check fail.

## Build round R3 (2026-08-07) — themes

`OUT_COLOR` and `IN_COLOR` were module-level `QColor`s. A module-level palette
read evaluates ONCE at import, so the chart would have kept the dark theme's
bright cyan and amber on a white card forever — the exact defect DESIGN.md ->
Live theme switching names. They are `out_color()` and `in_color()` now.

Everything else in this file already read `TOKENS` at paint time and needed no
change; `_alpha()` had even been written with this round in mind ("the HUE
still has to come from a token, never a hardcoded white: a fixed white-alpha
grid would all but vanish on the light palette headed for this file").
