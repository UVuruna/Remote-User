# Main Window — Flow

**About:** [description](../__about/main_window.md)

Layout sketch — the window is one column of cards, stacked top to bottom in
the exact order `__init__` adds them to `root` (a `QVBoxLayout`). This is a
zone map, not a control-flow diagram.

The column used to be pinned at a hard 400 px. It is now RESIZABLE with a
COMPUTED minimum (`_computed_minimum()` + a settle loop, THE SPACE &
LEGIBILITY LAW): the widest real row it can show — the three bottom buttons at
their longest captions, the update button's full sentence, the widest settings
row, the QR — plus the height its longest guidance text (`REACH_TEXT`) needs
once wrapped at that width. With the shipped strings that is **676 × 787**
(dev machine, Segoe UI 13 px, 2026-08-05).

```mermaid
%%{init: {'flowchart': {'subGraphTitleMargin': {'top': 0, 'bottom': 35}}}}%%
flowchart TB
    subgraph WIN["MainWindow — resizable, computed minimum 676x787"]
        direction TB
        subgraph HEADER["Header row"]
            direction LR
            LOGO[logo 34x34]
            TITLES["title 'Remote User' (#h1)\ncaption 'Control this PC…'"]
            PILL["status pill\nrunning / starting / stopped / failed"]
        end
        subgraph QRCARD["QR card"]
            direction TB
            QR["qr_label 216x216\n(white QR PNG or 'Server stopped')"]
            URL["url_label — selectable pairing URL"]
            BTNS["Copy link | Open in browser"]
            REACH["reach_label — reachability hint text"]
        end
        subgraph SETCARD["Settings card"]
            direction TB
            FORM["Form: Monitor · Resolution · Bitrate ·\nFrame rate (combo boxes)"]
            APPLY["Apply && restart button (right-aligned)"]
        end
        subgraph BOTTOM["Bottom row"]
            direction LR
            POWER["power_btn\n'Start server' / 'Stop server'\n(#primary / #danger)"]
            SPACER[" "]
            TS["tailscale_btn\n'Set up' / 'Sign in' — hidden when connected"]
        end
        UPDATE["update_btn — hidden until a newer\nGitHub release is found"]
        FOOTER["footer — 'vX.Y.Z · closing hides to tray…'"]

        HEADER --> QRCARD --> SETCARD --> BOTTOM --> UPDATE --> FOOTER
    end

    subgraph TRAY["System tray icon"]
        direction TB
        TOPEN["Open Remote User"]
        TTOGGLE["Stop server / Start server"]
        TSEP["---"]
        TQUIT["Quit"]
        TOPEN --> TTOGGLE --> TSEP --> TQUIT
    end

    WIN -. closeEvent hides to .-> TRAY
```

Widget inventory per zone (nested-list form, for a quick text scan):

- Header
  - logo (`QLabel` pixmap)
  - titles (`QLabel#h1` + `QLabel#caption`)
  - `self.pill` (`QLabel#pill`, `state` dynamic property)
- QR card (`QFrame#card`)
  - `self.qr_label` (`QLabel#qr`, fixed 216x216)
  - `self.url_label` (selectable text)
  - `self.copy_btn`, `self.browser_btn`
  - `self.reach_label` (word-wrapped hint)
- Settings card (`QFrame#card`)
  - `QFormLayout`: `self.monitor_combo`, `self.resolution_combo`,
    `self.bitrate_combo`, `self.fps_combo`
  - `self.apply_btn`
- Bottom row
  - `self.power_btn` (`#primary`/`#danger`)
  - `self.tailscale_btn`
- `self.update_btn` (`#primary`, hidden by default)
- Footer `QLabel#caption`
- Tray (`QSystemTrayIcon` + `QMenu`)
  - open action, `self.tray_toggle`, separator, quit action
