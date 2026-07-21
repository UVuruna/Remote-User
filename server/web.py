"""FastAPI application: serves the client page, streams frames, receives input.

Protocol (see project CLAUDE.md):
- client -> server, JSON text: auth, pointer_down, pointer_up, pointer_move,
  scroll, viewport
- server -> client: one JSON text `config` message after auth (monitor size),
  then binary frames: 16-byte header (4 x float32 LE — the monitor-normalized
  x, y, w, h region the frame covers) followed by the JPEG bytes

No message is processed before a valid `auth` — hard security rule.
"""

import asyncio
import json
import logging
import struct

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import clipboard
import monitors
from capture import ScreenStreamer
from config import SETTINGS
from input_injector import BUTTON_FLAGS, InputInjector

logger = logging.getLogger(__name__)


class FrameHub:
    """Fans frames from the capture thread out to client queues, dropping stale ones."""

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


def create_app(
    hub: FrameHub, injector: InputInjector, streamer: ScreenStreamer, token: str
) -> FastAPI:
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

    app.mount("/static", StaticFiles(directory=SETTINGS.client_dir), name="static")

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        if not await _authenticate(ws, token):
            await ws.close(code=4401)
            return
        logger.info("Client authenticated: %s", ws.client)
        await _send_config(ws, streamer)
        await ws.send_text(json.dumps({"type": "actions", "sets": _load_actions()}))
        queue = hub.subscribe()
        sender = asyncio.create_task(_send_frames(ws, queue))
        try:
            await _receive_input(ws, injector, streamer)
        except WebSocketDisconnect:
            logger.info("Client disconnected: %s", ws.client)
        finally:
            sender.cancel()
            hub.unsubscribe(queue)
            streamer.set_viewport(0.0, 0.0, 1.0, 1.0)

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


def _load_actions() -> list:
    """Reads the owner's action sets fresh (edits apply on the next connect).
    A missing or invalid file is logged and yields no sets — never a crash."""
    try:
        data = json.loads(SETTINGS.actions_path.read_text(encoding="utf-8"))
        return data.get("sets", [])
    except FileNotFoundError:
        logger.warning("actions.json not found at %s — no action sets", SETTINGS.actions_path)
        return []
    except (json.JSONDecodeError, OSError) as e:
        logger.error("actions.json could not be loaded: %s", e)
        return []


async def _send_config(ws: WebSocket, streamer: ScreenStreamer) -> None:
    await ws.send_text(json.dumps({
        "type": "config",
        "monitor_width": streamer.width,
        "monitor_height": streamer.height,
    }))


async def _toast(ws: WebSocket, text: str) -> None:
    await ws.send_text(json.dumps({"type": "toast", "text": text}))


async def _switch_monitor(ws: WebSocket, injector: InputInjector, streamer: ScreenStreamer) -> None:
    count = ScreenStreamer.output_count()
    if count < 2:
        await _toast(ws, "Only one active monitor")
        return
    new_index = (streamer.monitor_index + 1) % count
    streamer.stop()
    if streamer.switch_monitor(new_index):
        injector.set_monitor_rect(monitors.rect_for_size(streamer.width, streamer.height, new_index))
    streamer.start()
    await _send_config(ws, streamer)
    await _toast(ws, f"Monitor {streamer.monitor_index + 1}/{count}")


async def _screenshot(ws: WebSocket, streamer: ScreenStreamer) -> None:
    frame = await asyncio.to_thread(streamer.take_screenshot)
    if frame is None:
        await _toast(ws, "Screenshot failed — see server log")
        return
    ok = await asyncio.to_thread(clipboard.copy_image, frame)
    await _toast(ws, "Screenshot in PC clipboard — paste with right-click" if ok
                 else "Clipboard busy — try again")


async def _receive_input(ws: WebSocket, injector: InputInjector, streamer: ScreenStreamer) -> None:
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
            streamer.set_viewport(
                float(msg["x"]), float(msg["y"]), float(msg["w"]), float(msg["h"])
            )
        elif kind == "chord":
            injector.press_chord(str(msg["chord"]))
        elif kind == "monitor_switch":
            await _switch_monitor(ws, injector, streamer)
        elif kind == "screenshot":
            await _screenshot(ws, streamer)
        else:
            logger.warning("Unknown message type %r from client", kind)
