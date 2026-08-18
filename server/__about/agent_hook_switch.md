# Agent Hook Switch

**Script:** [Agent Hook Switch (script)](../agent_hook_switch.py)

## Purpose

The desktop switch that registers Claude Code's hooks on THIS PC - everything
that touches `~/.claude/settings.json` and the deployed copies of
`setup/agent_hook.py` / `setup/ledger_hook.py`. Split out of
[Notify](notify.md) on 2026-08-18 (THE STRUCTURE LAW): the notification feature
is useless until something tells us an agent finished, and on a stranger's
machine nobody types `agent_hook.py --install`.

The GUI owns the checkbox; this module owns the act, and every sentence the
switch can print is named HERE - a raw `OSError` repr must never reach the
owner's screen.

## Connections

### Uses
- `config` - `PROJECT_ROOT` / `BUNDLE_DIR` (dev checkout vs frozen bundle),
  `USER_DIR`, `FROZEN`

### Used by
- [Settings Window](../gui/__about/settings_window.md) - the checkbox calls
  `set_agent_hook(on)` and reads `agent_hook_installed()`
- [Notify](notify.md) - `refresh_agent_hook()` once, at `register()`

## Functions

- `_hook_module()`: `setup/agent_hook.py` imported by path (it must run
  standalone under any interpreter) - the only thing here allowed to raise
  past its caller, and only with a message already written for a human
- `_ledger_hook_source()`: `setup/ledger_hook.py` beside it, copied never
  imported
- `agent_hook_installed()`: state for the checkbox
- `refresh_agent_hook()`: heals the REGISTRATION (missing event lines) and then
  the deployed BYTES, so an app update cannot leave last version's hook running
- `set_agent_hook(on)` -> `(ok, what to tell the user)`

## The switch that turns it on (ROADMAP H2, owner 2026-08-06)

The feature shipped working in v0.0.081 and then stayed silent on the owner's
own PC for a day: `agent_hook.py --install` had never been run. The rule is
that an end user never types a command, so the desktop window carries a
checkbox and `agent_hook_installed()` / `set_agent_hook()` are what it
operates. They live here rather than in the GUI because this is the
notification feature's module — the window only owns the checkbox.

The switch shows the REAL state (it reads `~/.claude/settings.json` every
time) instead of remembering a setting of its own, so a hook removed by hand
is reflected the next time the window opens.

Two things the packaged app must handle and a dev checkout need not:

- **the script would vanish with the next update** — inside the bundle it is
  replaced wholesale, so turning the switch on copies it to the user directory
  and registers that permanent path;
- **there is no interpreter in the EXE** — `sys.executable` is the app itself,
  so a real `python` is looked up on PATH. A PC with none is TOLD so, plainly,
  in the caption under the switch. A switch that silently fails to arm is the
  same failure this whole task exists to end.

**And the script has to BE in the bundle** (owner screenshot 2026-08-06):
v0.0.085 shipped without it — `setup/agent_hook.py` was never in PyInstaller's
`--add-data` — so the installed app could not turn the switch on at all and
answered with `[Errno 2] No such file or directory: …\_internal\setup\
agent_hook.py`. Fixed at all three layers, because each failed on its own:
the file is bundled ([Build](../../setup/__about/build.md)), the build's
**payload gate** refuses to package without it, and `_hook_module()` no longer
hands a raw path to a user — a missing script is the APP being broken, so the
sentence says that, and the log keeps the path.

### Every sentence this switch can print is named, and NONE of them is `str(e)` (round R2's SECOND independent grader, 2026-08-07)

The fix above closed the ONE path that used to leak — `_hook_module()`'s own
missing-script check — but `set_agent_hook()` still had two UNGUARDED steps
downstream of it: `shutil.copyfile()` (copying the script to `USER_DIR` on a
frozen build) and `module.install(...)` (writing `~/.claude/settings.json`).
Either one raising a bare `OSError` — a locked file, a full disk, a
permissions error — flowed straight through to `gui/settings_window.py`'s
`except OSError as e: ... str(e)`, which is exactly how a raw exception's own
repr became the caption's text on the owner's screen: the SAME class of bug
`_hook_module()` had already been fixed for, one function down. The whole
body of `set_agent_hook()` (after `_hook_module()` itself, which is the only
thing still allowed to raise — always with a message written for a human) is
now inside one `try/except OSError`, and every sentence it can return is a
named constant instead of a call-site literal:

| Constant | Shown when |
|----------|-----------|
| `MISSING_SCRIPT_TEXT` | `_hook_module()` — the bundled script is genuinely absent |
| `UNLOADABLE_SCRIPT_TEXT` | `_hook_module()` — found, but `importlib` could not load it |
| `NO_PYTHON_TEXT` | frozen build, no `python`/`py` on PATH |
| `HOOK_CHANGE_FAILED_TEXT` | anything else raising `OSError` (copy, or the settings-file write inside `agent_hook.install()`) |

`gui/settings_window.py` also gives the caption the theme's semantic **Error**
colour when — and only when — it is showing one of these, instead of the
routine caption grey every other sentence in that window uses; the fixture in
`tests/test_layout_audit_qt.py` that used to hardcode the OLD raw exception
text as its "worst case" caption now imports `NO_PYTHON_TEXT` (the longest
sentence this module can produce today, 125 chars) so the audit can never
drift back to sizing the window for text the product no longer emits.
