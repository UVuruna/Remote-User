"""PHONE → PC CONTENT, OVER HTTP (the Attach set's other half).

Split out of [Web Layer](web.py) on 2026-08-13, at the structure law's wall and
by RESPONSIBILITY rather than by line count: `web.py`'s subject is the SOCKET —
the live session, its dispatcher, its stream — while these two routes are a
plain request/response that happens to end in one injected `Ctrl+V`. The same
split [Recents](recents.py) and [Notify](notify.py) already made, and they
register themselves the same way.

Both routes end IDENTICALLY, which is the feature and not an accident (owner
2026-08-04): whatever the phone sends — one photo, five files, a PDF — lands in
the PC clipboard and is pasted straight into the box he was already looking at.
Picking the thing was the whole gesture.

The two are separate because the CLIPBOARD FORMAT is: one image goes as a
CF_DIB bitmap, which is what an image box can take, while several files or any
non-image go as CF_HDROP — real files, exactly like Copy in Explorer.
"""

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import File, Request, UploadFile
from fastapi.responses import JSONResponse

import clipboard
import content
import traffic

logger = logging.getLogger(__name__)


def register(app, token: str, injector) -> None:
    """`POST /upload` (one image) and `POST /upload_files` (anything else).
    Token-gated exactly like the WebSocket."""

    @app.post("/upload")
    async def upload(request: Request, file: UploadFile = File(...)):  # noqa: ANN202
        """Phone → PC: decode an image the tablet sent (incl. HEIC — the phone
        camera default), put it in the PC clipboard and PASTE it into the
        focused box right away (Ctrl+V injected — picking the image was the
        whole gesture; the user clicked the target field before choosing it)."""
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        data = await file.read()
        traffic.METER.add_in(len(data))  # phone -> PC counts wherever it enters
        img = await asyncio.to_thread(content.decode_upload, data)
        if img is None:
            # magic bytes identify the format we failed on (e.g. b'ftypheic')
            logger.error("Upload not decodable: %d bytes, name=%r, type=%r, magic=%r",
                         len(data), file.filename, file.content_type, bytes(data[:12]))
            return JSONResponse({"ok": False, "error": "not an image"}, status_code=400)
        ok = await asyncio.to_thread(clipboard.copy_image, img)
        if ok:
            await asyncio.to_thread(injector.press_chord, "ctrl+v")
        return {"ok": ok}

    @app.post("/upload_files")
    async def upload_files(request: Request, files: list[UploadFile] = File(...)):  # noqa: ANN202
        """Phone → PC, the multi-file / any-type path (owner 2026-08-04):
        several gallery images, or a PDF from the phone's Files — saved to a
        temp drop folder, put on the clipboard as REAL files (CF_HDROP) and
        pasted right away, exactly like Copy in Explorer + Ctrl+V. A single
        image goes through /upload instead (bitmap — image boxes need that)."""
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        drop = Path(tempfile.gettempdir()) / "VibeCoderDrop"
        # The PREVIOUS upload's files are cleared here, not right after their
        # paste — a target app may still be reading them from the clipboard.
        shutil.rmtree(drop, ignore_errors=True)
        drop.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, f in enumerate(files):
            name = Path(f.filename or f"file_{i}").name or f"file_{i}"
            path = drop / name
            if path in paths:  # two picks may carry the same name
                path = drop / f"{i}_{name}"
            blob = await f.read()
            traffic.METER.add_in(len(blob))
            path.write_bytes(blob)
            paths.append(path)
        if not paths:
            return JSONResponse({"ok": False, "error": "no files"}, status_code=400)
        ok = await asyncio.to_thread(clipboard.copy_files, paths)
        if ok:
            await asyncio.to_thread(injector.press_chord, "ctrl+v")
        else:
            logger.error("CF_HDROP copy failed for %d files", len(paths))
        return {"ok": ok, "count": len(paths)}
