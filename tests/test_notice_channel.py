"""Gate: a notice reaches the phone while the owner is NOT looking at it.

The owner's report (2026-08-07): *"notifikacije mi stižu tek kada podignem
aplikaciju iako je sve vreme otvorena u pozadini"*. The cause was structural —
every notice rode the STREAMING socket, and that socket is closed on purpose
the moment the page hides (project CLAUDE.md constraint 8). At the exact moment
a notice mattered there was no channel, so `server/notify.py` queued it until
he opened the app himself. His decision was a small foreground service holding
a SEPARATE, MINIMAL channel: *"android strana čeka signal, ne prima ništa od
kompjutera, ali ostane u stanju čekanja signala."*

What must hold, and what each check would let through if it were missing:

  1. `/notices` refuses an unauthenticated caller — it would otherwise be a way
     to make any phone on the network buzz, and to learn an agent runs here.
  2. With the PAGE CLOSED, a notice arrives down the waiting channel, whole:
     the agent's name, the composed line, speak/voice/rate and the timestamp.
     This is the entire feature.
  3. It is never delivered TWICE. With the page open the page takes it and the
     waiting channel hears nothing but its beat — the carriers are a chain of
     returns, not three sends.
  4. A waiting channel is NOT a present phone. Attaching one must leave the
     server's one-device slot empty, the client count at zero, the capture
     stopped, the layout registry untouched, and must arm neither the presence
     watchdog nor the focus guard. A notice connection that looked present
     would nail the owner's windows always-on-top over his own desk.
  5. The queue is the LAST resort, not the normal path: nothing is queued while
     either channel lives, everything is queued when neither does, and what was
     held is handed over the moment the phone starts waiting again — oldest
     first.
  6. Idle really is idle: between notices the channel carries exactly one byte
     per beat and nothing else.

The Kotlin half (NoticeService / NoticeLink / Bridge) cannot be exercised here
— there is no Android runtime on this machine and no device attached. This gate
proves the PC's half of the contract and the exact bytes the shell must read;
what the shell does with them is proven only on the owner's phone.

Run:  .venv\\Scripts\\python tests/test_notice_channel.py
"""

import json
import queue
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import uvicorn  # noqa: E402

import focus_guard  # noqa: E402
import notify  # noqa: E402
import presence  # noqa: E402
import web  # noqa: E402

TOKEN = "noticetoken"
PORT = 8899
# The real beat is 60 s (notify.BEAT_S). Shortened here so "idle" and "the
# channel noticed the phone went away" are observable in a few seconds — the
# VALUE is a tuning number, the BEHAVIOUR is what this gate pins.
TEST_BEAT_S = 0.4


# ═══════════════════════════ THE FAKES ═══════════════════════════
class FakeStream:
    """JPEG-mode duck interface. `running` is the whole point: a notice
    connection must never start the capture."""
    mode = "jpeg"
    width = 1920
    height = 1080
    monitor_index = 0

    def __init__(self):
        self.running = 0

    def output_count(self):
        return 1

    def set_viewport(self, x, y, w, h):
        pass

    def start(self):
        self.running += 1

    def stop(self):
        self.running -= 1

    def switch_to(self, index):
        return False

    def take_screenshot(self):
        return None


class FakeRegistry:
    """Only what a session teardown touches — both counters must stay 0."""

    def __init__(self):
        self.minimized = 0
        self.cleared = 0
        self.layouts: list = []

    def minimize_members(self):
        self.minimized += 1

    def clear_topmost(self):
        self.cleared += 1

    def resume_index(self):
        return None


class FakePageWs:
    """Stands in for the page's authenticated socket, exactly as web.py holds
    it in its one-device slot."""

    def __init__(self, dead: bool = False):
        self.sent: list = []
        self.dead = dead

    async def send_text(self, text: str) -> None:
        if self.dead:
            raise RuntimeError("socket closed")
        self.sent.append(json.loads(text))


# How many times the server armed a real session's background tasks. A notice
# connection must add nothing to either.
armed = {"watchdog": 0, "focus": 0}
_real_watchdog, _real_watch = presence.watchdog, focus_guard.watch


async def _counting_watchdog(*a, **k):
    armed["watchdog"] += 1
    return await _real_watchdog(*a, **k)


async def _counting_watch(*a, **k):
    armed["focus"] += 1
    return await _real_watch(*a, **k)


presence.watchdog = _counting_watchdog
focus_guard.watch = _counting_watch

stream = FakeStream()
layouts = FakeRegistry()
stats = web.ServerStats()
server_ready = threading.Event()
server_error: list = []


def run_server() -> None:
    import asyncio

    async def main():
        loop = asyncio.get_running_loop()
        app = web.create_app(stream, web.FrameHub(loop), injector=None,
                             token=TOKEN, stats=stats, layouts=layouts)
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=PORT,
            log_level="warning", log_config=None, lifespan="off",
        ))
        server_ready.set()
        await server.serve()

    try:
        asyncio.run(main())
    except BaseException as e:  # noqa: BLE001 — a taken port exits via SystemExit
        server_error.append(e)
        server_ready.set()


# ═══════════════════════════ THE PHONE'S HALF ═══════════════════════════
class Waiting:
    """What the Android foreground service does, in twenty lines: open
    `/notices` once and block on readline() forever. It sends NOTHING."""

    def __init__(self):
        self.lines: queue.Queue = queue.Queue()
        self.beats = 0
        self._response = None
        self._stop = False
        self._thread = threading.Thread(target=self._read, daemon=True)

    def open(self, timeout: float = 5.0) -> "Waiting":
        self._response = urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/notices?token={TOKEN}", timeout=timeout)
        self._thread.start()
        return self

    def _read(self) -> None:
        while not self._stop:
            try:
                raw = self._response.readline()
            except (OSError, AttributeError, ValueError):
                # close() from the main thread yanks the socket out from under
                # a blocked readline — teardown noise in THIS harness only.
                return
            if not raw:
                return                      # the PC ended the response
            text = raw.decode().strip()
            if not text:
                self.beats += 1             # the one-byte beat — not news
                continue
            self.lines.put(json.loads(text))

    def next(self, timeout: float = 4.0):
        try:
            return self.lines.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        self._stop = True
        if self._response is not None:
            self._response.close()


def post(payload: dict, token: str = TOKEN) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/notify?token={token}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def until(pred, timeout: float = 4.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.05)
    return False


def reset() -> None:
    notify._pending.clear()
    notify._page["ws"] = None


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def check_notices_refuses_a_bad_token() -> bool:
    try:
        urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/notices?token=wrong", timeout=5).close()
    except urllib.error.HTTPError as e:
        return e.code == 403
    return False


def check_a_closed_page_still_gets_the_notice(chan: Waiting) -> bool:
    """THE feature. The page is gone; the phone is waiting; the notice lands
    whole — same agent, same line, same voice instructions as on the page."""
    reset()
    status, answer = post({"agent": "Remote User · 3f9c1a", "event": "waiting",
                           "text": "controls round"})
    got = chan.next()
    return (status == 200 and answer.get("ok") is True
            and got is not None
            and got["type"] == "notify"
            and got["agent"] == "Remote User · 3f9c1a"
            and got["title"] == "Remote User · 3f9c1a needs you"
            and got["text"] == "controls round"
            and "speak" in got and "voice" in got and "rate" in got
            and got["at"] > 0
            # ...and it was NOT also queued for later.
            and not notify._pending)


def check_a_waiting_phone_is_not_a_present_phone() -> bool:
    """A notice connection must look like nothing at all to the rest of the
    server. If it ever counted as presence, the owner's own Chrome and VSCode
    would be nailed above his desk by a phone in his pocket."""
    return (notify.waiting() is True
            and notify._page["ws"] is None      # the one-device slot, untouched
            and stats.clients == 0              # no client, so no traffic session
            and stream.running == 0             # no capture, no encoder
            and layouts.minimized == 0 and layouts.cleared == 0
            and armed["watchdog"] == 0 and armed["focus"] == 0)


def check_idle_costs_one_byte(chan: Waiting) -> bool:
    """Between notices the channel carries the beat and nothing else — the
    'minimal' half of his instruction, measured."""
    before = chan.beats
    if not until(lambda: chan.beats >= before + 2, timeout=TEST_BEAT_S * 8):
        return False
    return chan.lines.empty()


def check_an_open_page_takes_it_alone(chan: Waiting) -> bool:
    """No notice may arrive twice. With the page open, the page is the carrier
    and the waiting channel hears only its beat."""
    reset()
    page = FakePageWs()
    notify._page["ws"] = page
    _, answer = post({"agent": "Both", "event": "finished", "text": ""})
    delivered = until(lambda: len(page.sent) == 1)
    # Give the waiting channel more than a beat's worth of time to prove it
    # got nothing — an instant check would pass even on a real double.
    time.sleep(TEST_BEAT_S * 3)
    notify._page["ws"] = None
    return (delivered and answer.get("ok") is True
            and page.sent[0]["agent"] == "Both"
            and chan.lines.empty()          # the phone's other ear stayed shut
            and not notify._pending)        # and nothing was queued either


def check_a_dying_page_falls_through_not_into_the_queue(chan: Waiting) -> bool:
    """The page hides and its socket dies between the check and the send. The
    service is already waiting — that notice belongs to it, not to a queue the
    owner has to open the app to empty."""
    reset()
    notify._page["ws"] = FakePageWs(dead=True)
    _, answer = post({"agent": "Falling", "event": "finished", "text": ""})
    got = chan.next()
    notify._page["ws"] = None
    return (got is not None and got["agent"] == "Falling"
            and answer.get("ok") is True and not notify._pending)


def check_the_queue_is_the_last_resort() -> bool:
    """No channel of either kind = the phone is truly unreachable. Only then
    does the queue fill — and it hands everything over, oldest first, the
    moment the phone starts waiting again."""
    reset()
    if not until(lambda: notify.waiting() is False, timeout=6):
        return False                        # the closed channel must detach
    for i in range(3):
        post({"agent": f"Held{i}", "event": "finished", "text": ""})
    status, answer = post({"agent": "Held3", "event": "finished", "text": ""})
    if not (status == 200 and answer.get("ok") is False
            and "held" in str(answer.get("reason", "")).lower()
            and len(notify._pending) == 4):
        return False
    chan = Waiting().open()
    try:
        got = [chan.next() for _ in range(4)]
        return ([n["agent"] for n in got if n] == ["Held0", "Held1", "Held2", "Held3"]
                and not notify._pending)
    finally:
        chan.close()


def main() -> int:
    notify.BEAT_S = TEST_BEAT_S
    threading.Thread(target=run_server, daemon=True).start()
    server_ready.wait(15)
    deadline = time.time() + 10
    while time.time() < deadline:
        if server_error:
            raise server_error[0]
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)

    results: dict[str, bool] = {}
    results["/notices refuses a bad token"] = check_notices_refuses_a_bad_token()

    chan = Waiting().open()
    try:
        if not until(notify.waiting, timeout=4):
            results["the phone can attach a waiting channel"] = False
        else:
            results["the phone can attach a waiting channel"] = True
            # FIRST, before any check calls reset(): this one reads the state
            # the ATTACH itself left behind, and a later reset would scrub a
            # real defect out from under it (found by planting one).
            results["a waiting phone is never a present phone"] = (
                check_a_waiting_phone_is_not_a_present_phone())
            results["a CLOSED page still gets the notice, whole"] = (
                check_a_closed_page_still_gets_the_notice(chan))
            results["idle carries the beat and nothing else"] = (
                check_idle_costs_one_byte(chan))
            results["an open page takes the notice ALONE — never twice"] = (
                check_an_open_page_takes_it_alone(chan))
            results["a page dying mid-notice falls through to the channel"] = (
                check_a_dying_page_falls_through_not_into_the_queue(chan))
    finally:
        chan.close()

    results["the queue is the last resort, and drains oldest first"] = (
        check_the_queue_is_the_last_resort())

    print("\n=== NOTICE CHANNEL GATE ===")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok in results.items() if not ok]
    if failed:
        print(f"\nNOTICE CHANNEL GATE FAILED — {len(failed)} check(s).",
              file=sys.stderr)
        return 1
    print("\nNOTICE CHANNEL GATE PASSED — the PC reaches a phone whose page is "
          "closed, exactly once, without ever looking present.")
    return 0


def test_notice_channel():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
