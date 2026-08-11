"""The phone's SET EDITOR — `actions_update`, the one message that lets the
tablet change what the desktop Controls editor changes.

WHY THIS MODULE EXISTS AT ALL (owner, 2026-08-04 18:27, and again on
2026-08-11 as a ballot comment: "jako davno sam rekao, toliko davno da je
zabrinjavajuce sto jos niko to ne spominje" — lang-ok: owner quote, the record
of when this was asked for). His 2026-08-04 spec for the wheel ends with the
sentence this feature was owed — he gives the user the option to choose a
different arrangement for BOTH versions, the cross and the portrait column,
"dakle obe te opcije dozvoljavamo mu da slobodno bira raspored batona u tom
setu" (lang-ok: owner quote, the request itself).

He then said the PHONE's copy of that menu may not CREATE sets. It may not
create them; it was never told it may not arrange them, and arranging is the
part he does while holding the device — which is the only place the D-pad's
geometry can actually be judged.

WHAT THE PHONE MAY WRITE, AND WHY IT IS A SUBSET RATHER THAN A NEW RULE
-----------------------------------------------------------------------
`server/gui/controls_data.py` owns THE OWNERSHIP RULE: `OWNER_SET_KEYS` names
the per-set keys that belong to the owner and survive every shipped-pool merge.
The phone may write only `PHONE_EDITABLE`, and that set is asserted to be a
SUBSET of `OWNER_SET_KEYS` at import time — so a future round that makes a new
key phone-editable without adding it to the merge's owner list cannot start:
the server refuses to import, at the desk, instead of writing a field that the
next release's merge would silently delete out of his file. That deletion is
exactly the 2026-08-07 failure recorded in CLAUDE.md, arriving from the other
direction.

`enabled` is deliberately NOT phone-editable even though it IS an owner key:
it is the wheel COMPOSITION default, and the phone already owns composition
per DEVICE through the sets picker's SharedPreferences (which must stay per
device — the tablet and the phone want different wheels). This editor edits a
set's INTERIOR. The two never meet, and the wheel-cap law is untouched.

THE POOL IS THE FILE'S OWN, NOT A SECOND COPY
---------------------------------------------
Every id is validated against the `buttons` list of the set being edited IN
THE USER'S FILE — which, for a built-in or app set, IS the shipped pool: the
merge overwrites `buttons` from shipped on every start (it is OURS under the
ownership rule). Validating against a separately-read shipped file would add a
second source of truth for one list, and would have no answer at all for a
custom set, whose pool is his own. It is also exactly the list the phone was
shown, because the `actions` frame ships these same objects.
"""

import asyncio
import json
import logging
from pathlib import Path

from config import SETTINGS
from gui.controls_data import DPAD_SLOTS, OWNER_SET_KEYS, button_id

logger = logging.getLogger(__name__)


# ─────────────────────── READING actions.json for the phone ───────────────────
# `_merge_shipped_actions` and `load_actions` MOVED here from web.py on
# 2026-08-11 (THE STRUCTURE LAW — web.py stood at 1,004 lines, past the wall).
# The placement is by responsibility and not by line count: this module is now
# the one place that knows the shape of actions.json on the wire, which is
# exactly what the re-broadcast below needs and what a second copy of the field
# whitelist would have quietly desynchronised (`wheel_order` was a feature the
# desktop saved and the phone never saw for precisely that reason).

_shipped_pools_merged = False


def _merge_shipped_actions() -> None:
    """Owner round 4 (2026-08-05): the Controls editor merges a NEW version's
    shipped pools into the owner's %LOCALAPPDATA% actions.json — but only
    when the editor is OPENED, so a phone-visible default change (Language
    replacing Anywhere in Settings) never arrived without a desktop click.
    The same merge runs here, once per server start. FROZEN-only: in a dev
    checkout the repo file IS the shipped file and there is nothing to merge
    (which also keeps the PySide6 import below out of the headless CLI)."""
    global _shipped_pools_merged
    if _shipped_pools_merged:
        return
    _shipped_pools_merged = True
    from config import BUNDLE_DIR, FROZEN
    if not FROZEN:
        return
    user_path = Path(SETTINGS.actions_path)
    shipped_path = BUNDLE_DIR / "actions.json"
    if not user_path.exists() or user_path == shipped_path:
        return
    try:
        from gui.controls_editor import merge_shipped_pools
        data = json.loads(user_path.read_text(encoding="utf-8"))
        merge_shipped_pools(data, json.loads(shipped_path.read_text(encoding="utf-8")))
        user_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Shipped action pools merged into the user actions.json")
    except Exception as e:  # a failed merge must never stop the server
        logger.warning("Shipped-pools merge skipped: %s", e)


def load_actions() -> dict:
    """Reads the owner's action categories fresh (edits apply on the next
    connect, and immediately after a phone edit — see `actions_update`). A
    missing or invalid file is logged and yields no categories — never a
    crash.

    THE WHITELIST IS THE FEATURE GATE. It returns a FIXED set of keys, and a
    field missing from it is a feature the desktop saves and the phone never
    sees — which is exactly what happened to `wheel_order`. Anything a new
    round teaches actions.json must be added HERE too."""
    _merge_shipped_actions()
    empty = {"categories": [], "app_sets": [], "custom_sets": [], "left": 0,
             "right": 0, "wheel_order": [], "wheel_mode": "dropout"}
    try:
        data = json.loads(SETTINGS.actions_path.read_text(encoding="utf-8"))
        return {
            "categories": data.get("categories", []),
            # App-aware sets (owner 2026-08-04): shown by the client ONLY in
            # layout focus, when the focused layout's app matches `process`.
            "app_sets": data.get("app_sets", []),
            # Owner-made sets from the desktop Controls editor (owner
            # 2026-08-05): the client shows up to 3 of them after the five
            # built-ins; `enabled` is the desktop default, the phone's own
            # Sets picker overrides it per device.
            "custom_sets": data.get("custom_sets", []),
            "left": data.get("left", 0),
            "right": data.get("right", 0),
            # Where each set sits on the phone's wheel (build round R5, owner
            # 2026-08-07): position 1 is 12 o'clock, then clockwise. Without
            # this line the desktop editor saves an order the phone never sees
            # — the whole feature is a no-op, on a fresh install too.
            "wheel_order": data.get("wheel_order", []),
            # Drop-out vs fixed (task 181, 2026-08-11): "dropout" (default)
            # sheds a placed set off both wheels; "fixed" keeps today's
            # behaviour. Set by the desktop Controls editor, beside
            # "Wheel order…" — missing/unknown reads as the default.
            "wheel_mode": data.get("wheel_mode", "dropout"),
        }
    except FileNotFoundError:
        logger.warning("actions.json not found at %s — no action categories",
                       SETTINGS.actions_path)
        return empty
    except (json.JSONDecodeError, OSError) as e:
        logger.error("actions.json could not be loaded: %s", e)
        return empty

# The keys the phone's editor may write. See the module docstring: a strict
# subset of the merge's owner-owned keys, checked here so the two can never
# drift apart in silence.
PHONE_EDITABLE = frozenset({"active", "order_land", "order_port"})
assert PHONE_EDITABLE <= OWNER_SET_KEYS, (
    "a key the phone may edit is not owner-owned in the shipped-pool merge — "
    "add it to OWNER_SET_KEYS (server/gui/controls_data.py) in this same "
    "commit, or the next release's merge will delete his choice")

# Where a set can live. `custom_sets` is his entirely; the editor's scope there
# is the same as everywhere else — WHICH pool commands ride and WHERE. Writing
# the commands themselves stays on the desktop (owner decision 2026-08-05).
SECTIONS = ("categories", "app_sets", "custom_sets")


class Refused(Exception):
    """A message we will not act on, carrying the sentence the phone shows.

    Every refusal is a TOAST and a log line, never a silent no-op: a panel
    whose Save did nothing is indistinguishable from one that saved, and this
    project has already paid for that twice (the layout Move handle's three
    rounds, the actions.json field that never arrived)."""


def _find_set(data: dict, name: str) -> dict:
    for key in SECTIONS:
        for s in data.get(key) or []:
            if s.get("name") == name:
                return s
    raise Refused(f"No set named {name!r} on the PC")


def _validate_active(pool: list, ids) -> list[str]:
    """`active` — the <=4 pool commands that ride the D-pad, BY ID.

    Refused rather than trimmed when an id is unknown: a phone asking for a
    command this PC's pool does not have is a phone working from a stale
    `actions` frame, and quietly honouring the half it recognises would leave
    him looking at a D-pad he did not choose with no idea why."""
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise Refused("The set editor sent a broken button list")
    if not ids:
        raise Refused("A set needs at least one button")
    if len(ids) > DPAD_SLOTS:
        raise Refused(f"A D-pad holds {DPAD_SLOTS} buttons — {len(ids)} were sent")
    if len(set(ids)) != len(ids):
        raise Refused("The same button was chosen twice")
    known = {button_id(b) for b in pool}
    missing = [i for i in ids if i not in known]
    if missing:
        raise Refused(f"This PC has no command {missing[0]!r} in that set")
    return list(ids)


def _validate_order(value, n: int, which: str) -> list[int]:
    """`order_land` / `order_port` — a PERMUTATION of the active list's own
    positions, which is exactly what the client's `renderGroup` will accept.
    Anything else is refused here rather than falling back at render time: a
    silently-ignored arrangement is the one failure mode this feature has, and
    it is the one he already reported for the layout Move handle."""
    if not isinstance(value, list) or len(value) != n:
        raise Refused(f"The {which} arrangement does not fit {n} buttons")
    if sorted(value) != list(range(n)):
        raise Refused(f"The {which} arrangement is not a valid order")
    return [int(v) for v in value]


def apply_update(data: dict, msg: dict) -> tuple[str, dict]:
    """Validate `msg` against `data` (a loaded actions.json) and write the
    accepted keys INTO it. Pure — no file, no socket, no Qt — so its gate can
    drive every refusal by argument.

    Returns (set name, the keys written). Raises `Refused` with the phone's
    own sentence for anything it will not do.
    """
    name = msg.get("set")
    if not isinstance(name, str) or not name:
        raise Refused("The set editor did not say which set")
    # THE ALLOWLIST IS OVER WHAT ARRIVED, not over what we happen to read.
    # A message carrying `enabled`, `buttons`, `process`, `required` — anything
    # outside PHONE_EDITABLE — is refused WHOLE rather than filtered: a phone
    # (or anything on the LAN holding the token) that tried to rewrite a set's
    # commands must be told no, not partially obeyed.
    extra = sorted(k for k in msg if k not in PHONE_EDITABLE and k not in ("type", "set"))
    if extra:
        raise Refused(f"The set editor may not change {extra[0]!r}")

    target = _find_set(data, name)
    pool = target.get("buttons") or []
    written: dict = {}
    active = _validate_active(pool, msg.get("active"))
    written["active"] = active
    # Both orders are optional and are validated against the NEW active list's
    # length — the phone edits one orientation at a time, and the other one is
    # sent as the identity it was reset to (client/set-editor.js says so on the
    # card). An order for a different number of buttons cannot be honoured and
    # is refused, never trimmed.
    for key, which in (("order_land", "D-pad"), ("order_port", "column")):
        if key in msg:
            written[key] = _validate_order(msg[key], len(active), which)
    target.update(written)
    return name, written


def _user_path() -> Path:
    """The writable actions.json — the SAME file the desktop editor writes.

    `user_actions_path()` seeds the %LOCALAPPDATA% copy on a frozen install and
    repoints the running SETTINGS at it, so a phone edit made before the owner
    has ever opened the Controls editor still lands in his own file rather than
    failing against read-only Program Files."""
    try:
        from gui.controls_data import user_actions_path
        return user_actions_path()
    except Exception:  # PySide6-free headless CLI, or a dev checkout
        return Path(SETTINGS.actions_path)


def save_update(msg: dict) -> tuple[str, dict]:
    """Read -> validate -> write, on the real file. Blocking; call it in a
    thread. Raises `Refused`, or OSError/JSONDecodeError for a file that
    cannot be read — the caller turns both into one honest toast."""
    path = _user_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    name, written = apply_update(data, msg)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return name, written


async def send_actions(ws, saved=None) -> None:
    """The `actions` frame — the sets, as the phone must read them. One
    sender, used both by the first frame after `auth` and by the re-broadcast
    below, so the two can never carry different fields."""
    frame = {"type": "actions", **load_actions()}
    if saved is not None:
        frame["saved"] = saved
    await ws.send_text(json.dumps(frame))


async def actions_update(ws, msg: dict, saved=None) -> None:
    """The `actions_update` handler — the phone's set editor, saving.

    The re-broadcast is the point of the whole message. Without it his edit
    would sit in a file until the next reconnect, and "I changed it and nothing
    happened" is a bug report this project has already answered four times.
    """
    try:
        name, written = await asyncio.to_thread(save_update, msg)
    except Refused as e:
        logger.warning("Set edit refused: %s (message %r)", e, msg)
        await ws.send_text(json.dumps({"type": "toast", "text": str(e)}))
        return
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Set edit could not be saved: %s", e)
        await ws.send_text(json.dumps(
            {"type": "toast", "text": "The PC could not save that — see server log"}))
        return
    logger.info("Set %r edited from the phone: %s", name, written)
    await send_actions(ws, saved)
    await ws.send_text(json.dumps({"type": "toast", "text": f"{name} saved"}))
