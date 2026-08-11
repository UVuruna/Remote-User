"""Guard: THE WHEEL THAT SHEDS ITS ACTIVE SETS (task 181, owner decree
2026-08-11, ~17:45).

His decision, after the critique: DROP-OUT IS THE DEFAULT. A set placed on
either D-pad group drops off the wheel while it is placed — no set may ever
appear on both sides at once (that half ships in BOTH modes), and drop-out's
extra room is why the cap rises from 8 to 10. The FIXED-WHEEL variant (a
placed set still offers itself as a wheel choice, cap stays 8) is kept as a
tucked-away desktop option, next to "Wheel order…" in the Controls editor
(server/gui/controls_editor.py), because it is the same domain — set once,
never touched from the phone.

The logic under test lives in client/sets.js (`wheelCats`/`placedCat`/
`wheelCap`/`setWheelMode`) — run WHOLE in node, same harness as
test_app_set_wheel.py, so the guard sees the real composition + drop-out
interaction rather than a hand-lifted fragment. `groups` (which index each
D-pad side shows, into `allCats()`) is controls.js's own state; it is seeded
here exactly the way controls.js declares it.

Also proven, on the SERVER side, without node:
  - `wheel_mode` reaches the phone through `server/actions_api.py`'s
    `load_actions()` whitelist (the 2026-08-07 lesson — a field missing from
    that whitelist is a feature the phone never sees).
  - `wheel_mode` survives `merge_shipped_pools` as an OWNER key (the same
    lesson from the other direction: a key not in OWNER_TOP_KEYS is
    overwritten from shipped on every merge, silently erasing his choice).

Run:  .venv\\Scripts\\python tests/test_wheel_dropout.py
Requires: node on PATH for the client-side cases (server-side cases run with
plain Python and are never skipped).
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

SETS = PROJECT / "client" / "sets.js"


def run_js(body: str, app_sets: list, prefs: dict,
           categories: list | None = None, custom: list | None = None,
           wheel_order: list | None = None, wheel_mode: str = "dropout",
           groups: dict | None = None) -> object:
    """Runs client/sets.js WHOLE in node, behind its neighbours' stubs —
    same shape as test_app_set_wheel.py's harness, plus `groups` (the D-pad
    side -> allCats() index state controls.js declares) and `wheelMode`,
    since wheelCats()/placedCat() read both."""
    module = SETS.read_text(encoding="utf-8")
    for needed in ("function wheelCats", "function placedCat",
                   "function wheelCap", "function setWheelMode"):
        assert needed in module, f"{needed} left client/sets.js"
    g = groups if groups is not None else {"left": 0, "right": 0}
    script = f"""
let STORE = {json.dumps({"setsPrefs": json.dumps(prefs)})};
function prefGet(k) {{ return STORE[k]; }}
function prefSet(k, v) {{ STORE[k] = v; }}
let layoutActive = null;
let layouts = [];
let groups = {json.dumps(g)};
{module}
categories = {json.dumps(categories if categories is not None else [])};
appSets = {json.dumps(app_sets)};
customSets = {json.dumps(custom if custom is not None else [])};
wheelOrder = {json.dumps(wheel_order if wheel_order is not None else [])};
setWheelMode({json.dumps(wheel_mode)});
{body}
"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.mjs"
        path.write_text(script, encoding="utf-8")
        out = subprocess.run([shutil.which("node") or "node", str(path)],
                             capture_output=True, text=True, check=False)
        if out.returncode != 0:
            raise AssertionError(f"node failed:\n{out.stderr}")
        return json.loads(out.stdout.strip())


BASIC = [
    {"name": "Mouse", "required": True},
    {"name": "Input", "required": True},
    {"name": "Settings", "required": True},
    {"name": "Edit"},
    {"name": "Attach"},
    {"name": "Navigate"},
]
PREFS = {"apps": True, "appState": {}, "state": {}}


def wheel_names(side, **kw):
    body = f'console.log(JSON.stringify(wheelCats("{side}").map((c) => c.name)));'
    return run_js(body, [], PREFS, categories=BASIC, **kw)


# -- 1. a placed set is absent from the wheel in drop-out mode --------------

def test_dropout_sheds_the_placed_set_off_its_own_side():
    # left shows "Edit" (index 3 in the default order Mouse/Input/Settings/
    # Edit/Attach/Navigate) — drop-out must not offer it again on the left.
    got = wheel_names("left", wheel_mode="dropout", groups={"left": 3, "right": 0})
    assert "Edit" not in got, (
        f"Edit is PLACED on the left in drop-out mode — it must shed off "
        f"the left wheel too, not just the right: {got}")


def test_fixed_mode_still_offers_the_placed_set():
    """The tucked-away variant keeps today's behaviour on purpose."""
    got = wheel_names("left", wheel_mode="fixed", groups={"left": 3, "right": 0})
    assert "Edit" in got, (
        f"fixed mode must still offer the side's own placed set (owner's "
        f"tucked-away option, unchanged behaviour): {got}")


# -- 2. never on both sides -- ships in BOTH modes ---------------------------

def test_no_duplicate_on_both_sides_dropout():
    got = wheel_names("left", wheel_mode="dropout", groups={"left": 0, "right": 3})
    assert "Edit" not in got, f"right holds Edit — left must not offer it too: {got}"


def test_no_duplicate_on_both_sides_fixed():
    got = wheel_names("left", wheel_mode="fixed", groups={"left": 0, "right": 3})
    assert "Edit" not in got, (
        f"the no-duplicate rule ships in FIXED mode too (task 181): {got}")


def test_fixed_mode_still_offers_everything_else():
    got = wheel_names("right", wheel_mode="fixed", groups={"left": 3, "right": 0})
    assert set(got) == {"Mouse", "Input", "Settings", "Attach", "Navigate"}, (
        f"fixed mode sheds only the OTHER side's placed set: {got}")


# -- 3. capacity: 10 under drop-out, 8 under fixed, stated correctly --------

def test_capacity_is_ten_under_dropout_and_eight_under_fixed():
    body = "console.log(JSON.stringify(wheelCap()));"
    assert run_js(body, [], PREFS, wheel_mode="dropout") == 10
    assert run_js(body, [], PREFS, wheel_mode="fixed") == 8


def test_allcats_composition_honours_the_mode_cap():
    """`allCats()` is the composition list (separate from `wheelCats(side)`'s
    placement filter) — nine optional sets on top of the three required ones
    trims to 8 under fixed and rides whole under drop-out's cap of 10."""
    many = [{"name": "Mouse", "required": True}, {"name": "Input", "required": True},
            {"name": "Settings", "required": True}] + [
        {"name": f"Custom{i}"} for i in range(7)]  # 10 total
    body = "console.log(JSON.stringify(allCats().length));"
    assert run_js(body, [], PREFS, categories=many, wheel_mode="fixed") == 8
    assert run_js(body, [], PREFS, categories=many, wheel_mode="dropout") == 10


# -- 4. ranks close without a hole (the ordinary wheel_order guarantee,     --
#       now proven to hold across a shed) -----------------------------------

def test_ranks_close_no_hole_simple():
    """A cleaner, single-purpose case: placing the FIRST-ranked set must not
    leave a hole where it sat — the next-ranked set moves up to fill it."""
    order = ["Attach", "Edit", "Mouse", "Input", "Settings", "Navigate"]
    # groups["left"] must be the allCats() index of "Attach". allCats() with
    # no wheel_order applied yet is in declaration order: Mouse, Input,
    # Settings, Edit, Attach, Navigate -> Attach is index 4.
    got = wheel_names("right", wheel_mode="dropout", groups={"left": 4, "right": 0},
                      wheel_order=order)
    assert got[0] == "Edit", (
        f"Attach (rank 0) is placed on the left and sheds off the right "
        f"wheel too under drop-out — Edit (rank 1) must close up into its "
        f"place, not leave a gap: {got}")


# -- 5. the mode key survives merge_shipped (OWNER_TOP_KEYS) ---------------

def test_wheel_mode_is_owner_owned():
    from gui.controls_data import OWNER_TOP_KEYS, merge_shipped_pools
    assert "wheel_mode" in OWNER_TOP_KEYS, (
        "wheel_mode must be in OWNER_TOP_KEYS or the next shipped-pool merge "
        "silently erases his choice back to the default (the 2026-08-07 "
        "wheel_order lesson, from the other direction)")
    data = {"categories": [], "app_sets": [], "custom_sets": [],
            "wheel_mode": "fixed"}
    shipped = {"categories": [], "app_sets": [], "wheel_mode": "dropout"}
    merge_shipped_pools(data, shipped)
    assert data["wheel_mode"] == "fixed", (
        "his own wheel_mode choice must survive the merge unchanged")

    # And a user file that PREDATES the key gets the shipped default, exactly
    # like wheel_order did for a pre-R5 file.
    data2 = {"categories": [], "app_sets": [], "custom_sets": []}
    merge_shipped_pools(data2, shipped)
    assert data2.get("wheel_mode") == "dropout", (
        "a file with no opinion on wheel_mode must be seeded from shipped "
        f"(default drop-out): {data2.get('wheel_mode')!r}")


# -- 6. wheel_mode reaches the phone through _load_actions -------------------

def test_wheel_mode_reaches_the_phone_through_load_actions():
    import actions_api
    import config

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "actions.json"
        path.write_text(json.dumps({
            "categories": [], "app_sets": [], "custom_sets": [],
            "left": 0, "right": 0, "wheel_order": [], "wheel_mode": "fixed",
        }), encoding="utf-8")
        config.apply(actions_path=path)
        try:
            actions_api._shipped_pools_merged = True  # skip the FROZEN-only merge
            data = actions_api.load_actions()
        finally:
            actions_api._shipped_pools_merged = False
        assert data.get("wheel_mode") == "fixed", (
            f"a field missing from _load_actions' whitelist is a feature the "
            f"phone never sees (the wheel_order lesson) — wheel_mode: {data}")

    # Absent from the file entirely (a pre-181 install): the honest default.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "actions.json"
        path.write_text(json.dumps({
            "categories": [], "app_sets": [], "custom_sets": [],
        }), encoding="utf-8")
        config.apply(actions_path=path)
        try:
            actions_api._shipped_pools_merged = True
            data = actions_api.load_actions()
        finally:
            actions_api._shipped_pools_merged = False
        assert data.get("wheel_mode") == "dropout", (
            f"a pre-181 file with no wheel_mode key must default to dropout: {data}")


TESTS = [
    ("drop-out sheds the placed set off its OWN side",
     test_dropout_sheds_the_placed_set_off_its_own_side),
    ("fixed mode still offers the placed set (tucked-away option)",
     test_fixed_mode_still_offers_the_placed_set),
    ("no duplicate on both sides — drop-out",
     test_no_duplicate_on_both_sides_dropout),
    ("no duplicate on both sides — fixed (ships in both modes)",
     test_no_duplicate_on_both_sides_fixed),
    ("fixed mode still offers everything else",
     test_fixed_mode_still_offers_everything_else),
    ("capacity is 10 under drop-out, 8 under fixed",
     test_capacity_is_ten_under_dropout_and_eight_under_fixed),
    ("allCats() composition honours the mode's cap",
     test_allcats_composition_honours_the_mode_cap),
    ("ranks close around a shed set, no hole",
     test_ranks_close_no_hole_simple),
    ("wheel_mode is owner-owned across the shipped-pool merge",
     test_wheel_mode_is_owner_owned),
    ("wheel_mode reaches the phone through _load_actions",
     test_wheel_mode_reaches_the_phone_through_load_actions),
]


def main() -> int:
    print("\n=== WHEEL DROP-OUT GUARD (task 181) ===")
    failed = 0
    node_missing = not shutil.which("node")
    for name, fn in TESTS:
        if node_missing and fn not in (
            test_wheel_mode_is_owner_owned,
            test_wheel_mode_reaches_the_phone_through_load_actions,
        ):
            print(f"  SKIP  {name} (node not on PATH)")
            continue
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nWHEEL DROP-OUT GUARD FAILED — {failed} rule(s) broken.")
        return 1
    print("\nWHEEL DROP-OUT GUARD PASSED — a placed set sheds correctly, "
          "never duplicates, and its mode survives the merge and the wire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
