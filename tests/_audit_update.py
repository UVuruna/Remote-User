"""THE UPDATE CARD'S OWN STAGE — split out of tests/_audit_panels.py on
2026-08-17 (THE STRUCTURE LAW: that file stood at 1,011 lines the moment
this card's four states were added to it).

THE UPDATE CARD HAD NEVER BEEN PHOTOGRAPHED — the same blindness that let
the loading overlay ship unphotographed for its whole life, and photographing
THAT overlay found two real defects on its first honest run (a label sitting
on the cube because a rotated 110px cube overflows its own box, and a
truncation tooth that had never met a progress ellipsis — see loading.js's
own __about for the full account). This card gained five states, a
percentage, a progress fill and a spinning badge in the SAME round this
instrument is being written for, so it is staged before it can ship the
same, unphotographed way.

`updateBanner.hidden` is set directly rather than driven through
`refreshUpdateBanner()` — that function decides WHETHER an update exists at
all (it compares against a live `config.apk_version`, which this offline
audit page never receives), and this instrument is not testing that
decision; it is testing what each STATE looks like once the card is already
showing. `setUpdateCardState` is the exact function the real card calls on
every `__updateState` the shell sends — nothing here re-implements its own
picture of the card.
"""

# DOWNLOADING is staged at 100% — the WIDEST the percentage text can be
# ("100%", four characters, versus "8%"/"47%" at two or three) — because the
# truncation/clip hazard is about the text taking the most room, not about
# any particular progress. The bar's own fill width is cosmetic and not what
# either tooth measures.
UPDATE_DOWNLOADING_STAGE_JS = (
    "updateBanner.hidden=false; setUpdateCardState('downloading');"
    "window.__updateProgress(100, 100);")
UPDATE_INSTALLING_STAGE_JS = (
    "updateBanner.hidden=false; setUpdateCardState('installing');")
# The FAILED text is not a generic placeholder — it is one of the real
# sentences Updater.kt's own `readableFailure()` can send (the longest of
# the fixed ones), because a card measured against a short "failed" word
# proves nothing about the sentence it actually has to hold: the shell's
# failure detail is free text and can run to a full sentence.
UPDATE_FAILED_STAGE_JS = (
    "updateBanner.hidden=false; setUpdateCardState('failed',"
    " 'The device blocked the install. Check for a restriction on unknown "
    "app sources.');")
UPDATE_PERMISSION_STAGE_JS = (
    "updateBanner.hidden=false; setUpdateCardState('permission');")
# Returns the card to its true resting state — hidden, and spun down (the
# 'offer' state carries no cube) — so a later stage in the same page
# (another panel, the collision check) never inherits a spinning cube or a
# banner still occupying the top of the page.
UPDATE_CLOSE_JS = (
    "setUpdateCardState('offer'); updateBanner.hidden=true;"
    " document.documentElement.style.removeProperty('--update-top');")
