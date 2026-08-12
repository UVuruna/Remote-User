"""STREAM CARD GATE (owner ballot 2026-08-12, option A; his ticked verdict of
four levels the same day).

The desktop STREAM card is Monitor + ONE Quality dropdown of named steps + a
Custom… disclosure. The STEPS ARE THE OWNER'S OWN — four levels, his numbers
(20/60, 12/30, 6/10, 2/2… see `config.QUALITY_LADDER`) — and the phone offers
exactly the same four, as ABSOLUTE numbers rather than percentages of a base
that can move. He attached one condition to the shape itself: "just make sure
you connect Data saver to mobile data, the mechanic we already have."

That sentence is the whole reason this file exists, and it names a failure this
project has met before: a feature described in two places drifts, and the copy
nobody is looking at is the one that goes wrong. Here the two places are two
LANGUAGES. So every check below measures a door against ONE table
(`config.QUALITY_LADDER`, whose bottom rung is `config.DATA_SAVER` /
`DATA_SAVER_BITRATE`), never against a fixture written to match it — and the
phone-side checks READ client/quality.js, a file this gate may not edit, so the
day someone retunes one side alone the build stops.

What is proven here:

  A. Four named steps exist, they are HIS numbers, and each label carries the
     numbers it sets. A step that says "60 fps, 20 Mbps" and sets something
     else is the exact lie the descriptive shape was chosen to prevent.
 A2. THE LADDER IS A LADDER: going DOWN the list neither axis may rise, the
     BITRATE must fall STRICTLY (the rule that replaced a wrong one of mine —
     the retraction is written out where it stood), no adjacent bitrate drop
     is a cliff, the shipped default lands on a NAMED step, and every step's
     numbers really exist in the Custom combos it writes them into.
  B. The Data saver step IS `config.DATA_SAVER` — its fps and its bitrate,
     read from the one table.
  C. The legacy `reduced:true` door maps to the same table.
  D. THE PHONE'S FOUR ARE THE PC'S FOUR, rung for rung, read out of the real
     page source; its cellular level IS the bottom rung on both sides; it may
     never out-bid the PC; and a page still speaking high/mid/low keeps
     working.
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


class _FakeStream:
    """Just enough of a live stream for `config.stream_base` to read."""
    stream_size = (2560, 1440)
    width, height = 3840, 2160


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
    assert len(steps) == 4, f"expected four quality steps, found {len(steps)}"
    names = [label.split("—")[0].strip() for label, _, _ in steps]
    assert names == ["Max", "Smooth", "Sharp", "Data saver"], names
    # His numbers, checked as numbers and not as a name (owner verdict
    # 2026-08-12): 20/60, 12/30, 6/10, 2/10.
    got = [(fps, bitrate_bps(br)) for _, fps, br in steps]
    assert got == [(60, 20_000_000), (30, 12_000_000),
                   (10, 6_000_000), (10, 2_000_000)], got
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


# ── A RULE OF MINE THAT WAS WRONG, AND IS DELETED ─────────────────────────────
#
# `check_bits_per_frame_never_rises` used to stand HERE. It required that a
# step never spend more bits per frame than the step above it, on the argument
# that a lower rung rendering a SHARPER picture makes its name a lie. That rule
# was MINE — I invented it in the round that proposed the five-step table — and
# the owner's own ladder (his ticked verdict, 2026-08-12) breaks it on purpose:
#
#     Max         60 fps  20 Mbps    333k bits/frame
#     Smooth      30 fps  12 Mbps    400k      <- rises
#     Sharp       10 fps   6 Mbps    600k      <- rises
#     Data saver  10 fps   2 Mbps    200k
#
# HE IS RIGHT AND THE RULE WAS WRONG. His instruction was to sort the levels so
# the PICTURE stays decently good everywhere. Going down his ladder, SMOOTHNESS
# is what is spent (60 → 30 → 10) and the picture itself only at the bottom;
# my rule would have forced a little of both to be traded at every step, which
# is a worse ladder for the person watching. "Bits per frame" is a number, not
# something he sees; a stutter and a mush are both things he sees, and his
# ordering picks which one he meets first.
#
# What survives is the NARROWER invariant that actually catches the complaint
# my rule was invented for — `check_the_bitrate_falls_strictly`, below. The
# table he rejected had High and Balanced BOTH at 12 Mbps, so the lower step
# rendered strictly sharper and its humbler name was a lie; his ladder passes
# a strict-descent check comfortably. Do not reinstate the bits-per-frame rule.

def check_the_bitrate_falls_strictly():
    """The replacement, and the rule his rejected table really broke: going
    DOWN the ladder the bitrate must fall STRICTLY at every step.

    Two steps at the SAME bitrate is the defect he saw — the lower one runs
    at fewer frames, so it renders a strictly sharper picture while wearing
    the humbler name. Equal is therefore not good enough; it has to fall."""
    card = _card()
    steps = card.QUALITY_STEPS
    for (upper, _, up_br), (lower, _, low_br) in zip(steps, steps[1:]):
        assert bitrate_bps(low_br) < bitrate_bps(up_br), (
            f"{lower!r} does not carry LESS bitrate than {upper!r} above it "
            f"({low_br} vs {up_br}) — two steps at the same bitrate mean the "
            "lower one renders a sharper picture under a humbler name, which "
            "is the exact table the owner rejected on 2026-08-12")


def check_no_cliff_between_adjacent_bitrates():
    """The owner's second rejection: 12 Mbps straight to 1.2 Mbps is a factor
    of TEN with nothing in between, so a link that cannot hold one step has
    only the saving profile left.

    THE COMPARISON MUST ADMIT EXACTLY 3x AND REFUSE ABOVE IT. His own bottom
    step is 6 -> 2 Mbps, which is 3.0 on the nose, so a strict `<` here would
    fail his ladder for being precisely at the limit rather than past it —
    the limit is a ceiling, and a value ON a ceiling is under it. Both sides
    come from `bitrate_bps`, which returns exact integers, so 3.0 really is
    3.0 and there is no float fuzz for the boundary to fall through."""
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
    assert named.startswith("Smooth"), named


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

def _phone_ladder():
    """The phone's own four levels, read out of client/quality.js. This gate
    may not edit that file, so it READS it — the same technique that has kept
    the cellular profile honest across the two languages since this file was
    written. The literal is deliberately JSON-shaped on that side."""
    source = QUALITY_JS.read_text(encoding="utf-8")
    match = re.search(r"const QUALITY_LEVELS = (\[[\s\S]*?\n\]);", source)
    assert match, ("client/quality.js no longer has a readable QUALITY_LEVELS "
                   "table — this gate cannot prove the two ladders agree, "
                   "which is worse than a mismatch")
    return json.loads(match.group(1)), source


def check_the_phone_offers_the_same_four_levels():
    """THE OWNER'S VERDICT, MADE MECHANICAL (2026-08-12). The phone offers the
    SAME four levels as absolute numbers — no longer percentages of a base
    that can move. Rung for rung, id, label, fps and bitrate.

    This is what dissolves a mismatch that used to be written up as
    unavoidable: the desktop's Data saver step and the phone's cellular level
    are now the same numbers BY CONSTRUCTION, and this check is where that
    claim is kept rather than in a comment."""
    phone, _ = _phone_ladder()
    desk = [dict(rung) for rung in config.QUALITY_LADDER]
    assert phone == desk, (
        "the phone's ladder and the PC's have drifted apart\n"
        f"  client/quality.js : {phone}\n"
        f"  config.QUALITY_LADDER: {desk}")


def check_the_cellular_level_is_the_bottom_rung():
    """Auto-on-cellular picks the BOTTOM level (his verdict, 2026-08-12) —
    proven on BOTH sides of the wire from the same one table.

    On the server: `config.DATA_SAVER` is the last rung read out. On the
    phone: the cellular branch returns `dataSaverQuality()`, which is built
    from the last rung of the phone's own ladder rather than typed — so
    moving the bottom rung moves the cellular profile with it, and this check
    computes what that function must return and compares it to DATA_SAVER."""
    phone, source = _phone_ladder()
    bottom = phone[-1]
    assert re.search(
        r"p\.auto\s*&&\s*transportCellular\(\)\)\s*return\s+dataSaverQuality\(\)",
        source), ("client/quality.js no longer sends the saving profile on "
                  "cellular by reading its own bottom rung")
    assert re.search(r"function dataSaverQuality\(\)\s*\{\s*return \{ fps: "
                     r"DATA_SAVER_LEVEL\.fps, res: \"1/2\", bitrate: "
                     r"DATA_SAVER_LEVEL\.id \};", source), (
        "dataSaverQuality() no longer derives from the ladder's bottom rung — "
        "a typed-out copy is exactly the drift this check exists to stop")
    computed = {"fps": bottom["fps"], "res": "1/2", "bitrate": bottom["id"]}
    assert computed == DATA_SAVER, (
        f"the phone sends {computed} on mobile data while the one definition "
        f"(config.DATA_SAVER) is {DATA_SAVER} — the desktop's bottom step and "
        "the phone's cellular level have drifted apart")
    # …and the server's own copy is the bottom rung too, not a coincidence.
    assert DATA_SAVER["bitrate"] == config.QUALITY_LADDER[-1]["id"]
    assert DATA_SAVER["fps"] == config.QUALITY_LADDER[-1]["fps"]


def check_the_phone_may_never_out_bid_the_pc():
    """"At or below what the PC is set to, and nothing above." The clamp lives
    in `config.bitrate_for_level`, so it holds whatever an old or hand-edited
    page asks for."""
    saved = SETTINGS.h264_bitrate
    try:
        config.apply(h264_bitrate="6M")           # the PC on the "sharp" rung
        assert bitrate_bps(config.bitrate_for_level("max")) == 6_000_000, (
            "a phone asking for the Max rung on a 6 Mbps PC got more than the "
            "PC allows")
        assert config.bitrate_for_level("saver") == "2M"
        assert config.bitrate_for_level("high") == "6M"   # follow-the-PC sentinel
        assert config.bitrate_for_level(None) == "6M"
        assert config.stream_base(_FakeStream())["level"] == "sharp"
    finally:
        config.apply(h264_bitrate=saved)


def check_an_old_page_still_works():
    """A page older than the ladder says "high"/"mid"/"low" on the wire, and a
    page older than the quality panel says `reduced:true`. Both must keep
    working — the levels are ours to rename, his phone's install is not."""
    saved = SETTINGS.h264_bitrate
    try:
        config.apply(h264_bitrate="20M")
        assert config.bitrate_for_level("high") == "20M"
        assert config.bitrate_for_level("mid") == "6M"    # translated to a rung
        assert config.bitrate_for_level("low") == "2M"    # …the bottom rung
        assert quality_override({"reduced": True}) == DATA_SAVER
        assert quality_override({"reduced": False}) is None
        # A saved pref of "mid"/"low" on the phone is translated too, not
        # dropped to a default the owner never picked.
        source = QUALITY_JS.read_text(encoding="utf-8")
        assert 'const LEGACY_BR = { mid: "sharp", low: "saver" };' in source
    finally:
        config.apply(h264_bitrate=saved)


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
    ("four named steps, HIS numbers, each carrying its own",
     check_four_steps_each_carrying_its_own_numbers),
    ("the ladder falls on BOTH axes",
     check_the_ladder_falls_on_both_axes),
    ("the bitrate falls STRICTLY at every step",
     check_the_bitrate_falls_strictly),
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
    ("the phone offers the SAME four levels, as absolute numbers",
     check_the_phone_offers_the_same_four_levels),
    ("auto-on-cellular IS the bottom rung, on both sides of the wire",
     check_the_cellular_level_is_the_bottom_rung),
    ("the phone may never out-bid the PC",
     check_the_phone_may_never_out_bid_the_pc),
    ("an old page's high/mid/low and reduced:true still work",
     check_an_old_page_still_works),
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
