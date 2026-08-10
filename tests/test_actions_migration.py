"""Gate: a NEW VERSION'S FIELDS actually reach the owner's actions.json.

This is the gate that four releases needed and did not have.

The owner's copy of actions.json is seeded ONCE, at his first install, and is
never replaced again. `merge_shipped_pools` is the only path a later version
has into it — and until 2026-08-07 that function copied a HARDCODED LIST of
fields (`name, icon, required, process, title`). Anything invented after that
list was written therefore never arrived. The bill:

  * The shipped Claude app set gained `"agent": "claude"` on 2026-08-06. His
    copy never did. Without it the set can only match by TITLE, and his window
    is titled "Voditi agente i kontrolisati grid skice - Remote User - Visual
    Studio Code [Administrator]" — Claude Code names its VS Code tab after the
    CONVERSATION, so the word "claude" is absent and always will be. An
    unsatisfiable condition, forever. He reported the Claude set missing
    across four or five releases.
  * The same engine kept "Anywhere" in his Settings set after the update that
    replaced it with "Language" (already in the project CLAUDE.md).
  * `wheel_order` (build round R5, 2026-08-07) was one release away from
    joining them: a top-level key his file has never had.

EVERY guard was green through all of it, and here is exactly why — the old
`tests/test_controls_sets.py` builds its "user file" with `user = copy(shipped)`.
A user file made out of the shipped file already HAS every new field. The
guards proved the repo's actions.json to itself. So this gate does the one
thing they never did: it starts from a user file of an OLDER SHAPE — the
owner's real one, quoted below — and proves the new field arrives while his
own choices survive.

And it does NOT test for the field named `agent`. Testing today's field name
would leave this repeating a sixth time on tomorrow's. It plants a field name
NOBODY HAS INVENTED and demands the rule carry it.

Run:  .venv\\Scripts\\python tests/test_actions_migration.py
"""

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))


def shipped_actions() -> dict:
    return json.loads((PROJECT / "actions.json").read_text(encoding="utf-8"))


def copy(data: dict) -> dict:
    return json.loads(json.dumps(data))


def named(sets: list, name: str) -> dict | None:
    return next((s for s in sets if s.get("name") == name), None)


# ───────────────────────── the owner's real file, 2026-08-07 ─────────────────
# The shape of %LOCALAPPDATA%\RemoteUser\actions.json as it actually was on his
# PC while he was reporting the bug: a Claude app set with `title` and NO
# `agent`, no top-level `wheel_order`, his own button rename on the left click,
# and his `enabled: false` ticks. Held here as literal text, not derived from
# the shipped file, because deriving it is precisely the mistake this gate
# exists to stop.
HIS_FILE = {
    "left": 0,
    "right": 1,
    "categories": [
        {"name": "Mouse", "icon": "mouse", "required": True,
         "buttons": [{"action": "click", "label": "Left"}, {"action": "right"},
                     {"action": "middle"}, {"action": "scroll"},
                     {"action": "drag"}, {"action": "x1"}, {"action": "x2"}],
         "active": ["click", "right", "middle", "scroll"]},
        {"name": "Cursor", "icon": "leftright", "enabled": False,
         "buttons": [{"label": "Left", "icon": "arrowl", "key": "left"}]},
        {"name": "Settings", "icon": "settings", "required": True,
         "buttons": [{"action": "monitor"}, {"action": "sets"},
                     {"action": "quality"}, {"action": "anywhere"}]},
    ],
    "custom_sets": [{"name": "Mine", "icon": "star",
                     "buttons": [{"label": "Hi", "chord": "ctrl+h"}]}],
    "app_sets": [
        {"process": "code", "name": "Claude", "icon": "claude",
         "buttons": [{"label": "Usage", "icon": "usage", "text": "/usage",
                      "enter": True}],
         "title": ["claude code", "claude"]},
        {"process": "code", "name": "VSCode", "icon": "vscode",
         "buttons": [{"label": "Sidebar", "icon": "sidebar", "chord": "ctrl+b"}]},
    ],
}


def test_his_real_file_receives_the_agent_switch():
    """THE REPORTED FAILURE, on his own file shape: the Claude set must come
    out of the merge carrying `agent`, because nothing else can ever match it."""
    from gui.controls_data import merge_shipped_pools
    shipped = shipped_actions()
    ship_claude = named(shipped["app_sets"], "Claude")
    assert ship_claude and ship_claude.get("agent") == "claude", (
        "this gate assumes the shipped Claude set still carries the agent "
        "switch — if the product changed, change the gate deliberately")
    user = copy(HIS_FILE)
    assert "agent" not in named(user["app_sets"], "Claude"), "bad fixture"

    merge_shipped_pools(user, shipped)

    claude = named(user["app_sets"], "Claude")
    assert claude.get("agent") == "claude", (
        "the `agent` switch did not reach the owner's file — the Claude set "
        "can then only match by TITLE, and his window title never says "
        f"'claude': {sorted(claude)}")


def test_a_field_nobody_has_invented_yet_arrives():
    """THE RULE, not the field. A gate that named `agent` would have to be
    rewritten for every future field — and the one it was not rewritten for
    would ship broken, which is the whole history here."""
    from gui.controls_data import merge_shipped_pools
    shipped = shipped_actions()
    named(shipped["app_sets"], "Claude")["future_switch_2027"] = {"deep": [1, 2]}
    named(shipped["categories"], "Mouse")["future_flag"] = True
    user = copy(HIS_FILE)

    merge_shipped_pools(user, shipped)

    assert named(user["app_sets"], "Claude").get("future_switch_2027") == {"deep": [1, 2]}, (
        "a field invented after this merge was written did not reach the user "
        "file — the ownership rule has degraded back into a hardcoded list")
    assert named(user["categories"], "Mouse").get("future_flag") is True, (
        "the same, for a built-in category")


def test_a_new_top_level_key_arrives():
    """`wheel_order` is the live case (build round R5): a top-level key added
    by a later version, absent from every file seeded before it. Proven for an
    invented top-level key too, for the same reason as above."""
    from gui.controls_data import merge_shipped_pools
    shipped = shipped_actions()
    assert "wheel_order" in shipped, "the shipped file lost its wheel_order"
    shipped["future_top_key"] = ["a", "b"]
    user = copy(HIS_FILE)
    assert "wheel_order" not in user, "bad fixture"

    merge_shipped_pools(user, shipped)

    assert user.get("wheel_order") == shipped["wheel_order"], (
        "the owner's file never received `wheel_order`, so his wheel "
        f"arrangement would silently do nothing: {user.get('wheel_order')}")
    assert user.get("future_top_key") == ["a", "b"], (
        "a top-level key invented later did not arrive")


def test_everything_he_owns_survives_the_migration():
    """The other half of the promise. A migration that delivered fields by
    flattening his file would be a worse bug than the one it fixes."""
    from gui.controls_data import merge_shipped_pools
    shipped = shipped_actions()
    user = copy(HIS_FILE)
    user["wheel_order"] = ["Settings", "Mouse"]          # his own arrangement
    mouse = named(user["categories"], "Mouse")
    mouse["order_land"] = ["scroll", "click", "right", "middle"]
    mouse["order_port"] = ["click", "right", "middle", "scroll"]

    merge_shipped_pools(user, shipped)

    mouse = named(user["categories"], "Mouse")
    assert user["wheel_order"] == ["Settings", "Mouse"], (
        f"his wheel order was overwritten by the shipped default: {user['wheel_order']}")
    assert mouse.get("active") == ["click", "right", "middle", "scroll"], (
        f"his D-pad picks were lost: {mouse.get('active')}")
    assert mouse.get("order_land") == ["scroll", "click", "right", "middle"], (
        "his landscape arrangement was lost")
    assert mouse.get("order_port") == ["click", "right", "middle", "scroll"], (
        "his portrait arrangement was lost")
    assert named(user["categories"], "Cursor").get("enabled") is False, (
        "his `enabled` tick was overwritten by the shipped default")
    assert user["custom_sets"] == HIS_FILE["custom_sets"], (
        f"his own sets were touched: {user['custom_sets']}")
    assert user["left"] == 0 and user["right"] == 1, "his D-pad groups moved"
    click = next(b for b in mouse["buttons"] if b.get("action") == "click")
    assert click.get("label") == "Left", (
        f"his button rename was lost by the pool refresh: {click}")


def test_a_field_we_retired_stops_lying():
    """The mirror image, and the same disease: a set key we STOPPED shipping
    has to leave his file too, or the phone keeps reading an answer the PC no
    longer gives. `app_sets` carried exactly such a key — the manual tick list
    (`Layout.app_sets`) was removed on 2026-08-07 because it outranked live
    detection forever."""
    from gui.controls_data import merge_shipped_pools
    shipped = shipped_actions()
    user = copy(HIS_FILE)
    named(user["app_sets"], "Claude")["retired_switch"] = "stale"
    named(user["categories"], "Mouse")["retired_flag"] = True

    merge_shipped_pools(user, shipped)

    assert "retired_switch" not in named(user["app_sets"], "Claude"), (
        "a field the shipped file no longer has stayed in the user file")
    assert "retired_flag" not in named(user["categories"], "Mouse"), (
        "the same, for a built-in category")


def test_the_nine_option_model_panel_becomes_the_official_five():
    """Tasks 190/191 (2026-08-10): the phone's Model panel used to offer NINE
    options nobody official ever offered (opus, sonnet, haiku, fable, best,
    opusplan, opus[1m], sonnet[1m], default — built from this project's own
    transcript vocabulary, never checked against the extension's own menu),
    and Thinking sent a bare `/effort` that only raised Claude's own menu and
    stopped. A static read of the extension's own binary settled both: the
    official picker is exactly five entries (Default / Opus 1M / Fable /
    Sonnet / Haiku, in that order) and `/effort <literal>` commits directly
    for low/medium/high/xhigh/max, so Thinking gets the same choosing panel
    Model already had. `buttons` is entirely OURS (`_merge_set` never
    consults OWNER_SET_KEYS for it), so this must reach his file exactly like
    `agent` finally did — proven here on his file's OLD nine/zero shape, not
    on a freshly-derived copy of the shipped file."""
    from gui.controls_data import merge_shipped_pools
    shipped = shipped_actions()
    user = copy(HIS_FILE)
    claude = named(user["app_sets"], "Claude")
    claude["buttons"] = [
        {"label": "Usage", "icon": "usage", "text": "/usage", "enter": True},
        {"label": "Model", "icon": "model", "text": "/model", "enter": True,
         "options": [
             {"label": "opus", "value": "claude-opus-5"},
             {"label": "sonnet", "value": "claude-sonnet-5"},
             {"label": "haiku", "value": "claude-haiku-4-5"},
             {"label": "fable", "value": "claude-fable-5"},
             {"label": "best — Fable where available, else Opus", "value": "best"},
             {"label": "opusplan — Opus plans, Sonnet runs", "value": "opusplan"},
             {"label": "opus[1m] — Opus, 1M context", "value": "claude-opus-5[1m]"},
             {"label": "sonnet[1m] — Sonnet, 1M context", "value": "claude-sonnet-5[1m]"},
             {"label": "default — your account's own", "value": "default"},
         ]},
        {"label": "Thinking", "icon": "thinking", "text": "/effort", "enter": True},
    ]

    merge_shipped_pools(user, shipped)

    claude = named(user["app_sets"], "Claude")
    model = next(b for b in claude["buttons"] if b["label"] == "Model")
    thinking = next(b for b in claude["buttons"] if b["label"] == "Thinking")

    assert model["options"] == [
        {"label": "Default (recommended)", "value": "default"},
        {"label": "Opus (1M context)", "value": "opus[1m]"},
        {"label": "Fable", "value": "fable"},
        {"label": "Sonnet", "value": "sonnet"},
        {"label": "Haiku", "value": "haiku"},
    ], (f"the Model panel did not become the official five, in the official "
        f"order: {model.get('options')}")
    assert thinking.get("options") == [
        {"label": "Low", "value": "low"},
        {"label": "Medium", "value": "medium"},
        {"label": "High", "value": "high"},
        {"label": "xHigh", "value": "xhigh"},
        {"label": "Max", "value": "max"},
    ], (f"Thinking did not gain a committing options panel like Model's: "
        f"{thinking.get('options')}")


def test_a_set_he_has_never_had_arrives_whole():
    """His file predates Chrome and Explorer entirely — a new SET must arrive,
    and the sets he does have must not be duplicated by it."""
    from gui.controls_data import merge_shipped_pools
    shipped = shipped_actions()
    user = copy(HIS_FILE)

    merge_shipped_pools(user, shipped)

    got = [s["name"] for s in user["app_sets"]]
    for name in [s["name"] for s in shipped["app_sets"]]:
        assert got.count(name) == 1, f"{name} is missing or duplicated: {got}"
    assert named(user["app_sets"], "Chrome").get("buttons"), (
        "a newly shipped set arrived without its commands")


CHECKS = [
    ("his real file receives the agent switch",
     test_his_real_file_receives_the_agent_switch),
    ("a field nobody has invented yet arrives",
     test_a_field_nobody_has_invented_yet_arrives),
    ("a new top-level key arrives", test_a_new_top_level_key_arrives),
    ("everything he owns survives the migration",
     test_everything_he_owns_survives_the_migration),
    ("a field we retired stops lying", test_a_field_we_retired_stops_lying),
    ("the nine-option Model panel becomes the official five",
     test_the_nine_option_model_panel_becomes_the_official_five),
    ("a set he has never had arrives whole",
     test_a_set_he_has_never_had_arrives_whole),
]


def main() -> int:
    failed = []
    print("\n=== ACTIONS MIGRATION GATE ===")
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed.append(f"{name}: {e}")
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nACTIONS MIGRATION GATE FAILED — {len(failed)} check(s).",
              file=sys.stderr)
        return 1
    print("\nACTIONS MIGRATION GATE PASSED — a new version's fields reach the "
          "owner's own file, and his choices survive them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
