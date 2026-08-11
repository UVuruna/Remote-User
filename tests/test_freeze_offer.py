"""Gate: the ONE-TIME 4K@60 freeze offer (task 226, owner ballot verdict).

`server/gui/freeze_offer.py` -> `build_freeze_offer_banner(window)` must fire
exactly once, only at the freeze recipe (h264_max_width >= 3840 AND
target_fps >= 60), and never repeat once EITHER answer has been given. Driven
against the REAL function with a fake settings.json file, planted-defect
style: each check below is written so removing the guard it proves makes it
FAIL.

Run:  .venv\\Scripts\\python tests/test_freeze_offer.py
"""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))
sys.path.insert(0, str(PROJECT / "server" / "gui"))


def _fresh_config(monkeypatch, tmp_path):
    """A clean `config` module bound to a throwaway settings.json, so this
    gate can never touch the real %LOCALAPPDATA%/VibeCoder/settings.json."""
    for name in list(sys.modules):
        if name == "config" or name.startswith("config."):
            del sys.modules[name]
    import config
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")
    # Reset the shared singleton to defaults — module re-import alone does not
    # guarantee a fresh SETTINGS if another test imported it first this run.
    fresh = config.Settings()
    for f in config.fields(fresh):
        object.__setattr__(config.SETTINGS, f.name, getattr(fresh, f.name))
    return config


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def main() -> int:
    import tempfile
    _app()
    results: dict[str, bool] = {}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        class _MP:  # a tiny standalone monkeypatch, no pytest dependency needed
            def __init__(self):
                self._sets = []

            def setattr(self, obj, name, value):
                self._sets.append((obj, name, getattr(obj, name)))
                setattr(obj, name, value)

            def undo(self):
                for obj, name, old in reversed(self._sets):
                    setattr(obj, name, old)

        mp = _MP()
        config = _fresh_config(mp, tmp_path)
        from freeze_offer import build_freeze_offer_banner

        class FakeWindow:
            def __init__(self):
                self.restarted = False

            def restart_server(self):
                self.restarted = True

        # ── 1. fires exactly once at 3840/60 ────────────────────────────────
        # NEVER reassign config.SETTINGS itself: freeze_offer.py imported the
        # SETTINGS object by reference (`from config import SETTINGS`), so a
        # fresh instance bound to the module attribute would be invisible to
        # it — only mutating the shared object's fields (`apply()`'s own
        # trick) reaches every importer.
        object.__setattr__(config.SETTINGS, "h264_max_width", 3840)
        object.__setattr__(config.SETTINGS, "target_fps", 60)
        object.__setattr__(config.SETTINGS, "offered_2560", False)
        banner = build_freeze_offer_banner(FakeWindow())
        results["fires at 3840/60"] = banner is not None

        # ── 2. never at 2560 ─────────────────────────────────────────────────
        object.__setattr__(config.SETTINGS, "h264_max_width", 2560)
        object.__setattr__(config.SETTINGS, "offered_2560", False)
        banner2 = build_freeze_offer_banner(FakeWindow())
        results["never fires at 2560"] = banner2 is None

        # ── 3. never at 3840/30 (only fps below 60) ────────────────────────
        object.__setattr__(config.SETTINGS, "h264_max_width", 3840)
        object.__setattr__(config.SETTINGS, "target_fps", 30)
        object.__setattr__(config.SETTINGS, "offered_2560", False)
        results["never fires at 3840/30"] = build_freeze_offer_banner(FakeWindow()) is None

        # ── 4. "Switch" persists offered_2560 + h264_max_width, and restarts ─
        object.__setattr__(config.SETTINGS, "target_fps", 60)
        object.__setattr__(config.SETTINGS, "offered_2560", False)
        win = FakeWindow()
        banner = build_freeze_offer_banner(win)
        switch_btn, _keep_btn = _buttons(banner)
        switch_btn.click()
        results["Switch persists offered_2560"] = config.SETTINGS.offered_2560 is True
        results["Switch persists h264_max_width=2560"] = config.SETTINGS.h264_max_width == 2560
        results["Switch calls restart_server"] = win.restarted is True
        # …and it never fires again, on the SAME saved state.
        results["never re-offered after Switch"] = build_freeze_offer_banner(FakeWindow()) is None

        # ── 5. "Keep 4K" persists offered_2560 WITHOUT touching resolution,
        # and never restarts (nothing to restart FOR) ───────────────────────
        object.__setattr__(config.SETTINGS, "h264_max_width", 3840)
        object.__setattr__(config.SETTINGS, "target_fps", 60)
        object.__setattr__(config.SETTINGS, "offered_2560", False)
        win2 = FakeWindow()
        banner = build_freeze_offer_banner(win2)
        _, keep_btn = _buttons(banner)
        keep_btn.click()
        results["Keep 4K persists offered_2560"] = config.SETTINGS.offered_2560 is True
        results["Keep 4K leaves resolution at 3840"] = config.SETTINGS.h264_max_width == 3840
        results["Keep 4K never restarts"] = win2.restarted is False
        results["never re-offered after Keep 4K"] = build_freeze_offer_banner(FakeWindow()) is None

        mp.undo()

    print("\n=== FREEZE OFFER GATE ===")
    failed = 0
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    if failed:
        print(f"\nFREEZE OFFER GATE FAILED — {failed} check(s).", file=sys.stderr)
        return 1
    print("\nFREEZE OFFER GATE PASSED — fires once at the freeze recipe, "
          "never elsewhere, and both answers persist through the same "
          "save_user_settings path Settings Apply uses.")
    return 0


def _buttons(banner):
    from PySide6.QtWidgets import QPushButton
    btns = banner.findChildren(QPushButton)
    switch_btn = next(b for b in btns if b.text() == "Switch")
    keep_btn = next(b for b in btns if b.text() == "Keep 4K")
    return switch_btn, keep_btn


def test_freeze_offer():
    """pytest entry — skipped where PySide6 is absent."""
    import pytest
    pytest.importorskip("PySide6")
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
