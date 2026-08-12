# Stream Card

**Script:** [Stream Card (script)](../stream_card.py) · **Flow:** [flow](../__flow/stream_card.md)

## Purpose
The STREAM card of the [Settings Window](settings_window.md) — what this PC sends — and the four named quality steps behind it.

It was split out of `settings_window.py` on 2026-08-12 (THE STRUCTURE LAW). That window had reached 854 lines and this round grows the card rather than shrinks it: four steps, a Custom disclosure and the numbers behind both. The seam is a real responsibility and not a size trick — this module answers *what does the PC encode*, the window answers *which cards are in the column and how big must it be*. Nothing here knows about notifications, focus or startup; the window no longer knows a bitrate from a frame rate.

## Connections

### Uses
- [Config](../../__about/config.md) — `SETTINGS` (every value shown), `save_user_settings()` (the one writer), `bitrate_bps()` (label arithmetic) and **`DATA_SAVER` / `DATA_SAVER_BITRATE`**, the one definition of the saving profile
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

### The five steps — a LADDER, not a list of presets

| Step | Frame rate | Bitrate | bits/frame |
|------|-----------|---------|-----------|
| Max | 60 fps | 20 Mbps | 333k |
| High | 60 fps | 12 Mbps | 200k |
| **Balanced** | 30 fps | 6 Mbps | 200k |
| Light | 20 fps | 3 Mbps | 150k |
| Data saver | 10 fps | 1.2 Mbps | 120k |

**The first draft had four steps and the owner rejected it** (2026-08-12), correctly, for two defects — and both are now rules with teeth:

1. **AN INVERTED LADDER.** High was 60 fps / 12 Mbps and Balanced 30 fps / 12 Mbps: the same bitrate at half the frame rate is TWICE the bits per frame, so "Balanced" would have rendered a SHARPER picture than "High". Both axes were non-rising, which is exactly why a third rule is needed — going DOWN the list, **bits per frame may not rise either**. A step below another must be worse in every way a person can perceive, or its name is a lie.
2. **A CLIFF.** 12 Mbps straight to 1.2 Mbps is a factor of ten with nothing in between, so a link that could not hold Balanced had only the saving profile left. **Light** fills it, and no adjacent bitrate drop now exceeds 2.5x (gated at `MAX_BITRATE_JUMP`, 3x — a ceiling against a future retune, not a description of today's table).

Balanced now means something that is actually true of it: **half the data and half the frames of High, at the same sharpness per frame.**

**Balanced is also the shipped default read out** (`target_fps` 30, `h264_bitrate` 6M) — deliberately, so a PC nobody has configured opens on a NAMED step instead of on the Custom entry. The default moved 12M → 6M in the same round, and it is defensible now in a way it would not have been a week ago: this round also added the region CROP and the device-panel SCALE, so the encoder is typically working at ~1920 wide instead of 3840, and 6 Mbps at that width is a better picture than 12 Mbps at 4K ever was — the bits are no longer spread over four times the pixels.

Every label is BUILT from its own values (`_step`), never typed beside them, so a step cannot advertise a number it does not set. And every value a step sets is offered by the Custom combos it writes into: `_select` falls back to index 0 for a value it cannot find, so a missing entry would make the dropdown say one thing and the encoder do another.

A PC whose saved values match no step (a hand-edited `settings.json`, an older release) gets an extra entry that STATES those numbers — `Custom — 30 fps, 12 Mbps` — rather than lighting a step that would be a lie.

## Data saver is not a fourth set of numbers

The owner attached one condition to this shape: *"just make sure you connect Data saver to mobile data, the mechanic we already have."*

Three doors reach that profile and there is ONE definition behind all three — [`config.DATA_SAVER`](../../__about/config.md):

1. **Automatically** — the phone's "save data on mobile networks" tick plus the `Android.transport()` bridge (`client/quality.js`).
2. **By hand** — this card's Data saver step.
3. **Legacy** — a page older than the quality panel sending `quality {reduced:true}`, mapped by `config.quality_override`.

`DATA_SAVER` is the per-client override shape; `DATA_SAVER_BITRATE` is the absolute number the `"low"` level resolves to at the shipped base, and it is what this card writes into `h264_bitrate` — because a base cannot be a percentage of itself.

## Resolution left the front of the card, not the product

The PC now scales to the watching device's panel, so a resolution the owner picks here is a ceiling he should not have to think about. `h264_max_width` is still a real setting, still user-adjustable, still reported to the phone by `config.stream_base`, still what a `res` step is measured against — and still written by this card's Apply, from behind Custom…. Removing the dial and removing the capability are different acts, and only the first was asked for.

A named step is a **(frame rate, bitrate) pair and nothing more**: picking one can never move the encoder width the owner is no longer shown.

## Why the three exact combos share one row
Ladder step 2, REFLOW ([GUI Rules](../../../../../rules/GUI.md) → Space & Legibility). This window's scarce axis is HEIGHT — it already spends most of the 1000 px the project's layout frame allows — while it has width to spare, so a disclosure that added three labelled rows would have bought its detail out of the only budget that binds. No sub-labels are invented because none are needed: every entry names its own unit ("2560 — QHD", "12 Mbps — default", "30 fps").

`settle()` pins those three combos to the widest of their own polished size hints, on first show. A QComboBox's *minimum* size hint is far smaller than its size hint, so three sharing a row are squeezed to a third of whatever the row has and the longest entry is clipped — the audit measured exactly that the first time this row was written (*"has 175x34, needs at least 181x34"*). And the hint is only correct after Qt has polished the widget, which is the same lesson `_align_label_column` carries and the reason both run from the same show.

## Gate
`tests/test_stream_card.py`, fail-closed in `setup/gates.py` (0at/6). It measures every Data-saver door against `config.DATA_SAVER` — including by READING the literal out of `client/quality.js`, so the two languages cannot drift — proves each step's label states the numbers it sets, enforces the LADDER (both axes non-rising, bits per frame non-rising, no adjacent drop past 3x, the shipped default on a NAMED step, every step selectable in Custom), and proves that removing Resolution from the card left the wire alone. Every check was proven by planting the defect it exists to catch.
