# Upload API — phone → PC content, over HTTP

Source: [`server/upload_api.py`](../upload_api.py) ·
Phone half: the Attach set ([`client/panels.js`](../../client/panels.js)) ·
Sibling: [`content.py`](content.md) (the decode), [`clipboard.py`](clipboard.md)

## Why it is its own module

Split out of [Web Layer](web.md) on 2026-08-13, at THE STRUCTURE LAW's wall and
by RESPONSIBILITY rather than by line count: `web.py`'s subject is the live
SOCKET — the session, its dispatcher, its stream — while these two routes are a
plain request/response that happens to end in one injected `Ctrl+V`. It is the
same split [Recents](recents.md) and [Notify](notify.md) already made, and they
register themselves the same way.

Nothing about the routes changed in the move. They are the owner's design of
2026-08-04, unaltered.

## The one thing both routes do

Whatever the phone sends — one photo, five files, a PDF — lands in the **PC
clipboard** and is pasted straight into the box he was already looking at.
Picking the thing was the whole gesture (owner, 2026-07-22): he tapped the
target field before he opened the picker, so a second "now paste it" step would
be asking him to say something he has already said.

## Why there are two routes and not one

The CLIPBOARD FORMAT is the difference, and it is not cosmetic:

* **`POST /upload`** — ONE image → `CF_DIB` bitmap. That is the only format an
  image box will take, and it is the common case (a camera shot, one gallery
  pick). The decode is Pillow-first with `pillow-heif` (phone cameras default
  to HEIC) and EXIF correction, with cv2 as the fallback —
  [`content.decode_upload`](content.md).
* **`POST /upload_files`** — several files, or any non-image → a temp drop
  folder plus `CF_HDROP`: REAL files, exactly like Copy in Explorer.

The previous upload's temp files are cleared at the START of the next upload
and never right after their paste: a target app may read the clipboard lazily,
and deleting the files it is about to read is a paste that silently produces
nothing.

## Honest limits

* Both routes are token-gated exactly like the WebSocket, and nothing else
  guards them — an upload is an injected `Ctrl+V` into whatever holds the
  keyboard, so the token IS the security boundary here.
* Traffic is metered where the bytes ENTER (`traffic.METER.add_in`), which is
  why an upload shows in the desktop Traffic window even though it never
  travelled the socket.
