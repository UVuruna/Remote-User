"""THE STATUS PILL'S OWN TEETH — what it may never BECOME, and never COVER.

OWNER DECREE 2026-08-17, on seeing this very audit's own screenshots: *sredi
to, ne sme da se preklapa ništa* (lang-ok: owner quote).

The status pill and the window-offer chip both live at the top centre — the
pill at `--topbar`, the chip just under it — and a toast arriving while a chip
stood landed straight over the chip's TITLE, which is the sentence naming WHICH
window he is being asked about. Without that sentence the chip's three answers
are a guess.

**Why it shipped in this file's own pictures for two rounds:** every other
measurement in the audit asks how ONE element fits — is it clipped, is it
elided, does it scroll while it still holds empty space — and not one of them
had ever asked whether two independent overlays COLLIDE. The law was right and
the instrument did not exist.

Its own MODULE by RESPONSIBILITY, and not because `test_layout_audit.py` stood
at THE STRUCTURE LAW's wall (it did — the file sat at exactly 1,000 lines, so
any addition broke it; that is never a reason to put a check anywhere in
particular): both of these are about ONE surface, the status pill, which is the
only thing on this page that is neither a panel nor a control and therefore
fits none of the sweeps next door. The circle check moved here with the
collision one for the same reason it was written in the first place — a toast
that lives outside every panel was never handed to any of them.

It measures the live rects, deliberately — `--status-top` can be written and
still be wrong, and "the variable is set" is exactly the kind of proof this
project keeps being burned by.
"""


def check_chip_clear_of_toast(page, label: str) -> bool:
    """Stage the chip and a toast TOGETHER and measure a real intersection.

    Returns True when they do not touch. On a collision it prints both boxes,
    because "they overlap" is not a report anybody can act on — which of the
    two moved wrongly, and by how much, is the whole diagnosis."""
    from _audit_panels import WIN_OFFER_NEW_STAGE_JS

    page.evaluate(WIN_OFFER_NEW_STAGE_JS)
    page.wait_for_selector("#window-offer", state="visible", timeout=2000)
    page.evaluate("() => showToast('Tap a window or tab on the screen…')")
    page.wait_for_selector("#status.connecting", state="visible", timeout=2000)
    # NO SETTLE WAIT. The pill's move is INSTANT by design (client/style.css),
    # and a wait here would hide the day somebody animates it again — an
    # animation is exactly what photographed badly the first time, the shot
    # catching the pill mid-flight inside the chip it was leaving.
    overlap = page.evaluate(
        "() => { const a = document.getElementById('window-offer')"
        ".getBoundingClientRect(),"
        " b = document.getElementById('status').getBoundingClientRect();"
        " const hit = !(a.right <= b.left || b.right <= a.left"
        " || a.bottom <= b.top || b.bottom <= a.top);"
        " return hit ? {chip: [a.top, a.bottom], pill: [b.top, b.bottom]}"
        " : null; }")
    page.evaluate("() => { hideWindowOffer();"
                  " setStatus('connected', 'Connected'); }")
    if overlap:
        print(f"  DETAIL chip/pill overlap @ {label}: {overlap}")
    return not overlap


def _check_never_a_circle(page, label: str) -> bool:
    """THE NOTIFY TOAST MUST NEVER BECOME A CIRCLE (owner screenshot,
    v0.0.107: a huge filled amber circle over the streamed VS Code, bold
    notification text clipped mid-word by its own curved edges).

    The toast reuses `#status`, which was `width: auto` shrink-to-fit: a notify
    sentence long enough to wrap but not long enough to fill the viewport
    landed on a near-SQUARE box, and `--radius-pill`'s `border-radius: 999px`
    — correct CSS, clamped by the browser to half the shorter side — turned
    that square into a circle. ALG-6's own instrument would have convicted the
    shape on sight; it never saw it, because every other call site points it at
    a staged PANEL ROOT and a toast lives outside every panel. The law and the
    tooth were both right; the coverage gap was the bug.

    A realistic long sentence is staged — the exact shape that produced the
    report, too long for one line and too short to fill the phone's width — so
    this proves the toast itself and not a synthetic square div."""
    page.evaluate(
        "() => showToast('Claude Code (Vibe Coder) needs you — "
        "razmisljam o resenju problema sa iscekivanjem konekcije i "
        "treba mi tvoja odluka pre nego sto nastavim dalje')")
    page.wait_for_selector("#status.connecting", state="visible", timeout=2000)
    bad = page.evaluate(
        "() => __radiusAndKin(document.body).filter("
        "(m) => m.includes(' connecting '))")
    page.evaluate("() => setStatus('connected', 'Connected')")
    if bad:
        print(f"  DETAIL notify toast radius @ {label}: {bad}")
    return not bad


def check_status_pill(page, label: str) -> dict:
    """Both of the pill's teeth, as audit result rows. One entry point, so a
    future third rule about this surface has an obvious home and cannot be
    added as a fourth call site inside another file's sweep."""
    return {
        f"the notify toast never clips into a circle @ {label}":
            _check_never_a_circle(page, label),
        f"the toast never covers the window chip @ {label}":
            check_chip_clear_of_toast(page, label),
    }
