"""All tunable values for the Vibe Coder server. No other file may hardcode these.

Two layers:
- `Settings` defaults (this file) — the single source of every tunable.
- A user settings JSON with overrides — written by the desktop GUI, loaded at
  startup. Only keys in USER_ADJUSTABLE may be overridden; bad values are
  logged and skipped, never fatal.

Paths depend on how the app runs:
- Dev (repo checkout): everything stays inside the project (logs/, PAIRING_QR.png,
  actions.json, ffmpeg from PATH).
- Installed EXE (PyInstaller onedir): user data (settings, token, logs, QR,
  edited actions.json) lives in %LOCALAPPDATA%/VibeCoder — Program Files is
  not writable; bundled read-only data (client/, default actions.json) comes
  from the PyInstaller bundle dir, and the installer places ffmpeg/ next to
  the exe.

The module-level SETTINGS instance is the only one, shared by every module.
Changing values at runtime goes through apply() (controlled mutation of the
shared instance — a plain assignment raises, catching accidental writes).
"""

import json
import logging
import os
import sys
from dataclasses import dataclass, fields
from pathlib import Path

# ═══════════════════════════ PATHS & RUNTIME MODE ═══════════════════════════
logger = logging.getLogger(__name__)
FROZEN = getattr(sys, "frozen", False)
PROJECT_ROOT = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))  # onedir: <app>/_internal
USER_DIR = (
    Path(os.environ["LOCALAPPDATA"]) / "VibeCoder" if FROZEN else PROJECT_ROOT / "logs"
)


def _migrate_legacy_user_dir() -> None:
    """Carry %LOCALAPPDATA%/RemoteUser across the 2026-08-11 rename.

    The app was called Remote User until then and its user data — settings,
    token, the owner's edited actions.json, the layout history, the topmost
    ledger — lived under that name. The rename moved the product, not his
    data: an installed copy that simply started looking at the new path would
    have read an empty folder and silently handed him factory defaults, which
    reads exactly like "the update wiped my settings".

    Runs ONCE, and only when the new folder does not exist yet: a MOVE, so a
    second start finds nothing left to do and the old name can never win over
    a newer file. A failure here is never fatal — the app must start even if
    Windows refuses the move (a stray handle from the copy being replaced),
    and the next start tries again.
    """
    if not FROZEN or USER_DIR.exists():
        return
    legacy = Path(os.environ["LOCALAPPDATA"]) / "RemoteUser"
    if not legacy.is_dir():
        return
    try:
        legacy.rename(USER_DIR)
        logger.info("User data carried over from %s to %s", legacy, USER_DIR)
    except OSError as error:                       # never fatal — retried next start
        logger.warning("Could not carry user data over from %s: %s", legacy, error)


_migrate_legacy_user_dir()
SETTINGS_PATH = USER_DIR / "settings.json"

# Keys the desktop GUI may override (persisted in settings.json).
USER_ADJUSTABLE = {
    "port", "monitor_index", "target_fps", "use_h264",
    "h264_max_width", "h264_bitrate", "jpeg_quality", "open_qr_image",
    # The desktop Settings window (round R2, owner 2026-08-07) — everything
    # that window can change, and nothing else. `foreground_lock` and
    # `update_check` are read at START as well as on the toggle, so they have
    # to survive a restart; the three notify keys ride in every notify frame.
    "notify_speak", "notify_voice", "notify_rate",
    "foreground_lock", "update_check",
    # Appearance (build round R3, 2026-08-07; corrected to three independent
    # axes 2026-08-08; made PER DEVICE 2026-08-12). `ui_theme` is the
    # DESKTOP's own palette and the only appearance dial this window still
    # carries. `phone_theme` / `phone_colored` / `phone_fill` stay here as the
    # DEFAULT a handset wears until it chooses for itself — they still ride
    # every `config` frame — but the choice itself now lives on the device
    # (Settings → Appearance, client/appearance-panel.js). They keep their
    # place in this set so a hand-edited settings.json can still move the
    # default a new phone starts from.
    "ui_theme", "phone_theme", "phone_colored", "phone_fill",
}


# ═══════════════════════════ DEFAULT-VALUE HELPERS ═══════════════════════════
def _default_ffmpeg() -> str:
    if FROZEN:
        bundled = PROJECT_ROOT / "ffmpeg" / "ffmpeg.exe"
        if bundled.exists():
            return str(bundled)
    return "ffmpeg"  # dev: on PATH


# ═══════════════════════════ THE QUALITY LADDER — ONE TABLE, BOTH ENDS ═══════════════
# THE OWNER'S OWN FOUR LEVELS AND HIS OWN NUMBERS (his ticked verdict,
# 2026-08-12). One rung is one (frame rate, bitrate) pair, and the SAME four
# rungs are what the desktop STREAM card offers and what the phone's quality
# panel offers. There is no second table anywhere, in either language.
#
#   Level        fps   bitrate   bits/frame
#   Max           60   20 Mbps      333k
#   Smooth        30   12 Mbps      400k
#   Sharp         10    6 Mbps      600k
#   Data saver    10    2 Mbps      200k
#
# THE LADDER DELIBERATELY RAISES BITS PER FRAME IN THE MIDDLE, and the rule
# that used to forbid that is retired (see tests/test_stream_card.py, where
# the retraction is written out). His instruction was to sort the levels so
# the PICTURE stays decently good everywhere: going down, SMOOTHNESS is spent
# first (60 → 30 → 10) and the picture itself only at the bottom. The
# invariant that survives — and the one his rejected table actually broke — is
# that the BITRATE falls STRICTLY at every step, so a lower rung can never
# render sharper than the rung above it while wearing a humbler name.
#
# ── DATA SAVER IS SIMPLY THE BOTTOM RUNG ────────────────────────────────────
# Three doors reach it and there must never be two sets of numbers behind
# them (owner ballot 2026-08-12: "just make sure you connect Data saver to
# mobile data, the mechanic we already have"):
#   * AUTOMATICALLY — the phone's "save data on mobile networks" tick plus the
#     `Android.transport()` bridge: while the handset is on cellular,
#     client/quality.js sends exactly this override instead of the saved one.
#   * BY HAND — the desktop STREAM card's "Data saver" step (gui/stream_card.py),
#     which writes this rung's numbers into the PC's own base.
#   * LEGACY — a page older than the quality panel sending
#     `quality {reduced: true}` — `quality_override` below maps it here.
#
# DATA_SAVER is the per-client OVERRIDE shape (what a `quality` message
# carries) and DATA_SAVER_BITRATE the absolute number the desktop step writes;
# both are READ OUT of the bottom rung rather than restated, so the desktop's
# Data saver step and the phone's cellular level are the same numbers BY
# CONSTRUCTION. That mismatch was previously documented as unavoidable,
# because the phone's steps were percentages of a base that could move; the
# percentage rule was never the owner's (his correction, 2026-08-12) and it is
# gone. DATA_SAVER_SCALE is the capture-side halving.
#
# The three `h264_reduced_*` settings below READ these rather than restating
# them, and tests/test_stream_card.py asserts the desktop step, the phone's
# own ladder literal, the cellular switch and the legacy mapping all against
# this one table.
QUALITY_LADDER = (
    {"id": "max",    "label": "Max",        "fps": 60, "bitrate": "20M"},
    {"id": "smooth", "label": "Smooth",     "fps": 30, "bitrate": "12M"},
    {"id": "sharp",  "label": "Sharp",      "fps": 10, "bitrate": "6M"},
    {"id": "saver",  "label": "Data saver", "fps": 10, "bitrate": "2M"},
)
# The bottom rung, named once so the saving profile has somewhere to point.
DATA_SAVER_LEVEL = QUALITY_LADDER[-1]
DATA_SAVER = {"fps": DATA_SAVER_LEVEL["fps"], "res": "1/2",
              "bitrate": DATA_SAVER_LEVEL["id"]}
DATA_SAVER_BITRATE = DATA_SAVER_LEVEL["bitrate"]
DATA_SAVER_SCALE = 2
# A page built before the ladder still says "mid"/"low" on the wire. They are
# TRANSLATED onto rungs, never given numbers of their own — an old phone gets
# a real level, and there is still exactly one table. ("high" is not here: it
# is the "follow the PC" sentinel and always was, and it still is.)
LEGACY_BITRATE_LEVELS = {"mid": "sharp", "low": "saver"}


def _default_actions() -> Path:
    if FROZEN:
        user_copy = USER_DIR / "actions.json"
        if user_copy.exists():
            return user_copy  # owner-edited copy wins over the bundled default
        return BUNDLE_DIR / "actions.json"
    return PROJECT_ROOT / "actions.json"


# ═══════════════════════════ SETTINGS TABLE ═══════════════════════════
@dataclass(frozen=True)
class Settings:
    # Network
    host: str = "0.0.0.0"
    port: int = 8777

    # Streaming
    monitor_index: int = 0          # which monitor to capture (0 = primary)
    target_fps: int = 30
    jpeg_quality: int = 70          # 1-100, higher = sharper + more bandwidth (JPEG fallback path)
    max_stream_width: int = 1600    # JPEG path: frames wider than this are downscaled before
                                    # encoding (a 4K monitor as JPEG at native res is ~216 Mbps)

    # H.264 streaming (hardware-encoded, inter-frame compressed — the responsive path).
    # The encoder is auto-detected at startup from a preference order (see below);
    # the JPEG path remains as the ultimate fallback if even software H.264 fails.
    use_h264: bool = True
    ffmpeg_path: str = _default_ffmpeg()
    # Preference order tried at startup — first one that actually encodes on THIS machine wins.
    # Covers NVIDIA, Intel iGPU, AMD, then pure-software (works on any CPU, no GPU needed).
    h264_encoder_order: tuple[str, ...] = ("h264_nvenc", "h264_qsv", "h264_amf", "libx264")
    # H.264 path cap — the width the encoder is FED, applied by
    # capture.RawFrameSource._stream_size before a single byte reaches the
    # pipe. It was 3840 (stream the monitor natively) on the argument that
    # inter-frame compression keeps a static 4K screen cheap in BITRATE. True,
    # and beside the point: the cost that hurts is not the bits on the wire,
    # it is the RAW PIXELS the CPU carries to the encoder every frame. At
    # 3840x2160 I420 that is 12.44 MB per frame — 0.75 GB/s at 60 fps, per
    # client, on top of the capture itself, and that is the pipeline the
    # owner's phone ran OUT OF FRAMES behind (task 151: his log's negative
    # `behind`, frozen for two minutes at 60 fps / 20 Mbps). 2560 costs
    # 5.53 MB per frame — 0.33 GB/s at 60 — and no phone or tablet panel
    # resolves more than that anyway.
    # The honest cost, stated rather than buried: H.264 always streams the
    # FULL frame, so this is also the ceiling a deep client-side zoom can
    # resolve. Screenshots are unaffected — `take_screenshot` reads the raw
    # camera frame at native resolution, before any of this.
    # A saved setting always wins: this is the default for a PC that has never
    # been told otherwise, never an override of a choice the owner made.
    h264_max_width: int = 2560
    # Target bitrate cap — reached only on heavy motion; a static screen uses a
    # fraction of it regardless of resolution.
    #
    # THE SHIPPED DEFAULT IS A RUNG OF THE OWNER'S LADDER, and it has to be:
    # the desktop card would otherwise open on its Custom entry on every fresh
    # install, telling a new owner his PC is set to something the product has
    # no word for. With `target_fps` at 30 the only rung that fits is SMOOTH
    # (30 fps, 12 Mbps) — his ladder pairs 6 Mbps with 10 fps and has no
    # (30 fps, 6 Mbps) rung at all, which is why the 6M default of earlier the
    # same day could not survive his table.
    #
    # It is a DEFAULT, never an override: a saved settings.json wins. The
    # phone's own bitrate steps are the ladder's ABSOLUTE numbers now, capped
    # at whatever this holds (`bitrate_for_level`) — the phone may pick any
    # level at or below the PC's, and nothing above it.
    h264_bitrate: str = "12M"
    h264_gop: int = 60              # keyframe every N frames (reconnect/seek granularity)
    h264_fragment_us: int = 16000   # fMP4 fragment target (µs) — below one frame interval,
                                    # so every encoded frame ships in its own fragment
    h264_head_timeout: float = 5.0  # seconds to wait for ffmpeg's init segment (ftyp+moov)
    h264_queue_chunks: int = 256    # per-client outbound chunk queue (~4 s at full bitrate); a
                                    # full queue means the client cannot keep up — its session
                                    # is reset instead of building latency
    # Per-client quality overrides (owner spec 2026-08-05, growing the
    # 2026-08-02 full/reduced pair into a picker: the phone panel chooses
    # fps / resolution (full, 2/3, 1/2 — half PER AXIS is quarter pixels,
    # so the middle step is 2/3) / bitrate level, or auto-reduces on mobile
    # data; the desktop Settings combos stay the DEFAULTS every level maps
    # against).
    #
    # THE BITRATE STEPS ARE THE LADDER'S OWN ABSOLUTE NUMBERS (owner verdict
    # 2026-08-12). `h264_bitrate_mid_pct` / `h264_bitrate_low_pct` are GONE
    # with the percentage rule they served: that rule was written into the
    # record as his decision of 2026-08-05 and it was never his (his
    # correction, 2026-08-12), and what it cost was the desktop's Data saver
    # step and the phone's cellular level drifting apart every time the base
    # moved. The hierarchy he really wanted is unharmed and is now plain: the
    # phone may pick any rung AT OR BELOW the PC's own, and nothing above it
    # (`bitrate_for_level` clamps).
    # Re-opening this client's encoder after a quality change (owner report
    # 2026-08-10 — "changing the bitrate kills the whole app"). A quality
    # override lives inside one ffmpeg flag, so the only way to apply it is a
    # NEW encoder; the FIRST session of a connection is fatal when it fails
    # (there is nothing to keep), but a RE-open is not — the socket carries
    # input, layouts and dictation too, and a transient encoder hiccup must
    # not take those with it. Bounded, because an unbounded retry is the
    # 2026-07-29 error loop (171 failures in 90 s).
    h264_reopen_tries: int = 4      # consecutive RE-open failures tolerated
    h264_reopen_pause_s: float = 0.8  # breath between them
    # The auto-on-mobile-data profile — READ from the one definition above
    # (DATA_SAVER), never restated here. The desktop STREAM card's "Data
    # saver" step and the phone's auto-on-cellular switch are the same
    # profile by construction, which is the whole point of the table.
    h264_reduced_scale: int = DATA_SAVER_SCALE   # halve width and height
    h264_reduced_fps: int = DATA_SAVER["fps"]
    h264_reduced_bitrate: str = DATA_SAVER_BITRATE

    # Virtual cursor — DXGI capture never includes the mouse pointer, so the
    # server streams the cursor position and the client draws it.
    cursor_hz: int = 30             # position polls per second (sent only on change)

    # Injection self-check — Windows EATS injected input (SendInput still
    # returns success) when an elevated window or the lock screen has focus
    # and this process is not elevated (UIPI; live failure 2026-07-29: every
    # phone session dead, stream fine, zero errors). A commanded cursor jump
    # of ≥ min_jump px must land within tolerance px; streak consecutive
    # misses alert the client visibly.
    inject_verify_min_jump: int = 24
    inject_verify_tolerance: int = 16
    inject_verify_streak: int = 3

    # Layouts — the always-on-top ledger (owner decree 2026-08-05). Layout
    # members are forced above every other window while the phone shows them,
    # and that band is ours only while we are running to take it back. Every
    # raised window is written to this file, so a run that is KILLED (Task
    # Manager, a crash, a power cut) cannot strand the owner's Chrome and
    # VSCode above everything with nothing left to fix them: the next start
    # reads the file and repairs them. Deleting it by hand is always safe.
    topmost_ledger_path: Path = USER_DIR / "topmost.json"

    # Traffic monitor (owner request 2026-08-05) — every byte to and from the
    # phone, sampled once a second for the desktop window's graph and appended
    # to a CSV so an overnight test can be read back in the morning. The
    # history is what the window can draw; the CSV is what survives a restart.
    traffic_sample_s: float = 1.0
    traffic_history_samples: int = 3600      # one hour of one-second samples
    traffic_csv_path: Path = USER_DIR / "traffic.csv"
    traffic_csv_max_bytes: int = 20_000_000  # ~4 months of idle sampling
    traffic_csv_backups: int = 1
    # BUILD ROUND R4 (owner-approved 2026-08-07): the "Od starta" / "Sve (iz
    # fajla)" spans read the CSV off the UI thread (traffic_history.py) and
    # fold it into at most this many points — a ceiling on the DISK read
    # only, comfortably above any real window width, so the chart's own
    # paint-time coalesce (never more than one point per pixel) is what
    # actually limits what gets drawn; this just bounds the read's time/memory.
    traffic_history_max_buckets: int = 2000
    # How often a long span re-reads the file while it stays selected — a
    # live watch should see new samples appear, but a 20+ MB file is not
    # worth re-scanning on every 1 s GUI tick.
    traffic_history_refresh_s: float = 30.0

    # Pairing
    token_bytes: int = 16           # entropy of the pairing token
    persist_token: bool = True      # reuse the token across restarts (no re-scan after
                                    # every server update); delete token_path to rotate
    token_path: Path = USER_DIR / "token.txt"

    # Remote access — a Cloudflare "quick tunnel" gives an https URL that works
    # from anywhere (no account, no login, no open port). Opt-in per run: turning
    # it on makes the PC reachable over the internet by anyone holding the URL+token.
    # (The desktop GUI can turn this into a one-tap toggle.)
    use_tunnel: bool = False
    cloudflared_path: Path = PROJECT_ROOT / "bin" / "cloudflared.exe"
    cloudflared_url: str = (
        "https://github.com/cloudflare/cloudflared/releases/latest/download/"
        "cloudflared-windows-amd64.exe"
    )
    tunnel_timeout: int = 25        # seconds to wait for the tunnel URL
    open_qr_image: bool = not FROZEN  # CLI: open the QR PNG in a viewer; the GUI shows it itself
    # Kept where the owner can reopen it; regenerated on every server start.
    qr_image_path: Path = (USER_DIR if FROZEN else PROJECT_ROOT) / "PAIRING_QR.png"

    # Desktop window — closing it hides to the tray, and the toast that SAYS
    # so is one-time guidance, not a status report (owner 2026-08-06: "stalno
    # dobijamo ovo obaveštenje, konstantno se otvara i zatvara"). An in-memory
    # flag only lasted one run, so every start/stop of the day produced it
    # again; the marker file is what makes "once" mean once. Deleting it shows
    # the notice again, which is the only reason to touch it.
    tray_notice_path: Path = USER_DIR / "tray_notice.seen"
    # "Start with Windows" (Settings window, round R2). The thing that really
    # starts the app at logon is a Task Scheduler task the installer creates
    # (setup/installer.nsi -> SecAutostart, /RL HIGHEST because HKCU Run
    # silently refuses elevated apps). The switch READS and WRITES that task,
    # never a preference of its own — a switch that only remembers an
    # intention is exactly the kind of lie this project keeps paying for.
    autostart_task: str = "VibeCoder"

    # Notifications to the phone (ROADMAP Phase H; the desktop Settings window
    # owns all three since round R2). `notify_speak` off still raises the
    # Android banner — the server simply sends speak:false, so nothing is
    # SAID; the notice is never lost. `notify_voice` is a TTS voice NAME
    # exactly as the phone reported it in `tts_info`, and a device that does
    # not have it falls back to its own default, so swapping phones can never
    # silence the feature. `notify_rate` is TextToSpeech's speech rate
    # (1.0 = the engine's normal pace); the window offers 0.8 / 1 / 1.25 / 1.5.
    notify_speak: bool = True
    notify_voice: str = ""
    notify_rate: float = 1.0

    # "Don't let applications steal focus" (Settings window, round R2 —
    # the desktop half of the focus work; the phone's half is focus_guard).
    # Windows' own foreground lock: for `foreground_lock_timeout_ms` after the
    # user's last input, no process may push itself to the front. Raised with
    # NO SPIF_UPDATEINIFILE on purpose — the value must never reach the
    # registry, where it would outlive this app and quietly change a PC we no
    # longer run on. It therefore dies with the process (and with a Windows
    # restart), and the ledger below is what repairs a run we were KILLED in,
    # exactly as topmost_ledger_path does for the always-on-top band.
    foreground_lock: bool = False
    foreground_lock_timeout_ms: int = 200_000
    foreground_lock_ledger_path: Path = USER_DIR / "foreground_lock.json"

    # Logging
    log_dir: Path = USER_DIR if FROZEN else PROJECT_ROOT / "logs"
    log_file: str = "server.log"
    log_max_bytes: int = 1_000_000
    log_backups: int = 3

    # Client files (bundled read-only in the installed app)
    client_dir: Path = BUNDLE_DIR / "client" if FROZEN else PROJECT_ROOT / "client"
    favicon_path: Path = (BUNDLE_DIR if FROZEN else PROJECT_ROOT) / "assets" / "logo.svg"
    # The Android app, served at /app.apk when present (downloaded by the
    # install funnel — no manual file shuffling). Built by setup/build_apk.py;
    # the desktop installer ships a copy next to the exe. Its presence also
    # decides whether Android browsers get routed to the funnel page.
    apk_path: Path = PROJECT_ROOT / ("VibeCoder.apk" if FROZEN else "dist/VibeCoder.apk")

    # Action sets (chord shortcuts shown in the radial wheels) — hand-edited by
    # the owner; re-read on every client connection, so edits show on refresh.
    actions_path: Path = _default_actions()

    # Updates — the GitHub repo whose Releases carry new installers. The
    # desktop GUI checks it once per start and offers the update in-window;
    # the phone never checks the internet (its update comes from the PC:
    # `config` carries the server version, /app.apk carries the matching APK).
    # `update_check` had no UI until round R2 — it existed only as a default
    # nobody could reach. The Settings window's "Check for new versions when
    # the app starts" is that switch; turning it off makes updates.check()
    # return None and hides the in-window Update button entirely.
    update_repo: str = "UVuruna/VibeCoder"
    update_check: bool = True

    # THE HANDOVER (owner report 2026-08-07). Installing an update KILLED the
    # very session he was installing from: *"čim uđem u instalaciju on će meni
    # ugasiti Vibe Coder i više neću moći da komandujem odavde."* So the
    # update is now unattended end to end — see server/update_handover.py — and
    # these are the three files it leaves behind on purpose. All three live in
    # USER_DIR, never in the install folder: the installer REPLACES the install
    # folder, and a handover cannot keep its own instructions somewhere the
    # thing it is driving is about to overwrite.
    update_record_path: Path = USER_DIR / "update.json"
    update_script_path: Path = USER_DIR / "update_handover.cmd"
    update_log_path: Path = USER_DIR / "update.log"
    # How long the handover waits for the old app to exit, and for the new one
    # to appear. The exit budget covers a server thread joining (10 s) plus
    # Qt's teardown; the start-up budget covers a cold PyInstaller onedir launch
    # of a PySide6 app from files written seconds ago (an antivirus first-touch
    # scan is what makes this number generous rather than tight).
    update_wait_exit_s: int = 30
    update_wait_up_s: int = 40

    # Appearance (build round R3, owner-approved 2026-08-07; CORRECTED to
    # three INDEPENDENT axes 2026-08-08 — his words: "teme postoje samo dve,
    # svetla i tamna … zatim dalje pričam samo za ove komande … on može da
    # bude obojen, neobojen, i može da bude transparentan ili pun. dakle to
    # je ukupno osam kombinacija". The 2026-08-07 shape folded colour into a
    # FOURTH theme name ("colored" / "colored-light"), which produced the
    # same eight looks by accident but said the page has four themes when the
    # owner's own model is two themes plus two switches that belong to the
    # CONTROLS (the D-pad groups and the radial wheel), not to the page. The
    # desktop Settings card is what he actually operates, so it must match
    # his model exactly, not an equivalent one.
    #   ui_theme      — this PC's palette: "dark" or "light" (gui/theme.py).
    #                   Untouched by this correction — always was two values.
    #   phone_theme   — the phone PAGE: "dark" or "light". Same two values as
    #                   ui_theme now that colour is its own axis.
    #   phone_colored — whether the D-pad groups and the radial wheel wear
    #                   each set's own colour. The palette is `SET_COLORS`
    #                   below and it does NOT depend on the theme (owner
    #                   2026-08-08) — a set's colour is its identity, and an
    #                   identity that changes with the sun/moon switch is not
    #                   one. False leaves the controls the theme's plain
    #                   foreground colour ("samo belo" on dark).
    #   phone_fill    — "transparent" (outlined) or "full" (filled). It reaches
    #                   the SAME surfaces `phone_colored` does and no others
    #                   (owner 2026-08-08: "vazi isto samo za controls, sets i
    #                   te buttone na ekranu sto su stalno vidljivi — layout,
    #                   hide..."), independent of theme AND colour.
    # 2 x 2 x 2 = 8 combinations, all real. An unknown value is treated as the
    # default by the surface that reads it, never as a reason to fail.
    #
    # PER DEVICE SINCE 2026-08-12 (owner ballot: "appearance is also per
    # device, not global, so it belongs on the phone / tablet"). The 2026-08-07
    # answer to P4 — one source of truth, no menu on the phone — was right
    # about there being ONE answer and wrong about where it lives: he uses a
    # tablet AND a phone, and one desktop dropdown could only ever describe
    # one of them. So the three values below are now the DEFAULT rather than
    # the decree: they still ride every `config` frame, a handset that has
    # never chosen wears them byte for byte, and a handset that HAS chosen
    # keeps its own answer in its own SharedPreferences (client/theme.js —
    # `uiChoice`, the sets-picker's bridge, never bare localStorage). Two
    # devices therefore render the same frame differently, which is the whole
    # request.
    ui_theme: str = "dark"
    phone_theme: str = "dark"
    phone_colored: bool = False
    phone_fill: str = "transparent"


# ═══════════════════════════ APPEARANCE — THE PHONE'S SET COLOURS ═══════════════════════════
# One colour per shipped set — as the button OUTLINE in the transparent fill
# and as the button FILL in the full one. The phone computes every INK from
# the surface the text really lands on (client/theme.js), so a set's label can
# never land unreadable on its own colour whatever is tuned here later.
#
# ONE TABLE, BOTH THEMES (owner decision 2026-08-08, on seeing the variants).
# This replaces the two-table split of 2026-08-07, and the correction is his:
#
#   "nema dve verzije za obojene setove. Oni ce uvijek imati ove jake
#    upecatljive boje. Ono sto se menja su ostali elementi, light ili dark
#    temi, ali kontrole i setovi ce biti obojeni."
#
# The 2026-08-07 reasoning was that the colour does a different job on each
# page — the BODY of the button on dark, the INK on light — so no single hex
# could be both. That analysis was not wrong about the JOBS; it was wrong
# about what he wanted. He does not want the set colours to follow the page at
# all. A set's colour is its IDENTITY, and an identity that changes when he
# flips a switch is not one — Mouse is that teal on both pages, and the theme
# moves everything else around it.
#
# It also removes a whole class of the bug this project keeps meeting: two
# tables are two things to keep in step, and the second one goes stale.
#
# THE RULE THIS TABLE OBEYS, and why each hex is what it is:
#   * HSL saturation is CAPPED at 72%. "Sto saturacija ne treba ni u jednom
#     modu": nothing here is a pure hue.
#   * Lightness 26-54% — vivid enough to be "ona klasična jaka", dark enough
#     that a WHITE label clears AA on it as a fill, which is what makes the
#     same hex work on both pages: the label reads against the COLOUR, not
#     against the page behind it.
#   * HUE **and** LIGHTNESS separate the sets that share the wheel. The four
#     blues (Mouse 196, Settings 215, VSCode 222, Windows 232) and the four
#     warms (Claude 13, Explorer 24, Attach 36, Chrome 50) are pulled apart in
#     lightness as well as hue, so a colour-blind eye still has a second
#     signal.
#   * A SET THAT IS MISSING HERE IS NOT UNCOLOURED — IT WEARS ANOTHER SET'S
#     COLOUR (grader 2026-08-11). `client/theme.js -> setColors` hands an
#     unnamed set the next colour of this palette nothing already holds, and
#     when every colour IS held it falls through to the first one — so
#     `Claude Tools` (task 219) rendered rgb(24,107,137), byte-identical to
#     Mouse, and two sets sat on one wheel wearing one identity. That fallback
#     is right for a set the owner invents and names himself; a set WE ship
#     must be in this table. Its hue 94 is the widest gap the ring had left
#     (between Chrome's 50 and Input's 145) and it is 33% light against
#     Input's 26%, so hue and lightness separate it from the only green here,
#     per the rule two lines up.
#
# Every combination is swept by tests/test_layout_audit.py — all 14 colours,
# BOTH themes, both fills, D-pad and wheel — and the ink is computed from the
# surface the text really lands on (client/theme.js), never tabled, so the
# contrast tooth stays green whatever he retunes here later.
#
# CUSTOM sets are not listed and never will be: he names them himself in the
# Controls editor, so the phone hands each one the next colour of this palette
# that no shipped set already holds (client/theme.js -> `setColors`).
SET_COLORS = {
    "Mouse": "#186B89",
    "Input": "#14713B",
    "Settings": "#476185",
    "Edit": "#702BB6",
    "Attach": "#C38322",
    "Navigate": "#146F65",
    "Media": "#BA2630",
    "Windows": "#4356D0",
    "VSCode": "#204DB6",
    "Chrome": "#A58E1D",
    "Explorer": "#DC7028",
    "Claude": "#A3472E",
    "Claude Tools": "#4E8A1F",
    "Cursor": "#B02971",
}

# The two names the 2026-08-07 split introduced, kept pointing at the ONE
# table so an import that outlived the split cannot quietly resurrect a
# second palette. New code uses SET_COLORS.
SET_COLORS_DARK = SET_COLORS
SET_COLORS_LIGHT = SET_COLORS


def set_colors(theme: str | None = None) -> dict:
    """The set palette — THE SAME ON BOTH THEMES (owner decision 2026-08-08:
    "nema dve verzije za obojene setove, oni ce uvijek imati ove jake
    upecatljive boje"). A set's colour is its identity, and an identity that
    changes when he flips the sun/moon switch is not one.

    `theme` is still accepted and still ignored, deliberately: every caller
    passes it (the phone config, the desktop preview, the audit sweep), and
    removing the parameter would break them all for a change that has nothing
    to do with them. It stays as the record that the question was ASKED and
    answered with "it does not matter" — not as an argument nobody thought
    about.

    A monochrome look never reads this map at all (client/theme.css wires the
    `--set-*` tokens only under `data-colored="true"`), so answering
    regardless of `phone_colored` costs nothing and keeps this function
    answering exactly one question."""
    del theme  # the palette does not depend on it — see above
    return dict(SET_COLORS)


def ui_config() -> dict:
    """The APPEARANCE half of every `config` frame (`web._send_config`).

    Deliberately a function here rather than lines built in web.py: the
    desktop owns this decision, config.py owns the desktop's settings, and
    web.py's job is only to put it on the wire.

    It is the DEFAULT, not the decree, since 2026-08-12: a device that has
    chosen for itself (Settings → Appearance) lays its own answer over these
    three axes and only the axes it never touched come from here. That is a
    rule on the PAGE, deliberately — the PC cannot know which handset is
    asking, and a per-device answer computed here would need a device
    identity on the wire for nothing.

    THREE INDEPENDENT AXES (owner correction 2026-08-08), not a shape derived
    from one. `theme`/`colored`/`fill` are three flat fields the phone applies
    without ever knowing colour used to be folded into the theme name.

    The PALETTE IS RESOLVED HERE, so the wire shape never changed on that
    front either: the phone receives one flat `{set: hex}` map and holds no
    table of its own. Resolving on the desktop is what kept this cheap when
    the two tables of 2026-08-07 became ONE on 2026-08-08 — the wire, the
    page and the cache all carried on unchanged, because none of them ever
    knew how many tables there were. A page that chose for itself would have
    been the copy that drifted.
    """
    return {"theme": SETTINGS.phone_theme,
            "colored": SETTINGS.phone_colored,
            "fill": SETTINGS.phone_fill,
            "colors": set_colors()}


# ═══════════════════════════ VERSION ═══════════════════════════
def app_version() -> str:
    """The running app's version from setup/app_info.json (bundled next to
    the exe). "dev" when the file is missing — an unpackaged checkout."""
    path = (BUNDLE_DIR if FROZEN else PROJECT_ROOT) / "setup" / "app_info.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["version"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return "dev"


def apk_version() -> str:
    """Version of the APK this server actually serves at /app.apk (sidecar
    written by build_apk.py, bundled by build.py). Falls back to the app
    version for trees without the sidecar. The phone's update banner MUST
    compare against this, not the server version — the APK does not change
    with desktop-only releases (owner bug 2026-08-02: eternal update offer)."""
    try:
        return Path(str(SETTINGS.apk_path) + ".version").read_text(encoding="utf-8").strip()
    except OSError:
        return app_version()


# ═══════════════════════════ SHARED INSTANCE & MUTATION ═══════════════════════════
SETTINGS = Settings()


def bitrate_bps(text: str) -> int:
    """"12M" / "1200k" / "900000" → bits per second. Unparsable text falls
    back to the 12 Mbps default rather than killing a stream."""
    raw = str(text).strip()
    factor = 1
    if raw and raw[-1] in "kK":
        factor, raw = 1_000, raw[:-1]
    elif raw and raw[-1] in "mM":
        factor, raw = 1_000_000, raw[:-1]
    try:
        return max(1, int(float(raw) * factor))
    except ValueError:
        logger.warning("Unparsable bitrate %r — using 12M", text)
        return 12_000_000


def level_for_bitrate(text: str) -> dict:
    """Which rung of QUALITY_LADDER a bitrate IS — the highest rung at or
    below it. A PC set by hand to something between two rungs counts as the
    lower one, so "at or below the PC" can never be read as permission to
    exceed it."""
    bps = bitrate_bps(text)
    for level in QUALITY_LADDER:
        if bitrate_bps(level["bitrate"]) <= bps:
            return level
    return DATA_SAVER_LEVEL


def bitrate_for_level(level: str | None) -> str:
    """The phone's bitrate step resolved to a real number (owner verdict
    2026-08-12: the phone gets the SAME four levels the desktop card offers,
    as ABSOLUTE numbers, and may pick any level at or below what the PC is set
    to).

    `None` and `"high"` are the "follow the PC" sentinel the wire has always
    carried — the PC's own value, unchanged. A rung's id resolves to that
    rung's own bitrate, CLAMPED to the PC's: the hierarchy the owner asked for
    on 2026-08-05 survives the percentages that never did. Legacy `"mid"` /
    `"low"` from an older page are translated onto rungs (LEGACY_BITRATE_LEVELS)
    rather than given numbers of their own."""
    name = str(level or "")
    name = LEGACY_BITRATE_LEVELS.get(name, name)
    rung = next((rung for rung in QUALITY_LADDER if rung["id"] == name), None)
    if rung is None:
        return SETTINGS.h264_bitrate
    if bitrate_bps(rung["bitrate"]) > bitrate_bps(SETTINGS.h264_bitrate):
        return SETTINGS.h264_bitrate       # never above the PC's own choice
    return rung["bitrate"]


def is_data_saver(level: str | None) -> bool:
    """Is this client running the SAVING PROFILE — the bottom rung?

    THE ONE NOTION OF "ON CELLULAR" THIS SERVER HAS, and it is deliberately
    not a new one (T79, owner: "for this house it does not matter that much
    but for Mobile Data it is very important that we optimise the BITRATE too"
    — lang-ok: owner quote, translated). The phone's "save data on mobile
    networks" tick plus the `Android.transport()` bridge already send exactly
    this rung as the client's override while the handset is on cellular
    (client/quality.js `effectiveQuality`), so the fact is already on the
    wire. Inventing a `transport` field beside it would be a SECOND answer to
    one question, and the two would drift the first time one of them moved.

    Reading it this way also, correctly, covers the owner picking Data saver
    BY HAND: a person who asked to spend less data means it whether or not the
    radio agrees. Legacy `"low"` from an older page is translated onto the
    rung first, exactly as `bitrate_for_level` does."""
    name = str(level or "")
    return LEGACY_BITRATE_LEVELS.get(name, name) == DATA_SAVER_LEVEL["id"]


def quality_override(msg: dict) -> dict | None:
    """The per-client encoder overrides carried by a `quality` message — or by
    the `auth` message's own `quality` field (task 203, 2026-08-11).

    ONE parser, two callers, and the second caller is the whole point. The
    phone restates its saved overrides on every connect, and that used to
    arrive only in the `quality` message — which `_receive_input` cannot read
    until the WHOLE connection setup has finished. So the first encoder was
    opened at DEFAULT quality, the restatement landed a moment later,
    `changed` was true, and the session that had just started was torn down and
    rebuilt: a second ffmpeg spawn and a second black gap on every return from
    an excursion. Measured in the owner's own log, 2026-08-11 10:08:08:

        10:08:08,773  H.264 session opened — 1 active
        10:08:08,864  H.264 session closed — 0 active      91 ms later
        10:08:10,086  H.264 session opened — 1 active      1.31 s of nothing

    Reading the same field out of `auth` makes the FIRST session the right one,
    and the restatement that follows compares equal and does nothing. `None`
    means "pure defaults" — identical to no override — so the comparison in the
    handler stays a plain `!=`.

    It lives HERE, beside `bitrate_for_level` and `stream_base`, because it is
    the same vocabulary and because web.py has no room (THE STRUCTURE LAW).

    Legacy `reduced: true` (pages older than the quality panel) maps to the
    auto-save profile — the ONE definition (DATA_SAVER), never a second copy
    of its numbers."""
    if "reduced" in msg and "res" not in msg:
        return dict(DATA_SAVER) if msg.get("reduced") else None
    quality = {
        "fps": int(msg.get("fps") or 0),
        "res": str(msg.get("res") or "full"),
        "bitrate": str(msg.get("bitrate") or "high"),
    }
    if quality == {"fps": 0, "res": "full", "bitrate": "high"}:
        return None  # pure defaults — same as no override
    return quality


def stream_base(stream) -> dict:
    """The desktop Settings card, as the phone needs to read it: the fps and
    the encoded size the PC allows, plus the bitrate every phone step is a
    percentage of. JPEG mode has no encoder size of its own — fall back to the
    monitor size.

    It lives HERE, beside `bitrate_for_level`, because every number in it is a
    reading of SETTINGS (moved out of web.py 2026-08-10, THE STRUCTURE LAW).

    `level` is the ladder rung this PC is really on, so the phone can grey out
    every rung above it without doing the arithmetic itself. `bitrate_mid` /
    `bitrate_low` stay on the wire for a page older than the ladder — they are
    now readings of rungs, not percentages of anything."""
    width, height = getattr(stream, "stream_size", (stream.width, stream.height))
    return {
        "fps": SETTINGS.target_fps,
        "width": width,
        "height": height,
        "bitrate": SETTINGS.h264_bitrate,
        "level": level_for_bitrate(SETTINGS.h264_bitrate)["id"],
        "bitrate_mid": bitrate_for_level("mid"),
        "bitrate_low": bitrate_for_level("low"),
    }


def apply(**changes) -> None:
    """Controlled mutation of the one shared SETTINGS instance — every module
    that imported it sees the new values (the dataclass stays frozen against
    accidental assignment). Server components must be restarted to pick up
    changes that shape them (port, monitor, encoder settings)."""
    for key, value in changes.items():
        object.__setattr__(SETTINGS, key, value)


# ═══════════════════════════ USER SETTINGS I/O ═══════════════════════════
# BACKWARD COMPATIBILITY (owner correction 2026-08-08, THE THREE-AXIS THEME
# MODEL). Before this build `phone_theme` carried four values, and "colored"
# / "colored-light" WERE the colour axis — a phone whose owner had picked one
# of them has that exact choice sitting in his settings.json right now. The
# decision here is to TRANSLATE, never to reset: his SAVED CHOICE must not
# silently become something else the first time a build that no longer
# understands the old spelling reads his file. "colored-light" meant
# dark-page-with-colour respelled as light-page-with-colour is exactly
# {"phone_theme": "light", "phone_colored": True} — no information is lost,
# only the shape changes from one field to two.
#
# This also covers the SAME situation arriving from a different direction: a
# phone's own local cache (`prefGet("uiLook")` in client/theme.js) can hold a
# `ui` object saved by an OLDER page, independent of what this server now
# sends — see client/theme.js's own `legacyTheme()` for that half of the same
# fix. Two call sites, one idea: an old four-value shape is DATA to translate,
# not an error to reject.
_LEGACY_PHONE_THEME = {
    "colored": {"phone_theme": "dark", "phone_colored": True},
    "colored-light": {"phone_theme": "light", "phone_colored": True},
}


# Keys THIS PROJECT retired. They are not the owner's mistakes — they were our
# settings, we removed the feature behind them, and his file kept them because
# nothing ever rewrites a file he does not open.
#
# `hand` is the one that showed it (his server.log, 2026-08-08, thirteen times
# in one day): "settings.json: 'hand' is not a user-adjustable key — ignored",
# on every single start, months after the left/right-hand offset system was
# deleted (2026-08-02, removed from the code and the docs 2026-08-07). Warning
# a man about a key HE never typed is not information, it is noise that teaches
# him to stop reading his own log — and the log is where the evidence for every
# bug in this project has come from.
#
# It is also the SAME CLASS as the actions.json failure recorded in CLAUDE.md:
# we change ours, his copy keeps the dead field forever. The rule adopted there
# says OURS is deleted if we retired it. This is that rule, one file over.
RETIRED_KEYS = {
    # 2026-08-02 the offset system went, 2026-08-07 the last of it.
    "hand",
}


def _drop_retired(raw: dict) -> tuple[dict, list[str]]:
    """Strips keys we retired. Returns the cleaned dict (a copy — callers must
    not have their own handed dict mutated) and what was dropped, so the caller
    can decide whether the file on disk is now worth rewriting."""
    dead = [k for k in raw if k in RETIRED_KEYS]
    if not dead:
        return raw, []
    return {k: v for k, v in raw.items() if k not in RETIRED_KEYS}, dead


def _migrate_legacy_ui(raw: dict) -> dict:
    """Translates a pre-2026-08-08 `phone_theme` value into the current
    three-axis shape, in place of the dict it is handed (a copy — callers must
    not have their own `raw`/`current` mutated from under them). Runs BEFORE
    the `USER_ADJUSTABLE` / type checks below: the legacy value is a
    recognisable, valid shape from an earlier version, not a bad one, and
    letting it fall into `_coerced` would have looked identical to a corrupt
    field and been silently dropped — which is exactly the reset this
    function exists to avoid.

    `setdefault` on `phone_colored`: if the file SOMEHOW already carries both
    the legacy theme name and an explicit `phone_colored` (hand-edited, or a
    future migration run twice), the explicit value wins — this function only
    fills in what the old shape did not have a field for."""
    hit = _LEGACY_PHONE_THEME.get(raw.get("phone_theme"))
    if not hit:
        return raw
    migrated = dict(raw)
    migrated["phone_theme"] = hit["phone_theme"]
    migrated.setdefault("phone_colored", hit["phone_colored"])
    return migrated


def _coerced(key: str, value):
    """Validates a user-file override against the dataclass field type.
    Returns the coerced value, or None when the value is unusable.
    (fields() reports the annotation as a class here; the string forms are
    accepted too in case deferred annotations are ever enabled.)"""
    kind = {f.name: f.type for f in fields(Settings)}[key]
    try:
        if kind in (bool, "bool"):  # bool first — bool is a subclass of int
            if not isinstance(value, bool):
                raise ValueError(f"expected true/false, got {value!r}")
            return value
        if kind in (int, "int"):
            return int(value)
        if kind in (float, "float"):
            return float(value)
        if kind in (str, "str"):
            return str(value)
    except (TypeError, ValueError) as e:
        logger.warning("settings.json: bad value for %s (%s) — using default", key, e)
        return None
    logger.warning("settings.json: %s has unsupported type %s — using default", key, kind)
    return None


def load_user_settings() -> None:
    """Applies overrides from the user settings file onto SETTINGS. Call once
    at startup, after logging is configured. Missing file = defaults."""
    try:
        # utf-8-sig: tolerate a BOM — editors and PowerShell redirects add one
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return
    except (json.JSONDecodeError, OSError) as e:
        logger.error("settings.json unreadable (%s) — using defaults", e)
        return
    raw = _migrate_legacy_ui(raw)
    # A key WE retired is dropped without a word, and the file is healed on the
    # spot rather than at some future save — he may never open Settings again,
    # and until he does the warning would print at every start forever (see
    # RETIRED_KEYS). A failure to rewrite is not worth a line either: the key
    # is already ignored in memory, so the only cost is repeating this next
    # time.
    raw, dead = _drop_retired(raw)
    if dead:
        logger.info("Dropped setting(s) this version no longer has: %s",
                    ", ".join(sorted(dead)))
        try:
            SETTINGS_PATH.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        except OSError:
            pass
    accepted = {}
    for key, value in raw.items():
        if key not in USER_ADJUSTABLE:
            # Still worth saying for a key nobody has ever shipped: that one is
            # a typo of his, and silence there would hide a setting he believes
            # is in effect.
            logger.warning("settings.json: %r is not a user-adjustable key — ignored", key)
            continue
        coerced = _coerced(key, value)
        if coerced is not None:
            accepted[key] = coerced
    if accepted:
        apply(**accepted)
        logger.info("User settings applied: %s", accepted)


def save_user_settings(changes: dict) -> None:
    """Persists the given overrides (merged over the existing file) and applies
    them to the running SETTINGS. The GUI is the only writer."""
    current = {}
    try:
        current = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    # The file SELF-HEALS on the very next save after an upgrade: without
    # this, a legacy "colored"/"colored-light" left over from before would
    # sit next to a freshly-written `phone_colored`, and the stale
    # `phone_theme` value would be an unrecognised string the next load has
    # to migrate all over again — harmless, but worth not repeating forever.
    current = _migrate_legacy_ui(current)
    current, _ = _drop_retired(current)
    unknown = set(changes) - USER_ADJUSTABLE
    if unknown:
        raise ValueError(f"Not user-adjustable: {sorted(unknown)}")
    current.update(changes)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(current, indent=2), encoding="utf-8")
    apply(**changes)
    logger.info("User settings saved: %s", changes)
