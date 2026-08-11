"""actions.json data plumbing for the Controls editor — no Qt in this module.

Split out of `controls_editor.py` (THE STRUCTURE LAW, build round R5,
2026-08-07 — the owner's "choose the wheel order" round pushed the dialog
module toward the 1,000-line threshold again). The file used to hold three
different jobs at once: FILE I/O + the shipped-pool MERGE (this module),
per-set/per-wheel ORDER EDITING (see [controls_order.py](controls_order.py))
and the WINDOW that assembles both into one dialog (`controls_editor.py`).
The responsibility line drawn here is testability: everything in this module
is a plain function over `dict`/`Path` — `tests/test_controls_sets.py` already
imported `merge_shipped_pools`/`active_buttons` directly, with no
`QApplication` in sight, which is the proof the split is real rather than a
line-count trim. Qt widgets (and the dialog that owns them) import FROM here;
nothing here imports a widget.
"""

import json
import logging
import re
from pathlib import Path

from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT, SETTINGS, USER_DIR, apply as apply_settings

logger = logging.getLogger(__name__)

DPAD_SLOTS = 4  # a D-pad cross has exactly four positions — the pool may be
                # longer, the phone still shows four (owner 2026-08-05)

WHEEL_MAX = 8  # sets in the phone's wheel at once, FIXED mode; Mouse/Input/
               # Settings are `required` (never hidden), everything else
               # toggles (owner 2026-08-05)
WHEEL_MAX_DROPOUT = 10  # DROP-OUT mode's cap (task 181, 2026-08-11 — the
                         # default): a set placed on either D-pad group sheds
                         # off the wheel while it rides there, which is the
                         # room the higher cap counts on.

# The file's own sections, in the order a fresh file lists them — this IS
# "today's order" (build round R5, 2026-08-07): the default `wheel_order`
# ships as exactly this sequence, so an owner who never opens the new list
# sees no change to his wheel.
SECTION_KEYS = ("categories", "app_sets", "custom_sets")

# ══════════════════════ THE OWNERSHIP RULE (2026-08-07) ══════════════════════
# A user's actions.json is SEEDED ONCE, at his first install, and is never
# replaced again — so the only way anything we invent later reaches him is
# this merge. Until today the merge copied a HARDCODED LIST of fields
# (`name, icon, required, process, title`), which means every field invented
# after that list was written silently never arrived. It cost the owner four
# releases: the shipped Claude app set gained `"agent": "claude"` on
# 2026-08-06, his copy never did, the set could only ever match by TITLE, and
# Claude Code names its VS Code tab after the CONVERSATION — an unsatisfiable
# condition, forever. It was the same engine that kept "Anywhere" in his
# Settings set after an update, and it was about to eat `wheel_order` too.
#
# So the list is INVERTED. It no longer names what WE deliver (a list that can
# only ever be out of date) — it names what HE OWNS, which is a short, stable,
# product-level fact:
#
#   OURS   → every key of a built-in / app set, and every top-level key, that
#            is not named below. Always taken from the shipped file. A key the
#            shipped file has RETIRED is deleted from his copy too, so a field
#            we stopped honouring cannot linger and lie.
#   HIS    → the keys below. Kept EXACTLY as he left them if he has them, and
#            SEEDED from the shipped file if he does not — a default he has
#            never expressed an opinion about is not an opinion to protect
#            (this is what finally delivers `wheel_order` to a file predating
#            it, while an owner who has arranged his wheel keeps his order).
#
# The rule works for fields NOBODY HAS INVENTED YET, which is the whole point.
# The one discipline it demands: **a new key the owner may edit MUST be added
# to one of these two sets in the same commit that makes it editable** — the
# editor and the phone must never be the only places that know. Button
# renames are the documented third owner-owned thing and are carried over by
# command ID inside `_merge_set` (a rename is per-button, not per-set).
OWNER_SET_KEYS = frozenset({"active", "order_land", "order_port", "enabled"})
# "wheel_mode" (task 181, 2026-08-11): "dropout" (default) or "fixed" — the
# Controls editor's tucked-away switch beside "Wheel order…". Owner-owned for
# the same reason wheel_order is: a default he never expressed an opinion
# about is seeded from shipped, a choice he made is kept exactly as he left it.
OWNER_TOP_KEYS = frozenset({"wheel_order", "left", "right", "wheel_mode"})
# Sets that are OURS, merged one by one below; `custom_sets` is his entirely
# and is never touched by any part of this module.
MERGED_SECTIONS = ("categories", "app_sets")


def user_actions_path() -> Path:
    """The writable actions.json. In the installed app the bundled default is
    read-only (Program Files), so the first use seeds the %LOCALAPPDATA% copy
    and repoints the RUNNING server at it (edits reach the phone on its next
    connection, no restart)."""
    path = Path(SETTINGS.actions_path)
    if not FROZEN:
        return path
    user_copy = USER_DIR / "actions.json"
    if not user_copy.exists():
        user_copy.parent.mkdir(parents=True, exist_ok=True)
        user_copy.write_bytes(path.read_bytes())
    apply_settings(actions_path=user_copy)
    return user_copy


def shipped_actions_path() -> Path:
    """The actions.json we SHIP — the source of every built-in set's command
    pool (and of the default `wheel_order`). It stays reachable after
    `user_actions_path()` repoints SETTINGS, which is what lets a new
    version's reserve commands reach an owner who already has his own copy."""
    return (BUNDLE_DIR if FROZEN else PROJECT_ROOT) / "actions.json"


def load_client_table(name: str, line_re: str,
                      source: str = "controls.js") -> dict[str, tuple[str, ...]]:
    """Parses a `const <name> = {...}` table out of a client script — one
    entry per line. Returns {} on any surprise (the editor then falls back to
    plain names — never a crash)."""
    try:
        text = (SETTINGS.client_dir / source).read_text(encoding="utf-8")
        block = re.search(r"const " + name + r" = \{(.*?)\n\};", text, re.S)
        if not block:
            return {}
        out: dict[str, tuple[str, ...]] = {}
        for line in block.group(1).splitlines():
            m = re.match(line_re, line)
            if m:
                out[m.group(1)] = tuple(m.groups()[1:])
        return out
    except OSError as e:
        logger.warning("Client table %s unavailable for the editor: %s", name, e)
        return {}


def load_client_icons() -> dict[str, str]:
    """{icon name: svg fragment} — the phone's own icon set. It lives in
    client/icons.js since the 2026-08-05 icon round (before that, in
    controls.js beside the actions)."""
    table = load_client_table("ICONS", r"\s*([A-Za-z0-9_]+):\s*'(.*)',?\s*$",
                              source="icons.js")
    return {name: body[0] for name, body in table.items()}


def load_client_builtins() -> dict[str, tuple[str, str]]:
    """{action: (label, icon)} — what the PHONE draws for a built-in action.
    The editor shows these instead of an empty field, so a built-in row tells
    the truth about the button it configures."""
    return load_client_table(
        "BUILTINS",
        r'\s*([A-Za-z0-9_]+):\s*\{[^}]*label:\s*"([^"]*)"[^}]*icon:\s*"([^"]*)"')


def button_id(btn: dict) -> str:
    """Stable identity of a pool command — what `active` stores. Explicit
    `id` wins; otherwise the action / chord / key / label, which are unique
    inside one set. IDs (not indices) survive a later version inserting or
    reordering pool commands."""
    return (btn.get("id") or btn.get("action") or btn.get("chord")
            or btn.get("key") or btn.get("label") or "")


def active_buttons(s: dict) -> list[dict]:
    """The ≤4 commands of `s` that sit on the D-pad — mirrors the client's
    activeButtons(): `active` by ID, or the first four (pre-pool behaviour)."""
    pool = s.get("buttons") or []
    ids = s.get("active")
    if not isinstance(ids, list):
        return pool[:DPAD_SLOTS]
    picked: list[dict] = []
    by_id = {button_id(b): b for b in pool}
    for i in ids:
        b = by_id.get(i)
        if b is not None and b not in picked:
            picked.append(b)
        if len(picked) == DPAD_SLOTS:
            break
    return picked or pool[:DPAD_SLOTS]


def _clone(value):
    """A deep copy that cannot share structure with the shipped dict — the
    user file is written back to disk, the shipped one is read again next
    start, and an aliased list would let one edit the other."""
    return json.loads(json.dumps(value))


def _merge_set(mine: dict, ship: dict) -> None:
    """One built-in / app set, migrated onto the shipped version of itself,
    under THE OWNERSHIP RULE above.

    His RENAMES survive (owner 2026-08-05): he may rename any button of a
    built-in set — Btn 4 / Btn 5 carry whatever his mouse driver puts on them
    — and a pool refresh that overwrote those names would quietly undo the
    only thing he is allowed to change here. Names are carried BY COMMAND ID,
    so a reordered or extended pool keeps them pointing at the right button.
    """
    renamed = {button_id(b): b["label"] for b in (mine.get("buttons") or [])
               if b.get("action") and b.get("label")}
    for key, value in ship.items():
        if key in OWNER_SET_KEYS:
            mine.setdefault(key, _clone(value))  # seed only what he lacks
        else:
            mine[key] = _clone(value)            # ours, whatever it is called
    for stale in [k for k in list(mine)
                  if k not in ship and k not in OWNER_SET_KEYS]:
        del mine[stale]                          # a field we retired
    for b in mine.get("buttons") or []:
        name = renamed.get(button_id(b))
        if name:
            b["label"] = name
    # A pool refresh can leave `active` pointing at a command that is no
    # longer in it — from a version that dropped one, or from a file the
    # editor corrupted before its write-guard existed. A choice that cannot be
    # honoured is not a choice: fall back to the shipped four rather than to a
    # two-button D-pad.
    ids = {button_id(b) for b in (mine.get("buttons") or [])}
    if not set(mine.get("active") or []) <= ids:
        mine.pop("active", None)


def merge_shipped_pools(data: dict, shipped: dict) -> None:
    """Migrates the owner's actions.json onto the SHIPPED one — the only path
    a new version has into a file that was seeded once and never replaced.

    Read THE OWNERSHIP RULE at the top of this module first: it is what
    decides, for every key that exists now or will ever exist, whether the
    shipped value wins or his does. This function is deliberately NOT a list
    of today's field names; a list is what shipped the 2026-08-07 failure
    (`agent` never reaching his Claude set through four releases).

    Three things happen, in this order:
      1. every top-level key — `wheel_order` included — under the rule;
      2. every built-in and app set, matched BY NAME, under the rule;
      3. a set we newly ship that he has never had is added whole.

    A set he has that we no longer ship is left alone: it may be a set that
    moved, and silently deleting a wheel entry is the failure this whole
    module exists to stop. `custom_sets` is his and is never touched.

    The name says "pools" for one reason only: `server/web.py` imports it by
    that name and that file sits on the STRUCTURE LAW's line limit. The
    responsibility is the whole migration.
    """
    for key, value in shipped.items():
        if key in MERGED_SECTIONS or key == "custom_sets":
            continue
        if key in OWNER_TOP_KEYS:
            data.setdefault(key, _clone(value))
        else:
            data[key] = _clone(value)
    for stale in [k for k in list(data)
                  if k not in shipped and k not in OWNER_TOP_KEYS
                  and k not in MERGED_SECTIONS and k != "custom_sets"]:
        del data[stale]
    # Both lists are keyed by NAME. App sets used to be keyed by `process`,
    # and that was the 2026-08-05 bug the owner hit within the hour: Claude
    # runs inside VSCode, so BOTH shipped sets carry process "code", the map
    # held one entry for that key, and merging Claude on top of it renamed his
    # VSCode set out of existence ("zašto je nestao VSCode kad si ubacio
    # Claude"). A name is what tells two sets of one process apart — it is
    # also what the phone's picker and the wheel show.
    for key in MERGED_SECTIONS:
        mine = data.get(key) or []
        by_ident = {s.get("name"): s for s in mine}
        for ship in shipped.get(key) or []:
            s = by_ident.get(ship.get("name"))
            if s is None:
                mine.append(_clone(ship))  # a set we newly ship
                continue
            _merge_set(s, ship)
        data[key] = mine


def natural_order(data: dict) -> list[str]:
    """Every set's name, in the order the FILE itself lists them — categories,
    then app_sets, then custom_sets (`SECTION_KEYS`). This is what ships as
    the DEFAULT `wheel_order` in actions.json (a user who never opens the new
    list sees no change), and what a saved order falls back to for any set it
    does not mention."""
    return [s.get("name", "?") for key in SECTION_KEYS for s in (data.get(key) or [])]


def effective_wheel_order(data: dict) -> list[str]:
    """`wheel_order` as saved, filtered to sets the file still has and
    extended with any it does not mention — appended at the END (build round
    R5: "a set that exists but is not mentioned in wheel_order goes to the
    end"). Never mutates `data`; the caller decides whether to save the
    result back."""
    names = natural_order(data)
    saved = [n for n in (data.get("wheel_order") or []) if n in names]
    saved += [n for n in names if n not in saved]
    return saved
