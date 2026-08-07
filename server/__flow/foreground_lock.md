# Foreground Lock — Flow

**About:** [description](../__about/foreground_lock.md)

## Algorithm — the whole life of a borrowed machine setting

```mermaid
flowchart TB
    A["process start — ServerController.__init__"] --> B["repair_stranded()"]
    B --> C{"ledger file on disk?"}
    C -- no --> G
    C -- "yes, our own pid" --> G
    C -- "yes, another run" --> D{"current timeout == the value that run raised it to?"}
    D -- no --> F["someone moved it since — leave it alone"]
    D -- yes --> E["write 'previous' back + log a warning"]
    E --> F
    F --> G["delete the ledger"]
    G --> H{"SETTINGS.foreground_lock?"}
    H -- no --> I["nothing raised; release() is a no-op forever"]
    H -- yes --> J["apply(True)"]
    J --> K["_read() the current value → _previous"]
    K --> L["_write(foreground_lock_timeout_ms) — flags 0, never the registry"]
    L --> M["_ledger_save(previous, raised)"]
```

The switch in the Settings window enters at `apply(on)` and leaves the same
way; nothing else in the app touches the setting.

## Algorithm — the way out, one net per way the process can end

```mermaid
flowchart TB
    A["tray Quit · Ctrl+C · console close · logoff · unhandled crash"] --> B["Qt aboutToQuit / atexit / SetConsoleCtrlHandler"]
    B --> C["foreground_lock.release()"]
    C --> D{"_previous is None?"}
    D -- yes --> E["no-op — we never raised it (and a stranded ledger stays for the next start)"]
    D -- no --> F["_write(_previous) + delete the ledger"]
    G["Task Manager kill · installer taskkill · power cut"] --> H["no code of ours runs"]
    H --> I["the ledger stays on disk"]
    I --> J["next start: repair_stranded() — see the diagram above"]
    K["Windows restart"] --> L["the value was never in the registry — already restored"]
```

`release()` is wired into BOTH entry points and is idempotent, so the three
overlapping nets can all fire on one exit without doing anything twice.
It is NOT wired into `ServerController.release_windows()`: that runs on every
server stop, including Apply & restart, and dropping the lock there would
silently switch the owner's setting off in the middle of a session.

## Algorithm — one Win32 call, twice

```mermaid
flowchart LR
    A["_read()"] --> B["SystemParametersInfoW(SPI_GET…, 0, &DWORD, 0)"]
    B --> C{"returned true?"}
    C -- yes --> D["int(value)"]
    C -- no --> E["log the last error → None (the switch reports it)"]
    F["_write(ms)"] --> G["SystemParametersInfoW(SPI_SET…, 0, c_void_p(ms), 0)"]
    G --> H{"returned true?"}
    H -- yes --> I["True"]
    H -- no --> J["log the last error → False"]
```

The SET call carries its value in `pvParam` cast to a pointer — that is this
particular SPI's documented convention, not a trick. The final `0` is the
flag word, and it is the whole safety story: `SPIF_UPDATEINIFILE` would
persist the change past our process.
