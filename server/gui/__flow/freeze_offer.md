# Flow — freeze_offer.py

## The offer, start to answered

```
MainWindow.__init__
        │
        ▼
build_freeze_offer_banner(window)
   SETTINGS.offered_2560 already True? ──yes──▶ return None (no banner)
        │ no
        ▼
   h264_max_width >= 3840 AND target_fps >= 60? ──no──▶ return None
        │ yes
        ▼
   build the bar: label + [Switch] + [Keep 4K]
   root.addWidget(bar)                    ← top of the window's column
        │
        ▼
   owner taps Switch ─────────────┐        owner taps Keep 4K
        │                         │               │
        ▼                         │               ▼
   save_user_settings({           │        save_user_settings({
     offered_2560: True,          │          offered_2560: True })
     h264_max_width: 2560})       │               │
        │                         │               │
        ▼                         │               ▼
   window.restart_server()        │        bar removed, nothing else changes
        │                         │
        └─────────────▶ bar removed, encoder restarts at 2560
```

The offer is asked at most once ever — the flag is set on both branches, so
neither answer leaves it able to ask again on the next start.
