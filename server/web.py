"""FastAPI application: serves the client page, streams frames, receives input.

Protocol (see project CLAUDE.md):
- client → server, JSON text: auth, pointer_down, pointer_up, click (at the
  current cursor, no coordinates), pointer_move, scroll, viewport (JPEG mode
  only), key_text, key_special, chord, monitor_switch, screenshot
- server → client, JSON text: `config` after auth and after every stream
  (re)start — monitor size plus `stream` ("h264" | "jpeg") and, in H.264 mode,
  the MSE `codec` string parsed from the live init segment; `actions` (radial
  sets); `toast` notices; `cursor` positions for the client-drawn virtual
  cursor (DXGI frames never contain the mouse pointer).
- server → client, binary:
  - H.264 mode: the raw fMP4 byte stream — the client appends it into MSE.
  - JPEG mode: 16-byte header (4 × float32 LE — monitor-normalized x, y, w, h
    of the covered region) + JPEG bytes.

No message is processed before a valid `auth` — hard security rule.

The `stream` argument everywhere is either an H264Manager or a JpegStreamer —
one duck interface: mode, width, height, monitor_index, output_count(),
switch_to(), take_screenshot(); the JPEG side adds set_viewport(), the H.264
side open_session()/close_session().
"""

import asyncio
import io
import json
import logging
import struct
from dataclasses import dataclass

import cv2
import numpy as np
import pillow_heif
from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps

import clipboard
import monitors
import pairing
from config import SETTINGS, app_version
from input_injector import BUTTON_FLAGS, InputInjector

logger = logging.getLogger(__name__)

# Phones (Samsung/Pixel defaults) shoot HEIC/HEIF, which neither OpenCV nor
# plain Pillow read — this registers the HEIF codec into Pillow.
pillow_heif.register_heif_opener()


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


@dataclass
class ServerStats:
    """Live counters the desktop GUI shows. Mutated only on the event loop."""
    clients: int = 0


class FrameHub:
    """JPEG mode: fans frames from the capture thread out to client queues,
    dropping stale ones (each JPEG frame is independent — H.264 bytes are NOT
    droppable and use per-session queues instead)."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    def push_threadsafe(self, jpeg: bytes, region: tuple[float, float, float, float]) -> None:
        """Called from the capture thread. A slow client keeps only the newest frame."""
        packet = struct.pack("<4f", *region) + jpeg
        self._loop.call_soon_threadsafe(self._push, packet)

    def _push(self, packet: bytes) -> None:
        for q in self._queues:
            if q.full():
                q.get_nowait()
            q.put_nowait(packet)


def create_app(stream, hub: FrameHub | None, injector: InputInjector, token: str,
               stats: ServerStats | None = None) -> FastAPI:
    stats = stats if stats is not None else ServerStats()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def no_cache(request, call_next):
        # Client files are served straight from disk and change with every
        # update — a cached index.html mixed with a fresh app.js crashes the
        # page before it ever connects. Never let the browser cache anything.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    async def index(request: Request):
        # Android browsers NEVER see the client (owner rule: no half-working
        # browser sessions — on a phone the product IS the app). They get a
        # full-screen install funnel; its "Open the app" hands this exact URL
        # (token included) to the app via intent://, so pairing is one tap.
        # The APK's WebView marks itself in the User-Agent and gets the real
        # client; so do desktop browsers (dev/testing) and any Android hit
        # while no APK is built yet.
        ua = request.headers.get("user-agent", "")
        if "Android" in ua and "RemoteUserApp" not in ua and SETTINGS.apk_path.exists():
            return FileResponse(SETTINGS.client_dir / "install.html")
        return FileResponse(SETTINGS.client_dir / "index.html")

    @app.get("/favicon.ico")
    async def favicon():
        # Browsers probe this on every fresh load; without it every session
        # starts with a 404 in the log. SVG content on an .ico URL is fine —
        # browsers honor the media type.
        return FileResponse(SETTINGS.favicon_path, media_type="image/svg+xml")

    @app.get("/ping")
    async def ping():
        """Reachability probe for the phone's in-page Tailscale wizard: the
        page fetches this (no-cors) on the Tailscale address to detect the
        moment the phone joins the mesh. Reveals nothing but 'server exists'
        (auth still gates every real endpoint)."""
        return Response(status_code=204)

    @app.get("/app.apk")
    async def apk():
        """The Android app, downloaded by the install funnel's Install button —
        the user never shuffles files by hand. Token-free on purpose: the APK
        embeds no secrets (the funnel hands the tokened URL over separately)."""
        if not SETTINGS.apk_path.exists():
            return JSONResponse({"ok": False, "error": "no APK built"}, status_code=404)
        return FileResponse(
            SETTINGS.apk_path,
            media_type="application/vnd.android.package-archive",
            filename="RemoteUser.apk",
        )

    @app.post("/upload")
    async def upload(request: Request, file: UploadFile = File(...)):
        """Phone → PC: decode an image the tablet sent (incl. HEIC — the phone
        camera default), put it in the PC clipboard and PASTE it into the
        focused box right away (Ctrl+V injected — picking the image was the
        whole gesture; the user clicked the target field before choosing it).
        Token-gated like the WebSocket."""
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        data = await file.read()
        img = await asyncio.to_thread(decode_upload, data)
        if img is None:
            # magic bytes identify the format we failed on (e.g. b'ftypheic')
            logger.error("Upload not decodable: %d bytes, name=%r, type=%r, magic=%r",
                         len(data), file.filename, file.content_type, bytes(data[:12]))
            return JSONResponse({"ok": False, "error": "not an image"}, status_code=400)
        ok = await asyncio.to_thread(clipboard.copy_image, img)
        if ok:
            await asyncio.to_thread(injector.press_chord, "ctrl+v")
        return {"ok": ok}

    app.mount("/static", StaticFiles(directory=SETTINGS.client_dir), name="static")

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        if not await _authenticate(ws, token):
            await ws.close(code=4401)
            return
        logger.info("Client authenticated: %s", ws.client)
        stats.clients += 1
        await ws.send_text(json.dumps({"type": "actions", **_load_actions()}))
        tasks = [asyncio.create_task(_send_cursor(ws, injector))]
        queue = None
        if stream.mode == "jpeg":
            await _send_config(ws, stream, token)
            queue = hub.subscribe()
            tasks.append(asyncio.create_task(_send_frames(ws, queue)))
        else:
            tasks.append(asyncio.create_task(_stream_h264(ws, stream, token)))
        try:
            await _receive_input(ws, injector, stream, token)
        except WebSocketDisconnect:
            logger.info("Client disconnected: %s", ws.client)
        finally:
            stats.clients -= 1
            for task in tasks:
                task.cancel()
            if queue is not None:
                hub.unsubscribe(queue)
                stream.set_viewport(0.0, 0.0, 1.0, 1.0)

    return app


async def _authenticate(ws: WebSocket, token: str) -> bool:
    try:
        first = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=5))
    except (asyncio.TimeoutError, json.JSONDecodeError, WebSocketDisconnect):
        logger.warning("Auth failed (no/invalid first message) from %s", ws.client)
        return False
    if first.get("type") != "auth" or first.get("token") != token:
        logger.warning("Auth failed (bad token) from %s", ws.client)
        return False
    return True


async def _send_frames(ws: WebSocket, queue: asyncio.Queue) -> None:
    while True:
        await ws.send_bytes(await queue.get())


async def _stream_h264(ws: WebSocket, manager, token: str) -> None:
    """One H.264 session per iteration: open (fresh init segment + keyframe),
    announce it via `config`, forward chunks until the session ends (monitor
    switch, slow-client reset, encoder death), then open the next. The task is
    cancelled on disconnect; the session always closes."""
    loop = asyncio.get_running_loop()
    while True:
        queue: asyncio.Queue = asyncio.Queue(maxsize=SETTINGS.h264_queue_chunks)

        def push(item, q=queue) -> None:
            # H.264 bytes cannot be dropped individually (the stream would
            # corrupt). A full queue means the client cannot keep up — drop
            # the WHOLE session: clear and sentinel; the loop reopens fresh.
            try:
                q.put_nowait(item)
            except asyncio.QueueFull:
                logger.warning("Client stream backlog — resetting the H.264 session")
                while not q.empty():
                    q.get_nowait()
                q.put_nowait(None)

        started = loop.time()
        try:
            # Default args bind THIS iteration's push — `push` itself rebinds
            # next iteration, and a late callback from a dying session must
            # land in its own (dead) queue, never the fresh session's.
            session = await asyncio.to_thread(
                manager.open_session,
                lambda chunk, p=push: loop.call_soon_threadsafe(p, chunk),
                lambda p=push: loop.call_soon_threadsafe(p, None),
            )
        except (RuntimeError, OSError) as e:
            logger.error("H.264 session failed to open: %s", e)
            await _toast(ws, "Stream failed to start — see server log")
            await ws.close(code=1011)
            return
        try:
            await _send_config(ws, manager, token, codec=session.codec)
            while (chunk := await queue.get()) is not None:
                await ws.send_bytes(chunk)
        except (WebSocketDisconnect, RuntimeError):
            return  # socket closed under us — the receive loop logs the disconnect
        finally:
            # Synchronous on purpose: it must run even mid-cancellation, and it
            # is fast (terminate ffmpeg; capture stop wakes within one frame).
            manager.close_session(session)
        if loop.time() - started < 2.0:
            await asyncio.sleep(1.0)  # a session dying this fast is an error loop — pace it


async def _send_cursor(ws: WebSocket, injector: InputInjector) -> None:
    """Streams the PC cursor position for the client-drawn virtual cursor.
    Sent only on change, quantized to 4 decimals (~0.4 px on 4K)."""
    interval = 1.0 / SETTINGS.cursor_hz
    last = None
    while True:
        pos = injector.cursor_norm()
        if pos is not None:
            rounded = (round(pos[0], 4), round(pos[1], 4))
            if rounded != last:
                last = rounded
                try:
                    await ws.send_text(json.dumps(
                        {"type": "cursor", "x": rounded[0], "y": rounded[1]}
                    ))
                except (WebSocketDisconnect, RuntimeError):
                    return  # socket closed under us — normal lifecycle
        await asyncio.sleep(interval)


def _load_actions() -> dict:
    """Reads the owner's action categories fresh (edits apply on the next
    connect). A missing or invalid file is logged and yields no categories —
    never a crash."""
    empty = {"categories": [], "left": 0, "right": 0}
    try:
        data = json.loads(SETTINGS.actions_path.read_text(encoding="utf-8"))
        return {
            "categories": data.get("categories", []),
            "left": data.get("left", 0),
            "right": data.get("right", 0),
        }
    except FileNotFoundError:
        logger.warning("actions.json not found at %s — no action categories", SETTINGS.actions_path)
        return empty
    except (json.JSONDecodeError, OSError) as e:
        logger.error("actions.json could not be loaded: %s", e)
        return empty


async def _send_config(ws: WebSocket, stream, token: str, codec: str | None = None) -> None:
    # tailscale_url feeds the client's guided "access from anywhere" wizard:
    # null when the PC has no Tailscale yet (the desktop window guides that
    # side); checked fresh per config so a login mid-run shows on reconnect.
    ts_ip = await asyncio.to_thread(pairing.get_tailscale_ip)
    payload = {
        "type": "config",
        "monitor_width": stream.width,
        "monitor_height": stream.height,
        "stream": stream.mode,
        "tailscale_url": f"http://{ts_ip}:{SETTINGS.port}/?token={token}" if ts_ip else None,
        # The phone's update source is THIS PC, never the internet: the shell
        # compares this against its own version and offers /app.apk.
        "app_version": app_version(),
    }
    if codec:
        payload["codec"] = codec
    await ws.send_text(json.dumps(payload))


async def _toast(ws: WebSocket, text: str) -> None:
    await ws.send_text(json.dumps({"type": "toast", "text": text}))


async def _switch_monitor(ws: WebSocket, injector: InputInjector, stream, token: str) -> None:
    count = stream.output_count()
    if count < 2:
        await _toast(ws, "Only one active monitor")
        return
    new_index = (stream.monitor_index + 1) % count
    ok = await asyncio.to_thread(stream.switch_to, new_index)
    if not ok:
        await _toast(ws, "Monitor switch failed — see server log")
        return
    injector.set_monitor_rect(
        monitors.rect_for_size(stream.width, stream.height, stream.monitor_index)
    )
    if stream.mode == "jpeg":
        await _send_config(ws, stream, token)  # H.264 clients get config from their fresh session
    await _toast(ws, f"Monitor {stream.monitor_index + 1}/{count}")


async def _screenshot(ws: WebSocket, stream) -> None:
    frame = await asyncio.to_thread(stream.take_screenshot)
    if frame is None:
        await _toast(ws, "Screenshot failed — see server log")
        return
    ok = await asyncio.to_thread(clipboard.copy_image, frame)
    await _toast(ws, "Screenshot in PC clipboard — paste with right-click" if ok
                 else "Clipboard busy — try again")


async def _receive_input(ws: WebSocket, injector: InputInjector, stream, token: str) -> None:
    while True:
        msg = json.loads(await ws.receive_text())
        kind = msg.get("type")
        if kind in ("pointer_down", "pointer_up", "click"):
            button = msg.get("button", "left")
            if button not in BUTTON_FLAGS:
                logger.error("Unknown button %r from client", button)
                continue
            if kind == "click":
                injector.click(button)  # at the current cursor — no coordinates
                continue
            x, y = float(msg["x"]), float(msg["y"])
            if kind == "pointer_down":
                injector.button_down(x, y, button)
            else:
                injector.button_up(x, y, button)
        elif kind == "pointer_move":
            injector.move(float(msg["x"]), float(msg["y"]))
        elif kind == "scroll":
            injector.wheel(float(msg["x"]), float(msg["y"]), float(msg["ticks"]))
        elif kind == "key_text":
            injector.type_text(str(msg["text"]))
        elif kind == "key_special":
            injector.press_key(str(msg["key"]))
        elif kind == "viewport":
            if stream.mode == "jpeg":
                stream.set_viewport(
                    float(msg["x"]), float(msg["y"]), float(msg["w"]), float(msg["h"])
                )
            # H.264 streams the full frame — a viewport from a stale client is noise
        elif kind == "chord":
            injector.press_chord(str(msg["chord"]))
        elif kind == "monitor_switch":
            await _switch_monitor(ws, injector, stream, token)
        elif kind == "screenshot":
            await _screenshot(ws, stream)
        else:
            logger.warning("Unknown message type %r from client", kind)
