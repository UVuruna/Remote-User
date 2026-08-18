# Settings Window

**Script:** [Settings Window (script)](../settings_window.py) · **Flow:** [flow](../__flow/settings_window.md)


## THE FIXED FLOOR IS GONE (owner decision 2026-08-18)

This window's `_computed_minimum` used to SEARCH: it walked widths from the
content's own floor up to a hand-picked **1280x1000** screen frame and took the
first width whose measured height fitted underneath — deliberately WIDENING the
window to make it shorter, so it would fit a screen size nobody had measured.

His ruling ends that everywhere: a window is judged on the DEVICE PROFILES it
is shot against (`rules/devices.json`), and **a window taller than a screen
scrolls**. The minimum is now the honest one — the narrowest width the
unwrappable content really needs, and the height the layout really takes at
that width. `FLOOR_WIDTH` / `FLOOR_HEIGHT`, `CAPTION_STEP` and the search that
used them are gone, and so is `.claude/layout-frame.json`.

The frame's own history is kept here rather than thrown away with the file it
lived in, because it records two real decisions (a raise and its reversal) that
still explain why the ControlsEditor is shaped the way it is:

> Desktop-only app, single column by design, and the height floor is set by the two densest windows rather than by the main one. Since build round R2 (2026-08-07) the main window carries only what pairing needs - a QR at scan size (216 px fixed, exempted on its own line), the three-step guided pairing text THE SPACE & LEGIBILITY LAW forbids truncating, two short button rows and the update offer - and its measured minimum is 404x703, comfortably inside 1280x720. What needs the taller floor is the ControlsEditor and the Settings window (644x874: four cards of switches whose guidance captions wrap rather than truncate). Both stay far under the 1280 WIDTH; only the height needs the room, and no element in either holds slack. Reflowing a settings form into two columns was considered and rejected: it would put unrelated cards side by side and leave the shorter column empty, which is the very pattern this law calls a bug. RAISED WIDTH 1280->1700 (2026-08-11, Round 40) then LOWERED BACK 1700->1280 (task 232): the ControlsEditor had grown into a genuine three-pane tool (sets list | command table | selected-command form, plus the R5 wheel-order/mode row) whose honest measured minimum was 1662x598 - the earlier note called stacking the panes 'burying the command table', but the actual width driver was never the three panes, it was the Arrangement box's two OrderLists (D-pad + Stack orientation ladders) sitting SIDE BY SIDE inside the narrow LEFT column (sets list + arrangement), each carrying its own right-aligned slot column and the widest button label in the set. Moving the Arrangement box into the RIGHT column - under the command pool and the selected-command form, still with its two OrderLists side by side - let it share the width the pool/detail form already needs instead of adding a second demand on top of the set list's narrower column; nothing shrank or wrapped. New declared minimum: 881x806 (server/gui/controls_editor.py). This is the debt task 232 closes; a real narrow-screen (sub-1280) reflow, if ever wanted, is still a separate task.


## Purpose
Everything the owner can change about this PC, in the third window beside Controls and Traffic (round R2, owner 2026-08-07).

It exists because the [Main Window](main_window.md) had become two things at once: the thing you open to PAIR a phone, and the thing you open to CONFIGURE a PC. Pairing is a first-day task with a QR the size of a postcard; configuring is a rare, dense one. Keeping both in one column meant the settings form sat under the QR forever and every new switch made the pairing window taller. The owner's answer to this round's one open question was "yes, move the stream controls in", so they moved — behaviour unchanged, same four combos, same Apply & restart, same save path.

## Connections

### Uses
- [Config](../../__about/config.md) — `SETTINGS` (every value shown) and `save_user_settings()` (the only writer)
- [Notify](../../__about/notify.md) — `agent_hook_installed()` / `set_agent_hook()` for the hook switch. `voices()` is NO LONGER read here: the Voice dropdown left this window on 2026-08-12 (below), and the module is now imported by name only
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
| **STREAM** | Monitor · **Quality** (four named steps) · a **Custom…** disclosure holding Resolution · Bitrate · Frame rate, then **Apply & restart** — the card itself lives in [Stream Card](stream_card.md) since 2026-08-12 (THE STRUCTURE LAW) | on Apply — these shape the encoder, so the server restarts, exactly as before the move |
| **NOTIFICATIONS** | "Tell my phone when an agent finishes" (the ROADMAP H2 hook switch, moved from the main window) · "Say it out loud" — and a caption saying where the voice itself is chosen | at once |
| **FOCUS** | "Don't let applications steal focus" — default OFF | at once |
| **STARTUP** | "Check for new versions when the app starts" (`update_check`, which had existed in code with no UI at all) · "Start with Windows" | at once |
| **ADVANCED** (task 226, owner ballot verdict) | Port, then **Apply & restart** · "H.264 streaming" checkbox · JPEG quality (1-100, only spent while H.264 is off) · "Also open the QR as an image file" | Port on Apply (reshapes the listening socket); the other three at once |

A window where some switches act and others wait for a button is a window nobody can trust, so **everything except STREAM acts on the toggle** — the rule the notify switch already set on the main window.

**APPEARANCE is deliberately ABSENT, not stubbed.** Theme switching is round R3's work, and a card that promises a theme it cannot give is worse than no card. The seam is one line: build the card and insert it first in `_build_cards()`.

## Two things this window is careful about
- **The voice is NOT chosen here** (owner decision 2026-08-12). A Voice dropdown and a Speaking pace dropdown stood in the NOTIFICATIONS card until he pointed out what they could not do: he uses a tablet AND a phone, their text-to-speech engines carry different voices, and one PC-side choice can only ever name a voice that exists on one of them — pick the tablet's and the phone falls back to its own engine default, silently, while this window still shows a name. So the two MASTER switches stayed (they are decisions about the job: whether the PC calls at all, and whether the call is spoken) and the device-specific choice went to the device, where it can also be HEARD before it is picked — `openNotifyVoicePanel()` in [client/notify.js](../../../client/__about/notify.md), reached from the phone's Settings wheel.

  Nothing was deleted underneath it: `notify_voice` / `notify_rate` are still in the settings file and still ride every `notify` frame, so a phone that has never made its own choice behaves exactly as it did before, and an older APK is unaffected. They simply have no dial on this window. The card says so in one caption rather than leaving a gap — a setting that moves without a forwarding note reads as a setting that was taken away.
- **The label column is aligned across cards, ON SHOW.** Two `QFormLayout`s in two cards each size their own label column, so STREAM's combos started at one x and NOTIFICATIONS' at another. `_align_label_column()` gives every label the same measured minimum — and it runs in `showEvent`, because the theme's font only resolves when Qt polishes the widget (measuring in the constructor came out ~15 px short and both columns stepped apart again — the same lesson the [Traffic Window](traffic_window.md)'s span combo learned).

## Methods (beyond the builders)
- `_apply_settings()`: saves the four stream keys and calls the `restart` callable the main window handed in
- `_toggle_agent_hook(on)`: installs/removes the Claude Code `Stop` hook; a failure re-reads the real state and prints what happened, in the Error tone (see below)
- `_toggle_speak`: persists `notify_speak`, which rides every `notify` frame. `_save_voice` / `_save_rate` are GONE with their rows (2026-08-12) — the keys they wrote are untouched and still sent
- `_toggle_focus_lock(on)`: `foreground_lock.apply()`; a machine that refuses gets the tick put back and a sentence, in the Error tone
- `_toggle_update_check(on)` / `_toggle_autostart(on)`: `update_check`, and the real logon task; an autostart failure is shown in the Error tone
- `_refresh_live_state()`: on EVERY show — the autostart task and the agent hook can both be changed from outside this window (an installer run, `agent_hook.py --install`). It no longer re-reads the phone's voices: nothing on this window draws them
- `_computed_minimum()`: the law's measured floor — the label column plus the longest real combo entry, and the height every wrapping caption needs at that width. Since 2026-08-12 every string it measures is one this file owns; the voice names were the single input that came from another device, which is why they had to be measured rather than guessed
- `_resettle()`: the second-pass settle, and the point at which this window's geometry is FINAL — so it is also where [`clamp_to_screen`](sizing.md) runs. A settle only ever GROWS a window where Qt already placed it, and Qt placed it from its pre-show size, which is how his Settings window came up with its top edge off the screen (owner report 2026-08-12)
- `_set_caption(label, text, error=False)`: the ONE place any of the three failure captions (notify / focus / startup) sets its text — never a bare `label.setText(...)` for a failure. Colours the label with the live `gui.theme.TOKENS["error"]` when `error=True`, clears back to the ordinary `#caption` grey otherwise; read live (never cached), the same pattern `gui/switch.py`'s `_token_color` uses for its own paint calls.

## A raw exception is never the caption (round R2's SECOND independent grader, 2026-08-07)

The grader's finding, verbatim in substance: under "Tell my phone when an agent finishes", the caption slot was printing `[Errno 2] No such file or directory: 'C:\Program Files\Vibe Coder\_internal\setup\agent_hook.py'` — an `OSError` repr standing where a sentence belongs, in ordinary caption grey. The root cause was two-layered:

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
- **The phone** — **GONE FROM THIS WINDOW on 2026-08-12** (owner ballot:
  *"appearance is also per device, not global, so it belongs on the phone /
  tablet"*). Three combos stood here — theme, Coloured/Plain,
  Outlined/Filled — and they could only ever describe ONE handset while he
  uses a tablet and a phone. The choice now lives on the device
  ([Appearance Panel](../../../client/__about/appearance-panel.md)), stored
  through the SharedPreferences bridge.

  This is the SAME correction the Voice dropdown got earlier the same day, for
  the same reason, and it does NOT undo the 2026-08-08 three-axis model — the
  three axes are exactly the three rows the phone's card now offers.
  `phone_theme` / `phone_colored` / `phone_fill` survive in
  [Config](../../__about/config.md) as the DEFAULT a device wears until it
  chooses, still riding every `config` frame, so a handset he never touches
  looks exactly as it does today. A coloured look still wears the SAME palette
  under both themes (`config.SET_COLORS` — a set's colour is its identity, and
  an identity that changes with the sun/moon switch is not one).

  > "nema dve verzije za obojene setove. Oni ce uvijek imati ove jake upecatljive boje." — lang-ok: owner's verbatim decision quote, 2026-08-08

**WHAT IS LEFT IS NOT A HOLE.** The pill still rides the section heading's own
row where it always did, the form row that carried the trio is GONE rather
than emptied, and the caption below is the forwarding note — a setting that
moves without one reads as a setting that was taken away. An orphaned label
over an empty column is what a grader measures.

**A pre-2026-08-08 `settings.json` is still TRANSLATED, never reset** — see
[Config](../../__about/config.md) → `_migrate_legacy_ui`, and
`client/theme.js` → `legacyTheme` for the same translation on the device's own
cache. Neither path went anywhere; only the dial did.

### The reflow that makes this window FIT THE SCREEN (2026-08-12)

Round R3's fifth card put the minimum at **614x1048**, and the answer then was
to pair FOCUS and STARTUP on one row. That bought one rung and it was not
enough. By 2026-08-12 the minimum had reached **767x1226** and the guard named
the real defect:

    MIN 767x1226 does not fit the screen floor 1280x1000.

That is problem #4 on the owner's own list — *"desktop Settings escapes the
screen"* — and it is why round 46's `clamp_to_screen` could not answer it.
Clamping pulls a window that has been PUSHED off-screen back inside; it can do
nothing for a window that is TALLER than the screen. On a 1920x1080 display the
workspace is about 1040 px with the taskbar, so this window could not be shown
whole wherever it was put. The number was in the audit output the whole time,
and he was told twice that it was fixed.

**Ladder step 2, REFLOW** ([GUI Rules](../../../../../rules/GUI.md) — free space →
reflow → minimum → scroll). Step 1 was tried and dismissed on the numbers: card
padding is 36 px and the window margins 16/18, which together cannot pay a
fifth of a 226 px overshoot and would cost every card its breathing room. Step
3 is not available (the floor is what we must fit) and step 4 would put a
scrollbar in a window carrying ~500 px of unused WIDTH, which is an audit
failure on its own.

| Band | Cards | Why |
|---|---|---|
| full width | APPEARANCE | its caption is one line wide and four lines narrow — halving it buys height with one hand and gives it back with the other |
| full width | STREAM | it MUST be: the Exact row is three combos plus a label column, ~644 px that no half can give. Split it and the trio clips |
| left column | NOTIFICATIONS · FOCUS · STARTUP | what the app does while you work, and how it starts |
| right column | ADVANCED | alone, because it is nearly as tall as the other three together |

**Three and one is a MEASURED split, not a tidy one.** Any two-and-two
arrangement leaves one column ~120 px taller than the other, and the taller
column IS the window's height. FOCUS and STARTUP stopped sharing their old
half-of-a-half row in the same change; each is now simply a card in a column,
and both captions wrap at a real width for the first time.

New measured minimum: **959x996**.

### The minimum is MEASURED, not modelled

`_computed_minimum` used to model every heading, row, caption and card frame in
the window to predict its height. That model was already drifting — it read 875
where Qt needed 948 — and it could not see what actually binds: it believed
width kept buying height up to 1,175 px, where Qt stops improving at about 960.
It now asks the layout itself, `layout().totalHeightForWidth(w)`. Only the
WIDTH FLOOR is still computed by hand, because combo entries and checkbox
labels never reflow and no amount of height can pay for them: the form label
plus the longest combo entry, the Exact row's three combos, the APPEARANCE
heading with its pill, and the widest unwrappable thing in a switch card twice
over for the two columns.

The search also changed DIRECTION, and that fixed a typography defect the old
shape hid: it takes the **smallest width whose measured height fits the screen
floor**, instead of the widest width that minimises height. At 1,175 px the
guidance ran about 150 characters to the line; DESIGN.md calls 60–80 readable.

## The monitor list follows the real monitors (T113, 2026-08-17)

`_populate_monitors` asks `BaseCapture.output_count()` -> `dxcam.output_info()`,
and dxcam enumerates its outputs **once per process** (`dxcam.DXFactory` is an
import-time singleton — `docs/DECISIONS.md` constraint 30, measured; it cost a
3.8-hour dead picture). The list was therefore filled when the window was
BUILT and frozen for the life of the app: a monitor plugged in mid-run never
appeared, and reopening the window did not help — only a restart did.

The open window now subscribes to the process's one Display Watch, reached
through `controller.display_watch`, and refills the combo on a real change.

Three rules hold it together:

- **The callback arrives off the GUI thread** (a message-only window, or Qt's
  screen signals), so `_emit_displays_changed` only EMITS the
  `displays_changed` signal; the repopulate runs on the GUI thread through
  Qt's queued delivery. A widget touched from a foreign thread is a crash, not
  a glitch.
- **A closed window lets go.** `done()` — QDialog's one exit, which `accept()`,
  `reject()` and the window's own close button all pass through —
  unsubscribes. A dead window's callback held by the watch would keep the
  dialog alive and emit into a destroyed widget.
- **A repopulate never re-points the owner's choice.** The current selection is
  restored by data, not by index, whenever the monitor it names still exists.

Gate: `tests/test_log_wiring.py` (0b24/6).
