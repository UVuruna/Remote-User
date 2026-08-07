# Settings Window — Flow

**About:** [description](../__about/settings_window.md)

## Algorithm — opening the window

```mermaid
flowchart TB
    A["Settings button on the main window"] --> B{"built before?"}
    B -- no --> C["SettingsWindow(controller, main.restart_server, parent)"]
    C --> D["_build_cards — STREAM, NOTIFICATIONS, FOCUS, STARTUP"]
    D --> E["every control reads its LIVE source: SETTINGS, agent_hook_installed(), autostart.installed(), notify.voices()"]
    B -- yes --> F
    E --> F["show() → showEvent"]
    F --> G["_refresh_live_state() — voices, the hook, the logon task, re-read"]
    G --> H{"already settled?"}
    H -- yes --> K
    H -- no --> I["_align_label_column() — one label width for BOTH forms, in the polished font"]
    I --> J["settle_minimum(self, _computed_minimum(), 0x0)"]
    J --> K["the owner sees it"]
```

`_refresh_live_state()` runs on every show, not only the first: a phone may
have connected since (new voices), and an installer run may have created or
removed the logon task behind our back.

## Algorithm — what a change does

```mermaid
flowchart TB
    A["the owner changes something"] --> B{"which card?"}
    B -- "STREAM combos" --> C["nothing yet — the encoder is shaped by these"]
    C --> D["Apply & restart"] --> E["save_user_settings(monitor, width, bitrate, fps)"]
    E --> F["restart callable → MainWindow.restart_server()"]
    F --> G{"busy, or server stopped?"}
    G -- yes --> H["no-op — the next start reads the new values"]
    G -- no --> I["_run_worker(_restart_worker) — off the UI thread, buttons gated"]
    B -- "Tell my phone…" --> J["set_agent_hook(on) — installs the Claude Code Stop hook"]
    J --> K{"ok?"}
    K -- no --> L["tick back to the REAL state + _set_caption(…, error=True) — one of notify.py's named HUMAN sentences, never str(e)"]
    K -- yes --> M["caption switches between the on and off sentence, error colour cleared"]
    B -- "Say it out loud / Voice / Speaking pace" --> N["save_user_settings(notify_speak | notify_voice | notify_rate)"]
    N --> O["they ride in the NEXT notify frame — nothing is pushed to the phone"]
    B -- "Don't let applications steal focus" --> P["foreground_lock.apply(on)"]
    P --> Q{"Windows accepted?"}
    Q -- no --> R["tick back to foreground_lock.is_raised() + _set_caption(…, error=True)"]
    Q -- yes --> S["save_user_settings(foreground_lock) — re-applied at the next start, error colour cleared"]
    B -- "Check for new versions" --> T["save_user_settings(update_check) — updates.check() reads it"]
    B -- "Start with Windows" --> U["autostart.set_autostart(on) — schtasks Create/Delete"]
    U --> V{"ok?"}
    V -- no --> W["tick back to autostart.installed() + _set_caption(…, error=True) — Windows' own last line, or a fixed sentence if schtasks itself could not run"]
```

Every switch that can be REFUSED puts its tick back from the real state and
says why, in the theme's semantic Error colour (`_set_caption`, round R2's
second independent grader — see `__about/settings_window.md`). None of them
writes a setting the machine did not accept, and none of them ever shows the
raw text of an exception — that is what would turn this window into the thing
it exists to replace: a preference that only pretends, or a stack trace where
a sentence should be.

## Algorithm — the Voice dropdown, and why it cannot lose a choice

```mermaid
flowchart TB
    A["phone connects"] --> B["client/notify.js sendTtsInfo() → Android.ttsVoices()"]
    B --> C["tts_info {voices:[{name,label,locale}…]}"]
    C --> D["web.py → notify.set_voices() — held in memory, never persisted"]
    E["_populate_voices()"] --> F["'The phone's own default' (data = '')"]
    F --> G["one row per reported voice"]
    G --> H{"SETTINGS.notify_voice reported by this phone?"}
    H -- yes --> I["select it"]
    H -- "no, but stored" --> J["add '<name> — remembered, phone not connected' and select THAT"]
    H -- "not stored" --> K["select the default row"]
    I --> L["signals stay blocked throughout — populating never writes a setting"]
    J --> L
    K --> L
```

The list is never persisted on the PC: a list read from a phone that is no
longer here would offer the owner voices he cannot hear. The CHOICE is
persisted, as a plain name — a device that no longer has it falls back to its
own default rather than speaking in whichever voice now sits at that index.

## Build round R3 (2026-08-07) — themes

```
_build_cards(root)
   |- APPEARANCE          +-------------------------------------------+
   |                      | APPEARANCE            This PC   [ (  * ) ]|
   |                      | The phone   [Dark  v] [Outlined v]        |
   |                        Dark | Light | Colored dark | Colored light
   |                      | Colored gives every set its own colour -  |
   |                      | dark shades on a dark page, strong ones.. |
   |                      +-------------------------------------------+
   |- STREAM              (unchanged — the only card with an Apply)
   |- NOTIFICATIONS       (unchanged)
   `- QHBoxLayout         +------------------+ +----------------------+
         FOCUS   | 1      | FOCUS            | | STARTUP              |
         STARTUP | 1      | [ ] Don't let .. | | [x] Check for new .. |
                          | While this is on | | [x] Start with Win.. |
                          +------------------+ +----------------------+
                             ^ the reflow that kept the window inside
                               the declared 1000 px height floor
```

Minimum, measured in both palettes:

```
            width           height
before R3   614             890     (four cards, one column)
+ card      614            1048     <- past the declared 1000 floor
+ reflow    718             921     <- FOCUS | STARTUP on one row
```
