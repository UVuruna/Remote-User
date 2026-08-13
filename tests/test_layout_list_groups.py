r"""Creation-list gate: WHAT THE LIST OFFERS, AND FROM WHERE.

Owner request 2026-08-13, his point 4B, in translation: "LAYOUT FROM LIST from
inside a LAYOUT should offer TWO groups — first what it sees in that layout,
then the standard one; LAYOUT FROM LIST from the DESKTOP offers only the
standard, i.e. what it sees on the desktop."

Its own file rather than another check in `test_layout_protocol.py`: that gate
asks whether every layout MESSAGE answers the phone, and this one asks what one
answer CONTAINS. The protocol gate also stands at the structure law's wall, and
a rule bolted onto a full file is how a file stops being about one thing.

The harness is the protocol gate's own — the same faked desk, the same real
dispatcher, the same real `layout_api` — imported rather than copied, because
two fixtures of one desk drift apart and only one of them gets updated.

Run:  .venv/Scripts\python tests/test_layout_list_groups.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import window_manager  # noqa: E402

from test_layout_protocol import (  # noqa: E402
    FAKE_TABS, WIN_A, drive, fresh_conn, install_fakes, sent_of,
)


def check_the_list_from_a_layout_offers_that_layouts_own_tabs() -> bool:
    """His request, in translation: "LAYOUT FROM LIST from inside a LAYOUT
    should offer TWO groups — first what it sees in that layout, then the
    standard one; from the DESKTOP only the standard."

    Why the list could not show them: a window in a layout is excluded from
    the creation list (his own rule of 2026-08-03 — one window cannot be in two
    places), and excluding the window took its TABS with it. But a tab is not
    its window: it can be torn into a window of its own, which is exactly the
    flow he was already using by hand with the tap source. So the WINDOW stays
    out and its TABS come in, under a group of their own.

    Three promises, each planted against: the tabs are there, the member window
    is NOT, and the desktop list is untouched."""
    install_fakes()
    layouts = window_manager.LayoutRegistry()
    conn = fresh_conn()
    drive([{"type": "layout_list"},
           {"type": "layout_create", "slots": [{"hwnd": WIN_A, "tab": None,
                                                "x": 0.1, "y": 0.1}],
            "mode": "solo", "grid": None, "orient": "landscape"}],
          conn=conn, layouts=layouts)
    conn["active"] = 0
    ws, _, _ = drive([{"type": "layout_list"}], conn=conn, layouts=layouts)
    offer = sent_of(ws, "layout_offer")[-1]
    entries = offer["entries"]
    own = [e for e in entries if e.get("group") == "layout"]
    if [e["title"] for e in own] != FAKE_TABS[WIN_A]:
        print(f"  DETAIL the focused layout's own tabs were not offered: "
              f"{[e.get('title') for e in own]}")
        return False
    if offer.get("in_layout") is None:
        print("  DETAIL the phone was not told which layout the group is")
        return False
    if any(e["kind"] == "window" and e["hwnd"] == WIN_A for e in entries):
        print("  DETAIL the member WINDOW came back into the list — one "
              "window cannot be in two places (his rule of 2026-08-03)")
        return False
    if not any(e.get("group") == "desktop" for e in entries):
        print("  DETAIL the desktop group vanished")
        return False

    # …and from the DESKTOP the list is exactly what it has always been.
    ws, _, _ = drive([{"type": "layout_list"}], layouts=layouts)
    offer = sent_of(ws, "layout_offer")[-1]
    if offer.get("in_layout") is not None or any(
            e.get("group") == "layout" for e in offer["entries"]):
        print("  DETAIL the desktop list grew a layout group out of nothing")
        return False
    return True


CHECKS = [
    ("the list from inside a layout offers that layout's own tabs (4B)",
     check_the_list_from_a_layout_offers_that_layouts_own_tabs),
]


def main() -> int:
    print("=== CREATION LIST GATE ===")
    bad = 0
    for name, fn in CHECKS:
        ok = False
        try:
            ok = fn()
        except Exception as e:                      # noqa: BLE001
            print(f"  DETAIL {type(e).__name__}: {e}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        bad += 0 if ok else 1
    if bad:
        print(f"\nCREATION LIST GATE FAILED — {bad} check(s).")
        return 1
    print("\nCREATION LIST GATE PASSED — the list from a layout shows that "
          "layout's own tabs first.")
    return 0


def test_layout_list_groups():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
