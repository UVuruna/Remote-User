"""The phone's MONITOR commands: which screens exist, and moving to one.

Split out of web.py on 2026-08-09 (THE STRUCTURE LAW, and the file was sitting
exactly on the 1,000-line limit when task 155 needed two more fields). The seam
is the `layout_api` one: web.py is the socket and the dispatch, and a coherent
protocol responsibility with one engine underneath it — here `monitors` and the
capture source — lives in its own module.

WHAT CHANGED WITH TASK 155 (owner 2026-08-09). The Monitor action was a CYCLER
sitting in the phone's Settings set: it stepped to the next output and told you
where you had landed AFTERWARDS. His instruction was to take it out of Settings
and give it to the layout panels, where the single "Desktop" row becomes one row
per monitor, each naming its resolution — a list you choose from instead of a
button you press until the right screen appears. That needs two things this
module owns: the LIST (`config_fields`, which rides the `config` frame the
server already sends) and a switch that can be told WHICH monitor rather than
only "the next one" (`switch`, whose `index` is optional exactly so an older
phone keeps cycling).
"""

import asyncio
import logging

import layout_api
import monitors
from layout_api import toast

logger = logging.getLogger(__name__)


def config_fields(stream) -> dict:
    """The two OPTIONAL keys the `config` frame carries for task 155.

    `monitor` is the output being streamed; `monitors` is every output that can
    be streamed, `{index, width, height, primary}` each. Optional on purpose: a
    phone too old to read them draws the single "Desktop" row it always did, so
    nothing on the wire became required for a feature the phone can live
    without.

    Both are read FRESH per config rather than cached, and `config` is re-sent
    after every stream restart — a monitor switch included — so the phone's idea
    of which screen it is looking at is refreshed by the very event that changes
    it, with no second message to keep in step.
    """
    return {
        "monitor": stream.monitor_index,
        "monitors": monitors.describe(stream.monitor_index, stream.width,
                                      stream.height, stream.output_count()),
    }


async def switch(ws, injector, stream, layouts, conn, index, send_config) -> None:
    """Move the stream to another monitor.

    `index` is the monitor the phone ASKED for (task 155 — a row it tapped in
    the layout list) and is OPTIONAL: `None`, or anything outside the range of
    real outputs, falls back to the cycle this message has always performed, so
    a page written before the rows existed keeps working unchanged and a stale
    index from a monitor that has since been unplugged cannot address nothing.

    `send_config` is passed in rather than imported: it belongs to the socket in
    web.py, and a module that reached back for it would make the split a name
    change instead of a boundary.
    """
    count = stream.output_count()
    if count < 2:
        await toast(ws, "Only one active monitor")
        return
    asked = index if isinstance(index, int) and 0 <= index < count else None
    if asked == stream.monitor_index:
        return                      # already there — the phone's row is a no-op
    new_index = asked if asked is not None else (stream.monitor_index + 1) % count
    ok = await asyncio.to_thread(stream.switch_to, new_index)
    if not ok:
        await toast(ws, "Monitor switch failed — see server log")
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
        await send_config()  # H.264 clients get config from their fresh session
    await toast(ws, f"Monitor {stream.monitor_index + 1}/{count}")
