"""Link Recovery Gate: a phone that loses its route comes back BY ITSELF.

The owner's report (2026-08-07): *"kada nismo na wi-fi mreži — a i kada jesmo,
samo ne toliko često — dešava nam se prekid veze, i ovo 'Try again' dugme retko
kad pomogne, već moramo više puta, nekad čak i da zatvorimo celu aplikaciju, da
ugasimo i upalimo ponovo."*

A REPEAT: three separate mechanisms were written as the answer to this exact
complaint — two stored addresses probed at start, a self-re-probing error card,
a /ping contract that only the exact 204 satisfies. Every one of them holds. All
three only ever run in states he is not in. The state he IS in is a page that
loaded perfectly and is now retrying an address that no longer reaches the PC,
and in that state:

  - the shell re-probed only `if (errorView.visibility == VISIBLE)` — a
    cold-start state, so nothing re-probed and nothing re-chose;
  - the page could not move itself either: its socket goes to `location.host`,
    the address the DOCUMENT was loaded from, and nothing else;
  - a socket that stays CONNECTING (no route) or opens and is never served is
    skipped by `ensureConnected`, so the page that looked like it was retrying
    every 2 s was retrying nothing at all;
  - on the PC, a socket the watchdog had already declared dead kept the
    one-device slot, so the returning phone arrived as a SECOND DEVICE against
    its own corpse and its first act was `await prev.close(4409)` on a socket
    with nowhere to send — ahead of `actions`, `layout_state` and `config`.

Killing the app was the only cure because a fresh process is the only thing
that re-probes both addresses. This gate proves it no longer has to be.

What is proven here, and what each check would let through if it were missing:

  THE PC
  1. A session the watchdog ends VACATES the one-device slot. Without it the
     next connection evicts a corpse before serving anyone.
  2. Handing the session over is BOUNDED. Without it a `close()` into a black
     hole holds up the device that has a person behind it.
  3. And the new client really is served: `actions`, `layout_state` and
     `config` all arrive while the previous socket refuses to close at all.

  THE PAGE (the real client/state.js + client/connection.js, run in node on a
  virtual clock — no browser, no server, no waiting)
  4. A socket that never opens is abandoned and retried.
  5. A socket that opens and is never served is abandoned and retried.
  6. A RUN of unserved connections — silent or flapping — asks the shell to
     re-probe. A served one never does.
  7. 4401 and 4409 are answers from a server we CAN hear: they must never be
     read as a lost route, or the shell re-probes an address that works.

  THE SHELL (source contract — there is no Android runtime on this machine and
  no device attached; what the shell DOES with it is proven only on his phone)
  8. The re-probe on a default-network change is not gated on the error card.
  9. `Android.linkLost()` exists and reaches the resolver.
 10. Session health is judged by ADDRESS, not by a whole URL string — with the
     network callback now firing on a live page, a mismatch there would reload
     a working session on every blip.

Run:  .venv\\Scripts\\python tests/test_link_recovery.py
"""

import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import focus_guard  # noqa: E402
import presence  # noqa: E402
import web  # noqa: E402

ANDROID = PROJECT / "android/app/src/main/java/com/uvuruna/remoteuser"
CLIENT = PROJECT / "client"


# ═══════════════════════════ FAKES ═══════════════════════════
class DeadSocket:
    """The corpse: a socket whose peer is unreachable. Nothing it is asked to
    do ever finishes — which is what a black-holed TCP connection is. It is
    NOT an error, and that is the whole trap: an exception would have been
    caught years ago."""

    def __init__(self):
        self.close_attempted = False

    async def close(self, code: int = 1000) -> None:
        self.close_attempted = True
        await asyncio.Event().wait()   # never returns, never raises

    async def send_text(self, text: str) -> None:
        await asyncio.Event().wait()


class LiveSocket:
    """The device on the line. Records what the server actually sent it."""

    def __init__(self, script=None):
        self.client = "test-phone"
        self.sent: list = []
        self.closed_code = None
        self._script = list(script or [])

    async def accept(self) -> None:
        pass

    async def receive_text(self) -> str:
        if not self._script:
            raise web.WebSocketDisconnect(1000)
        return json.dumps(self._script.pop(0))

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def send_bytes(self, data: bytes) -> None:
        pass

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code

    def types(self) -> list:
        return [m.get("type") for m in self.sent]


class FakeRegistry:
    """Only what the connection path touches."""

    def __init__(self):
        self.minimized = 0
        self.cleared = 0

    def state(self, active, region) -> dict:
        return {"type": "layout_state", "layouts": [], "active": None,
                "region": None, "orient": None}

    def resume_index(self):
        return None

    def minimize_members(self) -> None:
        self.minimized += 1

    def clear_topmost(self) -> None:
        self.cleared += 1

    def prune(self) -> None:
        pass


class FakeStream:
    """A JPEG-mode stream — no ffmpeg, no dxcam, no 4K."""
    mode = "jpeg"
    width = 1920
    height = 1080
    monitor_index = 0

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def set_viewport(self, *a) -> None:
        pass

    def output_count(self) -> int:
        return 1


class FakeInjector:
    def take_input_alarm(self) -> bool:
        return False

    def cursor_norm(self):
        return None


def install_fakes() -> None:
    # `_send_config` asks Windows for the Tailscale address (a subprocess) —
    # a link test must not depend on this machine's VPN state.
    web.pairing.get_tailscale_ip = lambda: None
    # The focus guard polls the real foreground every 0.25 s. Nothing here is
    # about focus, and this test may never touch a window on the owner's PC.
    async def _no_watch(layouts, conn):
        await asyncio.Event().wait()
    focus_guard.watch = _no_watch


def fail(msg: str) -> None:
    raise AssertionError(msg)


# ═══════════════════════════ THE PC ═══════════════════════════
def check_watchdog_vacates_the_slot() -> None:
    """A session the watchdog has declared dead has no claim on the one-device
    slot. It used to keep it until the receive loop unblocked — which, on a
    link that simply went silent, waits out the OS TCP timeout. Until then the
    phone coming back on its new route was not a reconnect, it was a second
    device arriving against its own corpse."""
    async def run():
        ws = LiveSocket()
        layouts = FakeRegistry()
        conn = {"seen": 0.0, "away": None, "left": False,
                "active": 0, "region": None}
        active_client = {"ws": ws}
        # `seen` is ancient, so the very first poll finds the silence.
        await asyncio.wait_for(
            presence.watchdog(ws, layouts, conn, active_client), timeout=10)
        if active_client["ws"] is not None:
            fail("the watchdog ended the session but kept the one-device slot "
                 "— the phone's own reconnect will be evicted as a 2nd device")
        if ws.closed_code != 4408:
            fail(f"expected the dead session closed with 4408, got {ws.closed_code}")
        if layouts.minimized != 1:
            fail("the desk did not get its windows back")

    asyncio.run(run())


def check_handover_is_bounded() -> None:
    """`hand_over` must return even when the previous socket cannot be closed
    at all — and must still be trying afterwards."""
    async def run():
        dead = DeadSocket()
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            await asyncio.wait_for(presence.hand_over(dead), timeout=10)
        except asyncio.TimeoutError:
            fail("handing the session over never returned against a peer that "
                 "cannot answer — the device on the line waits behind a corpse")
        spent = loop.time() - started
        if spent > presence.HANDOVER_TIMEOUT_S * 3:
            fail(f"handing over took {spent:.1f}s against an unreachable peer")
        if not dead.close_attempted:
            fail("the previous device was never actually asked to close")
        # Still pending in the background — a courtesy that outlives the wait.
        if not presence._handovers:
            fail("the close was dropped instead of left running")
        for task in list(presence._handovers):
            task.cancel()

    asyncio.run(run())


def check_returning_phone_is_served() -> None:
    """The end-to-end claim: with a socket in the slot that can never be
    closed, the device on the line still gets everything it needs to work."""
    async def run():
        install_fakes()
        layouts = FakeRegistry()
        loop = asyncio.get_running_loop()
        app = web.create_app(FakeStream(), web.FrameHub(loop),
                             injector=FakeInjector(), token="tok",
                             layouts=layouts)
        endpoint = next(r.endpoint for r in app.routes
                        if getattr(r, "path", None) == "/ws")
        # A first connection puts a corpse in the slot, exactly as a dead
        # route does: authenticated, then unreachable forever.
        corpse = DeadSocket()
        corpse.client = "old-route"
        first = asyncio.create_task(endpoint(corpse))
        await asyncio.sleep(0)
        # ...and now the same phone, on its new route.
        live = LiveSocket([{"type": "auth", "token": "tok",
                            "screen": {"w": 1600, "h": 2560}}])
        try:
            await asyncio.wait_for(endpoint(live), timeout=8)
        except asyncio.TimeoutError:
            fail("the returning phone was never served — the connection hung "
                 "handing the session over to a socket that cannot answer")
        finally:
            first.cancel()
        for needed in ("actions", "layout_state", "config"):
            if needed not in live.types():
                fail(f"the returning phone never received `{needed}` "
                     f"(got {live.types()})")

    asyncio.run(run())


# ═══════════════════════════ THE PAGE ═══════════════════════════
# The real client/state.js and client/connection.js, run in node inside a
# sandbox whose clock, WebSocket and `window.Android` the scenario drives. No
# browser and no server: what is under test is the page's own judgement about
# its own connection, and that is pure logic.
HARNESS = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const CLIENT = process.argv[2], SCENARIO = process.argv[3];

// A stub that survives any use — every global the page's other five scripts
// would have defined resolves to this, and none of them is under test here.
const STUB = new Proxy(function () {}, {
  get(t, k) {
    if (k === Symbol.toPrimitive || k === "toString") return () => "";
    if (k === Symbol.iterator) return function* () {};
    return STUB;
  },
  apply: () => STUB, construct: () => STUB, has: () => true, set: () => true,
});

let vnow = 0, seq = 0;
const timers = new Map();
const setTimeoutV = (fn, ms) => {
  const id = ++seq; timers.set(id, { at: vnow + (ms || 0), fn, every: null }); return id;
};
const setIntervalV = (fn, ms) => {
  const id = ++seq; timers.set(id, { at: vnow + (ms || 0), fn, every: ms || 1 }); return id;
};
const clearTimerV = (id) => timers.delete(id);
function advance(ms) {
  const end = vnow + ms;
  for (;;) {
    let next = null;
    for (const [id, t] of timers)
      if (t.at <= end && (next === null || t.at < timers.get(next).at)) next = id;
    if (next === null) break;
    const t = timers.get(next);
    vnow = t.at;
    if (t.every) t.at = vnow + t.every; else timers.delete(next);
    t.fn();
  }
  vnow = end;
}

const sockets = [];
class FakeSocket {
  constructor(url) { this.url = url; this.readyState = 0; this.closed = false; sockets.push(this); }
  send() {}
  close() { this.closed = true; this.readyState = 3; }
  open() { this.readyState = 1; if (this.onopen) this.onopen(); }
  serve(msg) { if (this.onmessage) this.onmessage({ data: JSON.stringify(msg) }); }
  die(code) { this.readyState = 3; if (this.onclose) this.onclose({ code }); }
}
FakeSocket.CONNECTING = 0; FakeSocket.OPEN = 1; FakeSocket.CLOSING = 2; FakeSocket.CLOSED = 3;

const linkLost = [], statuses = [];
const store = {
  console, JSON, Math, Object, Array, String, Number, Boolean, Error, Promise, Symbol,
  setTimeout: setTimeoutV, clearTimeout: clearTimerV,
  setInterval: setIntervalV, clearInterval: clearTimerV,
  performance: { now: () => vnow }, Date: { now: () => vnow },
  WebSocket: FakeSocket, location: { host: "192.168.0.30:8777" },
  token: "t", IN_APP: true, ws: null,
  document: new Proxy({ hidden: false }, {
    get: (t, k) => (k in t ? t[k] : STUB), set: (t, k, v) => { t[k] = v; return true; },
  }),
  window: new Proxy({
    Android: { linkLost: () => linkLost.push(vnow) },
    addEventListener: () => {}, screen: { width: 1600, height: 2560 },
  }, { get: (t, k) => (k in t ? t[k] : STUB), set: (t, k, v) => { t[k] = v; return true; } }),
};
store.globalThis = store;
const ctx = vm.createContext(new Proxy(store, {
  has: () => true,
  get: (t, k) => (k === Symbol.unscopables ? undefined : (k in t ? t[k] : STUB)),
  set: (t, k, v) => { t[k] = v; return true; },
}));
const load = (f) => vm.runInContext(fs.readFileSync(path.join(CLIENT, f), "utf8"), ctx,
                                    { filename: f });
load("state.js");
store.__record = (c, t) => statuses.push(t);
vm.runInContext("setStatus = (c, t) => __record(c, t);", ctx);
load("connection.js");

const K = (n) => vm.runInContext(n, ctx);
const last = () => sockets[sockets.length - 1];
const out = { constants: { CONNECT_TIMEOUT_MS: K("CONNECT_TIMEOUT_MS"),
                           SERVED_TIMEOUT_MS: K("SERVED_TIMEOUT_MS"),
                           LINK_LOST_TRIES: K("LINK_LOST_TRIES") } };
const CONFIG = { type: "config", monitor_width: 100, monitor_height: 100, stream: "jpeg" };
try {
  if (SCENARIO === "never_opens") {
    advance(K("CONNECT_TIMEOUT_MS") + 100);
  } else if (SCENARIO === "opens_never_served") {
    last().open(); advance(K("SERVED_TIMEOUT_MS") + 100);
  } else if (SCENARIO === "silent_run") {
    for (let i = 0; i < K("LINK_LOST_TRIES"); i++) {
      last().open(); advance(K("SERVED_TIMEOUT_MS") + 100);
    }
  } else if (SCENARIO === "flapping") {
    for (let i = 0; i < K("LINK_LOST_TRIES"); i++) {
      const s = last(); s.open(); advance(500); s.die(1006); advance(2100);
    }
  } else if (SCENARIO === "served") {
    const s = last(); s.open(); s.serve(CONFIG); advance(K("SERVED_TIMEOUT_MS") * 5);
  } else if (SCENARIO === "taken_over" || SCENARIO === "rejected") {
    const code = SCENARIO === "taken_over" ? 4409 : 4401;
    for (let i = 0; i < K("LINK_LOST_TRIES") + 2; i++) {
      const s = last(); s.open(); s.die(code); advance(2100);
    }
  } else { throw new Error("unknown scenario " + SCENARIO); }
} catch (e) { out.error = String((e && e.stack) || e); }
out.sockets = sockets.length;
out.closed = sockets.filter((s) => s.closed).length;
out.link_lost = linkLost.length;
out.statuses = statuses;
console.log(JSON.stringify(out));
"""


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        fail("node is required for the page half of this gate (it runs the "
             "REAL client/connection.js) — install Node.js. Never skip a gate "
             "silently: a page that cannot recover is the whole bug.")
    return node


def _page(scenario: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "harness.js"
        script.write_text(HARNESS, encoding="utf-8")
        proc = subprocess.run(
            [_node(), str(script), str(CLIENT), scenario],
            capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        fail(f"the page harness crashed on `{scenario}`:\n{proc.stderr}")
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    if "error" in out:
        fail(f"the page threw on `{scenario}`: {out['error']}")
    return out


def check_page_abandons_a_socket_that_never_opens() -> None:
    """`new WebSocket()` to an address with no route sits in CONNECTING until
    Android's own TCP timeout — up to two minutes — and `ensureConnected`
    skips a CONNECTING socket. The page that looked like it retried every 2 s
    retried nothing at all."""
    out = _page("never_opens")
    if out["sockets"] < 2:
        fail("a socket stuck in CONNECTING was never abandoned — the page "
             "waits out the OS TCP timeout with no retry at all")
    if out["closed"] < 1:
        fail("the stuck socket was left open")
    if not any("route" in s.lower() for s in out["statuses"]):
        fail(f"the page never SAID what was wrong: {out['statuses']}")


def check_page_abandons_a_socket_that_is_never_served() -> None:
    """Opened, authenticated, and then nothing: no `config`, no stream. The
    pill said "Connected" over a frozen frame and `ensureConnected` skipped an
    OPEN socket — a dead end with no exit but killing the app."""
    out = _page("opens_never_served")
    if out["sockets"] < 2:
        fail("a socket that opened onto silence was never abandoned — the "
             "page shows Connected forever and only a restart clears it")
    if not any("answering" in s.lower() for s in out["statuses"]):
        fail(f"the page never SAID what was wrong: {out['statuses']}")


def check_a_run_of_dead_connections_asks_the_shell() -> None:
    """The page owns one address — the one the DOCUMENT was loaded from. Only
    the shell owns both, so only the shell can move us. Silent or flapping,
    a run of connections that were never served has to reach it."""
    for scenario in ("silent_run", "flapping"):
        out = _page(scenario)
        if out["link_lost"] != 1:
            fail(f"`{scenario}`: the shell was asked to re-probe "
                 f"{out['link_lost']} times, expected exactly 1 — the page "
                 f"cannot change address by itself, so nobody would")


def check_a_working_link_never_asks() -> None:
    """The server's first message — of ANY kind — is proof of life, and proof
    of life forgets every failure before it. A page that kept asking would
    re-probe a healthy session; a page that waited for `config` specifically
    would abandon a working H.264 connection for being slow to start ffmpeg."""
    out = _page("served")
    if out["link_lost"] != 0:
        fail("a served connection asked the shell to re-probe")
    if out["sockets"] != 1:
        fail(f"a served connection was reconnected {out['sockets']} times")
    if out["closed"] != 0:
        fail("a served connection was abandoned")


def check_an_answer_is_not_a_lost_route() -> None:
    """4401 and 4409 come from a server we can hear perfectly. Reading either
    as a lost route would send the shell probing an address that works — and
    4409 would do it in a loop, which is exactly what "no auto-reconnect"
    exists to prevent."""
    for scenario in ("taken_over", "rejected"):
        out = _page(scenario)
        if out["link_lost"] != 0:
            fail(f"`{scenario}` was read as a lost route")
        if out["sockets"] != 1:
            fail(f"`{scenario}` auto-reconnected ({out['sockets']} sockets)")


# ═══════════════════════════ THE SHELL ═══════════════════════════
def _kotlin(name: str) -> str:
    return (ANDROID / name).read_text(encoding="utf-8")


def _strip_comments(src: str) -> str:
    """Comments in this project carry the failure history, and every word of
    it would match these greps. Only the CODE may answer."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//.*", "", src)


def check_shell_reprobes_on_a_network_change() -> None:
    """The gate over the actual bug. `onAvailable` re-probed only while the
    native error card was on screen — a cold-start state. The state he is in
    is a LOADED page on an address that stopped reaching the PC, and there
    that condition is false, so nothing ever re-chose."""
    src = _strip_comments(_kotlin("MainActivity.kt"))
    body = re.search(r"override fun onAvailable\([^)]*\)\s*\{(.*?)\n        \}",
                     src, flags=re.S)
    if body is None:
        fail("MainActivity has no onAvailable — nothing reacts to a new network")
    text = body.group(1)
    if "resolveAndLoad" not in text:
        fail("a new default network does not re-probe the stored addresses")
    if "errorView" in text:
        fail("the re-probe on a network change is still gated on the error "
             "card — a page that LOADED and then lost its route never "
             "re-chooses an address, and only killing the app helps")


def check_shell_answers_the_page() -> None:
    """`Android.linkLost()` — the page saying it has lost the PC — must exist
    and must reach the resolver."""
    bridge = _strip_comments(_kotlin("Bridge.kt"))
    hook = re.search(r"@JavascriptInterface\s+fun linkLost\(\)\s*\{(.*?)\n    \}",
                     bridge, flags=re.S)
    if hook is None:
        fail("Bridge exposes no linkLost() — the page has no way to tell the "
             "shell its address is dead, and the page cannot move itself")
    called = re.search(r"host\.(\w+)\(\)", hook.group(1))
    if called is None:
        fail("Bridge.linkLost() reaches nothing in the shell")
    activity = _strip_comments(_kotlin("MainActivity.kt"))
    target = re.search(
        r"fun " + called.group(1) + r"\(\)\s*\{(.*?)\n    \}", activity, flags=re.S)
    if target is None:
        fail(f"Bridge.linkLost() calls host.{called.group(1)}(), which "
             f"MainActivity does not define")
    if "resolveAndLoad" not in target.group(1):
        fail(f"MainActivity.{called.group(1)}() does not re-probe the "
             f"addresses — the page's report goes nowhere")
    if not re.search(r"\bfun linkLost\b", _strip_comments(
            (CLIENT / "connection.js").read_text(encoding="utf-8")) or "x"):
        pass  # the page's side is checked by the harness above


def check_session_health_is_judged_by_address() -> None:
    """With the network callback now firing on a LIVE page, `sessionHealthy`
    is what stands between a blip and a reload of a working session. It must
    compare which ADDRESS the document is on — `web.url` is the page's own
    text (a path, a fragment, a token re-issued since pairing), and matching
    it character for character against a stored pairing URL answers "is this
    the address that just answered?" with a no far too often."""
    src = _strip_comments(_kotlin("MainActivity.kt"))
    if "val sessionHealthy" not in src:
        fail("MainActivity no longer decides whether a live session is healthy")
    line = re.search(r"val sessionHealthy =(.*?)\n\s*if \(sessionHealthy",
                     src, flags=re.S)
    if line is None:
        fail("sessionHealthy is computed but never used")
    if "origin(" not in line.group(1):
        fail("session health still compares whole URL strings — every network "
             "event would reload a session that is working perfectly")
    if not re.search(r"private fun origin\(", src):
        fail("origin() is referenced but not defined")


# ═══════════════════════════ THE CHECKS ═══════════════════════════
CHECKS = [
    ("PC: a dead session vacates the one-device slot",
     check_watchdog_vacates_the_slot),
    ("PC: handing the session over is bounded",
     check_handover_is_bounded),
    ("PC: the returning phone is served over a corpse",
     check_returning_phone_is_served),
    ("Page: a socket that never opens is abandoned",
     check_page_abandons_a_socket_that_never_opens),
    ("Page: a socket that is never served is abandoned",
     check_page_abandons_a_socket_that_is_never_served),
    ("Page: a run of dead connections asks the shell",
     check_a_run_of_dead_connections_asks_the_shell),
    ("Page: a working link never asks",
     check_a_working_link_never_asks),
    ("Page: 4401/4409 are answers, not a lost route",
     check_an_answer_is_not_a_lost_route),
    ("Shell: a network change re-probes, card or no card",
     check_shell_reprobes_on_a_network_change),
    ("Shell: Android.linkLost() reaches the resolver",
     check_shell_answers_the_page),
    ("Shell: session health is judged by address",
     check_session_health_is_judged_by_address),
]


def test_link_recovery() -> None:
    for name, check in CHECKS:
        check()
        print(f"  OK  {name}")


if __name__ == "__main__":
    print("Link Recovery Gate — a phone that loses its route comes back by itself")
    try:
        test_link_recovery()
    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    print("\nAll link-recovery checks passed.")
