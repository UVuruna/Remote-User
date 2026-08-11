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

TASK 209 (his own log, 2026-08-11) added the second half of the contract. The
channel was ONE SLOT, so his tablet and his phone kicked each other off it
every few seconds — continuously since 2026-08-09, thousands of log lines a
night, both radios woken for nothing, and a notice reaching only whichever
device held the slot at that instant while the other learned about it minutes
later out of the queue. It is now one channel PER DEVICE, keyed by an id the
shell sends as `&device=…`:

  7. Two devices waiting = two ears, not two copies. Each receives the notice
     exactly once, and neither is kicked.
  8. A request with NO device id is an older APK and keeps EXACTLY today's
     behaviour: it works alone, and a second id-less attach displaces it.
  9. A second attach from the SAME id replaces that device's own channel (its
     service restarted) and leaves every other device alone.
 10. The page still outranks everything: with the page open, neither waiting
     device hears a thing.
 11. The queue is reached only when NOBODY waits — one waiting device is
     enough to keep it empty.

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

    def __init__(self, device: str | None = None):
        # None = an APK older than task 209: it sends no `device` parameter at
        # all, which is exactly what the compatibility check has to exercise.
        self.device = device
        self.lines: queue.Queue = queue.Queue()
        self.beats = 0
        self.ended = threading.Event()      # the PC closed the response on us
        self._response = None
        self._stop = False
        self._thread = threading.Thread(target=self._read, daemon=True)

    def open(self, timeout: float = 5.0) -> "Waiting":
        url = f"http://127.0.0.1:{PORT}/notices?token={TOKEN}"
        if self.device is not None:
            url += f"&device={self.device}"
        self._response = urllib.request.urlopen(url, timeout=timeout)
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
                self.ended.set()            # displaced, or the server stopped
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


def quiet(chan: Waiting) -> bool:
    """Nothing more arrived on this channel. Given a beat's worth of grace by
    the caller — an instant check would pass even on a real double."""
    return chan.next(timeout=0.3) is None


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


# ═══════════════ TASK 209 — HIS TWO DEVICES, EACH WITH ITS OWN EAR ═════════
# What the single slot cost him is in his own log: attach → kicked → retry,
# every few seconds, between 192.168.0.30 and .27, all night, since 2026-08-09.
# These five checks are the contract that replaces it.
def check_two_devices_each_get_one_copy() -> bool:
    """The fix, stated: two devices waiting are two EARS, not two copies.
    Both hear the notice exactly once, and neither is kicked to make room."""
    reset()
    tablet = Waiting(device="tablet-a").open()
    phone = Waiting(device="phone-b").open()
    try:
        if not until(lambda: notify.waiting_devices() == 2):
            return False
        _, answer = post({"agent": "Two ears", "event": "finished", "text": ""})
        first, second = tablet.next(), phone.next()
        # Long enough for a second copy — or a kick — to show itself.
        time.sleep(TEST_BEAT_S * 3)
        return (answer.get("ok") is True
                and first is not None and second is not None
                and first["agent"] == "Two ears" == second["agent"]
                and quiet(tablet) and quiet(phone)      # never twice
                and not tablet.ended.is_set()           # and never kicked
                and not phone.ended.is_set()
                and notify.waiting_devices() == 2
                and not notify._pending)                # nobody was queued
    finally:
        tablet.close()
        phone.close()


def check_an_old_apk_behaves_exactly_as_before() -> bool:
    """COMPATIBILITY. A shell that predates task 209 sends no `device` at all.
    It must still attach and still receive — and two of them must still fight
    over the one legacy slot, because that is the behaviour it was built
    against and nothing about an old phone may change when this PC updates."""
    reset()
    old = Waiting().open()                     # no `device` parameter at all
    try:
        if not until(lambda: notify.waiting_devices() == 1):
            return False
        post({"agent": "Old shell", "event": "finished", "text": ""})
        got = old.next()
        if got is None or got["agent"] != "Old shell":
            return False
        newer = Waiting().open()               # a second id-less attach
        try:
            kicked = old.ended.wait(4)
            if not until(lambda: notify.waiting_devices() == 1):
                return False
            post({"agent": "Legacy two", "event": "finished", "text": ""})
            after = newer.next()
            return (kicked and after is not None
                    and after["agent"] == "Legacy two"
                    and quiet(old))
        finally:
            newer.close()
    finally:
        old.close()


def check_a_reattach_replaces_only_its_own_device() -> bool:
    """The phone's service restarts (Android reclaimed it, Wi-Fi moved). Its
    OWN older channel must end — otherwise the PC accumulates dead channels
    and writes every notice into a socket nobody reads — and the OTHER
    device's channel must not be touched, which is the whole bug."""
    reset()
    first = Waiting(device="same-id").open()
    other = Waiting(device="other-id").open()
    try:
        if not until(lambda: notify.waiting_devices() == 2):
            return False
        again = Waiting(device="same-id").open()
        try:
            replaced = first.ended.wait(4)
            time.sleep(TEST_BEAT_S * 3)
            if not (replaced and not other.ended.is_set()
                    and notify.waiting_devices() == 2):
                return False
            post({"agent": "After restart", "event": "finished", "text": ""})
            fresh, bystander = again.next(), other.next()
            return (fresh is not None and bystander is not None
                    and fresh["agent"] == "After restart"
                    and bystander["agent"] == "After restart"
                    and quiet(first))          # the replaced one hears nothing
        finally:
            again.close()
    finally:
        first.close()
        other.close()


def check_the_page_still_outranks_every_device() -> bool:
    """The carrier order is unchanged by task 209: the device he is LOOKING at
    takes the notice, and the waiting channels hear nothing at all. Fanning
    out to every device must not have become fanning out to everything."""
    reset()
    tablet = Waiting(device="tablet-a").open()
    phone = Waiting(device="phone-b").open()
    page = FakePageWs()
    try:
        if not until(lambda: notify.waiting_devices() == 2):
            return False
        notify._page["ws"] = page
        _, answer = post({"agent": "Looking", "event": "finished", "text": ""})
        delivered = until(lambda: len(page.sent) == 1)
        time.sleep(TEST_BEAT_S * 3)
        return (delivered and answer.get("ok") is True
                and page.sent[0]["agent"] == "Looking"
                and tablet.lines.empty() and phone.lines.empty()
                and not notify._pending)
    finally:
        notify._page["ws"] = None
        tablet.close()
        phone.close()


def check_one_waiting_device_keeps_the_queue_empty() -> bool:
    """The queue is the LAST resort and stayed one. With even a single device
    waiting, nothing may be held — a notice that is both delivered and queued
    arrives twice, hours apart, which is exactly what his phone did."""
    reset()
    lone = Waiting(device="lonely").open()
    try:
        if not until(lambda: notify.waiting_devices() == 1):
            return False
        _, answer = post({"agent": "Not held", "event": "finished", "text": ""})
        got = lone.next()
        return (got is not None and got["agent"] == "Not held"
                and answer.get("ok") is True        # not the "held" answer
                and "held" not in str(answer.get("reason", "")).lower()
                and not notify._pending)
    finally:
        lone.close()


# The companion permissions Android 14+ accepts for a `connectedDevice`
# foreground service. Holding NONE of them makes startForeground throw in the
# SERVICE's onCreate — off the caller's stack, so nothing catches it and the
# process dies at launch. That is exactly what v0.0.093 shipped: the app did
# not start at all on the owner's phone.
CONNECTED_DEVICE_COMPANIONS = (
    "android.permission.CHANGE_NETWORK_STATE",
    "android.permission.CHANGE_WIFI_STATE",
    "android.permission.CHANGE_WIFI_MULTICAST_STATE",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.BLUETOOTH_ADVERTISE",
    "android.permission.BLUETOOTH_SCAN",
    "android.permission.NFC",
    "android.permission.TRANSMIT_IR",
    "android.permission.UWB_RANGING",
)


def check_the_service_can_never_kill_the_app() -> bool:
    """The shell half: the channel may fail, the app may not die with it.

    Two independent teeth, because each alone was not enough on the phone:
      1. the manifest declares the companion permission its service TYPE
         requires — without it startForeground is refused outright;
      2. the refusal is CAUGHT in the service's own onCreate, so any future
         reason Android invents (a background start, a new policy) costs the
         notice channel and nothing else.
    """
    manifest = (PROJECT / "android/app/src/main/AndroidManifest.xml").read_text(
        encoding="utf-8")
    service = (PROJECT / "android/app/src/main/java/com/uvuruna/remoteuser"
               / "NoticeService.kt").read_text(encoding="utf-8")
    ok = True

    if 'android:foregroundServiceType="connectedDevice"' in manifest:
        if not any(p in manifest for p in CONNECTED_DEVICE_COMPANIONS):
            print("    the `connectedDevice` service type is declared with NO "
                  "companion permission — startForeground throws and the app "
                  "dies at launch", file=sys.stderr)
            ok = False

    # The catch must WRAP startForeground, not sit somewhere else in the file.
    body = service.split("override fun onCreate()", 1)
    if len(body) < 2:
        print("    NoticeService has no onCreate to guard", file=sys.stderr)
        return False
    guarded = body[1].split("override fun onStartCommand", 1)[0]
    start = guarded.find("startForeground")
    catch = guarded.find("catch")
    if start < 0 or catch < 0 or catch < start or "try" not in guarded[:start]:
        print("    startForeground is not inside a try/catch in onCreate — a "
              "refusal takes the whole app down with it", file=sys.stderr)
        ok = False
    elif "stopSelf" not in guarded[catch:]:
        print("    the refusal is caught but the service does not stop itself",
              file=sys.stderr)
        ok = False
    return ok


def check_the_shell_sends_an_id_and_backs_off() -> bool:
    """The shell's half of task 209, read from its source — the only thing a
    PC with no Android runtime can prove. Two promises, and the fix is worth
    nothing without either: the request must CARRY the id (a server keyed by
    device and a phone that sends none is the single slot again, exactly as
    before), and a connection that ended without the PC ever speaking must
    back OFF rather than retry at once, which is what turned a kick into a
    ping-pong every few seconds all night."""
    src = PROJECT / "android/app/src/main/java/com/uvuruna/remoteuser"
    link = (src / "NoticeLink.kt").read_text(encoding="utf-8")
    service = (src / "NoticeService.kt").read_text(encoding="utf-8")
    prefs = (src / "Prefs.kt").read_text(encoding="utf-8")
    ok = True
    # The id must reach the WIRE, encoded — not merely be mentioned in a
    # comment, which is the whole of what a source check can get wrong. So:
    # a line that builds `&device=` and encodes the value on the same line.
    if not any("&device=" in line and "Uri.encode(" in line
               for line in link.splitlines()) or "deviceId" not in link:
        print("    NoticeLink does not put a device id on the request — the "
              "PC cannot tell his tablet from his phone and the single slot "
              "is back", file=sys.stderr)
        ok = False
    if "deviceId" not in service:
        print("    NoticeService never hands the link a device id",
              file=sys.stderr)
        ok = False
    if "UUID.randomUUID" not in prefs or "KEY_DEVICE" not in prefs:
        print("    Prefs has no stored per-install id (and it must NOT be a "
              "hardware id)", file=sys.stderr)
        ok = False
    # A HARDWARE id would be restricted, survive an uninstall, and be a real
    # identifier riding in a query string for a job a random number does. The
    # two ways one could get in are named, not guessed at by keyword — the
    # comment in Prefs.kt says the word ANDROID_ID and must be allowed to.
    if "Settings.Secure" in prefs or "TelephonyManager" in prefs:
        print("    the device id is read from the SYSTEM — that is a hardware "
              "id, not a per-install one", file=sys.stderr)
        ok = False
    # The backoff must distinguish "answered and said nothing" from "answered
    # and talked to us": one variable for both is the old instant retry.
    if "SILENT" not in link or "QUIET_BACKOFF_MAX_MS" not in link:
        print("    NoticeLink does not back off after a connection that ended "
              "without a single beat — a kick retries instantly",
              file=sys.stderr)
        ok = False
    return ok


def check_close_channels_ends_the_drain() -> bool:
    """Task 234: `force_exit` stops uvicorn from accepting work, but an
    endless `/notices` generator parked on its queue held the shutdown drain
    for its whole join timeout — every Apply & restart stalled 10 s and left
    the old thread behind. `notify.close_channels()` — called from the GUI
    thread by `ServerController.stop()`'s exit funnel — must end every
    waiting response NOW, through the same sentinel a displaced channel gets.
    This check IS that call: a real attached connection, close_channels from
    a foreign thread, and the response must END well inside a beat."""
    chan = Waiting("dev-234").open()
    if not until(lambda: notify.waiting_devices() == 1, timeout=4):
        print("    the channel never attached", file=sys.stderr)
        chan.close()
        return False
    notify.close_channels()          # the foreign-thread call under test
    ended = chan.ended.wait(2.0)     # far under BEAT_S — the sentinel, not a beat
    chan.close()
    if not ended:
        print("    close_channels did not end the waiting response — the "
              "shutdown drain would wait out its full timeout", file=sys.stderr)
        return False
    return until(lambda: notify.waiting_devices() == 0, timeout=2)


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
    results["the notice channel can never kill the app"] = (
        check_the_service_can_never_kill_the_app())
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

    # Task 209 — one channel per device. These run with the single channel
    # above already closed, so each opens exactly the devices it is about.
    if not until(lambda: notify.waiting_devices() == 0, timeout=6):
        results["the closed channel really detaches"] = False
    results["the shell sends an id and backs off when kicked"] = (
        check_the_shell_sends_an_id_and_backs_off())
    results["two devices each get ONE copy, neither kicked"] = (
        check_two_devices_each_get_one_copy())
    results["an older APK (no device id) behaves exactly as before"] = (
        check_an_old_apk_behaves_exactly_as_before())
    results["a re-attach replaces its OWN channel and no other"] = (
        check_a_reattach_replaces_only_its_own_device())
    results["the page still outranks every waiting device"] = (
        check_the_page_still_outranks_every_device())
    results["one waiting device keeps the queue empty"] = (
        check_one_waiting_device_keeps_the_queue_empty())

    results["the queue is the last resort, and drains oldest first"] = (
        check_the_queue_is_the_last_resort())
    results["stop() ends every waiting channel at once (234)"] = (
        check_close_channels_ends_the_drain())

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
