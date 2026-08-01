# Encoders — Flow

**About:** [description](../__about/encoders.md)

## Algorithm

```mermaid
flowchart TB
    A["detect_encoder()"] --> B["_listed_encoders() — parse ffmpeg -encoders"]
    B --> C{ffmpeg runnable / any encoders listed?}
    C -- no --> D["return None — caller falls back to JPEG"]
    C -- yes --> E["FOR EACH name in h264_encoder_order:\nh264_nvenc -> h264_qsv -> h264_amf -> libx264"]
    E --> F{name in listed?}
    F -- no --> G[skip, log, try next]
    F -- yes --> H["_test_encode(name): encode 8 testsrc frames"]
    H -- fails --> G
    H -- succeeds --> I["return name — selected encoder"]
    G --> E
    E -- exhausted --> D
```

Pseudocode:

    detect_encoder():
        listed = names from `ffmpeg -encoders` (empty if ffmpeg is not runnable)
        IF listed is empty → return None
        FOR EACH name IN h264_encoder_order:            # nvenc, qsv, amf, libx264
            IF name in listed AND _test_encode(name):
                log "Selected H.264 encoder: {name}"
                RETURN name
            log "Skipping {name} (not listed or failed test)"
        RETURN None                                     # caller uses JPEG instead

    _test_encode(name):
        RUN ffmpeg: encode 8 frames of a synthetic test pattern with `name` + its
                    low-latency args, output discarded (-f null -)
        RETURN True only if ffmpeg exits 0
