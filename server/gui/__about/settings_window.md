# Settings Window

**Script:** [Settings Window (script)](../settings_window.py) · **Flow:** [flow](../__flow/settings_window.md)

## Purpose
Everything the owner can change about this PC, in the third window beside Controls and Traffic (round R2, owner 2026-08-07).

It exists because the [Main Window](main_window.md) had become two things at once: the thing you open to PAIR a phone, and the thing you open to CONFIGURE a PC. Pairing is a first-day task with a QR the size of a postcard; configuring is a rare, dense one. Keeping both in one column meant the settings form sat under the QR forever and every new switch made the pairing window taller. The owner's answer to this round's one open question was "yes, move the stream controls in", so they moved — behaviour unchanged, same four combos, same Apply & restart, same save path.

## Connections

### Uses
- [Config](../../__about/config.md) — `SETTINGS` (every value shown) and `save_user_settings()` (the only writer)
- [Notify](../../__about/notify.md) — `agent_hook_installed()` / `set_agent_hook()` for the hook switch, and `voices()` for the Voice dropdown
- [Autostart](../../__about/autostart.md) — the real Task Scheduler logon task
- [Foreground Lock](../../__about/foreground_lock.md) — Windows' own "no program may steal the foreground" setting
- [Sizing](sizing.md) — `settle_minimum()`, THE SPACE & LEGIBILITY LAW's measured minimum
- [Theme](theme.md) — `card()` (the shared card factory) and the QSS the parent window carries
- [Screen Capture](../../__about/capture.md) — `BaseCapture.output_count()` for the Monitor combo

### Used by
- [Main Window](main_window.md) — the Settings icon button; modeless, built once, and handed `restart_server` so a stream Apply restarts the server on the main window's own worker thread

## The cards, in reading order
| Card | Rows | When it takes effect |
|------|------|----------------------|
| **STREAM** | Monitor · Resolution · Bitrate · Frame rate, then **Apply & restart** | on Apply — these shape the encoder, so the server restarts, exactly as before the move |
| **NOTIFICATIONS** | "Tell my phone when an agent finishes" (the ROADMAP H2 hook switch, moved from the main window) · "Say it out loud" · Voice · Speaking pace | at once |
| **FOCUS** | "Don't let applications steal focus" — default OFF | at once |
| **STARTUP** | "Check for new versions when the app starts" (`update_check`, which had existed in code with no UI at all) · "Start with Windows" | at once |
| **ADVANCED** (task 226, owner ballot verdict) | Port, then **Apply & restart** · "H.264 streaming" checkbox · JPEG quality (1-100, only spent while H.264 is off) · "Also open the QR as an image file" | Port on Apply (reshapes the listening socket); the other three at once |

A window where some switches act and others wait for a button is a window nobody can trust, so **everything except STREAM acts on the toggle** — the rule the notify switch already set on the main window.

**APPEARANCE is deliberately ABSENT, not stubbed.** Theme switching is round R3's work, and a card that promises a theme it cannot give is worse than no card. The seam is one line: build the card and insert it first in `_build_cards()`.

## Two things this window is careful about
- **A saved voice is never silently dropped.** The Voice list comes from the phone (`tts_info`), so opening Settings with no phone connected would offer only the default. `_populate_voices()` therefore re-offers a stored voice the phone did not report, marked "remembered, phone not connected", and nothing in that method writes to the settings file.
- **The label column is aligned across cards, ON SHOW.** Two `QFormLayout`s in two cards each size their own label column, so STREAM's combos started at one x and NOTIFICATIONS' at another. `_align_label_column()` gives every label the same measured minimum — and it runs in `showEvent`, because the theme's font only resolves when Qt polishes the widget (measuring in the constructor came out ~15 px short and both columns stepped apart again — the same lesson the [Traffic Window](traffic_window.md)'s span combo learned).

## Methods (beyond the builders)
- `_apply_settings()`: saves the four stream keys and calls the `restart` callable the main window handed in
- `_toggle_agent_hook(on)`: installs/removes the Claude Code `Stop` hook; a failure re-reads the real state and prints what happened, in the Error tone (see below)
- `_toggle_speak` / `_save_voice` / `_save_rate`: persist `notify_speak` / `notify_voice` / `notify_rate` — all three ride in every `notify` frame
- `_toggle_focus_lock(on)`: `foreground_lock.apply()`; a machine that refuses gets the tick put back and a sentence, in the Error tone
- `_toggle_update_check(on)` / `_toggle_autostart(on)`: `update_check`, and the real logon task; an autostart failure is shown in the Error tone
- `_refresh_live_state()`: on EVERY show — a phone may have connected since the last one (new voices), and an installer run may have changed the task
- `_computed_minimum()`: the law's measured floor — the label column plus the longest real combo entry (the voice names are measured, not guessed), and the height every wrapping caption needs at that width
- `_set_caption(label, text, error=False)`: the ONE place any of the three failure captions (notify / focus / startup) sets its text — never a bare `label.setText(...)` for a failure. Colours the label with the live `gui.theme.TOKENS["error"]` when `error=True`, clears back to the ordinary `#caption` grey otherwise; read live (never cached), the same pattern `gui/switch.py`'s `_token_color` uses for its own paint calls.

## A raw exception is never the caption (round R2's SECOND independent grader, 2026-08-07)

The grader's finding, verbatim in substance: under "Tell my phone when an agent finishes", the caption slot was printing `[Errno 2] No such file or directory: 'C:\Program Files\Remote User\_internal\setup\agent_hook.py'` — an `OSError` repr standing where a sentence belongs, in ordinary caption grey. The root cause was two-layered:

1. **The literal path had already been fixed** (`notify._hook_module()`, v0.0.251) — the specific "script missing from the bundle" case prints a human sentence. What survived was the GUI's `except OSError as e: ok, detail = False, str(e)` in `_toggle_agent_hook` — a catch-all that would turn **any** `OSError` reaching it into raw text, and `notify.set_agent_hook()` still had two unguarded steps (`shutil.copyfile`, `agent_hook.install()`'s settings-file write) that could raise one. Closed at the source: see [Notify](../../__about/notify.md) → "Every sentence this switch can print is named".
2. **No caption in this window had a distinct colour for FAILURE.** `_set_caption()` is the fix: every one of the three toggle handlers (`_toggle_agent_hook`, `_toggle_focus_lock`, `_toggle_autostart`) now routes its failure text through it with `error=True`, painting the theme's semantic Error hue (DESIGN.md) instead of the routine `#caption` grey — colour and words fixed together, because the grader named both.

**Placement, not just colour.** The notify caption sits BETWEEN two checkboxes ("Tell my phone…" above, "Say it out loud" below), so a full-width line under it read as if it might belong to either. `_caption(box, text, indent=CAPTION_INDENT_LEFT)` indents it to the checkbox's own text column (16px indicator + 9px spacing = 25px, `gui/theme.py`'s `QCheckBox` rule) — it now visually hangs off "Tell my phone…" the way a form's helper text hangs off its field, in EITHER state. `_computed_minimum()`'s wrapped-caption search accounts for the narrower wrap width this costs (`width - CAPTION_INDENT_LEFT`).

`tests/test_layout_audit_qt.py`'s `make_settings_window()` fixture used to poke `window.notify_caption.setText(NOTIFY_WORST)` directly, bypassing all of the above — the audit's own "fullest state" screenshot was never proof of the fix. It now calls `window._set_caption(window.notify_caption, NOTIFY_WORST, error=True)`, the exact method the real toggle handler uses, so the standing screenshot IS the evidence.

## Build round R3 (2026-08-07) — themes; CORRECTED to three axes, THEN to one set palette (both 2026-08-08)

### APPEARANCE — the card the R2 seam was left for

First in `_build_cards`, exactly where round R2 said it would go. It holds the
whole look of the product, both halves:

- **This PC** — the sun/moon pill ([Switch](switch.md)), riding the section
  heading's own row rather than taking a row of its own.
- **The phone** — THREE combos on ONE row (owner correction 2026-08-08):
  theme (Dark / Light), whether the controls are Coloured or Plain, and their
  fill (Outlined / Filled). Chosen here and only here: the owner's answer to
  this round's P4 was one source of truth and no menu on the phone, so the
  page applies `config.ui` and asks the device nothing.

  **THREE COMBOS, NOT TWO** (owner correction 2026-08-08, replacing the
  2026-08-07 shape that folded colour into a fourth `phone_theme` value:
  `"colored"` / `"colored-light"`). His own words: *"teme postoje samo dve,
  svetla i tamna … a ove komande … on može da bude obojen, neobojen, i može
  da bude transparentan ili pun."* A coloured look wears the SAME palette
  whichever theme combo is picked (`config.SET_COLORS` — a SECOND owner
  correction, the same day, kept below with a `lang-ok` note since it quotes
  him verbatim — a set's colour is its identity, and an identity that changes
  with the sun/moon switch is not one). `SET_COLORS_DARK` / `SET_COLORS_LIGHT`
  still exist in `server/config.py`, both names pointing at that one table,
  so an import written before this correction cannot quietly resurrect a
  second one. `PHONE_COLORED` is its own dropdown, independent of both
  `PHONE_THEMES` and `PHONE_FILLS` — it only switches the identity colours on
  or off, never which colours they are.

  > "nema dve verzije za obojene setove. Oni ce uvijek imati ove jake upecatljive boje." — lang-ok: owner's verbatim decision quote, 2026-08-08

All three phone combos save immediately (`save_user_settings`), like every
card in this window except STREAM. The caption says the honest thing — the
phone reads the change on its NEXT connection, which in practice means
locking and unlocking it, because `ui` rides the `config` frame.

**A pre-2026-08-08 `settings.json` is TRANSLATED, never reset** — see
[Config](../../__about/config.md) → `_migrate_legacy_ui`. This window always
reads `SETTINGS.phone_theme` / `SETTINGS.phone_colored` / `SETTINGS.phone_fill`
AFTER `load_user_settings()` has already run the migration, so the three
combos never have to know the old shape existed.

### The reflow the fifth card paid for

A fifth card put the measured minimum at **614x1048**, past the 1000 px height
this project declares in `.claude/layout-frame.json`. Raising that frame is the
owner's decision, and the ladder says reflow first anyway (rules/GUI.md — free
space -> reflow -> minimum -> scroll).

So **FOCUS and STARTUP now share one row**. They are the two shortest cards
AND the two that belong together — both answer "how does Remote User behave on
this PC" rather than "what does it send". The window has roughly 666 px of
unused WIDTH inside its own frame and 0 px of spare height, so spending one to
save the other is what the ladder's first two rungs are for. The three cards
above keep their full width: their captions are long, and halving them would
have bought height back with one hand while giving it away with the other.

Result: **718x921**, inside the frame, audited clean in both palettes.
`_computed_minimum` gained `phone_row` (two combos side by side can be wider
than the widest single one), `head_row` (heading + "This PC" + the pill) and
`paired_row` (the longer of FOCUS/STARTUP's checkboxes, twice over, plus both
cards' padding), and its `height_at` charges the paired row only the TALLER of
the two cards at HALF width.
