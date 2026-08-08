# Config

**Script:** [Config (script)](../config.py) ·
**Flow:** [diagram](../__flow/config.md)

## Purpose
Single source of truth for every tunable value in the server (root Rule #4 — no hardcoded values elsewhere): network binding, streaming/H.264 parameters, injection self-check thresholds, pairing, remote access, logging, and update-check settings.

**Two layers, one instance.** Code defaults (the `Settings` dataclass) plus a user settings JSON (`settings.json`, written only by the desktop GUI) validated against a `USER_ADJUSTABLE` allowlist — unknown keys or bad values are logged and skipped, never fatal. The module-level `SETTINGS` is the ONLY instance; runtime changes go through `apply()` (controlled mutation of the shared frozen dataclass via `object.__setattr__`), so every module that imported `SETTINGS` sees updates without rebinding.

**Paths follow the run mode.** Dev checkout: everything stays inside the project (`logs/`, `PAIRING_QR.png` at the root, `actions.json`, ffmpeg from PATH). Installed EXE (`sys.frozen`): user data (settings, token, logs, QR, an owner-edited `actions.json` copy) lives in `%LOCALAPPDATA%\RemoteUser` (Program Files is not writable); bundled read-only data (`client/`, the default `actions.json`) comes from the PyInstaller bundle dir (`sys._MEIPASS`), and the installer places `ffmpeg/` next to the exe.

`app_version()` reads the running version from the bundled `setup/app_info.json` — `"dev"` in an unversioned checkout. It is the single source the GUI footer, the update check, and the `config` WebSocket message all read from.

**Round R2 (owner 2026-08-07) added five user-adjustable keys**, all of them owned by the new [Settings window](../gui/__about/settings_window.md): `notify_speak` / `notify_voice` / `notify_rate` (how the phone SAYS a notice — they ride in every `notify` frame), `foreground_lock` (Windows' own foreground rule, re-applied at every start), and `update_check`, which had lived here as a default with no UI at all. Two non-adjustable companions came with them: `foreground_lock_timeout_ms` + `foreground_lock_ledger_path` (see [Foreground Lock](foreground_lock.md)) and `autostart_task`, the Task Scheduler task name shared with the installer (see [Autostart](autostart.md)).

**The Updates section gained five non-adjustable keys the same day** (owner report 2026-08-07 — installing an update killed the session he was installing FROM): `update_record_path`, `update_script_path`, `update_log_path`, `update_wait_exit_s`, `update_wait_up_s`. All three paths sit in `USER_DIR` and never in the install folder, for one reason worth stating here — the installer REPLACES the install folder, so a handover cannot keep its own instructions inside the thing it is driving. See [Update Handover](update_handover.md).

See the [flow doc](../__flow/config.md) for the full section/key tree.

## Connections

### Uses
- Nothing (leaf module)

### Used by
- Every other file in this folder — [Bootstrap](bootstrap.md), [Server Core](server_core.md), [Screen Capture](capture.md), [H.264 Streamer](h264_streamer.md), [Encoders](encoders.md), [Input Injector](input_injector.md), [Web Layer](web.md), [Pairing](pairing.md), [Updates](updates.md), [Update Handover](update_handover.md), [Autostart](autostart.md), [Foreground Lock](foreground_lock.md) — plus `gui/main_window.py` and `gui/settings_window.py` (see [GUI (subfolder)](../gui/___gui.md))

## Classes

### Settings
Frozen dataclass — the module-level `SETTINGS` instance is the only one. See the section tree in the flow doc.

## Functions
- `app_version()`: running version from `setup/app_info.json`, `"dev"` when absent/unreadable
- `apply(**changes)`: controlled mutation of the shared `SETTINGS` (bypasses the frozen dataclass via `object.__setattr__`) — components that shape themselves from a value (port, monitor, encoder settings) need a restart to pick up a change
- `load_user_settings()`: applies `settings.json` overrides onto `SETTINGS` once at startup (after logging is configured); missing file = defaults, unreadable file logs and keeps defaults
- `save_user_settings(changes)`: the GUI's only write path — merges `changes` over the existing file (rejects keys outside `USER_ADJUSTABLE` with `ValueError`), writes it, and applies them to the running `SETTINGS`
- `_coerced(key, value)`: validates one override against the dataclass field's declared type (bool checked before int — bool is an int subclass); returns `None` (logged) for an unusable value
- `bitrate_bps(text)`: `"12M"` / `"1200k"` / `"900000"` → bits per second; unparsable text logs and falls back to 12 Mbps rather than killing a stream
- `bitrate_for_level(level)`: the phone's bitrate step resolved against the DESKTOP choice — `"high"` is `h264_bitrate` itself, `"mid"`/`"low"` are `h264_bitrate_mid_pct` / `_low_pct` percent of it. Percentages replaced the absolute `"5M"`/`"1200k"` on 2026-08-05: fixed numbers meant the desktop Bitrate combo applied only while the phone sat on "High", so the PC's choice was silently discarded the moment the phone picked Mid

## Settings trim (owner 2026-08-02); `hand` removed for good (owner 2026-08-07)
"Phone hand" left the Settings form on 2026-08-02 (the cursor-offset system it
fed was removed — the pointer sits under the finger). The `hand` field itself
is now GONE too: the owner ordered every remaining offset-era remnant
deleted, not kept as a compatibility shim ("sve ono što smo računali offset —
uopšte, to se neće koristiti više"), so `Settings.hand` no longer exists and
`config` no longer sends it. Frame rate gained a "10 fps — light" choice. An
old settings.json that still carries `"hand"` is now CLEANED (2026-08-08),
and the sentence that used to stand here — "unaffected … logs a warning and
skips the key, exactly like any other unrecognized key" — was the reason
nobody looked. It is not like any other unrecognized key: the owner never
typed `hand`, WE wrote it, and treating our own retired setting as his mistake
printed `settings.json: 'hand' is not a user-adjustable key — ignored` in his
log at every start, thirteen times in one day, months after the feature was
deleted. A log that scolds him for our leftovers is a log he stops reading,
and his log is where the evidence for every bug in this project has come from.

`RETIRED_KEYS` now names what we removed. Those keys are dropped SILENTLY and
the file is rewritten on the spot — not on the next save, because he may never
open the Settings window again. A key nobody ever shipped still warns: that
one is a typo of his, and it means a setting he believes is in effect is not.
Same rule, same reason as `OWNER_SET_KEYS` in the actions.json migration: OURS
is deleted if we retired it, HIS is kept. Gate: `tests/test_user_settings.py`,
fail-closed in `build.py` (0l/6) and in `run_guards.py`, and it starts from the
LITERAL text of his own file rather than one we compose.

## apk_version (owner bug 2026-08-02)
`apk_version()` reads the `RemoteUser.apk.version` sidecar (written by
`build_apk.py`, bundled by `build.py`) — the version of the APK this server
serves at /app.apk. The phone's update banner compares against THIS, not
`app_version()`: the APK does not change with desktop-only releases, and the
old comparison offered a phantom update forever.

## Build round R3 (2026-08-07) — themes; CORRECTED to three axes, THEN to one set palette (both 2026-08-08)

### APPEARANCE (build round R3, owner-approved 2026-08-07; owner correction 2026-08-08)

Four settings and one set-colour table (`SET_COLORS` — `SET_COLORS_DARK` and
`SET_COLORS_LIGHT` remain only as aliases pointing at it), all in
`USER_ADJUSTABLE` or their own section:

| Key | Values | What it is |
|---|---|---|
| `ui_theme` | `dark` / `light` | THIS PC's palette (`server/gui/theme.py`) |
| `phone_theme` | `dark` / `light` | the PHONE PAGE's |
| `phone_colored` | `True` / `False` | do the D-pad + wheel wear each set's colour |
| `phone_fill` | `transparent` / `full` | outlined buttons, or filled |

**THREE INDEPENDENT AXES, not a fourth theme name** (owner correction
2026-08-08, replacing the 2026-08-07 shape). His own words: *"teme postoje
samo dve, svetla i tamna … a ove komande … on može da bude obojen, neobojen,
i može da bude transparentan ili pun. dakle to je ukupno osam kombinacija."*
The 2026-08-07 shape folded colour into `phone_theme` itself (`"colored"` /
`"colored-light"`), producing the same eight looks by accident but claiming
the page has four themes when the owner's own model is two themes plus two
switches that belong to the CONTROLS — the D-pad groups and the radial
wheel — not the page. `phone_theme` is back to two values; `phone_colored` is
new and independent of both `phone_theme` and `phone_fill`.

**Backward compatibility — a saved choice is TRANSLATED, never reset.** A
`settings.json` written before this correction may still hold
`phone_theme: "colored"` / `"colored-light"`. `_migrate_legacy_ui()` runs on
every read (`load_user_settings`) and on `save_user_settings`'s own re-read
of the current file (so the file self-heals on its very next save), turning
`"colored"` into `{"phone_theme": "dark", "phone_colored": True}` and
`"colored-light"` into `{"phone_theme": "light", "phone_colored": True}` —
exactly the owner's original choice, spelled with two fields instead of one.
The SAME situation reaches the phone from a different direction — a device's
own cached `ui` (`prefGet("uiLook")`), written by an older page — and is
translated there too, in `client/theme.js` → `legacyTheme()`; see
[theme.md](../../client/__about/theme.md).

### The set palette — two tables became one (owner correction 2026-08-08)

He adopted the first, single palette with "tune later", split it into two the
next day, then collapsed the two back into one on the SAME day as the axis
correction above. His words on the final shape:

> "nema dve verzije za obojene setove. Oni ce uvijek imati ove jake upecatljive boje. ono sto se menja su ostali elementi light ili dark temi ali kontrole i setovi ce biti obojeni."

That reverses the two-table reasoning he had approved a day earlier — kept
here because the record of why the split happened, and why it was undone, is
the useful part:

> "kada je DARK tema treba da budu jako tamne nijanse, dakle mali lightness/brightness; a ovaj mod LIGHT treba da ima jako svetla slova, velikim, u boji, dakle ona klasična jaka. Sto saturacija ne treba ni u jednom modu." — lang-ok: owner's verbatim decision quote, kept for the record of why the two-table split happened and why it was undone

That sentence is a true statement about CONTRAST — on a dark page the colour
is the BODY of the button and a white label does the reading; on a light page
the colour is the INK — and the two-table split was not wrong about those two
jobs. It was wrong about what he actually wanted: a set's colour is its
IDENTITY, and an identity that changes when he flips the sun/moon switch is
not one. Mouse is the same teal on both pages; the theme moves everything
else around it, never the set colours. Losing the second table also removes a
class of bug this project keeps meeting on its own: two tables are two things
to keep in step, and the second one is always the one that goes stale.

`SET_COLORS` is now the one surviving table, tuned to the values that used to
be `SET_COLORS_LIGHT` — HSL lightness 26–54%, saturation capped at 72% (still
never full saturation, the third of his original three sentences, unaffected
by this correction): dark enough that a white label clears AA on it as a
FILL, vivid enough to still read as itself as an OUTLINE. That is what lets
one hex answer both jobs — the label reads against the COLOUR, never against
whatever page sits behind it. `SET_COLORS_DARK` and `SET_COLORS_LIGHT` still
exist as names in `server/config.py`, both pointing at the exact same dict,
so an import written before this correction cannot quietly resurrect a second
table; new code reads `SET_COLORS`. Hue AND lightness still separate the sets
that share the wheel, unchanged by the correction — the four blues and the
four warms are pulled apart on both axes, so an eye that cannot tell two hues
apart still has a second signal. The exact thirteen hexes are not restated
here or anywhere else — they live only in `server/config.py` → `SET_COLORS`,
see [theme.md](../../client/__about/theme.md).

Custom sets are deliberately NOT listed — the owner names his own sets, so the
phone hands each unnamed one the next colour of the palette that nothing
already wears (`client/theme.js`). One table, no second one to keep in step.

`set_colors(theme=None)` is still the ONLY place that decides "which palette
does a set wear" — but it now returns the same dict regardless of `theme`.
The parameter is kept and DELIBERATELY IGNORED: every caller (the phone
config, the desktop preview, the audit sweep) already passes one, and
dropping it would break every call site for a change that has nothing to do
with them — it stays as the record that the question was asked and answered
with "it does not matter". `ui_config()` is still the whole APPEARANCE half of
a `config` frame, `{theme, colored, fill, colors}`, with the palette already
resolved — so the wire shape for `colors` never changed and the phone still
receives one flat `{set: hex}` map, with no idea a second table ever existed.
Both live here rather than in `web.py` on purpose: the desktop owns this
decision, this file owns the desktop's settings, and the web layer's job is
only to put it on the wire.
