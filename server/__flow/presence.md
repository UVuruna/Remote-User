# Presence — Flow

**About:** [description](../__about/presence.md)

## Algorithm — deciding what a page-hide means

```mermaid
flowchart TB
    A["page hides (screen off / app switch / picker)"] --> B["client: hideReason()"]
    B --> C{"in the APK?"}
    C -- yes --> D["Android.hideReason() — the shell KNOWS"]
    C -- "no (dev browser)" --> E["inExcursion() — the 12 s fallback timer"]
    D --> F{"reason"}
    E --> F
    F -- "lock" --> G["away {reason: lock}"]
    F -- "excursion" --> H["away {reason: excursion}"]
    F -- "'' (switched away/closed)" --> G
    G --> I["server: is_excursion → False"]
    H --> J["server: is_excursion → True"]
    I --> K["leave_session: minimize members + clear_topmost — NOW"]
    J --> L["conn.away = True; layout held; stream paused"]
```

The shell answers `"lock"` whenever the screen is off or the device is locked,
and it tests that **before** its own picker flag: a picker can be open when the
screen goes off, and the screen wins.

## Algorithm — the watchdog, per connection

```mermaid
flowchart TB
    A["every WATCHDOG_POLL_S (2 s)"] --> B{"still the active client?"}
    B -- no --> C["return — a watchdog only ends its OWN session"]
    B -- yes --> D{"conn.away AND owner_at_the_desk(baseline)?"}
    D -- yes --> E["'local input on this PC' → end the session"]
    D -- no --> F{"silent ≥ (away ? 45 s : 12 s)?"}
    F -- yes --> G["'no signal from the phone' → end the session"]
    F -- no --> H{"away?"}
    H -- no --> I["refresh the desk baseline — still with us"]
    H -- yes --> J["keep holding"]
    E --> K["leave_session + ws.close(4408)"]
    G --> K
```

The baseline is refreshed on every poll while the phone is present, so at the
moment it *does* go away, "input newer than this" means the owner's own hands
and not the input we were injecting a minute ago.

## Algorithm — the hold that outlives its socket

```mermaid
flowchart TB
    A["away {excursion} then the socket closes"] --> B["ws_endpoint finally: arm excursion_backstop"]
    B --> C["the task handle is kept in `holds` — a bare create_task can be GC'd mid-sleep"]
    C --> D["every 2 s, up to EXCURSION_MAX_S"]
    D --> E{"a client reconnected?"}
    E -- yes --> F["return — its own session owns the layout again"]
    E -- no --> G{"owner_at_the_desk?"}
    G -- yes --> H["leave_session — his desk outranks the phone's parting word"]
    G -- no --> I{"deadline reached?"}
    I -- yes --> H
    I -- no --> D
```

A new authenticated socket **cancels** every armed hold. Its only test used to
be "no client connected", which is equally true in every ordinary reconnect
gap — so a stale hold could minimize the layout the owner was looking at.
