"""APPEARANCE PER DEVICE GATE (owner ballot 2026-08-12).

His verdict: "appearance is also per device, not global, so it belongs on the
phone / tablet." The three look axes — theme, whether the controls wear each
set's colour, and whether they are outlined or filled — used to live only in
the PC's Settings window and ride the `config` frame to every handset, so two
devices could not look different. They now live on the device, with the PC's
values as the DEFAULT.

WHY THIS GATE DRIVES THE REAL PAGE. The promise the owner will judge is a
RENDERING one: two devices, one frame, two looks. A check on a stored
preference proves nothing about that — this project has been burned exactly
there (the actions.json merge, CLAUDE.md: every guard built the "user file" as
a copy of the shipped one and proved the repo's file to itself). So the checks
below run client/theme.js WHOLE in node, one fresh module instance per
simulated device, with the prefs bridge and the page stubbed, and they read
what the page really writes onto <body> — `data-theme`, `data-colored`,
`data-fill`, the three attributes every rule in client/theme.css hangs off.

What is proven here:

  A. A device that has never chosen renders the PC's frame BYTE FOR BYTE.
  B. The device store is read FIRST: a stored choice beats the frame.
  C. Two devices with different stored choices render the SAME frame
     differently. This is the owner's own sentence, measured.
  D. A `config` restating the PC's default does NOT overwrite a device's
     choice — otherwise every reconnect would silently undo it.
  E. Handing an axis back to the PC really hands it back: the axis follows the
     frame again, rather than being pinned to the value it had.
  F. The legacy four-value theme ("colored" / "colored-light") still migrates
     — from the FRAME and from a device store written by an older page.
  G. The choice is stored under its own key through the prefs BRIDGE, not
     bare localStorage (per-ORIGIN, and the shell alternates between the LAN
     and Tailscale addresses — the "picker rotates" bug of 2026-08-05).
  H. The panel really exists and is really reachable: a pure module nobody
     calls is a feature that does not exist.
  I. The desktop card no longer carries the three phone combos, and the wire
     still carries the default.

Run:  .venv\\Scripts\\python tests/test_appearance_device.py
Requires: node on PATH — a HARD requirement (registered fail-closed in
setup/build.py, the test_view_anchor.py precedent). Never skip it silently.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
THEME = PROJECT / "client" / "theme.js"
PANEL = PROJECT / "client" / "appearance-panel.js"
PANELS = PROJECT / "client" / "panels.js"
CONTROLS = PROJECT / "client" / "controls.js"
INDEX = PROJECT / "client" / "index.html"
ACTIONS = PROJECT / "actions.json"
SETTINGS_WINDOW = PROJECT / "server" / "gui" / "settings_window.py"

# One simulated device: a prefs store, the PC's frame, and a script of calls.
# `theme.js` is run WHOLE — top-level `restoreUi` included, which is the path a
# real page takes before the socket has said anything.
HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const THEME = process.argv[2];
const input = JSON.parse(process.argv[3]);

function device(store, frames, ops) {
  const prefs = { ...store };
  const dataset = {};
  const sandbox = {
    console,
    performance: { now: () => 0 },
    prefGet: (k) => (k in prefs ? prefs[k] : null),
    prefSet: (k, v) => { prefs[k] = String(v); },
    document: { body: { dataset, style: {} } },
    getComputedStyle: () => ({
      backgroundColor: "rgb(15 23 42)",
      getPropertyValue: () => "",
    }),
    setCanvasBackdrop: () => {},
    categories: [], customSets: [], appSets: [],
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(THEME, "utf8"), sandbox, { filename: "theme.js" });
  for (const frame of frames) sandbox.applyUi(frame);
  for (const op of ops || []) {
    if (op.set) sandbox.setUiAxis(op.set, op.value);
    if (op.clear !== undefined) sandbox.clearUiAxis(op.clear || undefined);
  }
  return {
    dataset: { ...dataset },
    prefs,
    follows: ["theme", "colored", "fill"].map((a) => sandbox.uiFollowsPc(a)),
    pc: ["theme", "colored", "fill"].map((a) => sandbox.uiPcValue(a)),
  };
}

console.log(JSON.stringify(
  input.map((d) => device(d.store || {}, d.frames || [], d.ops || []))));
"""


def run(devices):
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "harness.js"
        script.write_text(HARNESS, encoding="utf-8")
        out = subprocess.run(
            ["node", str(script), str(THEME), json.dumps(devices)],
            capture_output=True, text=True, check=False)
        assert out.returncode == 0, f"node failed:\n{out.stderr}"
        return json.loads(out.stdout)


PC_FRAME = {"theme": "light", "colored": True, "fill": "full", "colors": {}}


# --- A -----------------------------------------------------------------------

def check_a_device_that_never_chose_wears_the_pc_value():
    [got] = run([{"frames": [PC_FRAME]}])
    assert got["dataset"] == {"theme": "light", "colored": "true", "fill": "full"}, (
        f"a handset with no choice of its own rendered {got['dataset']} "
        "instead of the PC's own frame")
    assert got["follows"] == [True, True, True], got["follows"]


# --- B -----------------------------------------------------------------------

def check_the_device_store_is_read_before_the_frame():
    [got] = run([{
        "store": {"uiChoice": json.dumps({"theme": "dark", "fill": "transparent"})},
        "frames": [PC_FRAME],
    }])
    assert got["dataset"]["theme"] == "dark", got["dataset"]
    assert got["dataset"]["fill"] == "transparent", got["dataset"]
    # …and the axis it did NOT claim still follows the PC.
    assert got["dataset"]["colored"] == "true", got["dataset"]
    assert got["follows"] == [False, True, False], got["follows"]


# --- C -----------------------------------------------------------------------

def check_two_devices_render_one_frame_differently():
    tablet, phone = run([
        {"store": {"uiChoice": json.dumps({"theme": "dark", "colored": False})},
         "frames": [PC_FRAME]},
        {"store": {"uiChoice": json.dumps({"fill": "transparent"})},
         "frames": [PC_FRAME]},
    ])
    assert tablet["dataset"] != phone["dataset"], (
        "two devices with different stored choices rendered the SAME look "
        f"from one frame: {tablet['dataset']}")
    assert tablet["dataset"] == {"theme": "dark", "colored": "false", "fill": "full"}
    assert phone["dataset"] == {"theme": "light", "colored": "true",
                                "fill": "transparent"}


# --- D -----------------------------------------------------------------------

def check_a_reconnect_never_overwrites_the_choice():
    """Every reconnect restates `config.ui`. If the frame landed on the
    rendered look rather than on the default, a device's choice would survive
    exactly until the next excursion."""
    [got] = run([{
        "store": {"uiChoice": json.dumps({"theme": "dark"})},
        "frames": [PC_FRAME, PC_FRAME, {"theme": "light"}],
    }])
    assert got["dataset"]["theme"] == "dark", (
        "a `config` frame overwrote a choice made on the device — that is the "
        "choice being undone on every single reconnect")


# --- E -----------------------------------------------------------------------

def check_handing_an_axis_back_really_hands_it_back():
    [got] = run([{
        "store": {"uiChoice": json.dumps({"theme": "dark"})},
        "frames": [PC_FRAME],
        "ops": [{"clear": "theme"}],
    }])
    assert got["dataset"]["theme"] == "light", (
        "clearing an axis left it pinned to the value it had instead of "
        "following the PC again")
    assert got["follows"] == [True, True, True]
    # …and a LATER frame moves it, which is what "follows the PC" means.
    [moved] = run([{
        "store": {"uiChoice": json.dumps({"theme": "dark"})},
        "frames": [PC_FRAME],
        "ops": [{"clear": "theme"}],
    }])
    assert moved["pc"][0] == "light", moved["pc"]


# --- F -----------------------------------------------------------------------

def check_the_legacy_four_value_theme_still_migrates():
    # …from the FRAME (an older server) …
    [frame_side] = run([{"frames": [{"theme": "colored", "fill": "full"}]}])
    assert frame_side["dataset"] == {"theme": "dark", "colored": "true",
                                     "fill": "full"}, frame_side["dataset"]
    [light_side] = run([{"frames": [{"theme": "colored-light"}]}])
    assert light_side["dataset"]["theme"] == "light"
    assert light_side["dataset"]["colored"] == "true"
    # …and from THIS DEVICE's own store, written by an older page.
    [cached] = run([{"store": {"uiLook": json.dumps({"theme": "colored-light"})}}])
    assert cached["dataset"]["theme"] == "light", cached["dataset"]
    assert cached["dataset"]["colored"] == "true", cached["dataset"]
    [chosen] = run([{"store": {"uiChoice": json.dumps({"theme": "colored"})},
                     "frames": [PC_FRAME]}])
    assert chosen["dataset"]["theme"] == "dark", chosen["dataset"]


# --- G -----------------------------------------------------------------------

def check_the_choice_is_stored_through_the_bridge_under_its_own_key():
    [got] = run([{"frames": [PC_FRAME], "ops": [{"set": "theme", "value": "dark"}]}])
    assert "uiChoice" in got["prefs"], (
        f"the choice was not written to the device store: {got['prefs']}")
    assert json.loads(got["prefs"]["uiChoice"]) == {"theme": "dark"}, (
        "the device store holds more than the axes actually chosen — an axis "
        "pinned by accident stops following the PC forever")
    # The frame cache stays the PC's word, so "follow the PC" has something
    # true to follow after a restart.
    assert json.loads(got["prefs"]["uiLook"])["theme"] == "light"
    source = THEME.read_text(encoding="utf-8")
    assert "prefGet(UI_CHOICE_PREF)" in source and "prefSet(UI_CHOICE_PREF" in source, (
        "the choice does not go through the prefs bridge — bare localStorage "
        "is keyed by ORIGIN and the shell alternates LAN/Tailscale addresses")
    for name, text in (("theme.js", source),
                       ("appearance-panel.js", PANEL.read_text(encoding="utf-8"))):
        # A COMMENT may name it — the reason it is banned is worth writing
        # down. A CALL may not: localStorage is keyed by ORIGIN, and the
        # bridge (prefGet/prefSet, controls.js) is the only legal store.
        code = "\n".join(line.split("//")[0] for line in text.splitlines())
        assert "localStorage" not in code, (
            f"client/{name} reaches for localStorage directly")


# --- H -----------------------------------------------------------------------

def check_the_panel_exists_and_is_reachable():
    assert PANEL.exists(), "client/appearance-panel.js is missing"
    panel = PANEL.read_text(encoding="utf-8")
    for axis in ("theme", "colored", "fill"):
        assert f'axis: "{axis}"' in panel, f"the panel offers no {axis} row"
    assert "setUiAxis" in panel and "clearUiAxis" in panel
    assert "appearance: () => openAppearancePanel()" in \
        PANELS.read_text(encoding="utf-8"), \
        "PANEL_KINDS does not open the Appearance card"
    assert 'kind: "appearance"' in CONTROLS.read_text(encoding="utf-8"), \
        "no action in controls.js opens it"
    index = INDEX.read_text(encoding="utf-8")
    assert 'id="appearance-panel"' in index, "the page has no panel container"
    assert "appearance-panel.js" in index, "the page does not load the module"
    assert index.index("panels.js") < index.index("appearance-panel.js"), \
        "appearance-panel.js loads before panels.js (segRow, ghostClickArmor)"
    actions = json.loads(ACTIONS.read_text(encoding="utf-8"))
    settings = next(s for s in actions["categories"] if s["name"] == "Settings")
    assert any(b.get("action") == "appearance" for b in settings["buttons"]), (
        "the Settings set's pool does not carry the appearance action — the "
        "panel could never be opened from the wheel")


# --- I -----------------------------------------------------------------------

def check_the_desktop_card_gave_the_choice_up_and_the_wire_did_not():
    window = SETTINGS_WINDOW.read_text(encoding="utf-8")
    for gone in ("phone_theme_combo", "phone_colored_combo", "phone_fill_combo",
                 "PHONE_THEMES", "PHONE_COLORED", "PHONE_FILLS"):
        assert gone not in window, (
            f"{gone} is still in the desktop Settings window — the phone's "
            "look is chosen on the phone now")
    assert "ThemeSwitch()" in window, "the PC's own sun/moon pill went with them"
    assert "Settings → Look" in window, (
        "the card leaves no forwarding note; a setting that moves without one "
        "reads as a setting that was taken away")
    sys.path.insert(0, str(PROJECT / "server"))
    from config import ui_config
    ui = ui_config()
    assert set(ui) == {"theme", "colored", "fill", "colors"}, ui
    assert ui["theme"] in ("dark", "light") and isinstance(ui["colored"], bool)


CHECKS = [
    ("a device that never chose wears the PC's value, byte for byte",
     check_a_device_that_never_chose_wears_the_pc_value),
    ("the device store is read before the frame",
     check_the_device_store_is_read_before_the_frame),
    ("two devices render ONE frame differently",
     check_two_devices_render_one_frame_differently),
    ("a reconnect never overwrites a device's choice",
     check_a_reconnect_never_overwrites_the_choice),
    ("handing an axis back to the PC really hands it back",
     check_handing_an_axis_back_really_hands_it_back),
    ("the legacy four-value theme still migrates, both sides",
     check_the_legacy_four_value_theme_still_migrates),
    ("the choice rides the prefs bridge, under its own key",
     check_the_choice_is_stored_through_the_bridge_under_its_own_key),
    ("the panel exists and is reachable from the Settings set",
     check_the_panel_exists_and_is_reachable),
    ("the desktop card gave the choice up; the wire kept the default",
     check_the_desktop_card_gave_the_choice_up_and_the_wire_did_not),
]


def main() -> int:
    print("\n=== APPEARANCE PER DEVICE GATE ===")
    if shutil.which("node") is None:
        print("APPEARANCE GATE FAILED — node is required (it runs the REAL "
              "client/theme.js) and is not on PATH. Never skip a gate "
              "silently.")
        return 1
    failed = 0
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nAPPEARANCE GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nAPPEARANCE GATE PASSED — one frame, two devices, two looks; and "
          "a device that never chose is unchanged.")
    return 0


def test_appearance_device():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
