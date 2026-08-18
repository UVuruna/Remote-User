# WS Commands - Flow

**About:** [description](../__about/ws_commands.md)

The connection, the auth handshake and the send loop are
[Web Layer - Flow](web.md); this document is what happens to ONE message
after the loop has read it.

## Algorithm - a message becomes a handler call

```mermaid
flowchart TB
    A["web._receive_input: msg = json.loads(ws.receive_text())"] --> B["presence bookkeeping<br/>seen · away · left · paused"]
    B --> C{"kind in TYPING_KINDS?"}
    C -- yes --> D["focus_guard.guard — the target is decided BEFORE the keys<br/>(layout = fence · desktop = pin · thief named in the log)"]
    C -- "no, in RETARGET_KINDS" --> E["focus_guard.retarget — the owner chose a window himself"]
    C -- neither --> F
    D --> F["click/press → layout_birth.note_click"]
    E --> F
    F --> G["handler = ws_commands.HANDLERS.get(kind)"]
    G -- None --> H["log 'Unknown message type' · next message"]
    G -- found --> I["await handler(Wire(ws, injector, stream, token, layouts, conn, msg))"]
    I --> A
    H --> A
```

The picture that used to live here - one `B -- kind -->` arrow per branch -
was a drawing of a chain that no longer exists. What replaced it is a lookup,
and a lookup has no shape worth drawing: the interesting half is now WHICH
handlers exist, which is the registry itself.

## Algorithm - the pointer trio, the one handler serving three kinds

```mermaid
flowchart TB
    A["_pointer_down(w) — kind is pointer_down | pointer_up | click"] --> B{"button in BUTTON_FLAGS?"}
    B -- no --> Z["log error · return (the message is dropped)"]
    B -- "yes, click" --> C["injector.click(button) — at the current cursor, no coordinates"]
    B -- "yes, down/up" --> D["x, y = msg['x'], msg['y']"]
    D --> E["injector.button_down / button_up(x, y, button)"]
```

Three kinds, one handler, because they are one decision about one button -
splitting them would be three copies of the same `BUTTON_FLAGS` check, which
is the duplication the registry exists to end.

## Algorithm - registration

```
@on("layout_grid")            ->  HANDLERS["layout_grid"] = _layout_grid
@on("pointer_down", "pointer_up", "click")
                              ->  all three keys, one coroutine
a kind registered twice       ->  RuntimeError AT IMPORT, never at runtime
```

The duplicate check is the property the `elif` chain could not have: a second
`elif kind == "chord"` further down the chain was simply dead code nobody
could see. Here it refuses to start the server.
