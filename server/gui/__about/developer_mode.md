# `developer_mode.py` — the doors that are not for a new user

Owner request **2026-08-19**. The desktop window's row of doors is what a
person sees ten seconds after installing this app, and **Traffic** — every byte
to and from the phone, on a chart — is not one of the things that person needs.
It is his own instrument, and he named it as the first of a class: *"i jos neke
naknadne opcije"* (and some other later options). <!-- lang-ok: owner request -->

So it is **hidden, not removed**, behind one switch that is opened by clicking
the window's title **five times**.

## What is in it

| Name | What it is |
|---|---|
| `is_on()` | whether the developer doors are shown — read from the live `SETTINGS` |
| `TitleTap` | an event filter that counts clicks on whatever it is installed over |
| `TAPS_TO_TOGGLE` / `TAP_WINDOW_S` | five, inside three seconds |
| `ON_TEXT` / `OFF_TEXT` | what the tray says afterwards |

The list of doors is **not** here — it is `DOORS` in
[main_window.py](main_window.md), one row per button with a `dev` column. A new
developer door is a row with `dev=True` and nothing else: THE ONE KIND, ONE
CLASS law, applied the first time the class had two members.

## Why five taps and not a checkbox in Settings

The thing being hidden is hidden from the person who does not know it exists —
which is exactly who a checkbox would show it to. The gesture is Android's own
(tap the build number seven times) and it is the one convention a user of this
app already has.

It **toggles**: five taps again and the row is what a stranger sees. That is
also the answer to the obvious failure — somebody opens it by accident and
cannot work out how to close it — and it is why the tray says so both ways
rather than letting a button silently appear.

## Why an event filter and not a QPushButton

The header is a logo and two lines of text. Turning it into a button would tell
every user there is something here to press, which is the one thing this must
not do. Nothing about the widget changes; it simply also counts — and
`eventFilter` returns `False` always, so the click is never swallowed and the
header goes on being a header.

The filter is installed on the header container **and on its three children**,
because a click lands on the label under the pointer, not on the box around it.

## The window is what makes five clicks deliberate

Five clicks inside three seconds is a gesture. Five clicks spread over a working
day is a person who happens to click the header now and then, and that must
never wake this — so a click later than `TAP_WINDOW_S` after the previous one
restarts the count at one rather than extending it.

## It is not a lock

The value sits in plain text in the user's `settings.json`, and anyone who edits
that file gets the same result — `developer_tools` is a user-adjustable key like
every other, which is also what makes the five taps survive a restart.

**Nothing may ever go behind this door that would be unsafe in a stranger's
hands.** It hides clutter; it guards nothing, and treating it as a guard is how
a hidden feature becomes a security claim nobody checked.

## What a failed write does

A settings file that cannot be written is not a reason to lie about what the row
is showing: the live value is applied anyway (so the row follows the click) and
the log says the choice will not survive the restart.

## Gate

[tests/test_developer_tools.py](../../../tests/test_developer_tools.py) — a
fresh install's row has no Traffic; five clicks put it back **in its own
place**; four do not; clicks outside the window never add up; the gesture never
swallows its click; the setting is user-adjustable and a string in the JSON is
ignored rather than truthy; and the window's declared minimum is the same number
with the door open and closed, because it is measured against all three
captions either way.

The row is also photographed in both states by
[tests/_audit_windows.py](../../../tests/_audit_windows.py) →
`make_main_window_developer`.

Up: [server/gui/___gui.md](../___gui.md) · Beside: [main_window.md](main_window.md)
