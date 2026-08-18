# Layout Popup — Flow

**About:** [description](../__about/layout_popup.md)


Where the window is PUT once he has said yes, and how it is let go again:
[Popup Contain — Flow](popup_contain.md).

## Algorithm — a foreground window that is not a member

```mermaid
flowchart TB
    A["focus_guard._decide — a layout is focused,<br/>fg is NOT one of its members"] --> B{"fg already adopted?"}
    B -- yes --> C["re-measure: still inside the region?"]
    C --> Z["accept — the keyboard may sit on it"]
    B -- no --> D{"owner chain root is a member?<br/>(a dialog of a member)"}
    D -- yes --> P["ATTRIBUTED"]
    D -- no --> E{"was it standing when the phone connected?<br/>(the baseline)"}
    E -- yes --> X["STRANGER — the guard's refusal runs,<br/>focus goes back to the layout"]
    E -- no --> F{"same process as a member?"}
    F -- yes --> P
    F -- no --> G{"its process was started by a member's?<br/>(parent links, up to ANCESTRY_HOPS)"}
    G -- yes --> P
    G -- no --> K{"a new window AND an injected click<br/>within CLICK_GRACE_S? (task 240)"}
    K -- yes --> P
    K -- no --> X
    P --> Q{"already offered, or already declined?"}
    Q -- yes --> X
    Q -- no --> O["ONE CHIP on the phone:<br/>Show in layout / Leave on desktop"]
    O --> X
    T["his tap comes back — POST /window_offer → pick()"] --> U{"act"}
    U -- "layout" --> H["record in Layout.adopted — the ledger owes it a way down"]
    U -- "desktop / no answer / anything else" --> V["remembered as DECLINED — nothing moves, ever"]
    H --> C
```

**Nothing moves before he taps** (his amendment, 2026-08-11): until then the
window is an ordinary desktop window and the fence treats it as one — which is
also why the offer path returns "" and the guard's refusal runs, exactly as it
did before this feature existed. The chip goes out from `focus_guard.watch`
over the page's own socket ([Notify](../__about/notify.md)'s one-device slot); his answer
comes back over HTTP, because the socket's dispatcher belongs to `web.py`.

A window is judged **once**: after the decision it joins the baseline set, so a
stranger that fights for the foreground does not cost a process-table read four
times a second, and a popup we could not place is never re-read as a thief.

**The click tier (task 240) is the LAST resort, not an extra chance for
everyone.** It only fires when a window is genuinely NEW since the baseline
AND none of the process-based rules found a tie — an already-running
third-party app opened by his click through the stream is exactly the shape
none of rules 1–3 could ever reach, because its process has no relation to any
member at all. It reuses `click_times`, the same list task 185's `note_click`
fills from every injected left click or press (`web.py`), so a click already
being tracked for one feature is what the other reads too.

## Algorithm — the sweep: it is seen WITHOUT the foreground (task 239)

His fourth report of one failure, and his own observation carried the cause:
the chip appeared only after he **left the layout and came back**. The flow
above starts at `focus_guard._decide` with the FOREGROUND — and the window
this module exists for cannot have it. It opens under the members'
always-on-top band (constraint 10); Windows refuses the foreground to a
process with no input of its own; and `watch`'s own defence hands focus back
inside the layout anyway. So the report window stood there, attributable and
unseen, until a layout switch dropped the members out of the topmost band and
it finally reached the foreground.

```mermaid
flowchart TB
    A["focus_guard.watch — every WATCH_POLL_S,<br/>a layout focused and the phone watching"] --> B{"SWEEP_EVERY_S elapsed?"}
    B -- no --> Z["nothing"]
    B -- yes --> C["EnumWindows — handles only"]
    C --> D{"new since the baseline,<br/>and not a member / adopted / asked / declined?"}
    D -- no --> Z
    D -- yes --> E["the SAME attribution as above<br/>(owner chain, process, ancestry, injected click)"]
    E -- attributed --> O["judged, then ONE CHIP — the same _offer()"]
    E -- "not (yet)" --> G{"first seen more than SWEEP_GRACE_S ago?"}
    G -- yes --> J["judged: a stranger, for good"]
    G -- no --> Z
```

The sweep **moves nothing** — no raise, no placement, no foreground; the only
act is a sentence on the phone. It shares `popup_asked` / `popup_declined` /
`popup_known` with the foreground path, so a window one eye has offered can
never be offered again by the other, whichever saw it first. The grace exists
because `_judged` is permanent: a window is often visible a moment before the
thing that identifies it, and one look taken too early would make it a
stranger for the rest of the session.

