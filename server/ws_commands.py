"""THE PHONE'S COMMANDS: one handler per `kind`, in one registry.

Split out of `web.py` on 2026-08-18 (THE STRUCTURE LAW + ONE KIND ONE CLASS,
VC-R2). Until this round every client message was a branch in a 366-line
`if kind == "hb": / elif kind == "press": / ...` chain inside
`web._receive_input`, and adding a command meant inserting another `elif` into
one function. That is exactly the shape the law names a violation: a KIND with
36 instances and no registry, grown by copying a branch.

A command is now an OBJECT in `HANDLERS` — `@on("layout_grid")` above an
`async def` — and adding one is adding an entry, never editing a chain. The
chain's own shape is preserved exactly: every body below is byte-identical to
the branch it came from, `continue` became `return` (the dispatch was the last
thing in the loop, so they are the same statement), and the ORDER the branches
were written in no longer matters at all, because a dict lookup cannot fall
through to the wrong one.

## The context object

Each branch used to read four things straight out of `_receive_input`'s
closure — `ws`, `injector`, `stream`, `token` — plus the two the loop threads
through, `layouts` and `conn`, and the message itself. A registry has no
closure, so those seven travel in one explicit `Wire`, built once per message.
Every handler's first line unpacks exactly the names its body uses, which is
what keeps the bodies untouched.

## What stayed in web.py

The loop itself, and everything that runs BEFORE the dispatch for every
message alike: the presence bookkeeping (`seen`, `away`, `left`), the focus
prelude (`TYPING_KINDS` / `RETARGET_KINDS` — which must stay in web.py, its
own gate reads that source), and the double-click note. Those are not commands;
they are the frame every command arrives in.
"""

import asyncio
import logging
from dataclasses import dataclass

from fastapi import WebSocket

import actions_api
import agents
import claude_api
import clipboard
import clipboard_sync
import config
import content
import focus_guard
import layout_acts_api
import layout_api
import ledger_api
import monitor_api
import notify
import presence
import traffic
import uia
from config_api import send_config as _send_config
from input_injector import BUTTON_FLAGS, InputInjector
from layout_api import toast as _toast

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Wire:
    """One message and everything a handler may act on. Built once per
    message by `web._receive_input`, which owns the socket and the loop.

    It replaces the closure the 36 branches used to share. The fields are
    exactly what those branches read, and nothing else reaches a handler:
    a command cannot touch the receive loop, the auth state or the send
    task, because it is never handed them."""

    ws: WebSocket
    injector: InputInjector
    stream: object
    token: str
    layouts: object
    conn: dict
    msg: dict

    @property
    def kind(self) -> str:
        """The message's own `type` field — the key it was dispatched on.
        A handler serving several kinds (the pointer trio) still has to know
        which one it got, exactly as the branch did."""
        return self.msg.get("type")


# `kind` -> the coroutine that serves it. THE registry: one entry per command,
# and `web._receive_input` does nothing but look a message up in it.
HANDLERS: dict[str, object] = {}


def on(*kinds: str):
    """Register one handler under every `kind` it serves.

    Several kinds may share one handler where the branch always did — the
    pointer trio is one decision about one button, and splitting it would be
    three copies of the same `BUTTON_FLAGS` check."""
    def register(fn):
        for kind in kinds:
            if kind in HANDLERS:
                raise RuntimeError(f"two handlers for {kind!r}")
            HANDLERS[kind] = fn
        return fn
    return register


async def _screenshot(ws: WebSocket, stream, injector: InputInjector, msg: dict) -> None:
    """PC screenshot into the PC clipboard. The Attach set's Shot button sends
    the REGION the phone currently views (owner 2026-08-04 — zoomed = that
    part, layout focus = the layout's rect, never the whole desktop) plus
    paste=true, and the server injects Ctrl+V itself; the legacy snap action
    sends neither and only fills the clipboard."""
    frame = await asyncio.to_thread(stream.take_screenshot)
    if frame is None:
        await _toast(ws, "Screenshot failed — see server log")
        return
    ok = await asyncio.to_thread(clipboard.copy_image, content.crop_to_region(frame, msg))
    if ok and msg.get("paste"):
        await asyncio.to_thread(injector.press_chord, "ctrl+v")
        await _toast(ws, "Screenshot pasted on the PC")
    else:
        await _toast(ws, "Screenshot in PC clipboard — paste with right-click" if ok
                     else "Clipboard busy — try again")


@on("hb")
async def _hb(w: Wire) -> None:
    msg = w.msg
    # The timestamp above IS the heartbeat. It may carry the phone's
    # own traffic counters (Android TrafficStats — what OUR app spent
    # and what the whole device spent); the desktop graph shows both
    # sides so "does it run while the screen is off" stops being an
    # argument (owner 2026-08-05).
    if msg.get("net"):
        traffic.METER.note_phone(msg["net"])
    # ...and the phone's own battery (T80d), riding this SAME beat
    # exactly as `net` does. Absent whenever the device will not say,
    # and absent must never become zero — see `traffic.note_battery`.
    if msg.get("bat"):
        traffic.METER.note_battery(msg["bat"])
    return


@on("away")
async def _away(w: Wire) -> None:
    stream, layouts, conn, msg, kind = w.stream, w.layouts, w.conn, w.msg, w.kind
    # The page is about to be hidden, and it says WHY. An EXCURSION
    # (image picker, camera, voice, a permission dialog) means the
    # owner is still working with us and comes straight back — hold
    # everything. Anything else, above all a LOCK, hands the desk its
    # windows back immediately.
    #
    # The word comes from the Android shell, which reads the screen
    # and keyguard state and knows whether it launched the picker
    # itself. It replaces a 90-second timer in the page that guessed
    # — and guessed "excursion" for a tablet locked seconds after
    # dictating, which is the whole 2026-08-05 topmost failure.
    if msg.get("net"):
        traffic.METER.note_phone(msg["net"])
    # The session's LAST battery reading (T80d): the parting word is
    # the only moment a closing level exists.
    if msg.get("bat"):
        traffic.METER.note_battery(msg["bat"])
    # Nothing may be SENT to a phone that has gone: the page normally
    # closes the socket right behind this message, but when its Wi-Fi
    # falls asleep first the socket lingers — and the encoder was
    # happily filling it for as long as the hold lasted (audit
    # 2026-08-05). The stream stops here, on every kind of away; only
    # the LAYOUT rides the excursion timer.
    conn["paused"] = True
    if conn.get("reset_stream"):
        conn["reset_stream"]()
    if presence.is_excursion(msg):
        conn["away"] = True
        logger.info("Phone announced an excursion — layout held")
    else:
        conn["away"] = None   # a leave is not served by the long budget
        logger.info("Phone left (%s) — the desk gets its windows back",
                    msg.get("reason") or "no reason given")
        await presence.leave_session(layouts, conn,
                                     reason=msg.get("reason"))
    return


@on("pointer_down", "pointer_up", "click")
async def _pointer_down(w: Wire) -> None:
    injector, msg, kind = w.injector, w.msg, w.kind
    button = msg.get("button", "left")
    if button not in BUTTON_FLAGS:
        logger.error("Unknown button %r from client", button)
        return
    if kind == "click":
        injector.click(button)  # at the current cursor — no coordinates
        return
    x, y = float(msg["x"]), float(msg["y"])
    if kind == "pointer_down":
        injector.button_down(x, y, button)
    else:
        injector.button_up(x, y, button)


@on("press")
async def _press(w: Wire) -> None:
    injector, msg = w.injector, w.msg
    # CLICK/HOLD mouse buttons (owner 2026-08-04): down when the
    # finger lands, up when it lifts — at the current cursor.
    button = msg.get("button", "left")
    if button not in BUTTON_FLAGS:
        logger.error("Unknown button %r from client", button)
        return
    injector.press(button, bool(msg.get("down")))


@on("pointer_move")
async def _pointer_move(w: Wire) -> None:
    injector, msg = w.injector, w.msg
    injector.move(float(msg["x"]), float(msg["y"]))


@on("scroll")
async def _scroll(w: Wire) -> None:
    injector, msg = w.injector, w.msg
    # `hticks` is optional (backward compat: an older page that sends
    # only `ticks` scrolls exactly as before — absent means zero, no
    # horizontal event at all, see InputInjector.wheel).
    injector.wheel(float(msg["x"]), float(msg["y"]), float(msg["ticks"]),
                    float(msg.get("hticks", 0.0)))


@on("key_text")
async def _key_text(w: Wire) -> None:
    ws, injector, layouts, conn, msg = w.ws, w.injector, w.layouts, w.conn, w.msg
    # The fence goes INTO the injection, not just before it: typing a
    # dictated sentence takes ~1.1 s of SendInput, and whatever a thief
    # still costs us is TOLD to the phone (focus_guard, round R1).
    lost = await asyncio.to_thread(injector.type_text, str(msg["text"]),
                                   focus_guard.typist(layouts, conn))
    if lost:
        await _toast(ws, focus_guard.loss_notice(lost))


@on("key_special")
async def _key_special(w: Wire) -> None:
    ws, injector, layouts, conn, msg = w.ws, w.injector, w.layouts, w.conn, w.msg
    # HALF 2 of the 2026-08-13 measured defect: `key_text` and
    # `paste_text` both toast a loss when the fence is lost —
    # `key_special` (Backspace, Enter's chord sibling, arrows…) had
    # no check at all, so a key that landed nowhere was invisible to
    # the owner ("buttons randomly stopped working" instead of a
    # named error, constitution priority D). `focus_guard.typist()`
    # is the SAME checkpoint `type_text`'s chunk loop uses between
    # characters — a single key has no chunks, so it is checked once,
    # verified (a bare foreground read on the happy path, a settled
    # retry only when it disagrees) — never the un-verified `guard()`
    # call a few lines above, which only ATTEMPTS a refocus and
    # returns its target regardless of whether it landed.
    ok = await asyncio.to_thread(focus_guard.typist(layouts, conn))
    if ok:
        injector.press_key(str(msg["key"]))
    else:
        await _toast(ws, focus_guard.loss_notice(
            str(msg["key"]), unit="key press"))


@on("paste_text")
async def _paste_text(w: Wire) -> None:
    ws, injector, layouts, conn, msg = w.ws, w.injector, w.layouts, w.conn, w.msg
    # A TYPED command button (owner 2026-08-05 — the Claude set's
    # /usage, /model, /effort). The text goes through the CLIPBOARD
    # and one Ctrl+V rather than key-by-key: a slash command types
    # into an autocomplete menu that re-filters on every character,
    # and one atomic insert cannot be raced by it. Enter is a separate
    # press so `enter: false` can leave the menu standing for the
    # finger to pick from. `focus: "claude"` puts the caret in the
    # Claude prompt first (owner order 2026-08-11) — a refusal there
    # injects NOTHING and has already toasted, so nothing is typed
    # into whatever window really held the keyboard.
    if msg.get("focus") == "claude" and not await claude_api.focus_prompt(
            ws, injector, focus_guard.typist(layouts, conn)):
        return
    lost = await asyncio.to_thread(
        content.paste_text, injector, str(msg.get("text", "")),
        bool(msg.get("enter", True)), focus_guard.typist(layouts, conn))
    if lost:
        await _toast(ws, focus_guard.loss_notice(lost))


@on("viewport")
async def _viewport(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    if stream.mode == "jpeg":
        stream.set_viewport(
            float(msg["x"]), float(msg["y"]), float(msg["w"]), float(msg["h"])
        )
    else:
        # THE ZOOM RAISES THE ENCODED RESOLUTION (owner design,
        # round 3 of T76): the settled rect earns a quantized step
        # (layout_api.zoom_step), the crop never moves, a pan never
        # rebuilds — only a step crossing resets the session.
        await layout_api.zoom_region(ws, layouts, conn, msg)


@on("chord")
async def _chord(w: Wire) -> None:
    ws, injector, conn, msg = w.ws, w.injector, w.conn, w.msg
    chord_text = str(msg["chord"])
    injector.press_chord(chord_text)
    # A chord is guarded on the way IN (Ctrl+V must land in his box)
    # but may itself MOVE the window — Alt+Tab, Win+arrow, Ctrl+W. So
    # the target is re-read on the next key instead of being dragged
    # back to where the chord just left (focus_guard).
    focus_guard.retarget(conn)
    # THE CLIPBOARD LIVES ON BOTH DEVICES (task 182): Copy/Cut push
    # what they just filled the PC clipboard with to the phone.
    await clipboard_sync.after_copy_chord(ws, conn, chord_text)


@on("monitor_switch")
async def _monitor_switch(w: Wire) -> None:
    ws, injector, stream, token, layouts, conn, msg = w.ws, w.injector, w.stream, w.token, w.layouts, w.conn, w.msg
    # `index` is the monitor the phone's layout list asked for (task
    # 155) and is optional — absent means the cycle this message has
    # always been (server/monitor_api.py).
    await monitor_api.switch(
        ws, injector, stream, layouts, conn, msg.get("index"),
        lambda: _send_config(ws, stream, token))


@on("screenshot")
async def _screenshot(w: Wire) -> None:
    ws, injector, stream, msg = w.ws, w.injector, w.stream, w.msg
    await _screenshot(ws, stream, injector, msg)


@on("layout_pick")
async def _layout_pick(w: Wire) -> None:
    ws, stream, layouts, msg = w.ws, w.stream, w.layouts, w.msg
    await layout_api.layout_pick(ws, layouts, stream, msg)


@on("layout_list")
async def _layout_list(w: Wire) -> None:
    ws, stream, layouts, conn = w.ws, w.stream, w.layouts, w.conn
    await layout_api.layout_list(ws, layouts, stream, conn)


@on("layout_acts")
async def _layout_acts(w: Wire) -> None:
    ws, layouts, conn = w.ws, w.layouts, w.conn
    # WHAT THE LAYOUT'S OWN APP CAN DO (owner ballot 2026-08-13, T29).
    # Asked by the New panel when it opens INSIDE a layout — from the
    # desktop there is no member to act on and the answer is empty,
    # which is what makes the panel draw one group instead of two.
    await layout_acts_api.layout_acts(ws, layouts, conn)


@on("layout_act")
async def _layout_act(w: Wire) -> None:
    ws, injector, layouts, conn, msg = w.ws, w.injector, w.layouts, w.conn, w.msg
    await layout_acts_api.layout_act(ws, layouts, conn, injector, msg)


@on("layout_recent")
async def _layout_recent(w: Wire) -> None:
    ws = w.ws
    # The FOURTH creation source (task 228): every layout previously
    # created on this PC, persisted across restarts.
    await layout_api.layout_recent(ws)


@on("layout_recent_use")
async def _layout_recent_use(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    await layout_api.layout_recent_use(ws, layouts, stream, conn, msg)


@on("next_input")
async def _next_input(w: Wire) -> None:
    ws, layouts, conn = w.ws, w.layouts, w.conn
    # Scope follows the view (owner spec): layout focus → only its
    # member windows; full desktop → every visible window.
    hwnds = None
    if conn["active"] is not None and 0 <= conn["active"] < len(layouts.layouts):
        hwnds = list(layouts.layouts[conn["active"]].members)
    name = await asyncio.to_thread(uia.focus_next_input, hwnds)
    label = (name or "")[:40]
    await _toast(ws, f"→ {label}" if name else "No text boxes found")


@on("quality")
async def _quality(w: Wire) -> None:
    ws, stream, conn, msg = w.ws, w.stream, w.conn, w.msg
    # Per-client quality overrides (owner spec 2026-08-05: the phone's
    # panel picks fps / resolution / bitrate level, or auto-reduces on
    # mobile data — the CLIENT decides when and sends the EFFECTIVE
    # values). H.264: the running session is reset and reopens with
    # the new encoder settings. Legacy `reduced: true` (older client
    # pages) maps to the auto-save profile.
    # Parsed in config.quality_override — the SAME function that reads
    # the `auth` message's copy, so the phone's restatement on connect
    # compares equal to what the first session already opened with and
    # cannot force a second encoder (task 203).
    quality = config.quality_override(msg)
    changed = quality != conn.get("quality")
    # RAISING past the desktop's own numbers rebuilds capture and the
    # picture blinks (owner decision, task 131 — the panel says so
    # before he taps). Lowering never reaches here: it lives inside
    # this client's ffmpeg. Safe with one client by rule (4409).
    raise_fps = int(msg.get("raise_fps") or 0) or None
    raise_width = int(msg.get("raise_width") or 0) or None
    if (raise_fps or raise_width or conn.get("raised")) and \
            hasattr(stream, "raise_limits"):
        conn["raised"] = bool(raise_fps or raise_width)
        await asyncio.to_thread(stream.raise_limits, raise_fps, raise_width)
    conn["quality"] = quality
    if changed:
        # SAID OUT LOUD, because it forces an encoder re-open and a
        # re-open is what used to kill the whole socket. His 2026-08-10
        # crash could not be dated in his own log: this branch was the
        # only unlogged cause of a close-and-reopen.
        logger.info("Quality change from the phone: %s", quality)
    if changed and stream.mode == "h264" and conn.get("reset_stream"):
        conn["reset_stream"]()
    if changed:
        await _toast(ws, "Stream: " + (
            "default quality" if quality is None else
            f"{quality['fps'] or 'max'} fps · {quality['res']} res · "
            f"{quality['bitrate']} bitrate"))


@on("tts_info")
async def _tts_info(w: Wire) -> None:
    msg = w.msg
    # The phone lists the text-to-speech voices IT has, once per
    # connection (owner round R2, 2026-08-07). The PC cannot
    # enumerate another device's TTS engine, so this is the only
    # source the desktop Settings window's "Voice" dropdown can have.
    notify.set_voices(msg.get("voices"))


@on("claude_state")
async def _claude_state(w: Wire) -> None:
    ws, layouts, conn = w.ws, w.layouts, w.conn
    # What the focused layout's conversation is running NOW (task 208)
    # — read from its own transcript, never from a phone-side memory.
    await claude_api.send_state(ws, layouts, conn)


@on("ledger_state")
async def _ledger_state(w: Wire) -> None:
    ws, layouts, conn = w.ws, w.layouts, w.conn
    # The focused layout's project ledger (T111) — read fresh from
    # disk every ask, never cached; see ledger_api's own docstring.
    await ledger_api.send_ledger(ws, layouts, conn)


@on("actions_update")
async def _actions_update(w: Wire) -> None:
    ws, msg = w.ws, w.msg
    # THE PHONE EDITS A SET'S INTERIOR (owner 2026-08-04, task 218b):
    # which pool commands ride the D-pad and in which slots. It writes
    # the SAME actions.json the desktop Controls editor writes, through
    # a validator that accepts only the owner-owned keys — the whole
    # handler lives in actions_api with the file's other reader.
    await actions_api.actions_update(ws, msg, agents.claude_settings())


@on("client_log")
async def _client_log(w: Wire) -> None:
    msg = w.msg
    # Silent phone-side diagnostics (owner round 2, 2026-08-05: voice
    # evidence goes to THIS log, never to a panel on the phone).
    logger.info("Phone: %s", str(msg.get("text", ""))[:500])


@on("layout_create")
async def _layout_create(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    await layout_api.layout_create(ws, layouts, stream, conn, msg)


@on("layout_aspect")
async def _layout_aspect(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    await layout_api.layout_aspect(ws, layouts, stream, conn, msg)


@on("layout_focus")
async def _layout_focus(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    index = int(msg["index"])
    if index < 0:
        # A DELIBERATE desktop choice is the state to resume into —
        # nothing to come back to (owner 2026-08-05).
        await asyncio.to_thread(layouts.forget_focus)
    await layout_api.layout_focus(ws, layouts, stream, conn, index)


@on("layout_rename")
async def _layout_rename(w: Wire) -> None:
    ws, layouts, conn, msg = w.ws, w.layouts, w.conn, w.msg
    # The owner's own name for a layout (owner 2026-08-05) — the window
    # title is only the default the creation panel offers.
    if not await asyncio.to_thread(
            layouts.rename, int(msg["index"]), str(msg.get("name", ""))):
        await _toast(ws, "That layout is gone")
    await layout_api.send_layout_state(ws, layouts, conn)
# `layout_apps` lived here — the owner re-ticking which app-aware sets
# a layout carries. Removed 2026-08-07 with the ticks themselves: the
# PC reads what is running (server/agents.py) on every state frame, so
# there is nothing left for anyone to declare.


@on("layout_grid")
async def _layout_grid(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    # The grid's ARRANGEMENT (owner 2026-08-07): a three-window layout
    # picks which edge its single window takes; two and four may only
    # change portrait/landscape. Lives beside the name and the aspect.
    if not await asyncio.to_thread(
            layouts.set_grid, int(msg["index"]),
            str(msg.get("grid", "")), msg.get("orient")):
        await _toast(ws, "That layout is gone")
        await layout_api.send_layout_state(ws, layouts, conn)
    else:
        await layout_api.layout_focus(ws, layouts, stream, conn,
                                      int(msg["index"]))


@on("layout_merge")
async def _layout_merge(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    # One layout dragged ONTO another becomes a grid of the two; the
    # dragged one disappears (owner 2026-08-07).
    src, dst = int(msg["source"]), int(msg["target"])
    if not await asyncio.to_thread(layouts.merge, src, dst,
                                   msg.get("grid")):
        await _toast(ws, "Those two cannot make a grid")
        await layout_api.send_layout_state(ws, layouts, conn)
    else:
        # The target's index slides down when the source sat above it.
        await layout_api.layout_focus(ws, layouts, stream, conn,
                                      dst - 1 if src < dst else dst)


@on("layout_member_remove")
async def _layout_member_remove(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    # ONE window out of a grid (owner request 2026-08-09, task 165) —
    # a four becomes a three, a three a two, a two a single. The whole
    # handler lives in layout_api with the rest of the layout
    # protocol; web.py stands at the 1,000-line wall.
    await layout_api.layout_member_remove(ws, layouts, stream, conn, msg)


@on("layout_member_list")
async def _layout_member_list(w: Wire) -> None:
    ws, stream, layouts, msg = w.ws, w.stream, w.layouts, w.msg
    await layout_api.layout_member_list(ws, layouts, stream, msg)


@on("layout_member_add")
async def _layout_member_add(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    await layout_api.layout_member_add(ws, layouts, stream, conn, msg)


@on("layout_split")
async def _layout_split(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    await layout_api.layout_split(ws, layouts, stream, conn, msg)


@on("layout_member_eject")
async def _layout_member_eject(w: Wire) -> None:
    ws, stream, layouts, conn, msg = w.ws, w.stream, w.layouts, w.conn, w.msg
    await layout_api.layout_member_eject(ws, layouts, stream, conn, msg)


@on("layout_reorder")
async def _layout_reorder(w: Wire) -> None:
    ws, layouts, conn, msg = w.ws, w.layouts, w.conn, w.msg
    # Dropping BETWEEN two rows — the list's own order, nothing moves
    # on the PC (owner 2026-08-07). In layout_api because it must also
    # correct `conn["active"]`: the focus rides on an INDEX and a
    # reorder moves indices (see there), and web.py is at the wall.
    await layout_api.layout_reorder(ws, layouts, conn, msg)


@on("layout_remove")
async def _layout_remove(w: Wire) -> None:
    ws, layouts, conn, msg = w.ws, w.layouts, w.conn, w.msg
    index = int(msg["index"])
    # `close` is the owner's second act (2026-08-08, task 116): the
    # layout leaves AND its windows are asked to close. Read with an
    # explicit `is True` — the destructive half may only ever be
    # reached by a page that MEANT it, never by a truthy accident.
    close = msg.get("close") is True
    standing = await asyncio.to_thread(layouts.remove, index, close)
    if conn["active"] is not None:
        if conn["active"] == index:
            conn["active"], conn["region"] = None, None
        elif conn["active"] > index:
            conn["active"] -= 1
    await layout_api.send_layout_state(ws, layouts, conn)
    if standing:
        # An app with unsaved work put up its own dialog and is still
        # there. The phone SAYS so — the alternative is the layout
        # vanishing off the bar while a window he expected to close
        # sits waiting for an answer he never saw asked.
        await _toast(ws, f"{len(standing)} window(s) still open — "
                         f"answer the app on the PC")
