# Stream Card — Flow

**About:** [description](../__about/stream_card.md)

## Algorithm — building the card, and keeping the dropdown honest

```mermaid
flowchart TB
    A["SettingsWindow._build_stream_card()"] --> B["StreamCard(window, populate_monitors, restart)"]
    B --> C["build() — Monitor row, Quality row"]
    C --> D["Custom… tick + the Exact trio (Resolution · Bitrate · Frame rate)"]
    D --> E["select_current() — read SETTINGS into the EXACT combos"]
    E --> F["_refresh_steps() — derive which named step those numbers ARE"]
    F --> G{"step_for(fps, bitrate)"}
    G -- "a named step" --> H["light it"]
    G -- "no match" --> I["append 'Custom — 30 fps, 12 Mbps' and light that"]
    H --> J["_show_custom(False) — the disclosure starts shut"]
    I --> J
    J --> K["first show → settle(): pin the trio to their polished hint"]
```

The exact combos are **the model**; the Quality dropdown is a **view** of them. That direction is the whole design: it is why a step can never advertise numbers it does not set, and why there is exactly one save path.

## Algorithm — the two ways the owner changes it

```mermaid
flowchart TB
    P["picks a named step"] --> Q["_pick_step()"]
    Q --> R["write fps + bitrate into the EXACT combos (signals blocked)"]
    R --> S["Custom… now opens onto what the step chose"]

    T["edits an exact combo"] --> U["_exact_changed() → _refresh_steps()"]
    U --> V{"do the new numbers name a step?"}
    V -- yes --> W["that step lights"]
    V -- no --> X["the Custom entry appears, stating the numbers"]

    S --> Y["Apply & restart"]
    W --> Y
    X --> Y
    Y --> Z["save_user_settings(monitor, h264_max_width, h264_bitrate, target_fps)"]
    Z --> AA["restart() — these shape the encoder"]
```

`_pick_step` blocks the combos' signals while it writes, or every step pick would bounce straight back through `_exact_changed` and re-derive the step it just set. It deliberately touches **only** fps and bitrate: the resolution is behind Custom… and a named step must never move it.

## The one profile

```mermaid
flowchart LR
    A["config.DATA_SAVER<br/>{fps 10, res ½, bitrate low}<br/>+ DATA_SAVER_BITRATE 1200k"]
    A --> B["this card's 'Data saver' step<br/>(sets the PC's own base)"]
    A --> C["SETTINGS.h264_reduced_* <br/>(the capture-side halving)"]
    A --> D["config.quality_override({reduced:true})<br/>(a page older than the quality panel)"]
    A -. "gated, not imported" .-> E["client/quality.js — auto on cellular<br/>via Android.transport()"]
```

Four doors, one table. The dotted edge is the one that cannot be an import — it is another language — so `tests/test_stream_card.py` reads the literal out of `client/quality.js` and asserts it against `DATA_SAVER`. That is what makes the owner's condition ("connect Data saver to mobile data, the mechanic we already have") a mechanical fact instead of a promise.
