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
