# Content — Flow

**About:** [description](../__about/content.md)

## An image arriving from the phone

```
📱 Attach → Gallery / Camera / Files
   └─ POST /upload  (raw bytes)
             │
             ▼   web.py, in a thread
      content.decode_upload(data)
             │
             ├─ Pillow ──► EXIF orientation applied ──► RGB ──► BGR ndarray
             │              (HEIC readable because pillow_heif registered
             │               its opener at import — phone cameras default
             │               to it, and nothing else here reads it)
             │
             └─ Pillow refused ──► cv2.imdecode  (formats Pillow does not know)
                                        │
                                        ▼
                             clipboard.copy_image  →  the PC's clipboard
```

## A typed command arriving from the phone

```
📱 Claude set → "/usage"        (protocol: paste_text {text, enter})
             │
             ▼   web.py, in a thread, with focus_guard.typist as `guard`
      content.paste_text(injector, text, enter, guard)
             │
             ├─ clipboard.copy_text(text) ── ok ──► injector.press_chord("ctrl+v")
             │
             └─ clipboard BUSY ──► injector.type_text(text, guard)   ← per-character fence
                                        │
                                        └─ something was lost?
                                             └─ ENTER WITHHELD, the lost part returned
                                                (half a command must never be SUBMITTED)
             │
             ▼   enter requested?
      sleep(PASTE_ENTER_DELAY = 120 ms)      ← the app is still reacting to the paste
             │
             ▼   ⚠ THE GAP THE THIEF FITS IN
      guard()  ── focus back inside the fence? ──┬── yes ──► injector.press_key("enter")
                                                 │
                                                 └── no ───► ENTER WITHHELD, text returned
                                                             (it would RUN whatever the
                                                              stranger's box was holding)
             │
             ▼
      ""  = everything landed        |        anything else = the toast the phone shows
```

## What this module never touches

No WebSocket, no route, no client state, no layout. It is handed an injector and
a guard and returns a string. `web.py` owns the socket and the toast; the
[focus guard](focus_guard.md) owns what "inside the fence" means; the
[injector](input_injector.md) owns the Win32 calls.

That separation is the whole point of the 2026-08-08 split — see
[the description](../__about/content.md#why-it-is-its-own-module).
