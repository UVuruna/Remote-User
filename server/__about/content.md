# content.py — what the phone sends, turned into what the PC can receive

**Script:** [content.py](../content.py) · **Flow:** [Content (flow)](../__flow/content.md)

## Purpose

Two conversions, and nothing else:

| | From | To |
|---|---|---|
| `decode_upload(data)` | the raw bytes of an upload | a BGR image the clipboard can hold |
| `paste_text(injector, text, enter, guard)` | a string | keystrokes in the focused box on the PC |

## Why it is its own module

Split out of [web.py](web.md) on **2026-08-08**. The line count only forced the
question — the answer was that neither of these ever belonged to the transport.
Not one line here knows a WebSocket exists, and that is the test of whether the
split was real rather than mechanical (THE STRUCTURE LAW, `rules/CODE.md`:
*split by RESPONSIBILITY, never mechanically*).

`web.py` keeps what genuinely is transport — the routes, the frame fan-out, the
config frame, and the screenshot handler, which answers **on the socket** with a
toast — and calls in here for the conversions.

## `decode_upload` — Pillow first, on purpose

Phone cameras default to **HEIC/HEIF**, which neither OpenCV nor plain Pillow
reads; `pillow_heif.register_heif_opener()` at import is what makes them
readable at all. Pillow also applies the **EXIF orientation**, and `cv2.imdecode`
ignores it — a photo would paste rotated. OpenCV stays as the fallback for
formats Pillow does not know.

## `paste_text` — the order IS the feature

The clipboard write, then `Ctrl+V`, then `Enter`. `PASTE_ENTER_DELAY` (120 ms)
between the last two is not cosmetic: the target app reacts to the paste — a
command menu re-filters, an input resizes — and an Enter delivered inside that
reaction lands in the old state.

### The fence is re-checked across that wait (2026-08-08)

The paste and the Enter are two separate injections with 120 ms of nothing
between them, and 120 ms is a whole window for the thief
[constraint 11](../../CLAUDE.md) was written about: an app finishing its start,
a dialog, another agent's editor taking the foreground. `InputInjector.type_text`
re-checks before **every character** for exactly that reason — and the one key
that *submits* was the only one still crossing an unguarded gap.

**An Enter that lands in a stranger's box does not lose a keystroke; it RUNS
whatever that box was holding.** So if the guard cannot put focus back inside the
fence, the Enter is **withheld** and the text is returned to the caller for the
phone's toast. A command that was not submitted can be submitted by hand; one
submitted in the wrong window cannot be taken back.

The same rule governs the clipboard-busy fallback: when the text has to be typed
character by character and some of it does not arrive, Enter is withheld too —
running the fragment that happened to land is worse than running nothing.

## Return value

`""` means all of it reached the PC. Anything else is what did **not**, and the
caller turns it into a toast the owner can actually see — the failure mode this
whole path exists to avoid is a button that silently does nothing.

## Gate

[`tests/test_input_pipeline.py`](../../tests/test_input_pipeline.py) — the
fail-closed INPUT GATE in `build.py` — pins the ORDER
(`clipboard → ctrl+v → enter`), the Menu button's *no Enter*, and the
clipboard-busy fallback.
