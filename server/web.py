"""FastAPI application: serves the client page, streams frames, receives input.

Protocol (see project CLAUDE.md):
- client -> server, JSON text: auth, pointer_down, pointer_up, pointer_move
- server -> client, binary: one JPEG per message

No message is processed before a valid `auth` — hard security rule.
"""

import asyncio
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

    def push_threadsafe(self, jpeg: bytes) -> None:
        """Called from the capture thread. A slow client keeps only the newest frame."""
        self._loop.call_soon_threadsafe(self._push, jpeg)

    def _push(self, jpeg: bytes) -> None:
        for q in self._queues:
            if q.full():
                q.get_nowait()
            q.put_nowait(jpeg)


def create_app(hub: FrameHub, injector: InputInjector, token: str) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

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
        queue = hub.subscribe()
        sender = asyncio.create_task(_send_frames(ws, queue))
        try:
            await _receive_input(ws, injector)
        except WebSocketDisconnect:
            logger.info("Client disconnected: %s", ws.client)
        finally:
            sender.cancel()
            hub.unsubscribe(queue)

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


async def _receive_input(ws: WebSocket, injector: InputInjector) -> None:
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
        else:
            logger.warning("Unknown message type %r from client", kind)
