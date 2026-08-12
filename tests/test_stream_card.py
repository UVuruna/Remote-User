"""STREAM CARD GATE (owner ballot 2026-08-12, option A).

The desktop STREAM card became Monitor + ONE Quality dropdown of named steps +
a Custom… disclosure. The first draft offered four and the owner REJECTED it,
correctly, for two defects now written into checks below (an inverted ladder
and a tenfold cliff); the shipped table has five. He attached one condition to
the shape itself: "just make sure you connect Data saver to mobile data, the mechanic we
already have."

That sentence is the whole reason this file exists, and it names a failure this
project has met before: a feature described in two places drifts, and the copy
nobody is looking at is the one that goes wrong. "Data saver" is reachable by
three doors — the desktop step, the phone's auto-on-cellular switch, and a
legacy `quality {reduced:true}` from a page older than the quality panel — and
there must be ONE definition behind all three. It is `config.DATA_SAVER` (plus
`DATA_SAVER_BITRATE`, the absolute number the desktop step writes, because a
base cannot be a percentage of itself).

So every check below measures a door against THAT table, never against a
fixture written to match it. Check D in particular reads the literal out of
client/quality.js — the file this gate may not edit — so the day someone
retunes the profile on one side and not the other, the build stops.

What is proven here:

  A. Five named steps exist, and each label carries the numbers it sets.
     A step that says "60 fps, 20 Mbps" and sets something else is the exact
     lie the descriptive shape was chosen to prevent.
 A2. THE LADDER IS A LADDER (owner rejection 2026-08-12, both his defects made
     into rules): going DOWN the list neither axis may rise, BITS PER FRAME may
     not rise either — the check that sees an inverted ladder both other checks
     call fine — no adjacent bitrate drop is a cliff, the shipped default lands
     on a NAMED step, and every step's numbers really exist in the Custom
     combos it writes them into.
  B. The Data saver step IS `config.DATA_SAVER` — its fps and its bitrate,
     read from the one table.
  C. The legacy `reduced:true` door maps to the same table.
  D. client/quality.js's auto-on-cellular literal is the same profile. This is
     the drift check, and it reads the real page source.
  E. The `h264_reduced_*` settings derive from the same table.
  F. Removing Resolution from the front of the card did not change what the
     wire carries: `h264_max_width` is still a user-adjustable setting, still
     reported to the phone by `stream_base`, still what a `res` step is
     measured against, and still written by the card's own Apply.
  G. A Quality step never sets a resolution — it is a (fps, bitrate) pair, so
     picking one cannot silently move the encoder width the owner is no longer
     shown.

Run:  .venv\\Scripts\\python tests/test_stream_card.py
"""

import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import config  # noqa: E402
from config import (  # noqa: E402
    DATA_SAVER, DATA_SAVER_BITRATE, SETTINGS, USER_ADJUSTABLE, bitrate_bps,
    quality_override, stream_base,
)

QUALITY_JS = PROJECT / "client" / "quality.js"


def _card():
    """The card module WITHOUT a QApplication — it is imported for its tables,
    not for its widgets, and a gate that needed a live Qt would be a gate that
    stops running on the build machine."""
    sys.path.insert(0, str(PROJECT / "server"))
    import gui.stream_card as stream_card
    return stream_card


# --- A -----------------------------------------------------------------------

def check_four_steps_each_carrying_its_own_numbers():
    card = _card()
    steps = card.QUALITY_STEPS
    assert len(steps) == 5, f"expected five quality steps, found {len(steps)}"
    names = [label.split("—")[0].strip() for label, _, _ in steps]
    assert names == ["Max", "High", "Balanced", "Light", "Data saver"], names
    for label, fps, bitrate in steps:
        assert f"{fps} fps" in label, f"{label!r} does not state its {fps} fps"
        mbps = card.mbps_label(bitrate)
        assert mbps in label, f"{label!r} does not state its bitrate ({mbps})"
    # …and no two steps are the same stream wearing two names.
    pairs = {(fps, bitrate_bps(br)) for _, fps, br in steps}
    assert len(pairs) == len(steps), f"two steps set the same stream: {pairs}"


# --- A2: THE LADDER (owner rejection 2026-08-12) ------------------------------
# The four-step draft was rejected for two defects, and both are now rules with
# teeth. Each check below is written to fire on the EXACT table he rejected.

def check_the_ladder_falls_on_both_axes():
    """Going DOWN the list, neither the frame rate nor the bitrate may RISE.
    A step below another must be worse in every way a person can perceive, or
    its name is a lie."""
    card = _card()
    steps = card.QUALITY_STEPS
    for (upper, up_fps, up_br), (lower, low_fps, low_br) in zip(steps, steps[1:]):
        assert low_fps <= up_fps, (
            f"{lower!r} runs at MORE frames than {upper!r} above it "
            f"({low_fps} > {up_fps}) — the ladder inverts")
        assert bitrate_bps(low_br) <= bitrate_bps(up_br), (
            f"{lower!r} carries MORE bitrate than {upper!r} above it "
            f"({low_br} > {up_br}) — the ladder inverts")


def check_bits_per_frame_never_rises():
    """The check the rejected draft needed. High at 60 fps / 12 Mbps and
    Balanced at 30 fps / 12 Mbps share a bitrate — so Balanced gets TWICE the
    bits per frame and renders a SHARPER picture than the step above it. Both
    axes were non-rising there; only this one sees it."""
    card = _card()
    steps = card.QUALITY_STEPS
    for (upper, up_fps, up_br), (lower, low_fps, low_br) in zip(steps, steps[1:]):
        up_bpf = bitrate_bps(up_br) / max(1, up_fps)
        low_bpf = bitrate_bps(low_br) / max(1, low_fps)
        assert low_bpf <= up_bpf + 1, (
            f"{lower!r} spends MORE bits per frame than {upper!r} above it "
            f"({low_bpf:,.0f} > {up_bpf:,.0f}) — a lower step would render a "
            "SHARPER picture than the one above it, which is the ladder "
            "contradicting its own naming")


def check_no_cliff_between_adjacent_bitrates():
    """The owner's second rejection: 12 Mbps straight to 1.2 Mbps is a factor
    of TEN with nothing in between, so a link that cannot hold one step has
    only the saving profile left."""
    card = _card()
    steps = card.QUALITY_STEPS
    limit = card.MAX_BITRATE_JUMP
    for (upper, _, up_br), (lower, _, low_br) in zip(steps, steps[1:]):
        jump = bitrate_bps(up_br) / bitrate_bps(low_br)
        assert jump <= limit, (
            f"{upper!r} drops to {lower!r} by {jump:.1f}x, past the {limit}x "
            "ceiling — that is a cliff, and the step below a link that cannot "
            "hold this one has to be reachable")


def check_the_shipped_default_lands_on_a_named_step():
    """A fresh install must open this card on a NAMED step. The Custom entry
    is honest, and it is useless as a first impression — it tells a new owner
    that his PC is set to something the product has no word for."""
    card = _card()
    named = card.step_for(SETTINGS.target_fps, SETTINGS.h264_bitrate)
    assert named is not None, (
        f"the shipped default ({SETTINGS.target_fps} fps, "
        f"{SETTINGS.h264_bitrate}) matches no step — the card would open on "
        "the Custom entry on every fresh install")
    assert named.startswith("Balanced"), named


def check_every_step_is_selectable():
    """A step WRITES its numbers into the Custom combos, and `_select` falls
    back to index 0 for a value it cannot find — so a step whose bitrate is
    missing from `BITRATES` would silently set a different one. The dropdown
    would say one thing and the encoder do another."""
    card = _card()
    rates = {value for _, value in card.FPS_CHOICES}
    bitrates = {bitrate_bps(value) for _, value in card.BITRATES}
    for label, fps, bitrate in card.QUALITY_STEPS:
        assert fps in rates, f"{label!r} sets {fps} fps, which Custom cannot hold"
        assert bitrate_bps(bitrate) in bitrates, (
            f"{label!r} sets {bitrate}, which Custom cannot hold — picking the "
            "step would silently select the first entry instead")


# --- B -----------------------------------------------------------------------

def check_data_saver_is_the_one_profile():
    card = _card()
    label, fps, bitrate = card.QUALITY_STEPS[-1]
    assert label.startswith("Data saver"), label
    assert fps == DATA_SAVER["fps"], (
        f"the Data saver step runs at {fps} fps while the profile the phone "
        f"switches to on mobile data runs at {DATA_SAVER['fps']} — the two "
        "have drifted apart (config.DATA_SAVER is the one definition)")
    assert bitrate_bps(bitrate) == bitrate_bps(DATA_SAVER_BITRATE), (
        f"the Data saver step is {bitrate} while the profile is "
        f"{DATA_SAVER_BITRATE}")


# --- C -----------------------------------------------------------------------

def check_the_legacy_reduced_door_maps_to_the_same_profile():
    got = quality_override({"reduced": True})
    assert got == DATA_SAVER, (
        f"a legacy `quality {{reduced:true}}` resolves to {got}, not the one "
        f"profile {DATA_SAVER}")
    assert quality_override({"reduced": False}) is None


# --- D -----------------------------------------------------------------------

def check_the_phone_auto_switch_uses_the_same_profile():
    """The drift check. client/quality.js decides what to send while the
    handset is on cellular, and this gate may not edit that file — so it READS
    it. A literal there that stops matching `config.DATA_SAVER` fails the
    build, which is the only way one profile stays one profile across two
    languages."""
    source = QUALITY_JS.read_text(encoding="utf-8")
    match = re.search(
        r"p\.auto\s*&&\s*transportCellular\(\)\)\s*return\s*(\{[^}]*\})", source)
    assert match, ("client/quality.js no longer has a recognisable "
                   "auto-on-cellular return — this gate cannot prove the two "
                   "profiles agree, which is worse than a mismatch")
    literal = match.group(1)
    # A JS object literal with bare keys → JSON.
    as_json = re.sub(r"(\w+):", r'"\1":', literal).replace("'", '"')
    got = json.loads(as_json)
    assert got == DATA_SAVER, (
        f"client/quality.js sends {got} on mobile data while the one "
        f"definition (config.DATA_SAVER) is {DATA_SAVER} — the manual Data "
        "saver step and the automatic switch have drifted apart")


# --- E -----------------------------------------------------------------------

def check_the_reduced_settings_derive_from_the_profile():
    assert SETTINGS.h264_reduced_fps == DATA_SAVER["fps"]
    assert SETTINGS.h264_reduced_bitrate == DATA_SAVER_BITRATE
    assert SETTINGS.h264_reduced_scale == config.DATA_SAVER_SCALE


# --- F -----------------------------------------------------------------------

def check_resolution_left_the_card_and_not_the_wire():
    card = _card()
    # Still a real setting the owner's file may carry…
    assert "h264_max_width" in USER_ADJUSTABLE
    assert isinstance(SETTINGS.h264_max_width, int)
    # …still reported to the phone, which measures its own steps against it…
    class _Stream:
        stream_size = (2560, 1440)
        width, height = 3840, 2160
    base = stream_base(_Stream())
    assert base["width"] == 2560 and base["height"] == 1440, base
    # …still honoured as a per-client step…
    assert quality_override({"fps": 0, "res": "1/2", "bitrate": "high"}) == {
        "fps": 0, "res": "1/2", "bitrate": "high"}
    # …and still written by the card's own Apply, from behind Custom….
    apply_src = card.StreamCard.apply.__doc__ or ""
    source = (PROJECT / "server" / "gui" / "stream_card.py").read_text(encoding="utf-8")
    assert '"h264_max_width": self.resolution_combo.currentData()' in source, (
        "the card's Apply no longer saves h264_max_width — removing the dial "
        "was asked for, removing the capability was not")
    assert apply_src, "apply() lost the note explaining its one save path"
    assert card.RESOLUTIONS, "the resolution steps themselves are gone"


# --- G -----------------------------------------------------------------------

def check_a_quality_step_never_moves_the_resolution():
    card = _card()
    for step in card.QUALITY_STEPS:
        assert len(step) == 3, (
            f"a quality step carries {len(step)} values — it must be exactly "
            "(label, fps, bitrate); a step that also set a width would move "
            "an encoder setting the owner is no longer shown")
    source = (PROJECT / "server" / "gui" / "stream_card.py").read_text(encoding="utf-8")
    picker = source.split("def _pick_step")[1].split("def _exact_changed")[0]
    assert "resolution_combo" not in picker, (
        "_pick_step touches the resolution combo — picking a named quality "
        "step must never change the encoder width")


CHECKS = [
    ("five named steps, each carrying its own numbers",
     check_four_steps_each_carrying_its_own_numbers),
    ("the ladder falls on BOTH axes",
     check_the_ladder_falls_on_both_axes),
    ("bits per frame never RISES going down the ladder",
     check_bits_per_frame_never_rises),
    ("no adjacent bitrate step is a cliff",
     check_no_cliff_between_adjacent_bitrates),
    ("the shipped default lands on a NAMED step",
     check_the_shipped_default_lands_on_a_named_step),
    ("every step's numbers exist in the Custom combos",
     check_every_step_is_selectable),
    ("Data saver IS config.DATA_SAVER, the one profile",
     check_data_saver_is_the_one_profile),
    ("the legacy reduced:true door maps to that same profile",
     check_the_legacy_reduced_door_maps_to_the_same_profile),
    ("the phone's auto-on-cellular switch uses that same profile",
     check_the_phone_auto_switch_uses_the_same_profile),
    ("the h264_reduced_* settings derive from it",
     check_the_reduced_settings_derive_from_the_profile),
    ("resolution left the card, not the wire",
     check_resolution_left_the_card_and_not_the_wire),
    ("a quality step never moves the resolution",
     check_a_quality_step_never_moves_the_resolution),
]


def main() -> int:
    print("\n=== STREAM CARD GATE ===")
    failed = 0
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nSTREAM CARD GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nSTREAM CARD GATE PASSED — a ladder that really falls, and Data "
          "saver is "
          "the same profile mobile data already switches to.")
    return 0


def test_stream_card():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
