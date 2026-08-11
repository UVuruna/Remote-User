"""Orientation Lock Gate (task 204): a portrait layout must STAY portrait when
the tablet is turned to landscape — not rotate with blue letterbox bars.

The owner's report: a portrait Chrome layout, focused; tablet turned to
landscape; the picture rotated instead of staying locked. Two independent
holes were found, and this gate proves both are closed:

  1. THE SHELL forgets. `Android.requestedOrientation` lives only on the LIVE
     Activity instance — Android never persists it. An Activity recreated
     while the phone was away (the process reclaimed for memory during an
     excursion's picker, an OEM quirk) comes back with a FRESH instance whose
     `requestedOrientation` is the manifest's unspecified default, and the
     page only calls `Android.lockOrientation` again when the layout FOCUS
     itself changes — which it did not. The fix REMEMBERS the mode in Prefs
     and re-asserts it in `onCreate`/`onResume`.

  2. THE PAGE unlocks during its own restore. After a reconnect, the
     server's FIRST `layout_state` says desktop — `layoutRestore` in
     connection.js only sends the `layout_focus` that re-selects the real
     layout a moment later. `applyOrientationLock()` ran on that INTERIM
     message and read "desktop" as "unlock", clearing the lock for the
     seconds the restore takes — exactly the reported symptom. The fix
     defers the unlock with `orientationRestoring` while a restore is
     genuinely in flight, and still releases it the moment the restore either
     lands (a real focus arrives) or fails to verify (the remembered layout
     is gone) — a stuck restore must never hold the lock forever.

What is proven here, and what each check would let through if it were
missing:

  THE SHELL (source contract — no Android runtime on this machine; what the
  shell DOES with it is proven only on his phone)
  1. Prefs remembers the lock mode (a KEY_ORIENT get/set pair).
  2. Bridge.lockOrientation writes it to Prefs on every call from the page.
  3. onCreate re-asserts the remembered mode before the page has even loaded.
  4. onResume re-asserts it too — the excursion-return path.

  THE PAGE (the real client/state.js + client/connection.js + client/layouts.js,
  run in node on a virtual clock — no browser, no server)
  5. The interim "desktop" layout_state during a pending restore does NOT
     call `Android.lockOrientation("")`.
  6. The restore's own later layout_state (the real focus landing) DOES
     re-lock, with the layout's own orientation.
  7. A restore that fails to verify (the remembered layout is gone) releases
     the hold and unlocks for real — the guard must not survive a restore
     that can never land.
  8. A genuine desktop choice, with no restore in flight, unlocks immediately
     — the guard must not fire when there was never anything to protect.

Run:  .venv\\Scripts\\python tests/test_orientation_lock.py
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ANDROID = PROJECT / "android/app/src/main/java/com/uvuruna/remoteuser"
CLIENT = PROJECT / "client"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def _kotlin(name: str) -> str:
    return (ANDROID / name).read_text(encoding="utf-8")


def _strip_comments(src: str) -> str:
    """Comments here carry the failure history and would match these greps
    on their own — only the CODE may answer."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//.*", "", src)


# ═══════════════════════════ THE SHELL ═══════════════════════════
def check_prefs_remembers_the_lock() -> None:
    src = _strip_comments(_kotlin("Prefs.kt"))
    if "KEY_ORIENT" not in src:
        fail("Prefs has no dedicated key for the orientation lock mode")
    if not re.search(r"fun orientLock\(context: Context\)", src):
        fail("Prefs has no orientLock() reader — nothing to re-assert from")
    if not re.search(r"fun setOrientLock\(context: Context, mode: String\)", src):
        fail("Prefs has no setOrientLock() writer — the mode is never remembered")


def check_bridge_persists_every_lock_call() -> None:
    src = _strip_comments(_kotlin("Bridge.kt"))
    body = re.search(
        r"fun lockOrientation\(mode: String\)\s*\{(.*?)\n    \}", src, flags=re.S
    )
    if body is None:
        fail("Bridge.lockOrientation() is missing")
    if "Prefs.setOrientLock" not in body.group(1):
        fail(
            "Bridge.lockOrientation() no longer writes to Prefs — a future "
            "Activity recreation has nothing to re-assert, and the fix "
            "regresses silently"
        )


def check_activity_reasserts_on_create() -> None:
    src = _strip_comments(_kotlin("MainActivity.kt"))
    create = re.search(r"override fun onCreate\(.*?\n    \}", src, flags=re.S)
    if create is None:
        fail("MainActivity has no onCreate")
    if not re.search(r"applyOrientationLock\(\s*Prefs\.orientLock\(", create.group(0)):
        fail(
            "onCreate does not re-assert Prefs.orientLock() — a fresh Activity "
            "instance (the process reclaimed during an excursion) starts "
            "unlocked and stays that way until the layout FOCUS changes, "
            "which it will not if the phone reconnects into the SAME layout"
        )


def check_activity_reasserts_on_resume() -> None:
    src = _strip_comments(_kotlin("MainActivity.kt"))
    resume = re.search(r"override fun onResume\(.*?\n    \}", src, flags=re.S)
    if resume is None:
        fail("MainActivity has no onResume")
    if not re.search(r"applyOrientationLock\(\s*Prefs\.orientLock\(", resume.group(0)):
        fail(
            "onResume does not re-assert Prefs.orientLock() — returning from "
            "an excursion (picker, permission dialog, battery exemption "
            "sheet) on a recreated Activity instance leaves rotation "
            "unlocked exactly at the moment the owner turns the tablet"
        )


def check_apply_orientation_lock_is_shared() -> None:
    """Bridge and the two lifecycle hooks must all drive ONE function, not
    three copies of the same `when` that can drift apart."""
    activity = _strip_comments(_kotlin("MainActivity.kt"))
    if not re.search(r"fun applyOrientationLock\(mode: String\)", activity):
        fail("MainActivity has no applyOrientationLock() — nothing shared to re-assert")
    bridge = _strip_comments(_kotlin("Bridge.kt"))
    if "host.applyOrientationLock(" not in bridge:
        fail(
            "Bridge.lockOrientation() does not call host.applyOrientationLock() "
            "— it and the lifecycle re-assert could compute the orientation "
            "two different ways"
        )


# ═══════════════════════════ THE PAGE ═══════════════════════════
# The real client/state.js + client/connection.js + client/layouts.js, run in
# node inside a sandbox whose clock, WebSocket and `window.Android` the
# scenario drives.
HARNESS = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const CLIENT = process.argv[2], SCENARIO = process.argv[3];

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

const lockCalls = [];
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
    Android: {
      linkLost: () => {},
      lockOrientation: (mode) => lockCalls.push(mode),
    },
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
vm.runInContext("setStatus = () => {};", ctx);
// applyNoticeJump lives in notify.js, not loaded here — left unstubbed it
// resolves through the STUB proxy, and calling it returns STUB, which is
// TRUTHY, so `if (applyNoticeJump())` would always take the "a tap already
// decided" branch and never exercise the restore path under test.
vm.runInContext("applyNoticeJump = () => false;", ctx);
load("connection.js");
load("layouts.js");

const K = (n) => vm.runInContext(n, ctx);
const last = () => sockets[sockets.length - 1];
const CONFIG = { type: "config", monitor_width: 100, monitor_height: 100, stream: "jpeg" };
const PORTRAIT_LAYOUTS = [{ name: "Chrome", orient: "portrait" }];

const out = {};
try {
  if (SCENARIO === "deliberate_desktop_unlocks") {
    // No prior focus at all — a fresh connection landing straight on the
    // desktop, with nothing remembered to restore. layoutRestore stays null
    // throughout, so this must NOT be read as a pending restore.
    last().open(); last().serve(CONFIG);
    last().serve({ type: "layout_state", layouts: [], active: null, region: null });
    out.calls_after_desktop = lockCalls.slice();
  } else {
    // Every other scenario starts from an established focus (as if the
    // owner had already focused the portrait layout before whatever hides
    // the page next).
    last().open(); last().serve(CONFIG);
    last().serve({ type: "layout_state", layouts: PORTRAIT_LAYOUTS, active: 0, region: {} });
    const afterInitialFocus = lockCalls.length;

    if (SCENARIO === "restore_pending_no_unlock") {
      // The socket dies (an excursion) and reconnects — the server's FIRST
      // layout_state after reconnect says desktop while the restore is
      // still in flight (connection.js's own layoutRestore -> layout_focus
      // send).
      last().die(1006);
      advance(2100);
      last().open(); last().serve(CONFIG);
      last().serve({ type: "layout_state", layouts: PORTRAIT_LAYOUTS, active: null, region: null });
      out.calls_during_restore = lockCalls.slice(afterInitialFocus);
    } else if (SCENARIO === "restore_lands_relocks") {
      last().die(1006);
      advance(2100);
      last().open(); last().serve(CONFIG);
      last().serve({ type: "layout_state", layouts: PORTRAIT_LAYOUTS, active: null, region: null });
      // The restore's own reply: the real focus lands.
      last().serve({ type: "layout_state", layouts: PORTRAIT_LAYOUTS, active: 0, region: {} });
      out.calls_after_restore = lockCalls.slice(afterInitialFocus);
    } else if (SCENARIO === "restore_fails_unlocks") {
      last().die(1006);
      advance(2100);
      last().open(); last().serve(CONFIG);
      // The remembered layout is GONE by the time we reconnect
      // (renamed/removed) — layouts[0].name no longer matches, so the
      // restore can never verify.
      last().serve({
        type: "layout_state",
        layouts: [{ name: "Something Else", orient: "landscape" }],
        active: null, region: null,
      });
      out.calls_after_failed_restore = lockCalls.slice(afterInitialFocus);
    } else {
      throw new Error("unknown scenario " + SCENARIO);
    }
  }
} catch (e) { out.error = String((e && e.stack) || e); }
console.log(JSON.stringify(out));
"""


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        fail(
            "node is required for the page half of this gate (it runs the "
            "REAL client/connection.js + layouts.js) — install Node.js. Never "
            "skip a gate silently: a page that unlocks mid-restore is the "
            "whole bug."
        )
    return node


def _page(scenario: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "harness.js"
        script.write_text(HARNESS, encoding="utf-8")
        proc = subprocess.run(
            [_node(), str(script), str(CLIENT), scenario],
            capture_output=True, text=True, timeout=60,
        )
    if proc.returncode != 0:
        fail(f"the page harness crashed on `{scenario}`:\n{proc.stderr}")
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    if "error" in out:
        fail(f"the page threw on `{scenario}`: {out['error']}")
    return out


def check_interim_desktop_does_not_unlock() -> None:
    out = _page("restore_pending_no_unlock")
    calls = out["calls_during_restore"]
    if "" in calls:
        fail(
            f"the interim desktop layout_state during a pending restore "
            f"called Android.lockOrientation('') — rotation unlocked for "
            f"the seconds the restore takes, letting the tablet spin "
            f"sideways over a portrait layout (task 204). Calls: {calls}"
        )


def check_restore_landing_relocks() -> None:
    out = _page("restore_lands_relocks")
    calls = out["calls_after_restore"]
    if "" in calls:
        fail(f"the restore path unlocked rotation at some point: {calls}")
    if not calls or calls[-1] != "portrait":
        fail(
            f"the restore's own layout_state (the real focus landing) did "
            f"not re-lock to the layout's orientation: {calls}"
        )


def check_failed_restore_releases_the_hold() -> None:
    out = _page("restore_fails_unlocks")
    calls = out["calls_after_failed_restore"]
    if "" not in calls:
        fail(
            "a restore that can never verify (the remembered layout is "
            "gone) never released the hold — rotation would stay locked "
            "forever on a desktop the owner is actually looking at. "
            f"Calls: {calls}"
        )


def check_deliberate_desktop_still_unlocks() -> None:
    """The guard must fire ONLY while a real restore is pending — a genuine,
    immediate desktop focus (no prior layoutRestore) must keep unlocking
    exactly as before task 204."""
    out = _page("deliberate_desktop_unlocks")
    calls = out["calls_after_desktop"]
    if not calls or calls[-1] != "":
        fail(
            f"a genuine desktop focus with no restore pending did not "
            f"unlock rotation: {calls}"
        )


# ═══════════════════════════ THE CHECKS ═══════════════════════════
CHECKS = [
    ("Shell: Prefs remembers the lock mode", check_prefs_remembers_the_lock),
    ("Shell: Bridge persists every lockOrientation call", check_bridge_persists_every_lock_call),
    ("Shell: onCreate re-asserts the remembered lock", check_activity_reasserts_on_create),
    ("Shell: onResume re-asserts the remembered lock", check_activity_reasserts_on_resume),
    ("Shell: one shared applyOrientationLock, not three copies", check_apply_orientation_lock_is_shared),
    ("Page: interim desktop during a pending restore does not unlock", check_interim_desktop_does_not_unlock),
    ("Page: the restore landing re-locks to the layout's orientation", check_restore_landing_relocks),
    ("Page: a restore that fails to verify releases the hold", check_failed_restore_releases_the_hold),
    ("Page: a genuine desktop focus still unlocks", check_deliberate_desktop_still_unlocks),
]


def test_orientation_lock() -> None:
    for name, check in CHECKS:
        check()
        print(f"  OK  {name}")


if __name__ == "__main__":
    print("Orientation Lock Gate — a locked layout must survive a rotation, an excursion and a reconnect")
    try:
        test_orientation_lock()
    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    print("\nAll orientation-lock checks passed.")
