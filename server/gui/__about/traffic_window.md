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
- **PC → phone** and **phone → PC**, in bytes per second, as two filled lines.
- **A grey band wherever no client was connected.** That band is the point of
  the window: a locked phone must show a flat zero line *inside* the grey
  band, and if it ever shows traffic there, this is the evidence.
- **Header lines** — live rate and session total per direction, client count;
  the phone's own counters since it connected (Android `TrafficStats`: this
  app, and the whole device); and the line that settles the battery question —
  *what this app spent while it was away*, measured by the phone across the gap
  it was gone.
- **Footer** — the span picker (2 min / 10 min / 1 hour), the recording state
  and path, **Open the recording**, **Reset counters**.

The peak label has a 1 kB/s floor so an idle graph reads as a flat line along
the bottom instead of magnified noise.

Everything is `QPainter` on a plain `QWidget` — no new dependency for a
diagnostic window, and the chart takes every spare pixel (`Expanding`), so it
grows with the window instead of leaving slack beside it.

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

## Connections
### Uses
- [Traffic Meter](../../__about/traffic.md) — `history()`, `snapshot()`, `reset()`
- [Theme](theme.md) — tokens and the card shadow
- [Config](../../__about/config.md) — the recording path

### Used by
- [Main Window](main_window.md) — the **Traffic…** button

### Flow
- [Traffic Window — Flow](../__flow/traffic_window.md)
