"""What the encoder was DOING when these bytes went out — the per-second
stream descriptor beside every traffic sample (owner request 2026-08-15,
T106: "every point must also say which device, which quality settings, the
resolution of the slice, the zoom").

A traffic number without its cause is half a measurement: 2 MB/s at native
4K on Wi-Fi and 2 MB/s at a quarter crop on cellular are two different
findings, and until this module the CSV could not tell them apart. So one
descriptor is written per second — appended AFTER the existing columns
(`time,out_bytes,in_bytes,clients,device`), never inserted, so an older
server still reads its first fields and `traffic_history._parse_row` accepts
every width the file has ever had; a row without them reads as "not
recorded", never as a guess.

The descriptor is READ off the live `H264Session` at open (`from_session`)
and cleared at close; nothing here re-derives a value the encoder already
holds — a second copy of the scale arithmetic is exactly the drift this
project keeps paying for. Pure: no Qt, no I/O, so its gate can drive it
whole.

Fields (all strings on the wire, "" = not recorded):
    fps      the phone's fps choice ("0" = the PC's own — "max")
    res      the phone's resolution step: full / 2/3 / 1/2
    bitrate  the phone's bitrate level: high / mid / low  (low = data saver)
    crop     the SLICE encoded, as WxH pixels of the monitor (the focused
             layout's region, or the whole monitor)
    enc      the size the encoder really OUTPUTS after the panel ceiling
             and the zoom step (equal to crop when nothing is scaled)
    zoom     the settled pinch's resolution step, "1" when not zoomed
"""

STREAM_COLUMNS = ("fps", "res", "bitrate", "crop", "enc", "zoom")
_EMPTY = {name: "" for name in STREAM_COLUMNS}


def empty() -> dict:
    """The "nobody streaming" descriptor — six empty strings."""
    return dict(_EMPTY)


def from_session(session) -> dict:
    """The descriptor of a live `h264_streamer.H264Session`. Reads the
    session's own resolved fields (`_quality`, `_crop`, `_scale`, `_zoom`,
    `width`/`height`) — the very values `open_session` logs — so the CSV and
    the server log can never disagree about what was encoded."""
    quality = getattr(session, "_quality", None) or {}
    crop = getattr(session, "_crop", None)
    if crop:
        crop_w, crop_h = int(crop[0]), int(crop[1])
    else:
        crop_w, crop_h = int(getattr(session, "width", 0)), int(getattr(session, "height", 0))
    scale = getattr(session, "_scale", None)
    enc_w, enc_h = (int(scale[0]), int(scale[1])) if scale else (crop_w, crop_h)
    return {
        "fps": str(int(quality.get("fps") or 0)),
        "res": str(quality.get("res") or "full"),
        "bitrate": str(quality.get("bitrate") or "high"),
        "crop": f"{crop_w}x{crop_h}",
        "enc": f"{enc_w}x{enc_h}",
        "zoom": str(max(1, int(getattr(session, "_zoom", 1) or 1))),
    }


def to_csv_fields(info: dict | None) -> list[str]:
    """The six CSV cells, in `STREAM_COLUMNS` order. Every value is
    sanitised of commas and newlines — a descriptor must never be able to
    tear the row it rides on."""
    info = info or _EMPTY
    return [str(info.get(name, "")).replace(",", ";").replace("\n", " ")
            for name in STREAM_COLUMNS]


def from_csv_fields(parts: list[str]) -> dict:
    """The descriptor held in the cells AFTER the five base columns of a CSV
    row — `parts` is the whole split row. A row of any older width (4 or 5
    cells) reads as `empty()`; a partial tail (a torn line) fills what it has
    and leaves the rest ""."""
    info = empty()
    for i, name in enumerate(STREAM_COLUMNS):
        idx = 5 + i
        if idx < len(parts):
            info[name] = parts[idx].strip()
    return info


def is_recorded(info: dict | None) -> bool:
    """True when the row carried a descriptor at all — the `crop` cell is the
    one every recorded second has (a session always encodes SOME size)."""
    return bool(info and info.get("crop"))


def hover_lines(info: dict | None) -> list[str]:
    """The lines the chart's hover card adds under the byte counts (T106).
    "not recorded" for a second written before this column existed or while
    nobody streamed — never a guessed default."""
    if not is_recorded(info):
        return ["stream: not recorded"]
    fps = info.get("fps") or "0"
    fps_txt = "max fps" if fps in ("0", "") else f"{fps} fps"
    res = info.get("res") or "full"
    bitrate = info.get("bitrate") or "high"
    quality = f"quality: {fps_txt} · {res} · {bitrate}"
    if bitrate == "low":
        quality += " (data saver)"
    crop = info.get("crop") or "?"
    enc = info.get("enc") or crop
    slice_line = f"slice: {crop}" + (f" → sent {enc}" if enc != crop else " (sent as is)")
    zoom = info.get("zoom") or "1"
    zoom_line = "zoom: none" if zoom == "1" else f"zoom: x{zoom} (resolution step)"
    return [quality, slice_line, zoom_line]
