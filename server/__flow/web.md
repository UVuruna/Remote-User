# Web Layer — Flow

**About:** [description](../__about/web.md)

## Algorithm — one WebSocket connection

```mermaid
flowchart TB
    A["ws.accept()"] --> B["_authenticate(ws, token) — 5s timeout"]
    B -- fail --> C["ws.close(4401) — nothing is ever processed"]
    B -- ok --> D["stats.clients += 1"]
    D --> E["send actions from actions.json"]
    E --> F["start _send_cursor task"]
    F --> G{stream.mode?}
    G -- jpeg --> H["send config; subscribe to FrameHub; start _send_frames task"]
    G -- h264 --> I["start _stream_h264 task — opens its own session + sends config"]
    H --> J["_receive_input(ws) loop — awaits the connection"]
    I --> J
    J -- WebSocketDisconnect --> K["finally: stats.clients -= 1, cancel all tasks"]
    K --> L{was jpeg?}
    L -- yes --> M["unsubscribe from FrameHub, reset viewport to full frame"]
    L -- no --> N[done]
```

## Algorithm — _receive_input dispatch

The per-`kind` branches moved to a registry on 2026-08-18 (VC-R2) and the
picture moved with them: [WS Commands — Flow](ws_commands.md). What this loop
still does before every dispatch — presence bookkeeping, the focus prelude,
the double-click note — is the first diagram there.

## Algorithm — _stream_h264 per-connection loop

```mermaid
flowchart TB
    A["LOOP forever (task runs until cancelled on disconnect)"] --> B["new bounded queue (h264_queue_chunks)"]
    B --> B2["owner = manager.new_owner() -- the CLAIM, made before the encoder thread exists"]
    B2 --> C["push(item): if NOT owner.alive -> drop silently;\nelse put_nowait; on QueueFull -> drain + sentinel None\n(reset the WHOLE session -- bytes are never dropped individually)"]
    C --> D["manager.open_session(on_data=push, on_end=push(None), owner=owner)"]
    D -- RuntimeError/OSError --> E["owner.release(); toast + ws.close(1011); return"]
    D -- CANCELLED --> E2["owner.release(); re-raise\n(the thread runs on -- the claim is what closes what it builds)"]
    D -- ok --> F["_send_config(ws, manager, token, codec=session.codec)"]
    F --> G["WHILE chunk := queue.get() is not None: ws.send_bytes(chunk)"]
    G -- disconnect/RuntimeError --> H[return -- receive loop logs the disconnect]
    G -- queue yields None --> I["finally: owner.release() -- closes the session"]
    I --> J{session lived < 2s?}
    J -- yes --> K["sleep 1s -- pace a fast error loop"]
    J -- no --> A
    K --> A
```

Pseudocode:

    ws_endpoint(ws):
        accept the socket
        IF NOT _authenticate(ws, token) -> close(4401); return   # nothing before auth
        stats.clients += 1
        send {"type": "actions", ...} from actions.json
        start _send_cursor task
        IF stream.mode == "jpeg":
            send config; queue = hub.subscribe(); start _send_frames(queue) task
        ELSE:
            start _stream_h264 task (opens its own session, sends its own config)
        TRY: _receive_input(ws) loop forever
        FINALLY:
            stats.clients -= 1; cancel every task
            IF was jpeg: hub.unsubscribe(queue); stream.set_viewport(full frame)

    _receive_input(ws):
        WHILE True:
            msg = parse next JSON text message
            DISPATCH on msg.type to the matching injector call (see dispatch diagram)
            unknown type -> log warning, ignore

    _stream_h264(ws, manager, token, conn):
        hold = object()                      # this connection's capture hold
        TRY: _h264_loop(ws, manager, token, conn, hold)
        FINALLY: manager.release_source(hold)   # every exit, incl. cancellation

    _h264_loop(ws, manager, token, conn, hold):
        first, failures = True, 0
        LOOP forever:
            WHILE conn["paused"]:            # the phone is away
                manager.release_source(hold) # ...and holds nothing
                sleep 0.25
            queue = bounded Queue(h264_queue_chunks)
            owner = manager.new_owner()      # the claim -- see h264_streamer flow
            push(item): IF NOT owner.alive -> RETURN     # nothing reads this queue
                        put_nowait; ON QueueFull -> drain queue, put None
                        (a full queue means the client cannot keep up -- the WHOLE
                        session resets; H.264 bytes cannot be dropped individually)
            req_region = conn["region"]      # the focused layout's rect, read ONCE
            TRY: session = manager.open_session(on_data=push, on_end=lambda: push(None),
                                                quality=conn["quality"],  # phone panel overrides
                                                owner=owner,
                                                region=req_region)  # encoder CROPS to it
                 # (a changed `quality` message resets the session via conn["reset_stream"];
                 #  a changed REGION does too — layout_api.send_layout_state compares the
                 #  live conn["region"] against conn["stream_region"], the intention copy
                 #  recorded below; the loop reopens with the new fps/res/bitrate/crop)
            EXCEPT (RuntimeError, OSError):
                 owner.release(); failures += 1
                 IF first OR failures >= h264_reopen_tries:
                     toast, close(1011), return   # a FIRST open has nothing to keep
                 sleep h264_reopen_pause_s; CONTINUE  # a RE-open is retried, hold kept
            EXCEPT BaseException:            # cancelled -- socket death, 4409, server stop
                 owner.release(); re-raise   # to_thread cannot cancel the thread it started
            first, failures = False, 0
            conn["stream_region"] = req_region   # intention copy for the choke point
            traffic.METER.note_stream(traffic_stream.from_session(session))  # T106: the CSV learns what this session encodes; note_stream(None) in the finally that closes it
            send config (with the session's parsed codec + stream_region, the
                         even-rounded crop the page maps the video onto)
            WHILE (chunk := queue.get()) is not None:
                ws.send_bytes(chunk)
            FINALLY: manager.hold_source(hold)   # the gap to the next session --
                     owner.release()             # ...closing it must not stop dxcam
            IF this session lived < 2s -> sleep 1s (paces a fast error loop)
            # loop reopens a fresh session automatically

## Build round R3 (2026-08-07) — themes

```
_send_config(ws, stream, token, codec)
   payload = { type, monitor_width, monitor_height, stream,
               tailscale_url, app_version, apk_version,
               base: config.stream_base(stream),
               ui:   ui_config() }        <- R3: {theme, fill, colors}
   + codec (H.264 only)
```
