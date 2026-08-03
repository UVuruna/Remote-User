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
import uia
import window_manager
from config import SETTINGS, apk_version, app_version
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
        # NO browser EVER sees the client (owner rule, hardened 2026-08-02
        # after the tablet failure): Chrome on Android TABLETS presents a
        # desktop-Linux User-Agent with no "Android" token at all, so any
        # detect-Android routing silently serves the live client in a browser
        # — the exact forbidden half-experience. Therefore the client goes
        # ONLY to the APK's WebView (it appends the RemoteUserApp marker);
        # every other User-Agent, on every device, gets the install funnel,
        # whose "Open the app" hands this exact URL (token included) to the
        # app via intent:// — pairing stays one tap. Sole exception: a dev
        # checkout with no APK built yet, where the funnel would have nothing
        # to offer (official installers always bundle the APK).
        ua = request.headers.get("user-agent", "")
        if "RemoteUserApp" not in ua and SETTINGS.apk_path.exists():
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

    # Layouts live for the SERVER's lifetime (owner 2026-08-02): the phone may
    # disconnect and return, the slider list survives. One registry per app.
    layouts = window_manager.LayoutRegistry()
    # One device at a time (owner 2026-08-02 — tablet and phone must never
    # drive the PC together): the newest authenticated socket wins, the
    # previous one is closed with 4409 and its client stops auto-reconnecting.
    active_client: dict = {"ws": None}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        first = await _authenticate(ws, token)
        if first is None:
            await ws.close(code=4401)
            return
        logger.info("Client authenticated: %s", ws.client)
        prev = active_client["ws"]
        active_client["ws"] = ws
        if prev is not None:
            try:
                await prev.close(code=4409)  # taken over by this device
            except RuntimeError:
                pass  # already closing
        stats.clients += 1
        # The device's short/long side ratio — layout placement turns it into
        # a real aspect per the layout's chosen orientation.
        screen = first.get("screen") or {}
        try:
            w, h = float(screen.get("w", 9)), float(screen.get("h", 16))
            ratio = min(w, h) / max(w, h) if w > 0 and h > 0 else 9 / 16
        except (TypeError, ValueError):
            ratio = 9 / 16
        conn = {"ratio": ratio, "active": None, "region": None, "reduced": False}
        await ws.send_text(json.dumps({"type": "actions", **_load_actions()}))
        await _send_layout_state(ws, layouts, conn)
        tasks = [asyncio.create_task(_send_cursor(ws, injector))]
        queue = None
        if stream.mode == "jpeg":
            await _send_config(ws, stream, token)
            queue = hub.subscribe()
            tasks.append(asyncio.create_task(_send_frames(ws, queue)))
        else:
            tasks.append(asyncio.create_task(_stream_h264(ws, stream, token, conn)))
        try:
            await _receive_input(ws, injector, stream, token, layouts, conn)
        except WebSocketDisconnect:
            logger.info("Client disconnected: %s", ws.client)
        finally:
            stats.clients -= 1
            if active_client["ws"] is ws:
                active_client["ws"] = None
            for task in tasks:
                task.cancel()
            if queue is not None:
                hub.unsubscribe(queue)
                stream.set_viewport(0.0, 0.0, 1.0, 1.0)

    return app


async def _authenticate(ws: WebSocket, token: str) -> dict | None:
    """Returns the auth message (it may carry the device's `screen` size for
    layout placement) — None on failure."""
    try:
        first = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=5))
    except (asyncio.TimeoutError, json.JSONDecodeError, WebSocketDisconnect):
        logger.warning("Auth failed (no/invalid first message) from %s", ws.client)
        return None
    if first.get("type") != "auth" or first.get("token") != token:
        logger.warning("Auth failed (bad token) from %s", ws.client)
        return None
    return first


async def _send_frames(ws: WebSocket, queue: asyncio.Queue) -> None:
    while True:
        await ws.send_bytes(await queue.get())


async def _stream_h264(ws: WebSocket, manager, token: str,
                       conn: dict | None = None) -> None:
    """One H.264 session per iteration: open (fresh init segment + keyframe),
    announce it via `config`, forward chunks until the session ends (monitor
    switch, slow-client reset, quality change, encoder death), then open the
    next. The task is cancelled on disconnect; the session always closes."""
    conn = conn if conn is not None else {}
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

        # The quality handler ends the CURRENT session through this hook —
        # the loop then reopens with the new reduced/full encoder settings.
        conn["reset_stream"] = lambda p=push: loop.call_soon_threadsafe(p, None)
        started = loop.time()
        try:
            # Default args bind THIS iteration's push — `push` itself rebinds
            # next iteration, and a late callback from a dying session must
            # land in its own (dead) queue, never the fresh session's.
            session = await asyncio.to_thread(
                manager.open_session,
                lambda chunk, p=push: loop.call_soon_threadsafe(p, chunk),
                lambda p=push: loop.call_soon_threadsafe(p, None),
                conn.get("reduced", False),
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


INPUT_BLOCKED_TOAST = (
    "The PC is blocking remote input — an administrator window or the lock "
    "screen has focus on the PC."
)


async def _send_cursor(ws: WebSocket, injector: InputInjector) -> None:
    """Streams the PC cursor position for the client-drawn virtual cursor.
    Sent only on change, quantized to 4 decimals (~0.4 px on 4K).

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
                if rounded != last:
                    last = rounded
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
        "hand": SETTINGS.hand,
        "tailscale_url": f"http://{ts_ip}:{SETTINGS.port}/?token={token}" if ts_ip else None,
        # The phone's update source is THIS PC, never the internet. The
        # banner compares against apk_version — the version of the APK this
        # server actually serves (app_version nagged forever on desktop-only
        # releases); app_version stays for display/diagnostics.
        "app_version": app_version(),
        "apk_version": apk_version(),
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


def _mon_rect(stream) -> tuple[int, int, int, int]:
    return monitors.rect_for_size(stream.width, stream.height, stream.monitor_index)


async def _send_layout_state(ws: WebSocket, layouts, conn: dict) -> None:
    state = await asyncio.to_thread(layouts.state, conn["active"], conn["region"])
    if state["active"] is None:
        conn["active"], conn["region"] = None, None  # pruned under us
    await ws.send_text(json.dumps(state))


async def _layout_pick(ws: WebSocket, layouts, stream, msg: dict) -> None:
    """The phone's armed tap: identify the window under the point and offer
    the layout choices (solo / grid templates + open windows to fill cells)."""
    x, y = float(msg["x"]), float(msg["y"])
    target = await asyncio.to_thread(
        window_manager.window_at, _mon_rect(stream), x, y)
    if target is None:
        await _toast(ws, "No window there — tap on a window")
        return
    # Tab under the same point (step 2): the offer names it, and the client
    # echoes the pick point back in layout_create so extraction re-finds it.
    # Grid cells are picked by FURTHER taps (owner 2026-08-02), so no window
    # list rides along here — the list-based source is `layout_list`.
    # Only tab-capable apps are asked (owner 2026-08-03) — everything else's
    # TabItems are internal section switchers that cannot become a window.
    tab = None
    if uia.has_tabs(target["process"]):
        tab = await asyncio.to_thread(uia.tab_at, _mon_rect(stream), x, y)
    await ws.send_text(json.dumps({
        "type": "layout_offer",
        "target": target,
        "tab": tab,
        "x": x, "y": y,
        "grids": list(window_manager.GRID_TEMPLATES),
    }))


async def _layout_list(ws: WebSocket, layouts, stream) -> None:
    """The list-based creation source (owner 2026-08-02): every open window
    PLUS each window's content tabs as separate entries — 'Google Chrome'
    alone hid its tabs, the exact reported gap. Windows that already belong to
    a layout are LEFT OUT (owner 2026-08-03): one window cannot be shown in
    two places, so it stays off the list for as long as it is in a layout."""
    mon_rect = _mon_rect(stream)
    used = await asyncio.to_thread(layouts.member_hwnds)
    windows = await asyncio.to_thread(window_manager.list_windows, used)
    entries = []
    for w in windows:
        entries.append({"kind": "window", "hwnd": w["hwnd"], "title": w["title"],
                        "process": w["process"], "icon": w["icon"]})
        if not uia.has_tabs(w["process"]):
            continue  # its TabItems are internal sections, not real tabs
        for tab in await asyncio.to_thread(uia.list_tabs, mon_rect, w["hwnd"]):
            entries.append({"kind": "tab", "hwnd": w["hwnd"],
                            "tab": {"name": tab["name"]},
                            "x": tab["x"], "y": tab["y"],
                            "title": tab["name"],
                            "process": w["process"], "icon": w["icon"]})
    await ws.send_text(json.dumps({
        "type": "layout_offer",
        "target": None,
        "entries": entries,
        "grids": list(window_manager.GRID_TEMPLATES),
    }))


async def _resolve_slot(ws: WebSocket, stream, slot: dict) -> tuple[int, str | None] | None:
    """One creation slot → a concrete hwnd. A slot naming a TAB is extracted
    into its own window first (app command → Explorer path → drag); every
    failure falls back to the slot's whole window."""
    hwnd = int(slot["hwnd"])
    tab = slot.get("tab")
    if not tab:
        return (hwnd, None)
    info = await asyncio.to_thread(window_manager.window_at_hwnd, hwnd)
    if info is None:
        return None
    extracted = await asyncio.to_thread(
        uia.extract_tab, _mon_rect(stream),
        float(slot.get("x", 0.5)), float(slot.get("y", 0.5)),
        info, tab.get("name"))
    if extracted is None:
        await _toast(ws, f"Could not separate “{tab.get('name', 'tab')}” — using the whole window")
        return (hwnd, None)
    return (extracted, tab.get("name"))


async def _layout_create(ws: WebSocket, layouts, stream, conn: dict, msg: dict) -> None:
    orient = "wide" if msg.get("orient") == "wide" else "portrait"
    slots = msg.get("slots") or []
    if not slots:
        await _toast(ws, "Nothing selected — layout not created")
        await _send_layout_state(ws, layouts, conn)
        return
    resolved: list[tuple[int, str | None]] = []
    for i, slot in enumerate(slots):
        r = await _resolve_slot(ws, stream, slot)
        if r is not None:
            resolved.append(r)
        # one turn of the phone's loading cube per processed window
        await ws.send_text(json.dumps(
            {"type": "layout_progress", "done": i + 1, "total": len(slots)}))
    if not resolved:
        await _toast(ws, "Those windows are gone — layout not created")
        await _send_layout_state(ws, layouts, conn)
        return
    target, name = resolved[0]
    index = await asyncio.to_thread(
        layouts.create, target, str(msg.get("mode", "solo")),
        msg.get("grid"), [h for h, _ in resolved[1:]],
        orient, conn["ratio"], _mon_rect(stream), name)
    if index is None:
        await _toast(ws, "That window is gone — layout not created")
    else:
        await _layout_focus(ws, layouts, stream, conn, index)
        return
    await _send_layout_state(ws, layouts, conn)


async def _layout_aspect(ws: WebSocket, layouts, stream, conn: dict, msg: dict) -> None:
    """The phone's Aspect panel (owner 2026-08-03): store this layout's W:H
    (0/0 = back to the phone's own shape) and focus it — the focus is what
    re-places the windows into the new region."""
    index = int(msg["index"])
    w, h = int(msg.get("w") or 0), int(msg.get("h") or 0)
    if not await asyncio.to_thread(layouts.set_ratio, index, w, h):
        await _toast(ws, "That layout is gone")
        await _send_layout_state(ws, layouts, conn)
        return
    await _layout_focus(ws, layouts, stream, conn, index)


async def _layout_focus(ws: WebSocket, layouts, stream, conn: dict, index: int) -> None:
    """index -1 = back to the full desktop. Region is re-read fresh on every
    focus — desk-side moves/resizes never break a layout (owner rule)."""
    if index < 0:
        conn["active"], conn["region"] = None, None
        # Desktop position minimizes every layout member — the desktop shows
        # only the windows that are NOT layout material (owner 2026-08-02).
        await asyncio.to_thread(layouts.minimize_members)
    else:
        region = await asyncio.to_thread(
            layouts.focus, index, conn["ratio"], _mon_rect(stream))
        if region is None:
            conn["active"], conn["region"] = None, None
            await _toast(ws, "That layout's window is gone")
        else:
            conn["active"], conn["region"] = index, region
    await _send_layout_state(ws, layouts, conn)


async def _receive_input(ws: WebSocket, injector: InputInjector, stream, token: str,
                         layouts=None, conn: dict | None = None) -> None:
    conn = conn if conn is not None else {"ratio": 9 / 16, "active": None, "region": None}
    layouts = layouts if layouts is not None else window_manager.LayoutRegistry()
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
        elif kind == "layout_pick":
            await _layout_pick(ws, layouts, stream, msg)
        elif kind == "layout_list":
            await _layout_list(ws, layouts, stream)
        elif kind == "next_input":
            # Scope follows the view (owner spec): layout focus → only its
            # member windows; full desktop → every visible window.
            hwnds = None
            if conn["active"] is not None and 0 <= conn["active"] < len(layouts.layouts):
                hwnds = list(layouts.layouts[conn["active"]].members)
            name = await asyncio.to_thread(uia.focus_next_input, hwnds)
            label = (name or "")[:40]
            await _toast(ws, f"→ {label}" if name else "No text boxes found")
        elif kind == "quality":
            # Full vs reduced stream (owner spec: lower resolution + ~10 fps,
            # chosen always or only on mobile data — the CLIENT decides when
            # and just tells us the effective state). H.264: the running
            # session is reset and reopens with the reduced encoder settings.
            conn["reduced"] = bool(msg.get("reduced"))
            if stream.mode == "h264" and conn.get("reset_stream"):
                conn["reset_stream"]()
            await _toast(ws, "Reduced quality — saving data" if conn["reduced"]
                         else "Full quality")
        elif kind == "layout_create":
            await _layout_create(ws, layouts, stream, conn, msg)
        elif kind == "layout_aspect":
            await _layout_aspect(ws, layouts, stream, conn, msg)
        elif kind == "layout_focus":
            await _layout_focus(ws, layouts, stream, conn, int(msg["index"]))
        elif kind == "layout_remove":
            index = int(msg["index"])
            await asyncio.to_thread(layouts.remove, index)
            if conn["active"] is not None:
                if conn["active"] == index:
                    conn["active"], conn["region"] = None, None
                elif conn["active"] > index:
                    conn["active"] -= 1
            await _send_layout_state(ws, layouts, conn)
        else:
            logger.warning("Unknown message type %r from client", kind)
