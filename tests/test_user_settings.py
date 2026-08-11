"""THE USER'S settings.json IS HIS, AND A KEY WE RETIRED IS OURS TO REMOVE.

Why this gate exists (owner evidence, 2026-08-08). His server.log printed, on
every single start:

    WARNING config: settings.json: 'hand' is not a user-adjustable key — ignored

thirteen times in one day. `hand` was the left/right-hand offset system, which
the code stopped using on 2026-08-02 and lost the last of on 2026-08-07. He
never typed that key — WE wrote it. So the app was scolding him, forever, for a
setting of ours that we removed, in the one place every bug in this project has
been diagnosed from. A log that cries wolf on every line teaches its reader to
stop opening it.

THE CLASS, and it is already in CLAUDE.md under actions.json: we change ours,
his copy keeps the dead field, because nothing ever rewrites a file he does not
open. The rule adopted there — OURS is deleted if we retired it — is what this
gate holds for settings.json.

AND IT STARTS FROM HIS FILE, NOT FROM OURS. The actions.json failure ran four
releases green because every guard built its "user file" as a copy of the
shipped one, so it already had the new shape before the migration ran. The
fixture below is the LITERAL text of %LOCALAPPDATA%/VibeCoder/settings.json as
it stood on his machine on 2026-08-08, dead key and all.
"""

import json
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import config  # noqa: E402

# His own file, verbatim. Do not "tidy" it — the point is that it is his.
HIS_FILE = """{
  "monitor_index": 0,
  "h264_max_width": 3840,
  "h264_bitrate": "12M",
  "target_fps": 30,
  "hand": "right",
  "ui_theme": "dark"
}"""


class _Captured(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)

    def at(self, level: int) -> str:
        return " | ".join(r.getMessage() for r in self.records
                          if r.levelno == level)


def _load(text: str) -> tuple[Path, _Captured]:
    """Point config at a throwaway settings file holding `text`, load it, and
    return the path plus everything that was logged."""
    path = Path(tempfile.mkdtemp(prefix="ru_settings_gate_")) / "settings.json"
    path.write_text(text, encoding="utf-8")
    config.SETTINGS_PATH = path
    cap = _Captured()
    logger = logging.getLogger("config")
    logger.addHandler(cap)
    try:
        config.load_user_settings()
    finally:
        logger.removeHandler(cap)
    return path, cap


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def test_a_retired_key_never_scolds_him():
    """The whole report: no WARNING for a key WE retired."""
    _, cap = _load(HIS_FILE)
    warned = cap.at(logging.WARNING)
    assert "hand" not in warned, (
        f"his own file still produces a warning about our dead key: {warned!r}")


def test_the_file_heals_itself_without_him_opening_settings():
    """He may never open the Settings window again. If the key only went on
    the next SAVE, the line would print at every start until he did."""
    path, _ = _load(HIS_FILE)
    healed = json.loads(path.read_text(encoding="utf-8"))
    assert "hand" not in healed, (
        f"the dead key survived on disk: {sorted(healed)}")


def test_nothing_of_his_is_lost_while_healing():
    """Rewriting his file is the dangerous part of this fix — every real
    setting must come back byte-identical."""
    path, _ = _load(HIS_FILE)
    before = json.loads(HIS_FILE)
    after = json.loads(path.read_text(encoding="utf-8"))
    for key, value in before.items():
        if key == "hand":
            continue
        assert after.get(key) == value, (
            f"{key} changed while dropping a retired key: "
            f"{value!r} -> {after.get(key)!r}")


def test_a_key_nobody_ever_shipped_still_warns():
    """Silence here would be the opposite mistake: a typo of HIS is a setting
    he believes is in effect, and he must be told it is not."""
    _, cap = _load('{"monitor_index": 0, "targt_fps": 30}')
    assert "targt_fps" in cap.at(logging.WARNING), (
        "a key the owner mistyped was dropped in silence")


def test_the_legacy_theme_migration_still_runs():
    """The retired-key drop runs beside `_migrate_legacy_ui`; neither may eat
    the other. A pre-2026-08-08 four-value theme is DATA to translate."""
    path, _ = _load('{"phone_theme": "colored-light", "hand": "left"}')
    healed = json.loads(path.read_text(encoding="utf-8"))
    assert healed.get("phone_theme") == "light" and healed.get("phone_colored") is True, (
        f"the legacy theme stopped migrating once a retired key sat beside it: {healed}")
    assert "hand" not in healed


def test_saving_does_not_write_the_dead_key_back():
    """`save_user_settings` merges over whatever is on disk. Without the same
    drop there, one save would resurrect a key the load had just removed."""
    path = Path(tempfile.mkdtemp(prefix="ru_settings_gate_")) / "settings.json"
    path.write_text(HIS_FILE, encoding="utf-8")
    config.SETTINGS_PATH = path
    config.save_user_settings({"target_fps": 15})
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "hand" not in saved, f"a save brought the dead key back: {sorted(saved)}"
    assert saved["target_fps"] == 15


def test_every_retired_key_is_really_gone_from_the_code():
    """A name may only sit in RETIRED_KEYS once the feature behind it is gone.
    If it were still adjustable, this would silently delete a live setting."""
    still_live = config.RETIRED_KEYS & config.USER_ADJUSTABLE
    assert not still_live, (
        f"retired but still user-adjustable — the drop would delete a LIVE "
        f"setting of his: {sorted(still_live)}")


CHECKS = [
    ("a retired key of OURS never scolds him", test_a_retired_key_never_scolds_him),
    ("his file heals itself, without him opening Settings",
     test_the_file_heals_itself_without_him_opening_settings),
    ("nothing of his is lost while healing", test_nothing_of_his_is_lost_while_healing),
    ("a key HE mistyped is still reported", test_a_key_nobody_ever_shipped_still_warns),
    ("the legacy theme migration still runs beside it",
     test_the_legacy_theme_migration_still_runs),
    ("a save never writes the dead key back",
     test_saving_does_not_write_the_dead_key_back),
    ("nothing retired is still adjustable",
     test_every_retired_key_is_really_gone_from_the_code),
]


def main() -> int:
    failed = []
    print("\n=== USER SETTINGS GATE ===")
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed.append(f"{name}: {e}")
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nUSER SETTINGS GATE FAILED — {len(failed)} check(s).",
              file=sys.stderr)
        return 1
    print("\nUSER SETTINGS GATE PASSED — a setting we retired leaves his file "
          "quietly, and a setting he mistyped is still reported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
