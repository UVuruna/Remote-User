"""The `config` message — the phone's full view reset, on the wire.

Sent after auth and after EVERY stream (re)start (monitor switch, H.264
session reset, quality change): the client tears down and rebuilds its whole
view/decode pipeline from this one frame. Moved out of web.py on 2026-08-12
(THE STRUCTURE LAW — web.py stood at the 1,000-line wall again; the
actions_api precedent: the module that owns a message's wire SHAPE is one
module, so no second sender can ever carry different fields).
"""

import asyncio
import json

import config
import monitor_api
import pairing
from config import SETTINGS, apk_version, app_version, ui_config


async def send_config(ws, stream, token: str, codec: str | None = None,
                      region: dict | None = None, zoom: int = 1) -> None:
    # tailscale_url feeds the client's guided "access from anywhere" wizard:
    # null when the PC has no Tailscale yet (the desktop window guides that
    # side); checked fresh per config so a login mid-run shows on reconnect.
    ts_ip = await asyncio.to_thread(pairing.get_tailscale_ip)
    payload = {
        "type": "config",
        "monitor_width": stream.width,
        "monitor_height": stream.height,
        # `monitor` + `monitors` — every screen the PC can stream and which
        # one this is (owner 2026-08-09, task 155). Built in
        # monitor_api.config_fields; this module only ships it, like `base`.
        **monitor_api.config_fields(stream),
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
        "base": config.stream_base(stream),
        # How the phone should LOOK (build round R3, owner 2026-08-07) —
        # theme, fill and the per-set colours, decided on the DESKTOP and
        # nowhere else. Built in config.ui_config(); this module only ships it.
        "ui": ui_config(),
    }
    if codec:
        payload["codec"] = codec
    if region:
        # The monitor-normalized rect THIS stream covers (owner order
        # 2026-08-12): the per-client encoder crops to the focused layout, so
        # the page must map the video onto that rect, not the full monitor.
        # Absent = full frame — a page that predates the field changes nothing.
        payload["stream_region"] = region
    if zoom > 1:
        # The resolution step THIS stream was encoded with (owner design,
        # round 3 of T76): the page's decode ceiling must judge the RAISED
        # width, or a deep zoom would push a native-size stream at a device
        # whose decoder was only ever probed panel-capped — the exact "4K60 =
        # no picture" failure of 2026-08-12. Absent = step 1, old pages and
        # old servers both keep working.
        payload["stream_zoom"] = int(zoom)
    await ws.send_text(json.dumps(payload))
