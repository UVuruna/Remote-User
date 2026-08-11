"""Gate: THE PHONE EDITS A SET'S INTERIOR, and what it edits is HIS file.

Owner 2026-08-04 18:27, re-raised as a ballot comment on 2026-08-11 after a
week in nobody's list: from the same phone panel where sets are ticked on and
off, he configures the individual set — which buttons ride and at which
positions, the same job the desktop Controls editor does.

The four things this gate exists to prove, each one a failure this project has
already shipped at least once:

(a) THE EDIT LANDS IN THE USER'S FILE. Proven against a user actions.json of an
    OLDER SHAPE, held here as literal text — never `copy(shipped)`. That
    shortcut is what let four releases pass while a field never reached his
    %LOCALAPPDATA% copy (tests/test_actions_migration.py's whole preamble), and
    a save path measured against a file made out of today's shipped file proves
    nothing about the file on his PC.
(b) A NON-OWNER KEY IS REFUSED. The phone may write only `PHONE_EDITABLE`, and
    that set must stay a subset of the shipped-pool merge's `OWNER_SET_KEYS` —
    otherwise the next release's merge deletes his choice, silently, which is
    the 2026-08-07 failure arriving from the other direction.
(c) AN ID NOT IN THE POOL IS REFUSED. A phone working from a stale `actions`
    frame must be told no, never half-obeyed: honouring the ids we recognise
    would leave him looking at a D-pad he did not choose.
(d) THE RE-BROADCAST REACHES THE PAGE. An edit that only lands in a file until
    the next reconnect is the "I changed it and nothing happened" report this
    project has already answered four times, and it is why the message exists
    at all rather than a plain POST.

Plus the half that no server-side check can stand in for: THE PHONE REALLY
SENDS IT. A pure module nobody calls is a feature that does not exist (the
actions.json lesson of 2026-08-07, and task 164's before it), so the last block
opens the REAL page in a REAL Chromium, walks the owner's own path — Settings →
Sets → a set's edit door → untick, tick, swap two slots → Save — and reads the
`actions_update` off the wire, then feeds the page the `actions` frame the
server would answer with and measures that the live D-pad really changed.

Run:  .venv\\Scripts\\python tests/test_set_editor.py
The browser block needs the input gate's toolchain (playwright + chromium);
without it that block FAILS rather than skipping — never skip a gate silently.
"""

import json
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(PROJECT / "server"))

import actions_api  # noqa: E402
from gui.controls_data import OWNER_SET_KEYS  # noqa: E402

PORT = 8895  # this gate's own port — never the input gate's 8898 (see below)


# ───────────────────── HIS FILE, of an older shape, literal ──────────────────
# Deliberately NOT derived from the shipped actions.json. It carries: a Mouse
# set with a POOL longer than the D-pad and his own rename on the left click; a
# set with no `active` at all (pre-pool, which is still "the first four"); an
# app set; and a custom set. No `wheel_order`, no `order_land`, no `order_port`
# — the arrangement keys this feature writes are exactly the ones his file has
# never had, which is the interesting case and the one a copied file hides.
def his_file() -> dict:
    return json.loads(json.dumps({
        "left": 0,
        "right": 1,
        "categories": [
            {"name": "Mouse", "icon": "mouse", "required": True,
             "buttons": [{"action": "click", "label": "Left"}, {"action": "right"},
                         {"action": "middle"}, {"action": "scroll"},
                         {"action": "drag"}, {"action": "x1"}, {"action": "x2"}],
             "active": ["click", "right", "middle", "scroll"]},
            {"name": "Edit", "icon": "copy",
             "buttons": [{"chord": "ctrl+a", "label": "All"},
                         {"chord": "ctrl+c", "label": "Copy"},
                         {"chord": "ctrl+x", "label": "Cut"},
                         {"chord": "ctrl+v", "label": "Paste"},
                         {"chord": "ctrl+s", "label": "Save"}]},
        ],
        "app_sets": [
            {"name": "VSCode", "process": "code", "icon": "vscode",
             "buttons": [{"chord": "ctrl+b", "label": "Sidebar"},
                         {"chord": "ctrl+p", "label": "Go to file"},
                         {"chord": "ctrl+`", "label": "Terminal"}]},
        ],
        "custom_sets": [
            {"name": "Mine", "icon": "star", "enabled": True,
             "buttons": [{"id": "one", "chord": "f1", "label": "One"},
                         {"id": "two", "chord": "f2", "label": "Two"}]},
        ],
    }))


def named(data: dict, name: str) -> dict:
    for key in ("categories", "app_sets", "custom_sets"):
        for s in data.get(key) or []:
            if s.get("name") == name:
                return s
    raise AssertionError(f"no set named {name!r} in the file")


def refused(data: dict, msg: dict) -> str:
    """Drive `apply_update` and return the refusal sentence. An ACCEPTED
    message is the failure here — the caller says why."""
    try:
        actions_api.apply_update(data, msg)
    except actions_api.Refused as e:
        return str(e)
    return ""


# ═══════════════════════════ (b) THE OWNERSHIP CONTRACT ══════════════════════
def check_phone_editable_is_owner_owned():
    """The import-time assertion, restated where a human reads it: every key
    the phone may write must be one the shipped-pool merge protects. A key
    outside `OWNER_SET_KEYS` is overwritten from the shipped file on the next
    start — his edit would survive exactly until the update that carried it."""
    assert actions_api.PHONE_EDITABLE <= OWNER_SET_KEYS, (
        f"the phone may write {sorted(actions_api.PHONE_EDITABLE - OWNER_SET_KEYS)}, "
        "which the shipped-pool merge does not treat as the owner's — the next "
        "release would delete his choice without a word")
    assert "enabled" not in actions_api.PHONE_EDITABLE, (
        "`enabled` is the wheel COMPOSITION default and the phone owns "
        "composition per DEVICE through its own prefs; this editor edits a "
        "set's interior and may not reach across")


def check_a_non_owner_key_is_refused():
    """(b) — the message is refused WHOLE, not filtered. Anything on the LAN
    holding the token could otherwise rewrite a set's commands one accepted
    field at a time."""
    for key, value in [("buttons", [{"chord": "ctrl+q"}]),
                       ("enabled", False),
                       ("required", True),
                       ("process", "evil.exe"),
                       ("name", "Renamed")]:
        data = his_file()
        why = refused(data, {"type": "actions_update", "set": "Mouse",
                             "active": ["click", "right"], key: value})
        assert why, f"a message carrying {key!r} was accepted — it must be refused"
        assert key in why, (
            f"the refusal for {key!r} did not name the field ({why!r}); a phone "
            "told only 'no' cannot tell the user what it tried to do")
        assert named(data, "Mouse")["active"] == ["click", "right", "middle", "scroll"], (
            f"a message carrying {key!r} was refused and STILL changed `active` "
            "— a refusal must leave the file exactly as it was")


# ═══════════════════════════ (c) THE POOL IS THE LAW ═════════════════════════
def check_an_id_outside_the_pool_is_refused():
    """(c) — including the case that matters most: a message whose ids are
    MOSTLY valid. Trimming the unknown one would silently give him a
    three-button D-pad he never asked for."""
    data = his_file()
    why = refused(data, {"set": "Mouse", "active": ["click", "ctrl+q"]})
    assert "ctrl+q" in why, f"an unknown id was not named in the refusal: {why!r}"
    assert named(data, "Mouse")["active"] == ["click", "right", "middle", "scroll"], (
        "an unknown id was refused and the file changed anyway")
    # A command that exists in ANOTHER set is still not in this one's pool.
    assert refused(his_file(), {"set": "Mouse", "active": ["ctrl+c"]}), (
        "a command from a different set's pool was accepted into Mouse")


def check_the_shape_of_active_is_enforced():
    """Everything `renderGroup` would have to silently ignore is refused here
    instead — a silently-ignored arrangement is this project's own signature
    bug (the layout Move handle, four rounds)."""
    cases = {
        "empty": [],
        "five on a four-armed D-pad": ["click", "right", "middle", "scroll", "drag"],
        "the same button twice": ["click", "click"],
        "not a list": "click",
        "not strings": [0, 1],
    }
    for label, active in cases.items():
        assert refused(his_file(), {"set": "Mouse", "active": active}), (
            f"an `active` that is {label} was accepted")


def check_the_order_must_be_a_real_permutation():
    """`order_land` / `order_port` are permutations of the ACTIVE list's own
    positions — the exact test the client's `renderGroup` applies before it
    falls back. Refused here so the fallback never has to happen: a phone whose
    arrangement was quietly dropped shows him the old D-pad after a Save."""
    good = ["click", "right", "middle"]
    for label, order in {"too long": [0, 1, 2, 3], "too short": [0, 1],
                         "a repeat": [0, 0, 1], "out of range": [0, 1, 5],
                         "not a list": "012"}.items():
        assert refused(his_file(), {"set": "Mouse", "active": good,
                                    "order_land": order}), (
            f"an arrangement that is {label} was accepted")
    data = his_file()
    actions_api.apply_update(data, {"set": "Mouse", "active": good,
                                    "order_land": [2, 0, 1]})
    assert named(data, "Mouse")["order_land"] == [2, 0, 1], (
        "a valid arrangement did not reach the set")


def check_every_kind_of_set_is_editable():
    """Built-in, app-aware and custom, to the SAME depth — which pool commands
    ride and where. He arranges Mouse and Input most, and both are `required`:
    locked against the picker's tick is not locked against its own editor."""
    for name, active in [("Mouse", ["scroll", "click"]),
                         ("VSCode", ["ctrl+`", "ctrl+b"]),
                         ("Mine", ["two", "one"])]:
        data = his_file()
        actions_api.apply_update(data, {"set": name, "active": active,
                                        "order_land": [1, 0]})
        assert named(data, name)["active"] == active, (
            f"the {name} set could not be edited from the phone")
    assert refused(his_file(), {"set": "Nothing", "active": ["x"]}), (
        "a set this PC does not have was accepted")


# ═══════════════════ (a) IT LANDS IN THE USER'S OWN FILE ═════════════════════
def check_the_edit_lands_in_the_users_file():
    """(a) — the real read → validate → write, on a real file of HIS older
    shape. It also proves the two things a partial write would break: the file
    stays valid JSON with everything else intact, and a set that was NOT edited
    is untouched."""
    import config
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "actions.json"
        path.write_text(json.dumps(his_file(), indent=2), encoding="utf-8")
        before = config.SETTINGS.actions_path
        config.apply(actions_path=path)
        try:
            name, written = actions_api.save_update({
                "type": "actions_update", "set": "Edit",
                "active": ["ctrl+s", "ctrl+c"],
                "order_land": [1, 0], "order_port": [0, 1]})
        finally:
            config.apply(actions_path=before)
        assert name == "Edit" and set(written) == {"active", "order_land", "order_port"}
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        edit = named(on_disk, "Edit")
        assert edit["active"] == ["ctrl+s", "ctrl+c"], (
            f"the phone's choice is not in the file on disk: {edit.get('active')}")
        assert edit["order_land"] == [1, 0] and edit["order_port"] == [0, 1], (
            "the arrangement did not reach the file")
        assert len(edit["buttons"]) == 5, "the pool was damaged by the write"
        assert named(on_disk, "Mouse")["active"] == ["click", "right", "middle", "scroll"], (
            "editing one set changed another")
        assert named(on_disk, "Mouse")["buttons"][0]["label"] == "Left", (
            "his own button rename was lost by the phone's write")
        assert on_disk["left"] == 0 and on_disk["right"] == 1, (
            "a top-level key he owns was lost by the phone's write")


def check_a_refusal_never_touches_the_file():
    """The other half of (a): a refused message must leave the bytes alone.
    A validator that writes and then complains is worse than no validator."""
    import config
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "actions.json"
        original = json.dumps(his_file(), indent=2)
        path.write_text(original, encoding="utf-8")
        before = config.SETTINGS.actions_path
        config.apply(actions_path=path)
        try:
            try:
                actions_api.save_update({"set": "Mouse", "active": ["nope"]})
                raise AssertionError("an unknown id was accepted by save_update")
            except actions_api.Refused:
                pass
        finally:
            config.apply(actions_path=before)
        assert path.read_text(encoding="utf-8") == original, (
            "a refused message rewrote the file anyway")


# ═══════════════════════ (d) THE RE-BROADCAST ════════════════════════════════
class FakeWS:
    def __init__(self):
        self.frames = []

    async def send_text(self, text):
        self.frames.append(json.loads(text))


def check_the_rebroadcast_carries_the_new_state():
    """(d) — after a save the server sends a fresh `actions` frame down the
    SAME socket, so the wheel changes under his finger. And it must carry the
    NEW values: a re-broadcast read from a cache would be a frame that agrees
    with the phone about nothing."""
    import asyncio

    import config
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "actions.json"
        path.write_text(json.dumps(his_file(), indent=2), encoding="utf-8")
        before = config.SETTINGS.actions_path
        config.apply(actions_path=path)
        try:
            ws = FakeWS()
            asyncio.run(actions_api.actions_update(
                ws, {"type": "actions_update", "set": "Edit",
                     "active": ["ctrl+v", "ctrl+a"], "order_land": [1, 0]}))
            kinds = [f["type"] for f in ws.frames]
            assert "actions" in kinds, (
                f"no `actions` frame was broadcast after the save ({kinds}) — the "
                "wheel would not change until the next reconnect")
            frame = next(f for f in ws.frames if f["type"] == "actions")
            got = named(frame, "Edit")["active"]
            assert got == ["ctrl+v", "ctrl+a"], (
                f"the re-broadcast carried the OLD state ({got})")
            assert "toast" in kinds, "the save said nothing to the user"

            # And a REFUSAL broadcasts nothing but the reason: re-sending the
            # sets after a refusal would look exactly like a success.
            ws2 = FakeWS()
            asyncio.run(actions_api.actions_update(
                ws2, {"set": "Edit", "active": ["ctrl+q"]}))
            assert [f["type"] for f in ws2.frames] == ["toast"], (
                f"a refusal sent {[f['type'] for f in ws2.frames]} — it must send "
                "the reason and nothing else")
            assert "ctrl+q" in ws2.frames[0]["text"], (
                "the refusal toast does not say what was wrong")
        finally:
            config.apply(actions_path=before)


# ═════════════ THE PHONE REALLY SENDS IT — the real page, real browser ═══════
EDITOR_JS = """
window.__sent = [];
window.__wire = () => {
  if (window.__wired) return;
  window.__wired = true;
  const real = window.send;
  window.send = (m) => { window.__sent.push(m); return real(m); };
};
window.__editorGeom = () => {
  const cells = [...document.querySelectorAll('.se-slot')];
  return {
    open: !document.getElementById('set-editor-panel').hidden,
    slots: cells.map((c) => c.dataset.button),
    labels: cells.map((c) => c.querySelector('span').textContent),
    rows: [...document.querySelectorAll('#set-editor-panel .sets-row')].length,
    ticked: [...document.querySelectorAll('#set-editor-panel .sets-row input')]
              .filter((i) => i.checked).length,
    // The picture is the feature: every cell must be inside the card and none
    // of them may overlap another (a swap that leaves two on one square is
    // exactly the defect the layout member chooser's audit tooth catches).
    boxes: cells.map((c) => {
      const r = c.getBoundingClientRect();
      return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height};
    }),
    scrollW: document.scrollingElement.scrollWidth,
    w: innerWidth,
  };
};
// A REAL tap, not a bare click. `keepFocus` (client/controls.js) fires on a
// pointerup whose pointerdown it saw — the pointercancel rescue and the hold
// buttons depend on that pairing (CLAUDE.md constraint 9), so a gate that
// dispatched only an `up` would be measuring a path the product does not have.
window.__tap = (el) => {
  if (!el) throw new Error('nothing to tap');
  const o = {bubbles: true, pointerId: 1, isPrimary: true, clientX: 5, clientY: 5};
  el.dispatchEvent(new PointerEvent('pointerdown', o));
  el.dispatchEvent(new PointerEvent('pointerup', o));
};
window.__row = (root, text) =>
  [...document.querySelectorAll(root + ' .sets-row')]
    .find((r) => r.textContent.includes(text));
window.__padButtons = () =>
  [...document.getElementById('group-left').children]
    .filter((c) => !c.classList.contains('cat'))
    .map((c) => (c.textContent || '').trim());
"""


def start_server(actions_path: Path):
    """The input gate's harness on a PORT OF ITS OWN, pointed at a COPY of the
    fixture: this gate WRITES actions.json, and it may never write the repo's
    (the owner hand-edits that file — ACTIONS.md) nor the shared fixture."""
    import test_input_pipeline as gate
    gate.PORT = PORT
    gate.ACTIONS_FIXTURE = actions_path
    threading.Thread(target=gate.run_server, daemon=True).start()
    gate.server_ready.wait(15)
    deadline = time.time() + 10
    while time.time() < deadline:
        if gate.server_error:
            raise gate.server_error[0]
        try:
            with socket.create_connection(("127.0.0.1", gate.PORT), timeout=0.25):
                return gate
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("the set editor gate's server never started")


def check_the_phone_walks_the_path(browser, gate, actions_path: Path, results):
    """HIS OWN PATH, in a real browser: Settings → Sets → the Mouse row's edit
    door → untick one command and tick a reserve → swap two positions → Save.

    Then the two halves nothing else can prove: the message that leaves the
    page is the one the server validates, and the `actions` frame the server
    answers with really re-draws the D-pad."""
    ctx = browser.new_context(
        viewport={"width": 412, "height": 915}, has_touch=True, is_mobile=True,
        device_scale_factor=2,
        user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36 RemoteUserApp"))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
        page.wait_for_selector("#group-left button", timeout=8000)
        page.wait_for_function("() => monitor.w > 0", timeout=10000)
        page.evaluate("() => {" + EDITOR_JS + "}")
        page.evaluate("() => __wire()")

        # The door exists, on the row of a REQUIRED set — locked against the
        # tick, editable here (the point of the whole round: Mouse and Input
        # are the two he arranges most and both are required).
        page.evaluate("() => openSetsPanel()")
        page.wait_for_timeout(150)
        doors = page.evaluate(
            "() => [...document.querySelectorAll("
            "'#sets-panel .sets-row:not(.apps)')]"
            ".map((r) => [r.textContent.trim(), !!r.querySelector('.sets-edit')])")
        results["every set row carries an edit door"] = bool(doors) and all(d[1] for d in doors)
        if not all(d[1] for d in doors):
            print(f"  DETAIL rows without a door: {[d[0] for d in doors if not d[1]]}")

        target = page.evaluate(
            "() => { const r = __row('#sets-panel', 'Mouse');"
            " return r ? r.textContent.trim() : null; }")
        assert target, "the Mouse row is not in the picker"
        # THE DOOR MAY NOT TICK THE ROW IT SITS ON. A button inside a <label>
        # activates that label by default — opening an editor would have
        # switched the set off on the way in.
        page.evaluate(
            "() => { const r = __row('#sets-panel', 'Edit');"
            " window.__wasTicked = r.querySelector('input').checked;"
            " __tap(r.querySelector('.sets-edit')); }")
        page.wait_for_timeout(200)
        g = page.evaluate("() => __editorGeom()")
        results["the edit door opens the editor"] = g["open"]
        still = page.evaluate(
            "() => { closeSetEditor();"
            " const v = __row('#sets-panel', 'Edit').querySelector('input').checked;"
            " closeSetsPanel(); return [window.__wasTicked, v]; }")
        results["the edit door does not tick the row it sits on"] = still[0] == still[1]

        # Back into the editor and do the real work.
        page.evaluate("() => { closeSetsPanel(); openSetEditor("
                      "categories.find((c) => c.name === 'Mouse')); }")
        page.wait_for_timeout(150)
        g = page.evaluate("() => __editorGeom()")
        results["the pool is listed, the riding four are ticked"] = (
            g["rows"] > 4 and g["ticked"] == 4 and len(g["slots"]) == 4)
        if not (g["rows"] > 4 and g["ticked"] == 4):
            print(f"  DETAIL pool rows={g['rows']} ticked={g['ticked']} slots={g['slots']}")

        # THE ARRANGEMENT IS A DRAWING, and no two buttons share a square.
        boxes = g["boxes"]
        overlaps = [(i, j) for i in range(len(boxes)) for j in range(i + 1, len(boxes))
                    if boxes[i]["l"] < boxes[j]["r"] and boxes[j]["l"] < boxes[i]["r"]
                    and boxes[i]["t"] < boxes[j]["b"] and boxes[j]["t"] < boxes[i]["b"]]
        results["no two positions land on the same square"] = not overlaps
        results["the editor never scrolls the page sideways"] = g["scrollW"] <= g["w"] + 1
        results["every position is drawn with real size"] = all(
            b["w"] > 40 and b["h"] > 40 for b in boxes)

        page.screenshot(path=str(SHOT_DIR / "editor_open.png"))

        # Swap the first two positions — his tap-to-swap, through the page's
        # own handler and not a variable.
        before = page.evaluate("() => __editorGeom().slots")
        page.evaluate("() => { const c = document.querySelectorAll('.se-slot');"
                      " __tap(c[0]); __tap(c[1]); }")
        page.wait_for_timeout(150)
        after = page.evaluate("() => __editorGeom().slots")
        results["tapping two positions swaps them"] = (
            after[0] == before[1] and after[1] == before[0] and sorted(after) == sorted(before))
        if after == before:
            print(f"  DETAIL the swap did nothing: {before}")

        # Tick a reserve in place of a riding command.
        page.evaluate(
            "() => { const i = __row('#set-editor-panel', 'Scroll')"
            ".querySelector('input');"
            " i.checked = false; i.dispatchEvent(new Event('change')); }")
        page.wait_for_timeout(150)
        page.evaluate(
            "() => { const i = __row('#set-editor-panel', 'Btn 4')"
            ".querySelector('input');"
            " i.checked = true; i.dispatchEvent(new Event('change')); }")
        page.wait_for_timeout(150)

        page.evaluate("() => { window.__sent = [];"
                      " __tap(document.querySelector('#set-editor-panel .sets-done')); }")
        page.wait_for_timeout(600)

        sent = [m for m in page.evaluate("() => window.__sent")
                if m.get("type") == "actions_update"]
        results["Save puts an actions_update on the wire"] = len(sent) == 1
        if not sent:
            print(f"  DETAIL nothing was sent: {page.evaluate('() => window.__sent')}")
        else:
            m = sent[0]
            results["the message names the set and its four buttons by id"] = (
                m.get("set") == "Mouse" and "x1" in (m.get("active") or [])
                and "scroll" not in (m.get("active") or [])
                and len(m.get("active") or []) == 4)
            results["the message carries only owner-editable keys"] = set(m) <= (
                {"type", "set"} | actions_api.PHONE_EDITABLE)
            if not set(m) <= ({"type", "set"} | actions_api.PHONE_EDITABLE):
                print(f"  DETAIL the message carried {sorted(m)}")

        # THE FILE ON DISK — the whole point of routing this through the PC.
        page.wait_for_timeout(400)
        on_disk = json.loads(actions_path.read_text(encoding="utf-8"))
        mouse = named(on_disk, "Mouse")
        results["(a) the phone's edit is in the PC's actions.json"] = (
            "x1" in (mouse.get("active") or []) and "scroll" not in (mouse.get("active") or []))
        if "x1" not in (mouse.get("active") or []):
            print(f"  DETAIL the file says active={mouse.get('active')}")

        # (d) THE WHEEL FOLLOWS, with no reconnect: the server's re-broadcast
        # has already arrived by now, so the live D-pad must be showing the
        # new crew.
        pad = page.evaluate("() => __padButtons()")
        results["(d) the live controls changed without a reconnect"] = (
            any("Btn 4" in t for t in pad) and not any("Scroll" in t for t in pad))
        if not any("Btn 4" in t for t in pad):
            print(f"  DETAIL the D-pad still shows {pad}")

        page.screenshot(path=str(SHOT_DIR / "after_save.png"))
        results["the page loads and edits clean"] = not errors
        if errors:
            print(f"  DETAIL page errors: {errors}")
    finally:
        ctx.close()


SHOT_DIR = PROJECT / ".claude" / "shots" / "task218b-set-editor"


# ═══════════════════════════ the run ═════════════════════════════════════════
PURE_CHECKS = [
    ("the phone may only write owner-owned keys", check_phone_editable_is_owner_owned),
    ("(b) a non-owner key is refused, whole", check_a_non_owner_key_is_refused),
    ("(c) an id outside the pool is refused", check_an_id_outside_the_pool_is_refused),
    ("the shape of `active` is enforced", check_the_shape_of_active_is_enforced),
    ("an arrangement must be a real permutation", check_the_order_must_be_a_real_permutation),
    ("built-in, app and custom sets are all editable", check_every_kind_of_set_is_editable),
    ("(a) the edit lands in the user's own file", check_the_edit_lands_in_the_users_file),
    ("a refusal never touches the file", check_a_refusal_never_touches_the_file),
    ("(d) the re-broadcast carries the new state", check_the_rebroadcast_carries_the_new_state),
]


def main() -> int:
    print("\n=== SET EDITOR GATE (task 218b) ===")
    results = {}
    for name, check in PURE_CHECKS:
        try:
            check()
            results[name] = True
        except Exception as e:  # noqa: BLE001
            # ANY exception is a FAIL, not a crash. A planted defect rarely
            # arrives as a tidy AssertionError — the "never write the file"
            # plant surfaces as a KeyError on a key that was never written —
            # and a gate that dies on the first plant reports nothing about
            # the rest of its checks.
            results[name] = False
            print(f"  DETAIL {name}: {type(e).__name__}: {e}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SET EDITOR GATE FAILED — playwright is required (the phone half "
              "opens the REAL page). Never skip a gate silently.")
        return 1

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        # A COPY of the pinned fixture: this gate writes actions.json, and the
        # repo's own file is the owner's to hand-edit.
        actions_path = Path(tmp) / "actions.json"
        # A COPY, and one with RESERVES: the shared fixture's Mouse set holds
        # exactly the four buttons it shows, and a pool the size of the D-pad
        # cannot demonstrate this feature at all. The two side buttons are added
        # to THIS copy (they are in the real shipped set, and every other gate
        # keeps the fixture it was written against), with `active` pinned to
        # today's four so nothing about the rendering changes until the phone
        # asks it to.
        fixture = json.loads((Path(__file__).resolve().parent / "fixtures"
                              / "actions.json").read_text(encoding="utf-8"))
        mouse = next(c for c in fixture["categories"] if c["name"] == "Mouse")
        mouse["active"] = [b["action"] for b in mouse["buttons"]]
        mouse["buttons"] += [{"action": "x1"}, {"action": "x2"}]
        actions_path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
        gate = start_server(actions_path)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                check_the_phone_walks_the_path(browser, gate, actions_path, results)
            except Exception as e:  # noqa: BLE001 — same reason as above
                results["the phone walks his path"] = False
                print(f"  DETAIL the phone half: {e}")
            finally:
                browser.close()

    failed = [k for k, ok in results.items() if not ok]
    for name in sorted(results):
        print(f"  {'PASS' if results[name] else 'FAIL'}  {name}")
    if failed:
        print(f"\nSET EDITOR GATE FAILED — {len(failed)} check(s) broken.")
        return 1
    print("\nSET EDITOR GATE PASSED — the phone edits a set's interior, the PC "
          "validates and writes HIS file, and the wheel follows at once.")
    return 0


def test_set_editor():
    """pytest entry."""
    import pytest
    pytest.importorskip("playwright.sync_api")
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
