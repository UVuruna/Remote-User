"""Focus gate: what the phone types lands where the owner is looking.

Regression proof for the 2026-08-06 live complaint, reported three times in
one evening and once by accident — a sentence he dictated for another project
arrived in THIS project's session, because mid-dictation the PC's focus moved
and every following keystroke followed it.

`SendInput` has no target: it types into whatever window Windows calls the
foreground at that instant. So anything on the PC that takes focus while he
speaks — an app starting, a dialog, another agent's editor window — takes the
rest of his sentence too, silently, with the stream still showing the PC.

This file proves the POLICY — where typed input may land. The machinery that
carries it (the foreground hook, its thread, the exit paths, the lock) is
proven next door in `test_focus_hook.py`; the two were split on 2026-08-07
when together they crossed THE STRUCTURE LAW's 1,000 lines. Neither touches
the owner's desktop: every Win32 call is answered by a fake
([_focus_fakes.py](_focus_fakes.py)).

1. IN A LAYOUT the fence is the layout: a foreground outside its members is
   refused, focus is handed back to the member that was being typed into, and
   only then do the keys go out.
2. A legitimate move inside the layout is followed, not fought — and a DIALOG
   of a member (Save As…) counts as that member.
3. AT THE DESKTOP the target is the window the typing burst started in, and it
   is re-armed by what the owner does on purpose (an injected click,
   `next_input`, a layout switch) — never by a thief, which sends no message.
4. Re-focusing a layout leaves the KEYBOARD member in front. Raising members
   in plain list order is the second half of the same bug: one excursion (a
   picker, a permission dialog) closes the socket, the page re-focuses the
   layout, and dictation resumed in whichever window sat last in the grid.
5. The thief is NAMED in the log every time — the app being the last to know
   is what cost three trips back to the phone.

And the hole closed by build round R1 (owner-approved, 2026-08-07): the fence
stood only BETWEEN messages. Typing is measured at ~1.84 ms per character on
this PC, so a dictated sentence is over a SECOND of `SendInput` during which a
thief got the rest of it, unlogged and unreplayed. The foreground is now
checked before every character (`TYPE_CHUNK_CHARS`, sized from that
measurement); a steal anywhere costs zero characters, a steal that cannot be
undone STOPS the typing rather than feeding the thief, and what was lost is
TOLD TO THE PHONE — not buried in a log he is not reading while he speaks.

Run:  .venv\Scripts\python tests/test_focus_guard.py
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import (  # noqa: E402
    DIALOG, MEMBER_A, MEMBER_B, THIEF, Catch, FakeInjector, FakeWs, Raises,
    TypeSpy, focus_guard, fresh_conn, input_injector, layout_with, run_checks,
    web, window_manager, with_win32,
)


# ═══════════════════ 1. the layout is a fence ═══════════════════
def check_a_thief_never_gets_the_keystroke() -> bool:
    """The report itself: focus moved to another agent's window mid-sentence.
    The keys must go back to the member he was typing into, first."""
    with_win32(fg=THIEF, alive=(MEMBER_A, MEMBER_B, THIEF))
    raises = Raises().install()
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    conn = fresh_conn(active=0)
    target = focus_guard.guard(reg, conn)
    return (target == MEMBER_B and raises == [(MEMBER_B, True)]
            and conn["pin"] == MEMBER_B)


def check_the_fence_holds_without_a_pin() -> bool:
    """A fresh connection after an excursion has no pin — the layout's own
    memory of which member held the keyboard is what answers."""
    with_win32(fg=THIEF, alive=(MEMBER_A, MEMBER_B, THIEF))
    raises = Raises().install()
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    return (focus_guard.guard(reg, fresh_conn(active=0)) == MEMBER_B
            and raises == [(MEMBER_B, True)])


def check_a_move_inside_the_layout_is_followed() -> bool:
    """He clicked into the other pane himself — that is not a theft, and the
    layout remembers the new target for the next reconnect."""
    with_win32(fg=MEMBER_B, alive=(MEMBER_A, MEMBER_B))
    raises = Raises().install()
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_A)
    conn = fresh_conn(active=0)
    return (focus_guard.guard(reg, conn) == MEMBER_B and not raises
            and reg.layouts[0].last_member == MEMBER_B and conn["pin"] == MEMBER_B)


def check_a_dialog_of_a_member_is_the_member() -> bool:
    """Save As… is a window of its own and belongs to no layout — yanking
    focus out of it would make typing a file name impossible."""
    with_win32(fg=DIALOG, alive=(MEMBER_A, DIALOG), owner={DIALOG: MEMBER_A})
    raises = Raises().install()
    reg = layout_with([MEMBER_A])
    return focus_guard.guard(reg, fresh_conn(active=0)) == DIALOG and not raises


# ═══════════════════ 2. the desktop has no fence, so build one ═══════════════════
def check_the_desktop_arms_on_the_first_key() -> bool:
    """No layout: the window the burst starts in IS the target."""
    fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A, THIEF))
    raises = Raises().install()
    conn = fresh_conn()
    if focus_guard.guard(None, conn) != MEMBER_A or conn["pin"] != MEMBER_A:
        return False
    # ...and the next utterance goes back there when something steals focus.
    fake.fg = THIEF
    return (focus_guard.guard(None, conn) == MEMBER_A
            # NOT topmost: this window is nobody's layout member (owner
            # decree 2026-08-05 — a raise there stranded windows above the desk)
            and raises == [(MEMBER_A, False)])


def check_the_owners_own_click_re_arms_it() -> bool:
    """He moved to another window through the phone — the target follows him,
    because a click is a message and a thief is not."""
    fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B))
    raises = Raises().install()
    conn = fresh_conn()
    focus_guard.guard(None, conn)          # armed on A
    focus_guard.retarget(conn)             # ...he clicked
    fake.fg = MEMBER_B
    return focus_guard.guard(None, conn) == MEMBER_B and not raises


def check_the_thief_is_named_in_the_log() -> bool:
    """A restored keystroke that logs nothing would only hide the next cause."""
    with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    Raises().install()
    with Catch(focus_guard.logger) as caught:
        focus_guard.guard(layout_with([MEMBER_A]), fresh_conn(active=0))
    return caught.naming(THIEF)


# ═══════════════════ 2b. the layout is DEFENDED, not merely checked ═══════════════════
def check_the_watcher_defends_without_a_keystroke() -> bool:
    """Owner decree 2026-08-06: while the phone shows a layout, nothing may
    take the keyboard out of it. Dictation is why waiting for a keystroke is
    too late — the recognizer hands over a whole utterance at the END of a
    round, so a thief mid-sentence destroys it instead of misplacing it."""
    with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    raises = Raises().install()
    reg = layout_with([MEMBER_A])
    target = focus_guard.guard(reg, fresh_conn(active=0), False)
    return target == MEMBER_A and raises == [(MEMBER_A, True)]


def check_the_watcher_leaves_the_desktop_alone() -> bool:
    """Outside a layout there is no fence to defend — only a memory of where
    typing began. Fighting the whole desktop for it would be US stealing
    focus, so the watcher does nothing there."""
    with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    raises = Raises().install()
    conn = fresh_conn()
    conn["pin"], conn["pin_stale"] = MEMBER_A, False
    focus_guard.guard(None, conn, False)
    return not raises


def check_the_watcher_sleeps_while_the_phone_is_away() -> bool:
    """An excursion or a leave hands those windows back to the desk; pulling
    focus to them there is the sin two earlier rounds were spent fixing."""
    with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    raises = Raises().install()
    reg = layout_with([MEMBER_A])

    async def run(conn):
        task = asyncio.ensure_future(focus_guard.watch(reg, conn))
        await asyncio.sleep(focus_guard.WATCH_POLL_S * 3)
        task.cancel()

    away = fresh_conn(active=0)
    away["away"] = True
    asyncio.run(run(away))
    if raises:
        return False
    # ...and it DOES defend the same layout when the phone is present.
    asyncio.run(run(fresh_conn(active=0)))
    return raises and raises[0] == (MEMBER_A, True)


def check_one_thief_is_logged_once_not_every_poll() -> bool:
    """Four polls a second against an app that fights back must not write the
    server log by itself."""
    with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    Raises().install()
    reg, conn = layout_with([MEMBER_A]), fresh_conn(active=0)
    with Catch(focus_guard.logger) as caught:
        for _ in range(5):
            focus_guard.guard(reg, conn, False)
    return len(caught.records) == 1


# ═══════════════════ 3. the other half: the re-focus order ═══════════════════
def check_refocus_leaves_the_keyboard_member_in_front() -> bool:
    """One excursion closes the socket, the page re-focuses the layout — and
    raising members in list order handed the keyboard to the wrong window."""
    with_win32(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B))
    raises = Raises().install()
    window_manager.place_window = lambda hwnd, rect: True
    window_manager._frame_rect = lambda hwnd: (0, 0, 100, 100)
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_A)
    reg.focus(0, 0.5, (0, 0, 1000, 1000))
    # Last raised = the one left holding the keyboard.
    return [hwnd for hwnd, _ in raises][-1] == MEMBER_A


def check_prune_moves_the_target_off_a_closed_window() -> bool:
    """The member he was typing into was closed at the desk — the target may
    not stay pointing at a dead handle."""
    with_win32(fg=MEMBER_A, alive=(MEMBER_A,))
    Raises().install()
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    reg.prune()
    return reg.layouts[0].last_member == MEMBER_A


# ═══════════════════ 4. end to end, through the real dispatcher ═══════════════════
def check_dictation_through_the_dispatcher() -> bool:
    """The whole path the owner's voice takes: `key_text` from the phone while
    a thief holds the foreground. The text must still arrive — in the layout."""
    with_win32(fg=THIEF, alive=(MEMBER_A, MEMBER_B, THIEF))
    raises = Raises().install()
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    conn = fresh_conn(active=0)
    injector = FakeInjector()

    async def run():
        ws = FakeWs([{"type": "key_text", "text": "zdravo"}])
        try:
            await web._receive_input(ws, injector=injector, stream=None,
                                     token="t", layouts=reg, conn=conn)
        except web.WebSocketDisconnect:
            pass

    asyncio.run(run())
    return injector.typed == ["zdravo"] and raises == [(MEMBER_B, True)]


def check_a_click_message_re_arms_through_the_dispatcher() -> bool:
    """`press` / `click` / `next_input` are the owner choosing a window; the
    dispatcher must mark the target stale for the next keystroke."""
    with_win32(fg=MEMBER_A, alive=(MEMBER_A,))
    Raises().install()
    conn = fresh_conn()
    conn["pin"], conn["pin_stale"] = MEMBER_B, False

    async def run():
        ws = FakeWs([{"type": "press", "button": "left", "down": True}])
        try:
            await web._receive_input(ws, injector=FakeInjector(), stream=None,
                                     token="t", layouts=None, conn=conn)
        except web.WebSocketDisconnect:
            pass

    asyncio.run(run())
    return conn["pin_stale"] is True


# ═══════════════════ 5. INSIDE one sentence (build round R1) ═══════════════════
SENTENCE = ("ovo je jedna duga izdiktirana rečenica koja se ubacuje znak po "
            "znak i mora cela da stigne tamo gde on gleda")
ASTRAL = "svaka reč 🎉 i još 🚀 emoji koje moraju stići cele "


def check_a_steal_anywhere_in_a_sentence_loses_nothing() -> bool:
    """The hole the guard did not cover: `SendInput` types one code unit at a
    time — measured ~1.84 ms per character on this PC, so a 600-character
    dictated sentence is over a SECOND long, and a window that takes focus
    inside that stretch used to receive the remainder. Nothing replays
    injected characters and Windows reports no error, so the owner only ever
    found out by reading his own sentence in another project.

    Placements matter, and this is the correction of a claim that was too
    generous: with 40-character chunks "zero lost" was true only when the
    steal landed exactly ON a boundary (35/20/39/25 characters reached the
    thief at other offsets). One character per check is what makes zero true
    everywhere — see TYPE_CHUNK_CHARS for what that costs."""
    for steal_at in (1, 7, 20, 39, 40, 41, 55, 80):
        fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, THIEF))
        raises = Raises().install(fake)
        reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_A)
        conn = fresh_conn(active=0)
        focus_guard.guard(reg, conn)       # the message's own guard, as web.py runs it
        spy = TypeSpy(fake, steal_at=steal_at)
        lost = spy.type_text(SENTENCE, focus_guard.typist(reg, conn))
        if (lost or spy.text != SENTENCE or not spy.landed_only_in(MEMBER_A)
                or raises != [(MEMBER_A, True)]):
            return False
    return True


def check_a_steal_inside_an_emoji_costs_at_most_its_tail() -> bool:
    """Astral characters, which the BMP-only cases above cannot speak for. A
    character is typed as a whole (two code units for an emoji), so a steal
    landing BETWEEN those two halves is the one thing a per-character check
    cannot pre-empt: the low surrogate follows the high one out. The honest
    guarantee is therefore "never a whole character, at most the tail of the
    one in flight" — and the text still arrives complete."""
    for steal_at in (1, 2, 11, 12, 13, 24, 25):
        fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A, THIEF))
        Raises().install(fake)
        reg, conn = layout_with([MEMBER_A]), fresh_conn(active=0)
        focus_guard.guard(reg, conn)
        spy = TypeSpy(fake, steal_at=steal_at)
        lost = spy.type_text(ASTRAL, focus_guard.typist(reg, conn))
        stolen = [unit for unit, fg in spy.units if fg == THIEF]
        if lost or spy.text != ASTRAL or len(stolen) > 1:
            return False
        # ...and what it could catch is only ever half of a surrogate pair
        if stolen and not 0xDC00 <= stolen[0] <= 0xDFFF:
            return False
    return True


def check_typing_stops_and_says_so_when_focus_is_lost() -> bool:
    """When focus CANNOT be brought back, the rest is not sent — a thief must
    never be fed — and both halves are in the log: the guard names the window
    holding it, the injector names how much never arrived. Text dropped in
    silence is exactly how this failure survived three reports."""
    fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A, THIEF))
    Raises().install()                          # the raise is refused: focus stays gone
    reg, conn = layout_with([MEMBER_A]), fresh_conn(active=0)
    focus_guard.guard(reg, conn)
    spy = TypeSpy(fake, steal_at=40)
    with Catch(focus_guard.logger, input_injector.logger) as caught:
        lost = spy.type_text(SENTENCE, focus_guard.typist(reg, conn))
    return (spy.text == SENTENCE[:40] and lost == SENTENCE[40:]
            and spy.landed_only_in(MEMBER_A)
            and caught.naming(THIEF)
            and any("ABORTED" in line for line in caught.records))


def check_the_phone_is_told_what_was_lost() -> bool:
    """Destroying the rest of a dictated sentence and saying so only in the
    server log is the very failure this module exists to end — he is looking
    at his phone, not at a log. The loss must reach the device, naming its
    size and the start of what is missing so he knows what to say again."""
    fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A,))
    Raises().install(fake)
    gone = "ostatak rečenice koji nikada nije stigao"
    injector = FakeInjector(lost=gone)
    box: dict = {}

    async def run():
        ws = FakeWs([{"type": "key_text", "text": "cela rečenica"}])
        box["ws"] = ws
        try:
            await web._receive_input(ws, injector=injector, stream=None,
                                     token="t", layouts=None, conn=fresh_conn())
        except web.WebSocketDisconnect:
            pass

    asyncio.run(run())
    toasts = [m for m in box["ws"].sent if m.get("type") == "toast"]
    return (len(toasts) == 1 and str(len(gone)) in toasts[0]["text"]
            and gone[:20] in toasts[0]["text"])


def check_half_a_character_never_goes_out_and_never_raises() -> bool:
    """A lone surrogate cannot be encoded to UTF-16 at all. Discovering that
    per chunk threw `UnicodeEncodeError` out of the middle of a sentence —
    part typed, the rest gone, and the exception escaping into the WebSocket
    dispatcher, which catches only `WebSocketDisconnect`: the socket died
    mid-dictation. It is reachable — the page reads printable characters by
    diffing UTF-16 strings and can hand us half an emoji."""
    fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A,))
    half = "zdravo \ud83c svete"
    spy = TypeSpy(fake)
    lost = spy.type_text(half, lambda: MEMBER_A)
    plain = TypeSpy(fake)                       # ...and with no fence either
    plain.type_text(half)
    return (lost == "\ud83c" and spy.text == "zdravo  svete"
            and plain.text == "zdravo  svete"
            and all(not 0xD800 <= unit <= 0xDFFF for unit, _ in spy.units))


def check_typing_without_a_fence_is_unchanged() -> bool:
    """Callers with no connection to fence pass no guard and get exactly the
    old behaviour. And the cut is by CHARACTER, never by code unit: a chunk
    boundary inside a surrogate pair would split an emoji in half."""
    fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A,))
    plain = TypeSpy(fake)
    plain.type_text(SENTENCE)                   # the old one-argument call still works
    emoji, boundaries = TypeSpy(fake), []
    emoji.type_text("🎉" * 60,
                    lambda: (boundaries.append(len(emoji.units)), MEMBER_A)[1])
    return (plain.text == SENTENCE and emoji.text == "🎉" * 60
            # every check fell BETWEEN characters — an odd count would mean a
            # surrogate pair was cut in half
            and boundaries and all(n % 2 == 0 for n in boundaries))


def check_the_dispatcher_hands_the_injector_the_fence() -> bool:
    """The wiring: `key_text` must reach the injector WITH the checkpoint, or
    everything above is dead code in a live build."""
    fake = with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    Raises().install(fake)
    reg, conn = layout_with([MEMBER_A]), fresh_conn(active=0)
    injector = FakeInjector()

    async def run():
        ws = FakeWs([{"type": "key_text", "text": "zdravo"}])
        try:
            await web._receive_input(ws, injector=injector, stream=None,
                                     token="t", layouts=reg, conn=conn)
        except web.WebSocketDisconnect:
            pass

    asyncio.run(run())
    return (injector.typed == ["zdravo"] and callable(injector.guards[0])
            and injector.guards[0]() == MEMBER_A)


CHECKS = [
    ("a focus thief never gets the keystroke", check_a_thief_never_gets_the_keystroke),
    ("the fence holds on a fresh connection (no pin yet)",
     check_the_fence_holds_without_a_pin),
    ("a move inside the layout is followed, not fought",
     check_a_move_inside_the_layout_is_followed),
    ("a dialog of a member counts as that member",
     check_a_dialog_of_a_member_is_the_member),
    ("at the desktop the burst's first window is the target",
     check_the_desktop_arms_on_the_first_key),
    ("the owner's own click re-arms the target", check_the_owners_own_click_re_arms_it),
    ("the thief is named in the log", check_the_thief_is_named_in_the_log),
    ("the layout is DEFENDED without waiting for a keystroke",
     check_the_watcher_defends_without_a_keystroke),
    ("the watcher leaves the desktop alone", check_the_watcher_leaves_the_desktop_alone),
    ("the watcher sleeps while the phone is away, defends while it is here",
     check_the_watcher_sleeps_while_the_phone_is_away),
    ("one thief is logged once, not on every poll",
     check_one_thief_is_logged_once_not_every_poll),
    ("re-focus leaves the keyboard member in front",
     check_refocus_leaves_the_keyboard_member_in_front),
    ("prune moves the target off a closed window",
     check_prune_moves_the_target_off_a_closed_window),
    ("dictation survives a thief through the real dispatcher",
     check_dictation_through_the_dispatcher),
    ("a click message re-arms the target through the dispatcher",
     check_a_click_message_re_arms_through_the_dispatcher),
    ("a steal ANYWHERE in a sentence loses nothing",
     check_a_steal_anywhere_in_a_sentence_loses_nothing),
    ("a steal inside an emoji costs at most its tail, never a character",
     check_a_steal_inside_an_emoji_costs_at_most_its_tail),
    ("typing stops — and says so — when focus cannot be restored",
     check_typing_stops_and_says_so_when_focus_is_lost),
    ("the phone is TOLD what never reached the PC",
     check_the_phone_is_told_what_was_lost),
    ("half a character never goes out, and never raises into the dispatcher",
     check_half_a_character_never_goes_out_and_never_raises),
    ("without a fence the injector behaves exactly as before",
     check_typing_without_a_fence_is_unchanged),
    ("the dispatcher hands the injector the mid-sentence fence",
     check_the_dispatcher_hands_the_injector_the_fence),
]


def main() -> int:
    return run_checks("FOCUS GATE", CHECKS,
                      "typed input lands where the owner is looking.")


def test_focus_guard():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
