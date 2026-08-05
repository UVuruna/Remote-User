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

```mermaid
flowchart TB
    A["msg = json.loads(ws.receive_text())"] --> B{msg.type}
    B -- pointer_down/up/click --> C{button in BUTTON_FLAGS?}
    C -- no --> Z[log error, ignore]
    C -- yes, click --> D["injector.click(button) — current cursor position"]
    C -- yes, down/up --> E["injector.button_down/up(x, y, button)"]
    B -- pointer_move --> F["injector.move(x, y)"]
    B -- scroll --> G["injector.wheel(x, y, ticks)"]
    B -- key_text --> H["injector.type_text(text)"]
    B -- key_special --> I["injector.press_key(key)"]
    B -- viewport --> J{stream.mode == jpeg?}
    J -- yes --> K["stream.set_viewport(x, y, w, h)"]
    J -- no --> L["ignored — H.264 always streams the full frame"]
    B -- chord --> M["injector.press_chord(chord)"]
    B -- monitor_switch --> N["_switch_monitor(...)"]
    B -- screenshot --> O["_screenshot(...)"]
    B -- unknown --> Z
    D --> A
    E --> A
    F --> A
    G --> A
    H --> A
    I --> A
    K --> A
    L --> A
    M --> A
    N --> A
    O --> A
```

## Algorithm — _stream_h264 per-connection loop

```mermaid
flowchart TB
    A["LOOP forever (task runs until cancelled on disconnect)"] --> B["new bounded queue (h264_queue_chunks)"]
    B --> C["push(item): put_nowait; on QueueFull -> drain + sentinel None\n(reset the WHOLE session -- bytes are never dropped individually)"]
    C --> D["manager.open_session(on_data=push, on_end=push(None))"]
    D -- RuntimeError/OSError --> E["toast + ws.close(1011); return"]
    D -- ok --> F["_send_config(ws, manager, token, codec=session.codec)"]
    F --> G["WHILE chunk := queue.get() is not None: ws.send_bytes(chunk)"]
    G -- disconnect/RuntimeError --> H[return -- receive loop logs the disconnect]
    G -- queue yields None --> I["finally: manager.close_session(session)"]
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

    _stream_h264(ws, manager, token):
        LOOP forever:
            queue = bounded Queue(h264_queue_chunks)
            push(item): put_nowait; ON QueueFull -> drain queue, put None
                        (a full queue means the client cannot keep up -- the WHOLE
                        session resets; H.264 bytes cannot be dropped individually)
            TRY: session = manager.open_session(on_data=push, on_end=lambda: push(None),
                                                quality=conn["quality"])  # phone panel overrides
                 # (a changed `quality` message resets the session via conn["reset_stream"];
                 #  the loop reopens here with the new fps/res/bitrate)
            EXCEPT (RuntimeError, OSError): toast "stream failed", close(1011), return
            send config (with the session's parsed codec)
            WHILE (chunk := queue.get()) is not None:
                ws.send_bytes(chunk)
            FINALLY: manager.close_session(session)
            IF this session lived < 2s -> sleep 1s (paces a fast error loop)
            # loop reopens a fresh session automatically
