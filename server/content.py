"""WHAT THE PHONE SENDS, TURNED INTO SOMETHING THE PC CAN RECEIVE.

Split out of `web.py` on 2026-08-08 (THE STRUCTURE LAW — the line count only
forced the question; the answer was that these two never belonged to the
transport). Everything here converts CONTENT: bytes off an upload into a
picture the clipboard understands, and a string into keystrokes the focused
box receives. Not one line of it knows a WebSocket exists, and that is the
test of whether the split was real.

`web.py` keeps what genuinely is transport — the routes, the frame fan-out,
the config frame, the screenshot handler (which answers ON the socket with a
toast) — and calls in here for the conversions.
"""

import io
import logging
import time

import clipboard
import clipboard_sync
import cv2
import numpy as np
import pillow_heif
from PIL import Image, ImageFile, ImageOps

from input_injector import InputInjector

logger = logging.getLogger(__name__)

# Phones (Samsung/Pixel defaults) shoot HEIC/HEIF, which neither OpenCV nor
# plain Pillow read — this registers the HEIF codec into Pillow.
pillow_heif.register_heif_opener()

# A PICTURE MISSING ITS LAST FIVE BYTES IS STILL A PICTURE (owner report
# 2026-08-09: he sent an image from the tablet, the loading animation ran, and
# nothing ever arrived on the PC). His own server log named it exactly:
#
#   WARNING content: Pillow could not decode upload (image file is truncated
#                    (5 bytes not processed)) — trying OpenCV
#   ERROR   web: Upload not decodable: 717894 bytes, name='1000006359.jpg',
#                type='image/jpeg', magic=b'\xff\xd8\xff\xe1\x00\xf6Exif\x00\x00'
#
# The magic bytes are a perfectly ordinary JPEG and there are seven hundred
# thousand of them; Pillow refused the whole thing over a short final scan, and
# OpenCV — which is only a fallback for formats Pillow does not KNOW — refused
# it too. Three of his uploads died that way, all from the tablet, while the
# phone's went through, which is what made it look like a tablet bug.
#
# Refusing here loses the entire picture to save nothing. Pillow's own switch
# says "decode what is there", and what is there is the image minus a few
# bytes of its last row.
ImageFile.LOAD_TRUNCATED_IMAGES = True


def decode_upload(data: bytes):
    """Uploaded image → BGR ndarray, or None (caller logs the failure).

    Pillow first: it covers JPEG/PNG/WEBP + HEIC (opener above) AND applies
    the EXIF orientation — phone photos carry it, and cv2.imdecode ignores it
    (the image would paste rotated). OpenCV remains as a fallback for formats
    Pillow does not know."""
    try:
        pil = Image.open(io.BytesIO(data))
        pil = ImageOps.exif_transpose(pil).convert("RGB")
        return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
    except Exception as e:
        logger.warning("Pillow could not decode upload (%s) — trying OpenCV", e)
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def crop_to_region(frame, msg: dict):
    """The captured frame cropped to the monitor-normalized rect the phone
    asked for (`screenshot {x, y, w, h}` — the Attach set's Shot sends the
    region it is really looking at, never the whole desktop). Missing or
    unreadable numbers mean the whole frame, which is the legacy snap.

    Pure pixel arithmetic, so it lives here and not in the transport (moved out
    of web.py 2026-08-10). Every edge is clamped INSIDE the frame and each side
    is forced at least one pixel wide — a zero-width crop is not an image and
    the clipboard would refuse it."""
    try:
        x, y = float(msg.get("x", 0)), float(msg.get("y", 0))
        w, h = float(msg.get("w", 1)), float(msg.get("h", 1))
    except (TypeError, ValueError):
        x, y, w, h = 0.0, 0.0, 1.0, 1.0
    fh, fw = frame.shape[:2]
    x1 = min(max(int(x * fw), 0), fw - 1)
    y1 = min(max(int(y * fh), 0), fh - 1)
    x2 = min(max(int((x + w) * fw), x1 + 1), fw)
    y2 = min(max(int((y + h) * fh), y1 + 1), fh)
    return frame[y1:y2, x1:x2]


# --- Typed commands (owner 2026-08-05) --------------------------------------
# A `paste_text` button pastes and then presses Enter. The pause between them
# is not cosmetic: the target app (Claude's prompt, a search box) reacts to
# the paste — filtering a command menu, resizing its input — and an Enter
# delivered inside that reaction lands in the old state.
PASTE_ENTER_DELAY = 0.12


# --- Focusing the Claude prompt first (owner order 2026-08-11, task 200) -----
# His complaint, in his own words: a Claude command "fails when the prompt is
# not selected" — the paste lands wherever the caret happens to be inside VS
# Code (the editor, the terminal, the file tree), so `/model` ends up as text in
# a source file. His instruction was to make the program put the caret in the
# prompt ITSELF before typing.
#
# The mechanism was measured this round. The Claude Code extension registers the
# command **"Claude Code: Focus input"** (`claude-vscode.focus`), whose webview
# receiver focuses the prompt box and, with an empty payload, inserts nothing —
# exactly the act wanted and nothing else. `Ctrl+Escape` was REJECTED: it is a
# focus/BLUR toggle, so firing it blind is a coin flip that half the time takes
# focus AWAY from the prompt. What is left is the one delivery that does not
# depend on any current state: the Command Palette.
#
# THE PROCESS IS ASSERTED FIRST AND THE REFUSAL IS TOTAL. `Ctrl+Shift+P` in a
# stranger's window is not a harmless no-op — it is a global chord fired into
# whatever the focus guard's target really is, and that accident is the class of
# failure this whole feature exists to prevent (constraint 11). So a target that
# is not VS Code costs ZERO injections and the phone is told why.
CLAUDE_FOCUS_COMMAND = "Claude Code: Focus input"
CLAUDE_FOCUS_PROCESS = "code.exe"
# Between the palette opening, the name landing in it and the Enter that runs
# it. Same reason as PASTE_ENTER_DELAY above, one step further: the palette
# FILTERS on every change, and a key delivered inside that reaction is applied
# to the list as it was.
FOCUS_STEP_DELAY = 0.18

# THE HAND-OFF AFTER THE ENTER IS NOT AN INJECTION GAP — IT IS ANOTHER
# PROCESS'S WORK (his report 2026-08-12, task 272: the Claude Tools commands
# "only work if text is SELECTED"). The palette's Enter is where OUR sequence
# ends and VS Code's begins, and what follows is measurable in the extension's
# own bundle. `claude-vscode.focus` builds an @-mention out of the editor
# selection — empty when there is none — and hands it to one function:
#
#   async function r(n){ if(t.deliverAtMention(n)) return;
#                        if(t.revealAndDeliverAtMention(n)) return; ... }
#
# `deliverAtMention` is the branch taken whenever a Claude chat surface is
# VISIBLE, which in a layout it always is. It posts the mention to the webview
# and returns true — it never calls `reveal()`, so the EXTENSION HOST moves no
# focus at all. Everything rests on the webview, in another process again:
#
#   else if (a.current?.focus(), Lt) a.current?.insertAtMention(Lt, !1)
#
# With a selection the prompt is focused TWICE — the bare `focus()` and then
# the caret the insert leaves behind, after the DOM write. With no selection
# `Lt` is `""` and there is exactly ONE focus, fired in the same tick the
# Command Palette is synchronously restoring focus to whatever it took it
# from. That is the whole asymmetry he reported, and neither half of it is
# ours to change.
#
# What IS ours is the wait. The old code gave the round trip
# palette-accept → extension host → webview → focus() one FOCUS_STEP_DELAY,
# 180 ms, and then pasted. His own log dates the sequence exactly — the two
# clipboard writes of one Claude button, the command name and then the
# command:
#
#   15:33:47,902 INFO clipboard: Text (24 chars) copied to clipboard
#   15:33:48,468 INFO clipboard: Text (12 chars) copied to clipboard
#
# 24 characters is `CLAUDE_FOCUS_COMMAND` and 12 is `/code-review`; 566 ms
# apart is three FOCUS_STEP_DELAYs plus the injections, so the palette really
# ran and the paste really followed 180 ms behind the Enter. A cross-process
# hand-off through an extension host that is itself running Claude Code does
# not reliably finish in 180 ms, and when it does not, the paste lands in
# whatever the palette restored focus to — the editor.
#
# So the hand-off gets its own, longer budget, spent in fence-checked slices
# rather than one blind sleep: 600 ms of nothing is exactly the window
# constraint 11 was written about, and the rule everywhere else in this file
# is that no gap goes unguarded.
CLAUDE_HANDOFF_DELAY = 0.6
CLAUDE_HANDOFF_SLICE = 0.15


def _target_process(hwnd: int) -> str:
    """The executable behind a window, lowercased. Imported where it is used
    rather than at module import: everything else in this file is pure content
    conversion, and only this one path needs the window layer."""
    import window_manager
    return (window_manager._process_name(hwnd) or "").lower()


def _settled(guard) -> bool:
    """The pause between two injections of one sequence, with the fence
    re-checked across it — the `PASTE_ENTER_DELAY` rule of `paste_text`,
    applied to every gap in the palette chord instead of only the last one."""
    time.sleep(FOCUS_STEP_DELAY)
    return guard is None or bool(guard())


def _handed_off(guard) -> bool:
    """The wait AFTER the palette's Enter, while VS Code's own two processes
    put the caret in the prompt (see CLAUDE_HANDOFF_DELAY above).

    Spent in slices with the fence re-read between them, for the reason every
    other gap here is: 600 ms in which we inject nothing is still 600 ms in
    which a thief can take the foreground, and the very next act is a paste.
    A lost fence answers False and the caller refuses — nothing further is
    injected, so the command is simply not sent."""
    waited = 0.0
    while waited < CLAUDE_HANDOFF_DELAY:
        slice_ = min(CLAUDE_HANDOFF_SLICE, CLAUDE_HANDOFF_DELAY - waited)
        time.sleep(slice_)
        waited += slice_
        if guard is not None and not guard():
            return False
    return True


def focus_claude_prompt(injector: InputInjector, guard=None,
                        process_of=None) -> str:
    """Puts the caret in Claude Code's prompt box. `""` = it is there; anything
    else is the sentence the phone is shown, and NOTHING was left half-done.

    Blocking on purpose (the caller runs it in a thread), like `paste_text`
    below, and it runs BEFORE that function rather than inside it: a refusal
    here must cost zero keystrokes, not a partial command."""
    process_of = process_of or _target_process
    target = guard() if guard is not None else 0
    if guard is not None and not target:
        logger.error("Claude focus refused — focus could not be secured")
        return "The command was NOT sent — another window holds the keyboard"
    name = process_of(target) if target else ""
    if name != CLAUDE_FOCUS_PROCESS:
        logger.error("Claude focus refused — the target runs %s, not %s",
                     name or "nothing readable", CLAUDE_FOCUS_PROCESS)
        return ("The command was NOT sent — VS Code is not the window in "
                "front. Open the Claude conversation first.")
    if not clipboard.copy_text(CLAUDE_FOCUS_COMMAND):
        # No typed fallback: the command name would go into the palette
        # character by character while it re-filters, and a MIS-filtered
        # palette entry run by the Enter below is an arbitrary VS Code command.
        logger.error("Clipboard busy — the Claude prompt was not focused")
        return "Clipboard busy — try the command again"
    injector.press_chord("ctrl+shift+p")
    if not _settled(guard):
        # The palette is left standing on the PC, deliberately: the Escape that
        # would close it is another injection, and focus is exactly what we no
        # longer have — it would land in the thief.
        logger.error("Claude focus abandoned — focus left before the command "
                     "name could be pasted")
        return "The command was NOT sent — another window took the keyboard"
    injector.press_chord("ctrl+v")
    if not _settled(guard):
        logger.error("Claude focus abandoned — focus left before the palette "
                     "entry could be run; nothing was submitted")
        return "The command was NOT sent — another window took the keyboard"
    injector.press_key("enter")
    if not _handed_off(guard):
        logger.error("Claude focus abandoned — focus left while VS Code was "
                     "still handing the caret to the prompt; nothing was typed")
        return "The command was NOT sent — another window took the keyboard"
    # Logged on SUCCESS too, and named. His 2026-08-12 report could not be
    # diagnosed from the log because this path was silent unless it refused:
    # the only trace a working sequence left was two clipboard writes 566 ms
    # apart, which says the palette ran and says nothing about where the caret
    # ended up. One line here is what makes the next report a read, not a hunt.
    logger.info("Claude prompt focused via the Command Palette (target 0x%x) "
                "— %.2fs hand-off honoured before the command is typed",
                target, CLAUDE_HANDOFF_DELAY)
    return ""


def paste_text(injector: InputInjector, text: str, enter: bool, guard=None) -> str:
    """Writes `text` into the focused box on the PC through the clipboard.

    Blocking on purpose (the caller runs it in a thread): the clipboard write,
    the paste and the Enter have to happen in that order, and Windows needs
    the paste to land before the next key. Falls back to typing the text
    character by character when the clipboard is busy — an owner watching his
    phone would otherwise see a button that silently did nothing.

    Returns what did NOT reach the PC ("" = all of it landed) for the toast.
    """
    if not text:
        return ""
    if clipboard.copy_text(text):
        # Written on the phone's behalf (task 182) — the live clipboard
        # listener must not read this back and push it to the phone as if
        # it were a fresh copy made at the PC.
        clipboard_sync.note_written(text)
        injector.press_chord("ctrl+v")
    else:
        logger.warning("Clipboard busy — typing %r instead of pasting it", text[:40])
        # Typed character by character now, so it needs the same mid-sentence
        # fence as dictation does (focus_guard.typist).
        lost = injector.type_text(text, guard)
        if lost:
            # Half a command must never be SUBMITTED: Enter is what makes a
            # slash command run, and running the fragment that happened to
            # arrive is worse than running nothing.
            logger.error("Enter withheld — %d characters of %r never reached "
                         "the PC", len(lost), text[:40])
            return lost
    if enter:
        # THE FENCE IS RE-CHECKED ACROSS THIS WAIT (2026-08-08). The paste and
        # the Enter are two separate injections with 120 ms of nothing between
        # them, and 120 ms is a whole window for the thief constraint 11 was
        # written about — an app finishing its start, a dialog, another agent's
        # editor taking the foreground. `type_text` re-checks before every
        # CHARACTER for exactly this reason; the one key that SUBMITS was the
        # only one still crossing an unguarded gap. An Enter that lands in a
        # stranger's box does not lose a keystroke, it RUNS whatever that box
        # was holding.
        time.sleep(PASTE_ENTER_DELAY)
        if guard is not None and not guard():
            # The guard could not put focus back inside the fence. Withholding
            # is the safe half of the same rule as the typed fallback above: a
            # command that is not submitted can be submitted by hand, and one
            # submitted in the wrong window cannot be taken back.
            logger.error("Enter withheld — focus left the fence during the "
                         "paste of %r", text[:40])
            return text
        injector.press_key("enter")
    return ""
