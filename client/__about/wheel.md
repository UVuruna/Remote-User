# Wheel — the category ring

**Folder:** [Client](../___client.md) · code: [wheel.js](../wheel.js) ·
**Geometry:** [Chrome](chrome.md) · **What it changes:** [Controls](controls.md)

## Purpose

The ring a group's dashed centre button opens: one circle per category, a tap
picks one, the ✕ or the backdrop cancels. Which sets ride it, in what order,
and how many fit is [Sets](sets.md)'s answer — this module only draws whatever
list it is given and reports the pick.

Split out of [Controls](controls.md) on 2026-08-13, when the rotation fix
below pushed that file past THE STRUCTURE LAW's 1,000 lines. The seam is a
real one: the wheel has its own state (which side is open), its own geometry
and its own lifecycle, and was never a paragraph of "everything that drives
the PC". It does drive the PC in the end — a pick changes which commands the
D-pad sends — which is why it is here and not in [Chrome](chrome.md), whose
stated boundary is that nothing in it ever reaches the PC.

## The ring follows the screen (owner report 2026-08-13)

With a set open he rotated the desktop from portrait to landscape and **the
wheel slid half off the edge**, only a little of it left visible.

The cause is one word: ABSOLUTE. `wheelPoints` returns pixel coordinates
measured against the viewport of the moment, and `openWheel` wrote them into
each item's `left`/`top` **once**. Nothing recomputed them, so after a
rotation every circle still sat around where the OLD screen's centre had been
— and on a screen that swapped its axes, that centre is off to one side.

So the layout is a function that can be RE-RUN (`layoutWheel`), and it is
re-run on `resize`, on `orientationchange`, and on `visualViewport`'s own
resize — the last for the same reason the layout bar and the renderer listen
to it: on Android the soft keyboard and the system bars move that viewport
without ever firing a window resize. Only the positions and the face size are
rewritten; the items themselves are left alone, because rebuilding them would
drop a press a finger already had on one of them.

## The circles must not touch (owner 2026-08-13)

His words, in translation: he likes the bigger circles, *"but shrink them a
few pixels so a little space is left between them — not much, but some"*.

The radius was a flat 118 px that knew nothing about how many items it was
arranging or how big they were, so the spacing fell out **by accident**.
Neighbouring centres sit `2·r·sin(π/n)` apart:

| items | old spacing at r=118 | face | result |
|-------|---------------------|------|--------|
| 8 | 90.3 px | 90 px | touching exactly |
| 10 (task 181's cap) | 72.9 px | 90 px | **17 px overlap** |

The mini radial had always derived its radius from its own face and gap
(`MINI_RADIUS`); the wheel simply never did. Now `wheelLayout` (in
[Chrome](chrome.md), pure) derives it the same way, and the shrink he asked
for is the LAST resort rather than the first move — the ladder this project
uses everywhere: **open the ring out until the gap fits, and only when the
screen will not allow that radius do the circles give up pixels.** Both faces
also lost 4 px as he asked (74 → 70, and 90 → 86 for the two-line wrap),
which is what makes an 8 px gap affordable at ten items on a phone.

`wheelLayout` returns `{radius, size, points}`; `size` is what the circles
must ACTUALLY be after the ladder, and both `openWheel` and `layoutWheel`
write it into `--wheel-item-size`. Writing `wheelItemSize` alone would put an
86 px circle on a 70 px plan.

## Gate

`tests/test_wheel_geometry.py` drives every count and screen shape through the
pure functions: the gap is never negative, no circle leaves the screen at any
supported size in either orientation, and the shrink only happens when the
radius genuinely cannot grow. The phone audit stages the ring itself
(`tests/_audit_panels.py` → the wheel stages), which is what measures the
two-line label's clearance from its own rim on the live page.
