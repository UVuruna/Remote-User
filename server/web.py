"""FastAPI application: serves the client page, streams frames, receives input.

Protocol (see project CLAUDE.md):
- client → server, JSON text: auth, pointer_down, pointer_up, pointer_move,
  scroll, viewport (JPEG mode only), key_text, key_special, chord,
  monitor_switch, screenshot
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
import json
import logging
import struct

import cv2
import numpy as np
from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import clipboard
import monitors
from config import SETTINGS
from input_injector import BUTTON_FLAGS, InputInjector

logger = logging.getLogger(__name__)


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


def create_app(stream, hub: FrameHub | None, injector: InputInjector, token: str) -> FastAPI:
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
    async def index():
        return FileResponse(SETTINGS.client_dir / "index.html")

    @app.post("/upload")
    async def upload(request: Request, file: UploadFile = File(...)):
        """Phone → PC: decode an image the tablet sent and put it in the PC
        clipboard, ready to paste. Token-gated like the WebSocket."""
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        data = await file.read()
        img = await asyncio.to_thread(
            cv2.imdecode, np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR
        )
        if img is None:
            logger.error("Upload could not be decoded as an image (%d bytes)", len(data))
            return JSONResponse({"ok": False, "error": "not an image"}, status_code=400)
        ok = await asyncio.to_thread(clipboard.copy_image, img)
        return {"ok": ok}

    app.mount("/static", StaticFiles(directory=SETTINGS.client_dir), name="static")

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        if not await _authenticate(ws, token):
            await ws.close(code=4401)
            return
        logger.info("Client authenticated: %s", ws.client)
        await ws.send_text(json.dumps({"type": "actions", **_load_actions()}))
        tasks = [asyncio.create_task(_send_cursor(ws, injector))]
        queue = None
        if stream.mode == "jpeg":
            await _send_config(ws, stream)
            queue = hub.subscribe()
            tasks.append(asyncio.create_task(_send_frames(ws, queue)))
        else:
            tasks.append(asyncio.create_task(_stream_h264(ws, stream)))
        try:
            await _receive_input(ws, injector, stream)
        except WebSocketDisconnect:
            logger.info("Client disconnected: %s", ws.client)
        finally:
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


async def _stream_h264(ws: WebSocket, manager) -> None:
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
            await _send_config(ws, manager, codec=session.codec)
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


async def _send_config(ws: WebSocket, stream, codec: str | None = None) -> None:
    payload = {
        "type": "config",
        "monitor_width": stream.width,
        "monitor_height": stream.height,
        "stream": stream.mode,
    }
    if codec:
        payload["codec"] = codec
    await ws.send_text(json.dumps(payload))


async def _toast(ws: WebSocket, text: str) -> None:
    await ws.send_text(json.dumps({"type": "toast", "text": text}))


async def _switch_monitor(ws: WebSocket, injector: InputInjector, stream) -> None:
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
        await _send_config(ws, stream)  # H.264 clients get config from their fresh session
    await _toast(ws, f"Monitor {stream.monitor_index + 1}/{count}")


async def _screenshot(ws: WebSocket, stream) -> None:
    frame = await asyncio.to_thread(stream.take_screenshot)
    if frame is None:
        await _toast(ws, "Screenshot failed — see server log")
        return
    ok = await asyncio.to_thread(clipboard.copy_image, frame)
    await _toast(ws, "Screenshot in PC clipboard — paste with right-click" if ok
                 else "Clipboard busy — try again")


async def _receive_input(ws: WebSocket, injector: InputInjector, stream) -> None:
    while True:
        msg = json.loads(await ws.receive_text())
        kind = msg.get("type")
        if kind in ("pointer_down", "pointer_up"):
            button = msg.get("button", "left")
            if button not in BUTTON_FLAGS:
                logger.error("Unknown button %r from client", button)
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
            await _switch_monitor(ws, injector, stream)
        elif kind == "screenshot":
            await _screenshot(ws, stream)
        else:
            logger.warning("Unknown message type %r from client", kind)
