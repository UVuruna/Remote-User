"""All tunable values for the Remote User server. No other file may hardcode these.

Two layers:
- `Settings` defaults (this file) — the single source of every tunable.
- A user settings JSON with overrides — written by the desktop GUI, loaded at
  startup. Only keys in USER_ADJUSTABLE may be overridden; bad values are
  logged and skipped, never fatal.

Paths depend on how the app runs:
- Dev (repo checkout): everything stays inside the project (logs/, PAIRING_QR.png,
  actions.json, ffmpeg from PATH).
- Installed EXE (PyInstaller onedir): user data (settings, token, logs, QR,
  edited actions.json) lives in %LOCALAPPDATA%/RemoteUser — Program Files is
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
    Path(os.environ["LOCALAPPDATA"]) / "RemoteUser" if FROZEN else PROJECT_ROOT / "logs"
)
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
    # axes 2026-08-08). `ui_theme` is the DESKTOP's palette; `phone_theme` /
    # `phone_colored` / `phone_fill` are the PHONE's, chosen here and nowhere
    # else (owner answer P4: one source of truth, no menu on the phone) and
    # carried to it in every `config` frame.
    "ui_theme", "phone_theme", "phone_colored", "phone_fill",
}


# ═══════════════════════════ DEFAULT-VALUE HELPERS ═══════════════════════════
def _default_ffmpeg() -> str:
    if FROZEN:
        bundled = PROJECT_ROOT / "ffmpeg" / "ffmpeg.exe"
        if bundled.exists():
            return str(bundled)
    return "ffmpeg"  # dev: on PATH


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
    h264_max_width: int = 3840      # H.264 path cap — native 4K streams fine (inter-frame
                                    # compression keeps a static screen at a few Mbps) and zoom
                                    # stays sharp; lower it only for weak decoders/links
    h264_bitrate: str = "12M"       # target bitrate cap — reached only on heavy motion; static
                                    # screens use a fraction of it regardless of resolution
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
    # against). "mid"/"low" are PERCENTAGES of the desktop bitrate, not fixed
    # numbers (owner 2026-08-05): absolute constants meant the desktop combo
    # applied only while the phone sat on "High" — picking "Mid" silently
    # threw the PC's own choice away, which is exactly the "the desktop
    # setting does nothing" report. As fractions the hierarchy holds on all
    # three steps: the phone can only ever go BELOW what the PC allows.
    h264_bitrate_mid_pct: int = 40
    h264_bitrate_low_pct: int = 10
    # The auto-on-mobile-data profile (legacy `reduced` maps to this too):
    h264_reduced_scale: int = 2     # halve width and height
    h264_reduced_fps: int = 10
    h264_reduced_bitrate: str = "1200k"

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
    autostart_task: str = "RemoteUser"

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
    apk_path: Path = PROJECT_ROOT / ("RemoteUser.apk" if FROZEN else "dist/RemoteUser.apk")

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
    update_repo: str = "UVuruna/Remote-User"
    update_check: bool = True

    # THE HANDOVER (owner report 2026-08-07). Installing an update KILLED the
    # very session he was installing from: *"čim uđem u instalaciju on će meni
    # ugasiti Remote User i više neću moći da komandujem odavde."* So the
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
    #                   each set's own colour. True picks a palette by
    #                   `phone_theme` (SET_COLORS_DARK / SET_COLORS_LIGHT,
    #                   below) — dark shades on a dark page, strong inks on a
    #                   light one, per his own words. False leaves them the
    #                   theme's plain foreground colour ("samo belo" on dark).
    #   phone_fill    — "transparent" (outlined) or "full" (filled) — the
    #                   SAME two controls, independent of theme AND colour.
    # 2 x 2 x 2 = 8 combinations, all real. The phone gets these in `config.ui`
    # and applies them; it has no menu of its own (owner answer P4). An
    # unknown value is treated as the default by the surface that reads it,
    # never as a reason to fail.
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
# TWO TABLES, ONE PER SURFACE (owner correction 2026-08-07, replacing the
# single table he adopted the same day with "tune later"). His words:
#
#   "kada je DARK tema treba da budu jako tamne nijanse, dakle mali
#    lightness/brightness; a ovaj mod LIGHT treba da ima jako svetla slova,
#    velikim, u boji, dakle ona klasična jaka. Sto saturacija ne treba ni u
#    jednom modu."
#
# One table cannot answer both halves of that, because the colour does a
# DIFFERENT JOB on each page. On a dark page the colour is the BODY of the
# button and the white label carries the reading — so the colour must be dark,
# or the button glows (the first palette's #38BDF8 filled a 58 px button with
# near-neon cyan on a near-black page). On a light page the colour is the INK
# — strong, vivid, classic — on a calm surface it must stay legible against.
# A dark navy that reads beautifully as a fill is invisible as ink on white,
# and a vivid ink is a searchlight as a fill; the same hex cannot be both.
#
# THE RULE BOTH TABLES OBEY, and the reason each hex is the one it is:
#   * HSL saturation is CAPPED — 66% on dark, 72% on light. "Sto saturacija ne
#     treba ni u jednom modu": nothing here is a pure hue. The two ceilings
#     differ because the jobs differ — 72% is what the classic strong inks
#     (a #B92 red, a #204DB6 blue) actually measure, and on dark a shade that
#     saturated turns muddy as it darkens.
#   * DARK: lightness 22–40%. The floor is not taste — a fill darker than that
#     stops reading as a button against the #0f172a page; the ceiling is where
#     white label text stops clearing AA on it. Both are measured, not guessed.
#   * LIGHT: lightness 26–54%, the band where a colour is vivid enough to be
#     "ona klasična jaka" and still dark enough to be read on #eceef6.
#   * HUE **and** LIGHTNESS separate the sets that share the wheel — the one
#     property of the first palette worth keeping. The four blues (Mouse 196,
#     Settings 215, VSCode 222, Windows 232) and the four warms (Claude 13,
#     Explorer 24, Attach 36, Chrome 50) are pulled apart in lightness as well
#     as hue, so a colour-blind eye still has a second signal.
#
# Every combination is swept by tests/test_layout_audit.py — all 13 colours,
# both surfaces, both fills, D-pad and wheel — and no entry here needs the
# client's own fill correction (`fillOn`): what the desktop shows is what the
# phone paints.
#
# CUSTOM sets are not listed and never will be: the owner names them himself
# in the Controls editor, so the phone hands each one the next colour of the
# palette in force that no shipped set already holds (client/theme.js →
# `setColors`). One table per surface, no third list to keep in step.
SET_COLORS_DARK = {
    "Mouse": "#1D6A86",
    "Input": "#1C693C",
    "Settings": "#4B5B71",
    "Edit": "#572B82",
    "Attach": "#7D561C",
    "Navigate": "#175E57",
    "Media": "#86282E",
    "Windows": "#354297",
    "VSCode": "#1C3878",
    "Chrome": "#5D5113",
    "Explorer": "#944D1E",
    "Claude": "#8D4834",
    "Cursor": "#7E2A57",
}

SET_COLORS_LIGHT = {
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
    "Cursor": "#B02971",
}


def set_colors(theme: str | None = None) -> dict:
    """The palette a given PHONE THEME wears — the SURFACE decides, nothing
    else (owner correction 2026-08-08: chosen by `theme` alone, never by a
    fourth theme name that used to fold the colour axis in). A monochrome
    look never reads this map at all (client/theme.css only wires the
    `--set-*` tokens under `data-colored="true"`), so resolving it here
    regardless of `phone_colored` costs nothing and keeps this function
    answering exactly one question."""
    name = SETTINGS.phone_theme if theme is None else theme
    return dict(SET_COLORS_LIGHT if name == "light" else SET_COLORS_DARK)


def ui_config() -> dict:
    """The APPEARANCE half of every `config` frame (`web._send_config`).

    Deliberately a function here rather than lines built in web.py: the
    desktop owns this decision, config.py owns the desktop's settings, and
    web.py's job is only to put it on the wire.

    THREE INDEPENDENT AXES (owner correction 2026-08-08), not a shape derived
    from one. `theme`/`colored`/`fill` are three flat fields the phone applies
    without ever knowing colour used to be folded into the theme name.

    The PALETTE IS RESOLVED HERE, so the wire shape never changed on that
    front either: the phone still receives one flat `{set: hex}` map and has
    no idea two tables exist. Sending both and letting the page choose would
    have put the same decision in two places, and the page's copy would be
    the one that drifts.
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


def bitrate_for_level(level: str | None) -> str:
    """The phone's bitrate step resolved against the DESKTOP choice (owner
    2026-08-05). "high" is the PC's own value; "mid"/"low" are percentages of
    it — so lowering the PC's bitrate lowers all three steps and the phone can
    never out-bid the PC's ceiling."""
    pct = {"mid": SETTINGS.h264_bitrate_mid_pct,
           "low": SETTINGS.h264_bitrate_low_pct}.get(str(level or ""))
    if pct is None:
        return SETTINGS.h264_bitrate
    return f"{max(1, bitrate_bps(SETTINGS.h264_bitrate) * pct // 100_000)}k"


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
    accepted = {}
    for key, value in raw.items():
        if key not in USER_ADJUSTABLE:
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
    unknown = set(changes) - USER_ADJUSTABLE
    if unknown:
        raise ValueError(f"Not user-adjustable: {sorted(unknown)}")
    current.update(changes)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(current, indent=2), encoding="utf-8")
    apply(**changes)
    logger.info("User settings saved: %s", changes)
