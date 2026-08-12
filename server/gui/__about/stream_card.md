# Stream Card

**Script:** [Stream Card (script)](../stream_card.py) · **Flow:** [flow](../__flow/stream_card.md)

## Purpose
The STREAM card of the [Settings Window](settings_window.md) — what this PC sends — and the four named quality steps behind it.

It was split out of `settings_window.py` on 2026-08-12 (THE STRUCTURE LAW). That window had reached 854 lines and this round grows the card rather than shrinks it: four steps, a Custom disclosure and the numbers behind both. The seam is a real responsibility and not a size trick — this module answers *what does the PC encode*, the window answers *which cards are in the column and how big must it be*. Nothing here knows about notifications, focus or startup; the window no longer knows a bitrate from a frame rate.

## Connections

### Uses
- [Config](../../__about/config.md) — `SETTINGS` (every value shown), `save_user_settings()` (the one writer), `bitrate_bps()` (label arithmetic) and **`QUALITY_LADDER`**, the ONE table of the owner's four levels (whose bottom rung is `DATA_SAVER`)
- [Settings Window](settings_window.md) — its `card()` / `section()` / `form()` / `row()` / `caption()` / `resettle()` helpers, so the card's rows line up with every other card's

### Used by
- [Settings Window](settings_window.md) — `_build_stream_card()` builds one `StreamCard` and keeps it as `self.stream_card`; the window's computed minimum imports this module's tables, and its first show calls `settle()`

## The card (owner ballot 2026-08-12, option A)

| Row | What it is |
|-----|-----------|
| **Monitor** | unchanged — a different question, and always was |
| **Quality** | ONE dropdown of four named steps, each carrying its own numbers |
| **Custom…** | a tick that reveals the exact values: Resolution · Bitrate · Frame rate, three combos on one row |
| **Apply & restart** | unchanged — these shape the encoder, so the server restarts |

It used to be four combos, three of which asked the owner to compose a stream out of parts. His verdict picked the descriptive shape, so what he reads is what he gets.

### His four levels — a LADDER, not a list of presets

| Step | Frame rate | Bitrate | bits/frame |
|------|-----------|---------|-----------|
| Max | 60 fps | 20 Mbps | 333k |
| **Smooth** | 30 fps | 12 Mbps | 400k |
| Sharp | 10 fps | 6 Mbps | 600k |
| Data saver | 10 fps | 2 Mbps | 200k |

**These are the owner's own numbers** (his ticked verdict, 2026-08-12), and the table itself lives in [`config.QUALITY_LADDER`](../../__about/config.md) so the phone's quality panel offers the identical four. This module only writes the numbers into labels.

**Bits per frame rise in the middle and that is the point.** An earlier round made *"bits per frame never rises"* a rule and gated it. That rule was OURS, not his, and his ladder breaks it deliberately and correctly: his instruction was to sort the levels so the PICTURE stays decently good everywhere, so going down the ladder SMOOTHNESS is what is spent (60 → 30 → 10) and the picture itself only at the bottom. Trading a little of both at every step — which our rule would have forced — is the worse ladder for the person watching. The retraction is written out where the deleted check stood, in `tests/test_stream_card.py`, so nobody reinstates it.

Two invariants survive, and they are the ones his rejected table really broke:

1. **THE BITRATE FALLS STRICTLY.** The rejected draft had High and Balanced BOTH at 12 Mbps, so the lower step rendered strictly sharper while wearing the humbler name. Equal is not good enough — it has to fall. (`check_the_bitrate_falls_strictly`; "fps never rises" stands beside it.)
2. **NO CLIFF.** 12 Mbps straight to 1.2 Mbps was a factor of ten with nothing in between. `MAX_BITRATE_JUMP` is 3.0 and the comparison must **admit exactly 3x** — his own bottom step, 6 → 2 Mbps, is 3.0 on the nose, so a strict `<` would fail his ladder for sitting precisely on a ceiling rather than past it. Both sides come from `bitrate_bps`, which returns exact integers, so there is no float fuzz for the boundary to fall through.

**Smooth is the shipped default read out** (`target_fps` 30, `h264_bitrate` 12M) — deliberately, so a PC nobody has configured opens on a NAMED step instead of on the Custom entry. The default had briefly moved to 6M earlier the same day; his ladder pairs 6 Mbps with 10 fps and has no 30 fps / 6 Mbps rung at all, so the pair had to land on one of his.

Every label is BUILT from its own values (`_step`), never typed beside them, so a step cannot advertise a number it does not set. And every value a step sets is offered by the Custom combos it writes into: `_select` falls back to index 0 for a value it cannot find, so a missing entry would make the dropdown say one thing and the encoder do another.

A PC whose saved values match no step (a hand-edited `settings.json`, an older release) gets an extra entry that STATES those numbers — `Custom — 30 fps, 12 Mbps` — rather than lighting a step that would be a lie.

## Data saver is simply the bottom rung

The owner attached one condition to this shape: *"just make sure you connect Data saver to mobile data, the mechanic we already have."*

Three doors reach that profile and there is ONE definition behind all three — the last rung of `QUALITY_LADDER`, read out as [`config.DATA_SAVER`](../../__about/config.md):

1. **Automatically** — the phone's "save data on mobile networks" tick plus the `Android.transport()` bridge (`client/quality.js` → `dataSaverQuality()`, itself derived from that side's bottom rung).
2. **By hand** — this card's Data saver step.
3. **Legacy** — a page older than the quality panel sending `quality {reduced:true}`, mapped by `config.quality_override`.

`DATA_SAVER` is the per-client override shape (`{fps 10, res "1/2", bitrate "saver"}`) and `DATA_SAVER_BITRATE` (`2M`) the absolute number this card writes into `h264_bitrate`. **The desktop step and the phone's cellular level are the same numbers by construction now** — they used to drift whenever the base moved, because the phone's steps were percentages of it; that percentage rule was never the owner's (his correction, 2026-08-12) and it is gone.

## Resolution left the front of the card, not the product

The PC now scales to the watching device's panel, so a resolution the owner picks here is a ceiling he should not have to think about. `h264_max_width` is still a real setting, still user-adjustable, still reported to the phone by `config.stream_base`, still what a `res` step is measured against — and still written by this card's Apply, from behind Custom…. Removing the dial and removing the capability are different acts, and only the first was asked for.

A named step is a **(frame rate, bitrate) pair and nothing more**: picking one can never move the encoder width the owner is no longer shown.

## Why the three exact combos share one row
Ladder step 2, REFLOW ([GUI Rules](../../../../../rules/GUI.md) → Space & Legibility). This window's scarce axis is HEIGHT — it already spends most of the 1000 px the project's layout frame allows — while it has width to spare, so a disclosure that added three labelled rows would have bought its detail out of the only budget that binds. No sub-labels are invented because none are needed: every entry names its own unit ("2560 — QHD", "12 Mbps — default", "30 fps").

`settle()` pins those three combos to the widest of their own polished size hints, on first show. A QComboBox's *minimum* size hint is far smaller than its size hint, so three sharing a row are squeezed to a third of whatever the row has and the longest entry is clipped — the audit measured exactly that the first time this row was written (*"has 175x34, needs at least 181x34"*). And the hint is only correct after Qt has polished the widget, which is the same lesson `_align_label_column` carries and the reason both run from the same show.

## Gate
`tests/test_stream_card.py`, fail-closed in `setup/gates.py` (0at/6). It measures every door against the one table — including by READING the phone's own `QUALITY_LEVELS` and `dataSaverQuality()` out of `client/quality.js`, so the two languages cannot drift — proves each step's label states the numbers it sets, enforces the LADDER (fps non-rising, **bitrate strictly falling**, no adjacent drop past 3x with 3x itself admitted, the shipped default on a NAMED step, every step selectable in Custom), proves the phone's four ARE the PC's four and may never out-bid it, proves a page still speaking `high`/`mid`/`low` or `reduced:true` keeps working, and proves that removing Resolution from the card left the wire alone. Every check was proven by planting the defect it exists to catch.
