# H.264 Streamer — Flow

**About:** [description](../__about/h264_streamer.md)

## Algorithm — one H264Session

```mermaid
flowchart TB
    A["start()"] --> B["spawn ffmpeg — rawvideo stdin, fMP4 stdout, unbuffered"]
    B --> C["register FrameSink with the shared RawFrameSource"]
    C --> D["start feed / read / stderr threads"]
    D --> E{"head_ready within h264_head_timeout?"}
    E -- no --> F["stop() + raise RuntimeError"]
    E -- yes, with error --> F
    E -- yes, clean --> G["session ready — codec parsed"]

    subgraph FEED["feed thread"]
        H["sink.take(0.5s)"] --> I{data?}
        I -- no --> H
        I -- yes --> J["ffmpeg.stdin.write(data)"]
        J --> H
    end

    subgraph READ["read thread"]
        K["ffmpeg.stdout.read(32KB)"] --> L{head_ready set?}
        L -- no --> M["accumulate into head buffer"]
        M --> N{"moov complete? (_moov_end)"}
        N -- no --> K
        N -- yes --> O["codec = _codec_string(head)"]
        O --> P["on_data(head) — init segment"]
        P --> Q["set head_ready"]
        L -- yes --> R["on_data(chunk) — one fMP4 fragment"]
        R --> K
        Q --> K
    end

    K -- EOF --> S["fire on_end() exactly once"]
```

Pseudocode:

    H264Session.start():
        spawn ffmpeg (rawvideo bgr24 stdin -> fMP4 stdout, unbuffered pipes)
        register this session's FrameSink with the shared RawFrameSource
        start feed_loop, read_loop, stderr_loop threads
        WAIT for head_ready (up to h264_head_timeout)
        IF timed out OR head_error -> stop(), raise RuntimeError

    feed_loop():                       # newest frame -> ffmpeg stdin
        WHILE running:
            data = sink.take(0.5s)     # None on stall -- re-checks running and loops
            IF data -> write to ffmpeg.stdin (BrokenPipe/OSError -> normal shutdown, break)

    read_loop():                       # ffmpeg stdout -> on_data, in two phases
        head = b""
        WHILE running:
            chunk = ffmpeg.stdout.read(32KB)
            IF chunk is empty (EOF):
                IF head never completed -> head_error = "no init segment"; set head_ready
                RETURN
            IF head_ready already set:
                on_data(chunk)                       # phase 2: forward every fragment
                CONTINUE
            head += chunk                            # phase 1: accumulate the init segment
            end = _moov_end(head)
            IF end == 0 -> CONTINUE                   # moov not complete yet
            codec = _codec_string(head[:end])
            on_data(head)                            # init segment (+ any fragment already read)
            set head_ready
        FINALLY: fire on_end() exactly once

    stop():                            # idempotent, any thread, fast
        running = False
        detach sink from the source
        close ffmpeg.stdin, terminate the process
        # daemon threads unwind on their own; read_loop's EOF fires on_end

## Algorithm — H264Manager session lifecycle

```mermaid
flowchart LR
    A["open_session(on_data, on_end)"] --> B{source already running?}
    B -- no --> C["source.start()"]
    B -- yes --> D
    C --> D["new H264Session; session.start()"]
    D -- raises --> E{any sessions left?}
    E -- no --> F["source.stop()"]
    E -- yes --> G[re-raise]
    F --> G
    D -- ok --> H["add to _sessions"]

    I["close_session(session)"] --> J["session.stop()"]
    J --> K["remove from _sessions"]
    K --> L{_sessions empty?}
    L -- yes --> M["source.stop()"]
    L -- no --> N[capture keeps running for the others]
```
