# Remote User — Setup Guide

Control your Windows PC from your Android phone. This is the canonical step-by-step flow. The apps guide you through these same steps on screen — this document is the source of truth for that guidance.

---

## Before you start

- **The first pairing must happen on the same Wi-Fi.** Put the phone on the *same home Wi-Fi as the PC*, not mobile data. (The QR points at the PC's home address `192.168.x`, which exists only on that Wi-Fi — mobile data can't reach it. Away-from-home use comes later, in Part 4.)
- You install nothing by hand beyond running one installer on the PC. Everything else — ffmpeg, the firewall rule, Tailscale — the installer handles.

---

## Part 1 — PC (once)

1. Run **`RemoteUser_Setup.exe`**.
2. If Windows asks to allow changes → **Yes**.
3. Wizard → **Next** on each step → **Install**. It sets the firewall rule and installs Tailscale (for away-from-home use) automatically.
4. Leave **“Launch Remote User”** checked → **Finish**.
5. The **Remote User** window opens: a **QR code** and a green **RUNNING** badge. The server is up.

You can close the window — the server keeps running in the tray (icon by the clock).

---

## Part 2 — Phone (once)

**First, put the phone on the same Wi-Fi as the PC.**

### 2a — Get the app
1. Point the phone **camera** at the QR on the PC screen → tap the link → a page opens in the browser.
2. On that page tap **“Install the app”** → allow the download (enable “install from this source” if asked) → open the downloaded file → **Install**.

### 2b — Open and pair
1. Tap **“Open the app”** on the same page (or open the **Remote User** app icon).
2. On the app’s pairing screen tap **“Scan the QR code”** → allow the camera → point at the QR on the PC.
3. **Connected** — you see the PC screen.

---

## Part 3 — Daily use (after the first time)

- **PC:** starts with Windows, runs in the tray. If closed, open the **Remote User** shortcut.
- **Phone:** just open the **Remote User** app. It reconnects by itself. **No QR scanning** — you only scan the first time (or when adding a new PC).

### Controls
- **One finger** = moves the PC cursor (does not click).
- **Click** button = left click at the cursor; press twice fast = double click.
- **Right / Drag / Scroll** = mode buttons; **two fingers** = zoom.
- **Keys** = keyboard; what you type appears in the focused box on the PC. The keyboard’s ↵ = new line; the **Enter** button = real Enter.
- Top-left **Move** = pan without clicking; top-right **Hide** = hide the buttons.

---

## Part 4 — Use from anywhere / mobile data (optional, later)

The home address does not work off the home Wi-Fi. For use anywhere you need **Tailscale** (free) on **both** devices.

- **PC:** Tailscale is already installed (Part 1). In the Remote User window, if prompted, tap **“Set up Tailscale”** and sign in.
- **Phone:**
  1. Install **Tailscale** from Google Play.
  2. Sign in with the **same account** as the PC.
  3. Turn it **ON**.
  4. **Connect once while at home** (on Wi-Fi) so the app learns the anywhere-address.
  5. After that it works over mobile data too — just open the app; it picks the reachable address by itself.

Without Tailscale **ON** on the phone, mobile data cannot work — that is the only requirement.

---

## Part 5 — Updating (automatic)

- **PC:** on start it checks for a newer release. When one exists, an **“Update to vX”** button appears — click it and it downloads and installs itself.
- **Phone:** when the PC is newer than the app, an **“Update the app”** banner appears in the app — one tap downloads the new app from the PC. The phone never needs the internet for this.

You never shuffle installer files by hand again.

---

## Troubleshooting

**Black screen / “Webpage not available” / “Cannot reach the PC”:**
- Usually the phone is on **mobile data** trying the home address. Put it on the **same Wi-Fi** as the PC (for mobile data see Part 4).
- Check the PC window shows green **RUNNING**.

**The app shows the “Install / Open the app” page inside itself and the buttons do nothing:**
- The installed app is an old version. **Uninstall it**, then reinstall from the browser (Part 2a) — the new app goes straight to the PC screen.

**“Invalid token” / “Link expired”:**
- Tap **“Scan a new QR”** in the app and scan the QR again (on the same Wi-Fi).

**Can’t type / dictate:**
- Tap **Keys**, then type. If a box is focused on the PC (click into it first with the **Click** button), the text lands there.

---

## Quick version

1. **PC:** run `RemoteUser_Setup.exe` → Finish → window shows the QR + RUNNING.
2. **Phone on the same Wi-Fi.**
3. Scan QR with the camera → **Install the app** → install → **Open the app**.
4. In the app: **Scan the QR code** → point at the PC’s QR. Done.
5. Next time: just open the app.
