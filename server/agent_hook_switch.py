"""The desktop switch that registers Claude Code's hooks on THIS PC.

Split out of `notify.py` on 2026-08-18 (THE STRUCTURE LAW). The notification
feature is useless until something tells us an agent finished, and on a
stranger's machine nobody types `agent_hook.py --install` — so the Settings
window carries a checkbox and these functions are what it operates. The GUI
owns the checkbox; this module owns everything that touches
`~/.claude/settings.json` and the deployed copies of the two hook scripts.

EVERY SENTENCE THIS SWITCH CAN PRINT IS NAMED HERE — a raw `OSError` repr
must never reach the owner's screen, which is exactly what happened once
(2026-08-07, a second independent grader).
"""

import logging
import pathlib
import shutil
import sys

from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT, USER_DIR

logger = logging.getLogger(__name__)

# ═══════════════════ THE SWITCH THAT TURNS IT ON (ROADMAP H2) ═══════════════
# The hook shipped working in v0.0.081 and then said nothing for a day on the
# owner's own PC, because it had never been registered — `agent_hook.py
# --install` is a command, and the rule is that an end user never types one.
# So the desktop window carries a switch, and these two functions are what it
# operates. They live here because this is the notification feature's module;
# the GUI only owns the checkbox.
#
# EVERY SENTENCE THIS SWITCH CAN PRINT IS NAMED HERE (round R2 grade,
# 2026-08-07, a SECOND independent grader). v0.0.251 already fixed the ONE
# path that used to leak — a missing bundled script — with the friendly text
# below; what it missed is that `set_agent_hook`'s own copy/install steps
# could still raise a BARE OSError (a locked target file, a full disk, a
# permissions error) straight through the GUI's `except OSError as e: ...
# str(e)`, which is exactly how a raw exception repr became the caption's
# text on the owner's own screen. So every risky step below is inside ONE
# try/except that turns anything unexpected into HOOK_CHANGE_FAILED_TEXT —
# `_hook_module()` is the only thing still allowed to raise past this
# function, and only with a message already written for a human.
MISSING_SCRIPT_TEXT = ("This copy of Vibe Coder is missing its notifier "
                       "script. Reinstalling the app from the latest release "
                       "puts it back.")
UNLOADABLE_SCRIPT_TEXT = "The notifier script could not be loaded on this PC."
NO_PYTHON_TEXT = ("This PC has no Python on PATH, and Claude Code's hooks "
                  "need one to run the notifier. Install Python and switch "
                  "this on again.")
HOOK_CHANGE_FAILED_TEXT = ("Vibe Coder could not change the notifier hook on "
                           "this PC — the log has the exact reason.")


def _hook_module():
    """`setup/agent_hook.py` imported by path — it is deliberately outside the
    server package (it must run standalone under any interpreter)."""
    import importlib.util
    path = PROJECT_ROOT / "setup" / "agent_hook.py"
    if not path.exists():                      # frozen: bundled beside the exe
        path = BUNDLE_DIR / "setup" / "agent_hook.py"
    if not path.exists():
        # v0.0.085 shipped without this file in the bundle, and the switch
        # answered the owner with a raw "[Errno 2] No such file or directory:
        # …\\_internal\\setup\\agent_hook.py". A path is not an explanation,
        # and it is not something HE can act on — the app is what is broken,
        # so the app says so in his words. (The build now refuses to package
        # without it: setup/build.py's payload gate.)
        logger.error("agent hook script missing from this build (%s)", path)
        raise OSError(MISSING_SCRIPT_TEXT)
    spec = importlib.util.spec_from_file_location("agent_hook", path)
    if spec is None or spec.loader is None:
        raise OSError(UNLOADABLE_SCRIPT_TEXT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ledger_hook_source() -> pathlib.Path:
    """`setup/ledger_hook.py` beside `agent_hook.py` — the session-ledger
    Stop/UserPromptSubmit hook (T111). Never imported (it needs nothing from
    this module), only copied — same reasoning as `_hook_module`'s own path
    fallback: a dev checkout has the repo file, a frozen build has it bundled
    beside the exe."""
    path = PROJECT_ROOT / "setup" / "ledger_hook.py"
    if not path.exists():
        path = BUNDLE_DIR / "setup" / "ledger_hook.py"
    return path


def agent_hook_installed() -> bool:
    try:
        return bool(_hook_module().is_installed())
    except OSError as e:  # noqa: BLE001 — a missing script is "not installed"
        logger.warning("agent hook state unreadable: %s", e)
        return False


def refresh_agent_hook() -> None:
    """Bring the installed copy of the hook up to date with the bundled one.

    The copy in USER_DIR is written only by `set_agent_hook(on=True)` — a
    toggle. An app update ships a newer script inside the bundle, but nothing
    re-toggled the switch, so the owner's machine kept running the OLD hook
    forever while the repo said fixed (found closing task 198). Called once at
    `register()`: when the hook is installed and the deployed bytes differ
    from the bundled ones, the deployed file is rewritten in place. Purely
    frozen-path: a dev checkout registers the repo file directly and has no
    second copy to age.
    """
    # THE REGISTRATION is healed first, frozen or not (owner report 2026-08-15,
    # top priority): a settings file that carries our `Stop` hook and lacks
    # our `Notification` hook was "installed" by every check this app made
    # and never announced a permission prompt to his phone. Re-register with
    # the SAME python and script the switch chose — the file heal below only
    # rewrites bytes, this rewrites the missing event lines.
    try:
        module = _hook_module()
        gap = module.missing_events() if module.is_installed() else ()
        if gap:
            pair = module.registered_command()
            if pair:
                ledger_script = (USER_DIR / "ledger_hook.py") if FROZEN else None
                module.install(script=pathlib.Path(pair[1]), python=pair[0],
                                ledger_script=ledger_script)
                logger.info("agent hook re-registered — %s hook(s) were missing",
                            ", ".join(gap))
    except OSError as e:
        logger.warning("agent hook registration heal failed: %s", e)
    if not FROZEN:
        return
    try:
        if not agent_hook_installed():
            return
        source = pathlib.Path(_hook_module().__file__)
        target = USER_DIR / "agent_hook.py"
        if not (target.exists() and target.read_bytes() == source.read_bytes()):
            USER_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            logger.info("agent hook refreshed to the bundled version (%s)", target)
        # The ledger hook rides beside it — same reasoning, same staleness
        # risk (T111): an update ships a newer ledger_hook.py and nothing
        # re-toggles the switch to pick it up otherwise.
        ledger_source = _ledger_hook_source()
        if ledger_source.exists():
            ledger_target = USER_DIR / "ledger_hook.py"
            if not (ledger_target.exists() and
                    ledger_target.read_bytes() == ledger_source.read_bytes()):
                USER_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ledger_source, ledger_target)
                logger.info("ledger hook refreshed to the bundled version (%s)",
                            ledger_target)
    except OSError as e:
        # A locked file or a permissions error must never stop the server —
        # the stale hook still works, it merely names agents the old way.
        logger.warning("agent hook refresh failed: %s", e)


def set_agent_hook(on: bool) -> tuple[bool, str]:
    """Register or remove the Claude Code Stop hook. Returns (ok, what to tell
    the user) — NEVER an exception's own text (see the block comment above).
    Two things the packaged app must handle and the dev checkout need not: the
    script lives inside the bundle and would vanish with the next update, so
    it is copied to the user directory; and there is no interpreter in the
    EXE, so a real python has to be found — if this PC has none, that is said
    plainly instead of leaving a switch that lies."""
    module = _hook_module()  # may raise OSError — always with a human message
    try:
        if not on:
            module.install(remove=True)
            return True, ""
        script = pathlib.Path(module.__file__)
        python = sys.executable
        ledger_script = None
        if FROZEN:
            target = USER_DIR / "agent_hook.py"
            USER_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(script, target)
            script = target
            ledger_source = _ledger_hook_source()
            if ledger_source.exists():
                ledger_target = USER_DIR / "ledger_hook.py"
                shutil.copyfile(ledger_source, ledger_target)
                ledger_script = ledger_target
            python = shutil.which("python") or shutil.which("py") or ""
            if not python:
                return False, NO_PYTHON_TEXT
        module.install(script=script, python=python, ledger_script=ledger_script)
    except OSError as e:
        # Anything from here down (a locked target file, a full disk, a
        # permissions error writing ~/.claude/settings.json inside
        # agent_hook.install()) is OUR problem to phrase, not the owner's to
        # decode — the raw text goes to the log and ONLY the log.
        logger.error("agent hook %s failed: %s", "on" if on else "off", e)
        return False, HOOK_CHANGE_FAILED_TEXT
    logger.info("agent hook installed (%s %s)", python, script)
    return True, ""
