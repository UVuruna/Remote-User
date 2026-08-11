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

## `crop_to_region` — the region the phone is really looking at

Moved out of `_screenshot` on **2026-08-10** (same rule as the split above:
pure pixel arithmetic is not transport). The Attach set's **Shot** sends the
monitor-normalized rect the phone currently views — zoomed, or a layout's own
region, never the whole desktop (owner 2026-08-04) — and the legacy `snap`
sends nothing, which is why missing or unreadable numbers mean the whole frame
rather than a failure. Every edge is clamped INSIDE the frame and each side is
forced at least one pixel wide: a zero-width crop is not an image, and the
clipboard would refuse it after the user had already spent the gesture.

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

## Focusing the Claude prompt first (owner order 2026-08-11, task 200)

His complaint: a Claude command "fails when the prompt is not selected". The
paste lands wherever the caret happens to be inside VS Code — the editor, the
terminal, the file tree — so `/model` arrives as literal text in a source file.
His instruction was that the program must put the caret in the prompt ITSELF
before typing.

The mechanism was measured this round. The Claude Code extension registers the
command **"Claude Code: Focus input"** (`claude-vscode.focus`), whose webview
receiver focuses the prompt box and, with an empty payload, inserts nothing —
exactly the act wanted and nothing else. `Ctrl+Escape` was REJECTED: it is a
focus/**blur** toggle, so firing it blind is a coin flip that half the time
takes focus away from the prompt. What is left is the one delivery that depends
on no current state: the Command Palette.

`focus_claude_prompt(injector, guard, process_of=None)` therefore runs
`Ctrl+Shift+P` → paste the command name → Enter, with the focus fence
re-checked across every gap (the `PASTE_ENTER_DELAY` rule of `paste_text`,
applied to all of them instead of only the last). It returns `""` on success,
or the sentence the phone is shown.

**The process is asserted first, and the refusal is total.** `Ctrl+Shift+P` is
a GLOBAL chord, not a harmless no-op — fired into a stranger's window it is
precisely the accident constraint 11 exists to prevent. A target that is not
`Code.exe`, a fence that could not be restored, or a busy clipboard all cost
**zero injections** and are told to the phone. There is no typed fallback for
the command name either: the palette re-filters on every character, and the
Enter would then run whatever it had filtered to — an arbitrary VS Code
command, submitted. If the fence is lost mid-sequence the palette is left
standing on the PC on purpose: the Escape that would close it is another
injection, and focus is exactly what we no longer have.

It runs BEFORE `paste_text` rather than inside it, from
[Claude API](claude_api.md) → `focus_prompt()`, so a refusal costs no
keystrokes at all instead of half a command. A `paste_text` without
`focus: "claude"` never reaches this path and behaves exactly as it has since
2026-08-05.

### Gate
[`tests/test_claude_focus.py`](../../tests/test_claude_focus.py) — fail-closed
in `build.py` (0ab/6): the palette completes strictly before the command's own
Ctrl+V, a plain `paste_text` is still exactly two injections, a non-VS-Code
target injects nothing, and a fence lost mid-sequence withholds the Enter.
