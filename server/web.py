"""FastAPI application: serves the client page, streams frames, receives input.

Protocol (see project CLAUDE.md):
- client → server, JSON text: auth, pointer_down, pointer_up, click (at the
  current cursor, no coordinates), press (one half of a CLICK/HOLD mouse
  button — down on finger-land, up on lift, at the current cursor),
  pointer_move, scroll (vertical `ticks` + optional horizontal `hticks`),
  viewport (JPEG mode only), key_text, key_special,
  chord, monitor_switch, screenshot (optionally with the region the phone
  views + paste=true — crops and injects Ctrl+V), tts_info (the voices the
  phone can speak with, once per connection — the desktop Settings window
  draws its Voice dropdown from them)
- server → client, JSON text: `config` after auth and after every stream
  (re)start — monitor size plus `stream` ("h264" | "jpeg") and, in H.264 mode,
  the MSE `codec` string parsed from the live init segment; `actions` (radial
  sets); `toast` notices; `cursor` (the pointer no DXGI frame contains) and
  `caret` (the row being typed into, or unknown) — both only on change.
- server → client, binary:
  - H.264 mode: the raw fMP4 byte stream — the client appends it into MSE.
  - JPEG mode: 16-byte header (4 × float32 LE — monitor-normalized x, y, w, h
    of the covered region) + JPEG bytes.

No message is processed before a valid `auth` — hard security rule.

The `stream` argument everywhere is either an H264Manager or a JpegStreamer —
one duck interface: mode, width, height, monitor_index, output_count(),
switch_to(), take_screenshot(); the JPEG side adds set_viewport() plus
start()/stop() (its capture runs on demand, driven by FrameHub.subscribers),
the H.264 side new_owner()/open_session()/close_session().
"""

import asyncio
import io
import json
import logging
import shutil
import struct
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pillow_heif
from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps

import caret
import clipboard
import config
import focus_guard
import layout_api
import monitors
import notify
import pairing
import presence
import traffic
import uia
import window_manager
from config import SETTINGS, apk_version, app_version, ui_config
from input_injector import BUTTON_FLAGS, InputInjector
from layout_api import toast as _toast

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


# Presence — the phone's heartbeat, its parting word, and the rule that the
# owner's own desk outranks both — lives in `presence.py` (split 2026-08-05,
# THE STRUCTURE LAW: one responsibility, its own failure history, its own
# gate in tests/test_presence.py). Its timings live there too.

# --- Typed commands (owner 2026-08-05) --------------------------------------
# A `paste_text` button pastes and then presses Enter. The pause between them
# is not cosmetic: the target app (Claude's prompt, a search box) reacts to
# the paste — filtering a command menu, resizing its input — and an Enter
# delivered inside that reaction lands in the old state.
PASTE_ENTER_DELAY = 0.12


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

    @property
    def subscribers(self) -> int:
        """How many clients are actually being fed — the JPEG capture runs on
        demand off this number, exactly as the H.264 path already does. It
        used to start with the SERVER and stop with it, so the fallback mode
        captured and encoded 30 frames a second at an empty room, all night
        (audit 2026-08-05)."""
        return len(self._queues)

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
               stats: ServerStats | None = None, layouts=None) -> FastAPI:
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
        traffic.METER.add_in(len(data))  # phone -> PC counts wherever it enters
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

    @app.post("/upload_files")
    async def upload_files(request: Request, files: list[UploadFile] = File(...)):
        """Phone → PC, the multi-file / any-type path (owner 2026-08-04):
        several gallery images, or a PDF from the phone's Files — saved to a
        temp drop folder, put on the clipboard as REAL files (CF_HDROP) and
        pasted right away, exactly like Copy in Explorer + Ctrl+V. A single
        image goes through /upload instead (bitmap — image boxes need that).
        Token-gated like the WebSocket."""
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        drop = Path(tempfile.gettempdir()) / "RemoteUserDrop"
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

    app.mount("/static", StaticFiles(directory=SETTINGS.client_dir), name="static")

    # Layouts live for the SERVER's lifetime (owner 2026-08-02): the phone may
    # disconnect and return, the slider list survives. The caller may hand one
    # in so it survives a RESTART too (Apply & restart used to build a fresh
    # empty registry, losing both the owner's layouts and the only in-memory
    # list of which windows were still always-on-top — audit 2026-08-05), and
    # `app.state` publishes it so teardown can reach it without the closure.
    layouts = layouts if layouts is not None else window_manager.LayoutRegistry()
    app.state.layouts = layouts
    # One device at a time (owner 2026-08-02 — tablet and phone must never
    # drive the PC together): the newest authenticated socket wins, the
    # previous one is closed with 4409 and its client stops auto-reconnecting.
    active_client: dict = {"ws": None}
    # "The PC calls you" (ROADMAP Phase H, owner 2026-08-05): anything on this
    # machine that finishes a job POSTs /notify, and the phone raises a real
    # notification naming the AGENT. It rides the same one-device slot above,
    # so a device that took the session over is the one that hears about it.
    notify.register(app, token, active_client)

    # An excursion hold outlives the socket that announced it, so its task
    # needs an owner here — a bare create_task is only referenced by the event
    # loop while it runs and may be garbage-collected mid-sleep, which would
    # silently skip the very release it exists for.
    holds: set = set()

    @app.websocket("/ws")
    async def ws_endpoint(raw_ws: WebSocket):
        await raw_ws.accept()
        # Every byte to and from this phone is counted from here on (owner's
        # traffic monitor 2026-08-05). Wrapping the socket ONCE is what makes
        # the measurement complete — counters added at each send call site
        # would measure most of the traffic, and "most" settles nothing.
        ws = traffic.MeteredSocket(raw_ws, traffic.METER)
        first = await _authenticate(ws, token)
        if first is None:
            await ws.close(code=4401)
            return
        logger.info("Client authenticated: %s", ws.client)
        prev = active_client["ws"]
        active_client["ws"] = ws
        if prev is not None:
            # Bounded, and never inline-blocking: the previous socket is very
            # often THIS SAME PHONE on a route that has died, so its 4409 may
            # have nowhere to go (presence.hand_over).
            await presence.hand_over(prev)
        # A hold armed by an EARLIER connection must not fire into this one:
        # its only test was "no client connected", which is equally true in
        # every ordinary reconnect gap, so a stale one would minimize the
        # layout the owner is looking at right now (audit 2026-08-05).
        for hold in list(holds):
            hold.cancel()
        stats.clients += 1
        traffic.METER.set_clients(stats.clients)
        # The device's short/long side ratio — layout placement turns it into
        # a real aspect per the layout's chosen orientation.
        screen = first.get("screen") or {}
        try:
            w, h = float(screen.get("w", 9)), float(screen.get("h", 16))
            ratio = min(w, h) / max(w, h) if w > 0 and h > 0 else 9 / 16
        except (TypeError, ValueError):
            ratio = 9 / 16
        conn = {"ratio": ratio, "active": None, "region": None, "quality": None,
                # presence: when we last heard from the phone, and whether it
                # announced an excursion on its way out (see presence.py)
                "seen": time.monotonic(), "away": None, "left": False,
                # focus_guard: which window this connection's typed input goes
                # to. Stale = the next key re-reads the foreground and arms it.
                "pin": None, "pin_stale": True}
        tasks: list = []
        queue = None
        # EVERYTHING that can raise a window lives inside this try (audit
        # 2026-08-05): the resume-focus below puts members into the
        # always-on-top band, and it used to sit OUTSIDE, so one exception
        # anywhere in the setup left them there with no finally to lower them.
        try:
            await ws.send_text(json.dumps({"type": "actions", **_load_actions()}))
            # Whatever finished while the phone was away (owner 2026-08-06):
            # two agents finished while he was on a call with the app closed
            # and both notices were thrown away. They wait now, briefly, and
            # arrive the moment he comes back — each carrying the time it
            # actually happened.
            await notify.send_pending(ws)
            await layout_api.send_layout_state(ws, layouts, conn)
            # Coming back resumes the layout the phone was last working in
            # (owner 2026-08-05) — leaving work mode minimized them, and the
            # desktop is NOT where the owner left off. Only a deliberate
            # desktop choice (which forgets the pointer) resumes on the desktop.
            resume = await asyncio.to_thread(layouts.resume_index)
            if resume is not None:
                await layout_api.layout_focus(ws, layouts, stream, conn, resume)
            tasks.append(asyncio.create_task(_send_cursor(ws, injector)))
            tasks.append(asyncio.create_task(caret.watch(ws, layouts, conn, injector)))
            tasks.append(asyncio.create_task(presence.watchdog(ws, layouts, conn, active_client)))
            # Nothing may take the keyboard out of the layout the phone is
            # showing (owner decree 2026-08-06) — defended continuously, not
            # only when a key arrives: dictation delivers at the END of a
            # round, so a thief that strikes mid-sentence destroys the whole
            # utterance instead of misplacing it.
            tasks.append(asyncio.create_task(focus_guard.watch(layouts, conn)))
            if stream.mode == "jpeg":
                await _send_config(ws, stream, token)
                queue = hub.subscribe()
                if hub.subscribers == 1:
                    await asyncio.to_thread(stream.start)  # first watcher
                tasks.append(asyncio.create_task(_send_frames(ws, queue)))
            else:
                tasks.append(asyncio.create_task(_stream_h264(ws, stream, token, conn)))
            await _receive_input(ws, injector, stream, token, layouts, conn)
        except WebSocketDisconnect:
            logger.info("Client disconnected: %s", ws.client)
        finally:
            stats.clients -= 1
            traffic.METER.set_clients(stats.clients)
            if active_client["ws"] is ws:
                active_client["ws"] = None
                # Nobody is watching any layout now. Only the LAST socket does
                # this: on a 4409 takeover the new device may be mid-focus.
                # An announced EXCURSION is not a leave — the owner is picking
                # an image and comes right back; the backstop covers the
                # excursion that never returns, and his own keyboard at this
                # PC cuts even that short (presence.py).
                if conn.get("away"):
                    logger.info("Phone away on an excursion — layout held")
                    hold = asyncio.create_task(
                        presence.excursion_backstop(layouts, active_client))
                    holds.add(hold)
                    hold.add_done_callback(holds.discard)
                else:
                    await presence.leave_session(layouts, conn)
            for task in tasks:
                task.cancel()
            if queue is not None:
                hub.unsubscribe(queue)
                stream.set_viewport(0.0, 0.0, 1.0, 1.0)
                if hub.subscribers == 0:
                    await asyncio.to_thread(stream.stop)  # nobody left to feed

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
        # The phone said it is gone. Capture, ffmpeg and the socket all stay
        # idle until it says otherwise — a stream nobody can see is exactly
        # the traffic the owner went looking for (owner 2026-08-05).
        while conn.get("paused"):
            await asyncio.sleep(0.25)
        queue: asyncio.Queue = asyncio.Queue(maxsize=SETTINGS.h264_queue_chunks)
        # This iteration's CLAIM on its session, made on the event loop BEFORE
        # the encoder thread exists — `asyncio.to_thread` cannot cancel the
        # thread it started (h264_streamer.SessionOwner; live 2026-08-07).
        owner = manager.new_owner()

        def push(item, q=queue, o=owner) -> None:
            # H.264 bytes cannot be dropped individually (the stream would
            # corrupt). A full queue means the client cannot keep up — drop
            # the WHOLE session: clear and sentinel; the loop reopens fresh.
            # A released claim means nothing reads this queue ever again: that
            # backlog is a DEAD phone, not a slow one (see SessionOwner).
            if not o.alive:
                return
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
                conn.get("quality"),
                owner,
            )
        except (RuntimeError, OSError) as e:
            owner.release()
            logger.error("H.264 session failed to open: %s", e)
            await _toast(ws, "Stream failed to start — see server log")
            await ws.close(code=1011)
            return
        except BaseException:
            # Cancellation lands HERE (socket death, 4409 takeover, server
            # stop) and the ffmpeg spawn it interrupted runs on regardless.
            # Releasing the claim closes whatever that thread produces.
            owner.release()
            raise
        try:
            await _send_config(ws, manager, token, codec=session.codec)
            while (chunk := await queue.get()) is not None:
                await ws.send_bytes(chunk)
        except (WebSocketDisconnect, RuntimeError):
            return  # socket closed under us — the receive loop logs the disconnect
        finally:
            # Synchronous on purpose: it must run even mid-cancellation, and it
            # is fast (terminate ffmpeg; capture stop wakes within one frame).
            # One call closes the session AND silences the queue closure, so
            # the two can never disagree about who is gone.
            owner.release()
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


_shipped_pools_merged = False


def _merge_shipped_actions() -> None:
    """Owner round 4 (2026-08-05): the Controls editor merges a NEW version's
    shipped pools into the owner's %LOCALAPPDATA% actions.json — but only
    when the editor is OPENED, so a phone-visible default change (Language
    replacing Anywhere in Settings) never arrived without a desktop click.
    The same merge runs here, once per server start. FROZEN-only: in a dev
    checkout the repo file IS the shipped file and there is nothing to merge
    (which also keeps the PySide6 import below out of the headless CLI)."""
    global _shipped_pools_merged
    if _shipped_pools_merged:
        return
    _shipped_pools_merged = True
    from config import BUNDLE_DIR, FROZEN
    if not FROZEN:
        return
    user_path = Path(SETTINGS.actions_path)
    shipped_path = BUNDLE_DIR / "actions.json"
    if not user_path.exists() or user_path == shipped_path:
        return
    try:
        from gui.controls_editor import merge_shipped_pools
        data = json.loads(user_path.read_text(encoding="utf-8"))
        merge_shipped_pools(data, json.loads(shipped_path.read_text(encoding="utf-8")))
        user_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Shipped action pools merged into the user actions.json")
    except Exception as e:  # a failed merge must never stop the server
        logger.warning("Shipped-pools merge skipped: %s", e)


def _load_actions() -> dict:
    """Reads the owner's action categories fresh (edits apply on the next
    connect). A missing or invalid file is logged and yields no categories —
    never a crash."""
    _merge_shipped_actions()
    empty = {"categories": [], "app_sets": [], "custom_sets": [], "left": 0,
             "right": 0, "wheel_order": []}
    try:
        data = json.loads(SETTINGS.actions_path.read_text(encoding="utf-8"))
        return {
            "categories": data.get("categories", []),
            # App-aware sets (owner 2026-08-04): shown by the client ONLY in
            # layout focus, when the focused layout's app matches `process`.
            "app_sets": data.get("app_sets", []),
            # Owner-made sets from the desktop Controls editor (owner
            # 2026-08-05): the client shows up to 3 of them after the five
            # built-ins; `enabled` is the desktop default, the phone's own
            # Sets picker overrides it per device.
            "custom_sets": data.get("custom_sets", []),
            "left": data.get("left", 0),
            "right": data.get("right", 0),
            # Where each set sits on the phone's wheel (build round R5, owner
            # 2026-08-07): position 1 is 12 o'clock, then clockwise. Without
            # this line the desktop editor saves an order the phone never sees
            # — the whole feature is a no-op, on a fresh install too.
            "wheel_order": data.get("wheel_order", []),
        }
    except FileNotFoundError:
        logger.warning("actions.json not found at %s — no action categories", SETTINGS.actions_path)
        return empty
    except (json.JSONDecodeError, OSError) as e:
        logger.error("actions.json could not be loaded: %s", e)
        return empty


def _stream_base(stream) -> dict:
    """The desktop Settings card, as the phone needs to read it: the fps and
    the encoded size the PC allows, plus the bitrate every phone step is a
    percentage of. JPEG mode has no encoder size of its own — fall back to the
    monitor size."""
    width, height = getattr(stream, "stream_size", (stream.width, stream.height))
    return {
        "fps": SETTINGS.target_fps,
        "width": width,
        "height": height,
        "bitrate": SETTINGS.h264_bitrate,
        "bitrate_mid": config.bitrate_for_level("mid"),
        "bitrate_low": config.bitrate_for_level("low"),
    }


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
        # The phone's update source is THIS PC, never the internet. The
        # banner compares against apk_version — the version of the APK this
        # server actually serves (app_version nagged forever on desktop-only
        # releases); app_version stays for display/diagnostics.
        "app_version": app_version(),
        "apk_version": apk_version(),
        # What the PC ITSELF is set to (desktop Settings card) — the phone's
        # quality panel is a set of overrides that may only go BELOW this, so
        # it has to be able to SAY what "Max / Full / High" currently mean and
        # to grey out the steps that can never take effect (owner 2026-08-05:
        # picking 30 fps under a 10 fps PC changed nothing and said nothing).
        "base": _stream_base(stream),
        # How the phone should LOOK (build round R3, owner 2026-08-07) —
        # theme, fill and the per-set colours, decided on the DESKTOP and
        # nowhere else. Built in config.ui_config(); this file only ships it.
        "ui": ui_config(),
    }
    if codec:
        payload["codec"] = codec
    await ws.send_text(json.dumps(payload))


async def _switch_monitor(ws: WebSocket, injector: InputInjector, stream, token: str,
                          layouts=None, conn: dict | None = None) -> None:
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
    # A focused layout stands on the monitor we just stopped watching, and it
    # is still always-on-top there — over a desk the phone can no longer even
    # see (audit 2026-08-05). Switching monitors therefore LEAVES the layout,
    # exactly like choosing Desktop; the layout bar is still there to step
    # back into it once the phone is looking at its monitor again.
    if layouts is not None and conn is not None and conn.get("active") is not None:
        await asyncio.to_thread(layouts.minimize_members)
        conn["active"], conn["region"] = None, None
        await layout_api.send_layout_state(ws, layouts, conn)
    if stream.mode == "jpeg":
        await _send_config(ws, stream, token)  # H.264 clients get config from their fresh session
    await _toast(ws, f"Monitor {stream.monitor_index + 1}/{count}")


async def _screenshot(ws: WebSocket, stream, injector: InputInjector, msg: dict) -> None:
    """PC screenshot into the PC clipboard. The Attach set's Shot button sends
    the REGION the phone currently views (owner 2026-08-04 — zoomed = that
    part, layout focus = the layout's rect, never the whole desktop) plus
    paste=true, and the server injects Ctrl+V itself; the legacy snap action
    sends neither and only fills the clipboard."""
    frame = await asyncio.to_thread(stream.take_screenshot)
    if frame is None:
        await _toast(ws, "Screenshot failed — see server log")
        return
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
    frame = frame[y1:y2, x1:x2]
    ok = await asyncio.to_thread(clipboard.copy_image, frame)
    if ok and msg.get("paste"):
        await asyncio.to_thread(injector.press_chord, "ctrl+v")
        await _toast(ws, "Screenshot pasted on the PC")
    else:
        await _toast(ws, "Screenshot in PC clipboard — paste with right-click" if ok
                     else "Clipboard busy — try again")


def _paste_text(injector: InputInjector, text: str, enter: bool, guard=None) -> str:
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
        time.sleep(PASTE_ENTER_DELAY)
        injector.press_key("enter")
    return ""


# Which messages TYPE (their effect lands in whatever window holds the
# keyboard) and which ones legitimately CHOOSE a window. The focus guard needs
# both lists: it fences the first and re-arms on the second (owner 2026-08-06
# — dictation that continued in another agent's session; see focus_guard).
TYPING_KINDS = frozenset({"key_text", "key_special", "chord", "paste_text",
                          "screenshot"})
RETARGET_KINDS = frozenset({"pointer_down", "click", "press", "next_input",
                            "layout_focus", "monitor_switch"})


async def _receive_input(ws: WebSocket, injector: InputInjector, stream, token: str,
                         layouts=None, conn: dict | None = None) -> None:
    conn = conn if conn is not None else {"ratio": 9 / 16, "active": None,
                                          "region": None, "seen": time.monotonic(),
                                          "away": None, "left": False}
    layouts = layouts if layouts is not None else window_manager.LayoutRegistry()
    while True:
        msg = json.loads(await ws.receive_text())
        kind = msg.get("type")
        # Every message is proof the phone is still with us — `away` is the one
        # message that deliberately says otherwise (presence, owner 2026-08-05).
        conn["seen"] = time.monotonic()
        if kind != "away":
            conn["away"] = None
        if kind not in ("away", "hb"):
            conn["left"] = False   # real work on this socket = the phone is back
            conn["paused"] = False  # ...so the stream may run again
        if kind == "hb":
            # The timestamp above IS the heartbeat. It may carry the phone's
            # own traffic counters (Android TrafficStats — what OUR app spent
            # and what the whole device spent); the desktop graph shows both
            # sides so "does it run while the screen is off" stops being an
            # argument (owner 2026-08-05).
            if msg.get("net"):
                traffic.METER.note_phone(msg["net"])
            continue
        if kind == "away":
            # The page is about to be hidden, and it says WHY. An EXCURSION
            # (image picker, camera, voice, a permission dialog) means the
            # owner is still working with us and comes straight back — hold
            # everything. Anything else, above all a LOCK, hands the desk its
            # windows back immediately.
            #
            # The word comes from the Android shell, which reads the screen
            # and keyguard state and knows whether it launched the picker
            # itself. It replaces a 90-second timer in the page that guessed
            # — and guessed "excursion" for a tablet locked seconds after
            # dictating, which is the whole 2026-08-05 topmost failure.
            if msg.get("net"):
                traffic.METER.note_phone(msg["net"])
            # Nothing may be SENT to a phone that has gone: the page normally
            # closes the socket right behind this message, but when its Wi-Fi
            # falls asleep first the socket lingers — and the encoder was
            # happily filling it for as long as the hold lasted (audit
            # 2026-08-05). The stream stops here, on every kind of away; only
            # the LAYOUT rides the excursion timer.
            conn["paused"] = True
            if conn.get("reset_stream"):
                conn["reset_stream"]()
            if presence.is_excursion(msg):
                conn["away"] = True
                logger.info("Phone announced an excursion — layout held")
            else:
                conn["away"] = None   # a leave is not served by the long budget
                logger.info("Phone left (%s) — the desk gets its windows back",
                            msg.get("reason") or "no reason given")
                await presence.leave_session(layouts, conn)
            continue
        # WHERE typed input lands is decided HERE, before a single key is
        # injected — never by whatever window happened to take focus while the
        # owner was speaking (owner 2026-08-06). In a layout the fence is the
        # layout's own members; at the desktop it is the window the burst
        # started in, re-armed by anything the owner did on purpose.
        if kind in TYPING_KINDS:
            await asyncio.to_thread(focus_guard.guard, layouts, conn)
        elif kind in RETARGET_KINDS:
            focus_guard.retarget(conn)
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
        elif kind == "press":
            # CLICK/HOLD mouse buttons (owner 2026-08-04): down when the
            # finger lands, up when it lifts — at the current cursor.
            button = msg.get("button", "left")
            if button not in BUTTON_FLAGS:
                logger.error("Unknown button %r from client", button)
                continue
            injector.press(button, bool(msg.get("down")))
        elif kind == "pointer_move":
            injector.move(float(msg["x"]), float(msg["y"]))
        elif kind == "scroll":
            # `hticks` is optional (backward compat: an older page that sends
            # only `ticks` scrolls exactly as before — absent means zero, no
            # horizontal event at all, see InputInjector.wheel).
            injector.wheel(float(msg["x"]), float(msg["y"]), float(msg["ticks"]),
                            float(msg.get("hticks", 0.0)))
        elif kind == "key_text":
            # The fence goes INTO the injection, not just before it: typing a
            # dictated sentence takes ~1.1 s of SendInput, and whatever a thief
            # still costs us is TOLD to the phone (focus_guard, round R1).
            lost = await asyncio.to_thread(injector.type_text, str(msg["text"]),
                                           focus_guard.typist(layouts, conn))
            if lost:
                await _toast(ws, focus_guard.loss_notice(lost))
        elif kind == "key_special":
            injector.press_key(str(msg["key"]))
        elif kind == "paste_text":
            # A TYPED command button (owner 2026-08-05 — the Claude set's
            # /usage, /model, /effort). The text goes through the CLIPBOARD
            # and one Ctrl+V rather than key-by-key: a slash command types
            # into an autocomplete menu that re-filters on every character,
            # and one atomic insert cannot be raced by it. Enter is a separate
            # press so `enter: false` can leave the menu standing for the
            # finger to pick from.
            lost = await asyncio.to_thread(
                _paste_text, injector, str(msg.get("text", "")),
                bool(msg.get("enter", True)), focus_guard.typist(layouts, conn))
            if lost:
                await _toast(ws, focus_guard.loss_notice(lost))
        elif kind == "viewport":
            if stream.mode == "jpeg":
                stream.set_viewport(
                    float(msg["x"]), float(msg["y"]), float(msg["w"]), float(msg["h"])
                )
            # H.264 streams the full frame — a viewport from a stale client is noise
        elif kind == "chord":
            injector.press_chord(str(msg["chord"]))
            # A chord is guarded on the way IN (Ctrl+V must land in his box)
            # but may itself MOVE the window — Alt+Tab, Win+arrow, Ctrl+W. So
            # the target is re-read on the next key instead of being dragged
            # back to where the chord just left (focus_guard).
            focus_guard.retarget(conn)
        elif kind == "monitor_switch":
            await _switch_monitor(ws, injector, stream, token, layouts, conn)
        elif kind == "screenshot":
            await _screenshot(ws, stream, injector, msg)
        elif kind == "layout_pick":
            await layout_api.layout_pick(ws, layouts, stream, msg)
        elif kind == "layout_list":
            await layout_api.layout_list(ws, layouts, stream)
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
            # Per-client quality overrides (owner spec 2026-08-05: the phone's
            # panel picks fps / resolution / bitrate level, or auto-reduces on
            # mobile data — the CLIENT decides when and sends the EFFECTIVE
            # values). H.264: the running session is reset and reopens with
            # the new encoder settings. Legacy `reduced: true` (older client
            # pages) maps to the auto-save profile.
            if "reduced" in msg and "res" not in msg:
                quality = ({"fps": SETTINGS.h264_reduced_fps, "res": "1/2",
                            "bitrate": "low"} if msg.get("reduced") else None)
            else:
                quality = {
                    "fps": int(msg.get("fps") or 0),
                    "res": str(msg.get("res") or "full"),
                    "bitrate": str(msg.get("bitrate") or "high"),
                }
                if quality == {"fps": 0, "res": "full", "bitrate": "high"}:
                    quality = None  # pure defaults — same as no override
            changed = quality != conn.get("quality")
            conn["quality"] = quality
            if changed and stream.mode == "h264" and conn.get("reset_stream"):
                conn["reset_stream"]()
            if changed:
                await _toast(ws, "Stream: " + (
                    "default quality" if quality is None else
                    f"{quality['fps'] or 'max'} fps · {quality['res']} res · "
                    f"{quality['bitrate']} bitrate"))
        elif kind == "tts_info":
            # The phone lists the text-to-speech voices IT has, once per
            # connection (owner round R2, 2026-08-07). The PC cannot
            # enumerate another device's TTS engine, so this is the only
            # source the desktop Settings window's "Voice" dropdown can have.
            notify.set_voices(msg.get("voices"))
        elif kind == "client_log":
            # Silent phone-side diagnostics (owner round 2, 2026-08-05: voice
            # evidence goes to THIS log, never to a panel on the phone).
            logger.info("Phone: %s", str(msg.get("text", ""))[:500])
        elif kind == "layout_create":
            await layout_api.layout_create(ws, layouts, stream, conn, msg)
        elif kind == "layout_aspect":
            await layout_api.layout_aspect(ws, layouts, stream, conn, msg)
        elif kind == "layout_focus":
            index = int(msg["index"])
            if index < 0:
                # A DELIBERATE desktop choice is the state to resume into —
                # nothing to come back to (owner 2026-08-05).
                await asyncio.to_thread(layouts.forget_focus)
            await layout_api.layout_focus(ws, layouts, stream, conn, index)
        elif kind == "layout_rename":
            # The owner's own name for a layout (owner 2026-08-05) — the window
            # title is only the default the creation panel offers.
            if not await asyncio.to_thread(
                    layouts.rename, int(msg["index"]), str(msg.get("name", ""))):
                await _toast(ws, "That layout is gone")
            await layout_api.send_layout_state(ws, layouts, conn)
        # `layout_apps` lived here — the owner re-ticking which app-aware sets
        # a layout carries. Removed 2026-08-07 with the ticks themselves: the
        # PC reads what is running (server/agents.py) on every state frame, so
        # there is nothing left for anyone to declare.
        elif kind == "layout_grid":
            # The grid's ARRANGEMENT (owner 2026-08-07): a three-window layout
            # picks which edge its single window takes; two and four may only
            # change portrait/landscape. Lives beside the name and the aspect.
            if not await asyncio.to_thread(
                    layouts.set_grid, int(msg["index"]),
                    str(msg.get("grid", "")), msg.get("orient")):
                await _toast(ws, "That layout is gone")
                await layout_api.send_layout_state(ws, layouts, conn)
            else:
                await layout_api.layout_focus(ws, layouts, stream, conn,
                                              int(msg["index"]))
        elif kind == "layout_merge":
            # One layout dragged ONTO another becomes a grid of the two; the
            # dragged one disappears (owner 2026-08-07).
            src, dst = int(msg["source"]), int(msg["target"])
            if not await asyncio.to_thread(layouts.merge, src, dst,
                                           msg.get("grid")):
                await _toast(ws, "Those two cannot make a grid")
                await layout_api.send_layout_state(ws, layouts, conn)
            else:
                # The target's index slides down when the source sat above it.
                await layout_api.layout_focus(ws, layouts, stream, conn,
                                              dst - 1 if src < dst else dst)
        elif kind == "layout_reorder":
            # Dropping BETWEEN two rows — the list's own order, nothing moves
            # on the PC (owner 2026-08-07).
            await asyncio.to_thread(layouts.reorder, int(msg["source"]),
                                    int(msg["before"]))
            await layout_api.send_layout_state(ws, layouts, conn)
        elif kind == "layout_remove":
            index = int(msg["index"])
            await asyncio.to_thread(layouts.remove, index)
            if conn["active"] is not None:
                if conn["active"] == index:
                    conn["active"], conn["region"] = None, None
                elif conn["active"] > index:
                    conn["active"] -= 1
            await layout_api.send_layout_state(ws, layouts, conn)
        else:
            logger.warning("Unknown message type %r from client", kind)
