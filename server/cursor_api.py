"""The cursor stream — the PC pointer's POSITION and SHAPE for the phone's
client-drawn virtual cursor, and the injector's self-check alarm ride-along.

Moved out of `web.py` on 2026-08-15 (THE STRUCTURE LAW: web.py stood at the
1,000-line wall) as its own module by responsibility: this is the one sender
of the `cursor` message, exactly as `config_api.py` is the one sender of
`config`. `web.py` imports `send_cursor` under its old `_send_cursor` name,
so the call site and `tests/test_cursor_shape.py` read unchanged.
"""

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

import cursor_shape
from config import SETTINGS

INPUT_BLOCKED_TOAST = (
    "The PC is blocking remote input — an administrator window or the lock "
    "screen has focus on the PC."
)


async def send_cursor(ws: WebSocket, injector) -> None:
    """Streams the PC cursor position AND ITS SHAPE for the client-drawn
    virtual cursor. Sent only on change, position quantized to 4 decimals
    (~0.4 px on 4K).

    The shape rides as an OPTIONAL `shape` field on this same message (owner
    request 2026-08-09, task 142 — a resize cursor at a window edge is how a
    person knows the edge is grabbable, and one fixed arrow told him nothing).
    Never its own message type and never an image: a page that predates the
    field simply ignores it, and a phone that has never heard of a name draws
    the arrow it always drew. A name the PC cannot read at all (secure
    desktop) is left OFF the wire rather than guessed.

    Also the delivery path for the injector's self-check alarm: when Windows
    eats injected input (UIPI — the 2026-07-29 dead-mouse failure), the phone
    must SAY so instead of looking healthy over a dead session."""
    interval = 1.0 / SETTINGS.cursor_hz
    last = None
    while True:
        try:
            if injector.take_input_alarm():
                await ws.send_text(json.dumps(
                    {"type": "toast", "text": INPUT_BLOCKED_TOAST}
                ))
            pos = injector.cursor_norm()
            if pos is not None:
                rounded = (round(pos[0], 4), round(pos[1], 4))
                shape = cursor_shape.current_cursor_name()
                # The SHAPE is part of "changed" — hovering a window edge
                # without moving a pixel still has to reach the phone — but
                # it never adds a frame: the cadence is this loop's, unchanged.
                if (rounded, shape) != last:
                    last = (rounded, shape)
                    frame = {"type": "cursor", "x": rounded[0], "y": rounded[1]}
                    if shape:
                        frame["shape"] = shape
                    await ws.send_text(json.dumps(frame))
        except (WebSocketDisconnect, RuntimeError):
            return  # socket closed under us — normal lifecycle
        await asyncio.sleep(interval)
