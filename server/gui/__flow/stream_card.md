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
    A["config.QUALITY_LADDER<br/>Max 60/20M · Smooth 30/12M<br/>Sharp 10/6M · Data saver 10/2M"]
    A --> A2["DATA_SAVER = the bottom rung<br/>{fps 10, res ½, bitrate saver}<br/>+ DATA_SAVER_BITRATE 2M"]
    A --> B["this card's four steps<br/>(set the PC's own base)"]
    A -. "gated, not imported" .-> F["client/quality.js QUALITY_LEVELS<br/>the phone's identical four"]
    A2 --> C["SETTINGS.h264_reduced_* <br/>(the capture-side halving)"]
    A2 --> D["config.quality_override({reduced:true})<br/>(a page older than the quality panel)"]
    A2 -. "gated, not imported" .-> E["client/quality.js dataSaverQuality()<br/>auto on cellular via Android.transport()"]
```

One table, both ends. The dotted edges are the ones that cannot be imports — that side is another language — so `tests/test_stream_card.py` parses `QUALITY_LEVELS` and `dataSaverQuality()` out of the real `client/quality.js` and asserts them rung for rung against `QUALITY_LADDER` and `DATA_SAVER`. That is what makes the owner's condition ("connect Data saver to mobile data, the mechanic we already have") a mechanical fact instead of a promise — and what dissolves the desktop/phone mismatch that used to be documented as unavoidable, since the phone's levels are the same ABSOLUTE numbers now and not percentages of a base that can move.
