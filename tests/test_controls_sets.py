"""Guard: the owner's control sets are never silently rewritten.

Both failures this pins were REAL, reported by the owner within an hour of the
release that carried them (2026-08-05), and both were silent — the sets simply
came back wrong:

  A. "zašto je nestao VSCode kad si ubacio Claude" — `merge_shipped_pools`
     keyed app sets by PROCESS, and Claude Code runs inside VSCode, so both
     shipped sets carry `code`. The second one merged on top of the first and
     the owner's VSCode set was renamed out of existence.
  B. "zašto je WIN u MOUSE i nema RIGHT CLICK" — the editor wrote the command
     form back into `pool[detail_row]` of whatever set was selected NOW, while
     the form still held the PREVIOUS set's command: a set switch dropped
     Windows' `Win` into Mouse's row 1, on top of `right`. Harmless until
     renaming shipped sets was allowed, at which point the write stopped being
     gated to custom sets.

Both are data corruption of a file the owner has hand-tuned, which is why they
get a guard rather than a fix and a promise.

Run:  .venv\\Scripts\\python tests/test_controls_sets.py
"""

import json
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def shipped_actions() -> dict:
    return json.loads((PROJECT / "actions.json").read_text(encoding="utf-8"))


def copy(data: dict) -> dict:
    return json.loads(json.dumps(data))


def test_two_sets_of_one_process_both_survive_a_merge():
    """A. Claude and VSCode share `Code.exe` — merging must keep both."""
    from gui.controls_data import merge_shipped_pools
    shipped = shipped_actions()
    names = [s["name"] for s in shipped["app_sets"]]
    assert names.count("VSCode") == 1 and "Claude" in names, (
        "this guard assumes the shipped file still ships VSCode and Claude")
    # A user copy from BEFORE Claude existed — exactly the owner's situation.
    user = copy(shipped)
    user["app_sets"] = [s for s in user["app_sets"] if s["name"] != "Claude"]
    merge_shipped_pools(user, shipped)
    got = [s["name"] for s in user["app_sets"]]
    assert got.count("VSCode") == 1, f"VSCode was overwritten: {got}"
    assert got.count("Claude") == 1, f"Claude did not arrive: {got}"
    processes = {s["name"]: s["process"] for s in user["app_sets"]}
    assert processes["VSCode"] == processes["Claude"] == "code", processes


def test_a_merge_keeps_renames_but_drops_impossible_choices():
    """The owner may rename any button; a stale `active` must not survive."""
    from gui.controls_data import active_buttons, merge_shipped_pools
    shipped = shipped_actions()
    user = copy(shipped)
    mouse = next(s for s in user["categories"] if s["name"] == "Mouse")
    for b in mouse["buttons"]:
        if b.get("action") == "x1":
            b["label"] = "Back"          # his rename
    mouse["active"] = ["click", "gone-command", "middle", "scroll"]
    merge_shipped_pools(user, shipped)
    mouse = next(s for s in user["categories"] if s["name"] == "Mouse")
    renamed = [b for b in mouse["buttons"] if b.get("action") == "x1"]
    assert renamed and renamed[0].get("label") == "Back", "the rename was lost"
    assert "active" not in mouse, "an unhonourable `active` was kept"
    assert len(active_buttons(mouse)) == 4, "the D-pad lost buttons"


def test_a_corrupted_pool_repairs_itself():
    """B's aftermath: a user copy that already has Win sitting in Mouse."""
    from gui.controls_data import merge_shipped_pools
    shipped = shipped_actions()
    broken = copy(shipped)
    mouse = next(s for s in broken["categories"] if s["name"] == "Mouse")
    mouse["buttons"][1] = {"label": "Win", "icon": "grid", "chord": "win"}
    mouse["active"] = ["click", "win", "middle", "scroll"]
    merge_shipped_pools(broken, shipped)
    mouse = next(s for s in broken["categories"] if s["name"] == "Mouse")
    actions = [b.get("action") for b in mouse["buttons"]]
    assert actions[:4] == ["click", "right", "middle", "scroll"], actions
    assert "active" not in mouse


def test_merge_preserves_the_owners_wheel_order():
    """E. Build round R5 (2026-08-07, owner: "he chooses the ORDER of the
    sets around the phone's category wheel"). `merge_shipped_pools` must
    PRESERVE `wheel_order` across a shipped-pool merge — the whole point of
    that function is that a new version's defaults reach the user WITHOUT
    discarding his own choices, exactly like `active`/`order_*`/`enabled`
    already do. Proven here even though the shipped file's OWN default order
    differs from the owner's — the merge must not fall back to it."""
    from gui.controls_data import merge_shipped_pools
    shipped = shipped_actions()
    shipped["wheel_order"] = ["Settings", "Input", "Mouse"]  # a future default
    user = copy(shipped)
    user["wheel_order"] = ["Navigate", "Attach", "Mouse"]  # the owner's own pick
    merge_shipped_pools(user, shipped)
    assert user["wheel_order"] == ["Navigate", "Attach", "Mouse"], (
        "the owner's wheel order must survive a shipped-pool merge exactly "
        f"as he left it: {user['wheel_order']}")


def test_switching_sets_never_writes_into_the_other_pool():
    """B itself, through the real dialog: select a command in one set, switch
    to another, and nothing of the first may land in the second."""
    from PySide6.QtWidgets import QApplication
    from gui.controls_editor import ControlsEditor

    app = QApplication.instance() or QApplication([])
    editor = ControlsEditor()
    entries = editor._entries()
    index = {s.get("name"): i for i, (_, _, s) in enumerate(entries)}
    pools = {s.get("name"): json.dumps(s.get("buttons")) for _, _, s in entries}

    # Every pair that can reach the bug: a long pool selected deep, then a
    # shorter one — the row index survives the switch, the command must not.
    for source in ("Windows", "Navigate", "Cursor", "Edit"):
        if source not in index:
            continue
        editor.set_list.setCurrentRow(index[source])
        app.processEvents()
        for row in (1, 2, 3):
            if row < editor.table.rowCount():
                editor.table.setCurrentCell(row, 1)
                app.processEvents()
                for target in ("Mouse", "Input", "Attach", "Settings"):
                    if target not in index:
                        continue
                    editor.set_list.setCurrentRow(index[target])
                    app.processEvents()
                    editor.set_list.setCurrentRow(index[source])
                    app.processEvents()

    after = {s.get("name"): json.dumps(s.get("buttons"))
             for _, _, s in editor._entries()}
    changed = [name for name, pool in pools.items() if after.get(name) != pool]
    assert not changed, (
        "set switching rewrote these pools: " + ", ".join(changed)
        + " — one set's command must never land in another's row")


def test_typed_command_shows_as_typed_not_chord():
    """C. The independent grader's screenshot (2026-08-07): the pool table
    said "types · /usage" for the Claude set's Usage row while the detail
    panel below it — for the SAME selected row — asked to RECORD a keystroke
    for a command that has no shortcut at all. `CommandTable.fill` already
    read a `{"text": …}` command correctly; `CommandDetail.show_button` had
    no branch for it and fell into the chord `else`, showing an empty
    "Shortcut (chord)" field with a live Record button under a table cell
    that already said "types". One window, two contradicting stories about
    one button.

    Guards, in order: the panel must resolve to the TEXT kind, must show the
    real text (never an empty field), and the two value rows (Shortcut vs
    Text) must never both be visible at once — showing both would just move
    the contradiction from "wrong label" to "two live answers"."""
    from PySide6.QtWidgets import QApplication
    from gui.controls_editor import ControlsEditor
    from gui.controls_widgets import KIND_TEXT

    app = QApplication.instance() or QApplication([])
    editor = ControlsEditor()
    entries = editor._entries()
    claude = next((i for i, (_, _, s) in enumerate(entries)
                   if s.get("name") == "Claude"), None)
    assert claude is not None, "this guard assumes the shipped file still ships Claude"
    editor.set_list.setCurrentRow(editor._row_of(claude))
    app.processEvents()
    usage_row = next(r for r in range(editor.table.rowCount())
                      if editor.table.item(r, 1).text() == "Usage")
    editor.table.setCurrentCell(usage_row, 1)
    app.processEvents()

    detail = editor.detail
    assert detail.kind.currentData() == KIND_TEXT, (
        f"the Usage row shows as kind {detail.kind.currentData()!r}, "
        "not a typed command — the table and the detail panel disagree again")
    assert detail.text.text() == "/usage", (
        f"the Text field must carry the real command, got {detail.text.text()!r}")
    assert detail.enter_check.isChecked(), "Usage carries \"enter\": true in actions.json"
    assert detail.chord.isHidden(), (
        "the Shortcut field must not show for a typed command — a user who "
        "selects a typed command must never be told to record a keystroke")
    assert detail.record.isHidden(), "the Record button must not show either"
    assert not detail.text.isHidden(), "the Text field must show for a typed command"
    assert not detail.enter_check.isHidden(), "the Enter checkbox must show too"


def test_a_custom_typed_command_round_trips():
    """A typed command must be CREATABLE and EDITABLE in a custom set, not
    merely displayable (owner brief, 2026-08-07): add a command, switch its
    Does combo to "Types (paste text)", fill in the text, and confirm
    `dump()` writes back exactly the `paste_text` shape the phone/server
    expect (ACTIONS.md → Typed text; `server/web.py`'s `paste_text` handler)."""
    from PySide6.QtWidgets import QApplication
    from gui.controls_editor import ControlsEditor
    from gui.controls_widgets import KIND_TEXT

    app = QApplication.instance() or QApplication([])
    editor = ControlsEditor()
    entries = editor._entries()
    custom = next((i for i, (kind, _, _) in enumerate(entries)
                   if kind == "custom_sets"), None)
    if custom is None:
        editor._add_set()   # the shipped file ships no custom set to reuse
        custom = len(editor._entries()) - 1
    editor.set_list.setCurrentRow(editor._row_of(custom))
    app.processEvents()
    editor._add_command()
    app.processEvents()

    detail = editor.detail
    detail.kind.setCurrentIndex(detail.kind.findData(KIND_TEXT))
    detail._kind_changed()
    detail.text.setText("/model")
    detail.enter_check.setChecked(False)
    detail.label.setText("Model")
    dumped = detail.dump()
    assert dumped == {"label": "Model", "text": "/model", "enter": False}, dumped


CHECKS = [
    ("two sets of one process both survive a merge",
     test_two_sets_of_one_process_both_survive_a_merge),
    ("a merge keeps renames, drops impossible choices",
     test_a_merge_keeps_renames_but_drops_impossible_choices),
    ("a corrupted pool repairs itself", test_a_corrupted_pool_repairs_itself),
    ("merge preserves the owner's wheel order",
     test_merge_preserves_the_owners_wheel_order),
    ("switching sets never writes into another pool",
     test_switching_sets_never_writes_into_the_other_pool),
    ("a typed command shows as typed, not chord",
     test_typed_command_shows_as_typed_not_chord),
    ("a custom typed command round-trips",
     test_a_custom_typed_command_round_trips),
]


def main() -> int:
    failed = []
    print("\n=== CONTROL SETS GUARD ===")
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed.append(f"{name}: {e}")
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nCONTROL SETS GUARD FAILED — {len(failed)} check(s).", file=sys.stderr)
        return 1
    print("\nCONTROL SETS GUARD PASSED — the owner's sets come back as he left them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
