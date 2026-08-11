"""RENAMING A LAYOUT APPLIES IMMEDIATELY — no re-open required (task 199).

Owner report: after renaming a layout from the ⚙ sheet, the new name did NOT
show anywhere on the phone — he had to open Rename a SECOND time before it
appeared. Root cause, found by reading the whole chain rather than guessing:

  client/layout-settings.js — openRenamePanel()'s Save handler sent
  `layout_rename` and immediately called closeLayoutPanel(), which just hides
  the overlay. It never touched `layouts[index].name` itself and never called
  `updateLayoutBar()`. Every surface that shows a layout's name — the bar
  (`layouts.js` updateLayoutBar(), reading `layouts[layoutActive].name`), the
  list row (`layouts.js` layRow(lay.name, …)) and the sheet's own header
  (`layout-settings.js` openLayoutSettings()'s `sub.textContent = lay.name`)
  — reads the SAME shared `layouts` array, and that array is only ever
  overwritten wholesale when connection.js's `layout_state` handler processes
  the server's reply (client/connection.js, the `msg.type === "layout_state"`
  branch). Rename was therefore the only control in that sheet with NO local
  effect of its own: unlike the aspect and grid Applies right above it in the
  same file (`sendLayoutShape`), which raise a real loading cube while the
  windows visibly move on the stream, a rename has nothing on the PC to show
  and nothing on the phone to bridge the wait — so the round trip's own
  latency read as "did nothing" the instant Save was tapped, and the FIRST
  screen that happened to re-read the (by-then-updated) array was whichever
  one he opened next: reopening Rename read fresh from `layouts[index]` too,
  which is why doing exactly that "fixed" it, coincidentally.

The fix makes the Save handler OPTIMISTIC (layout-settings.js): it mutates
`lay.name` — the very object every surface above reads — and calls
`updateLayoutBar()` synchronously, both BEFORE `send()`. The server's own
echoed `layout_state` still arrives a moment later and reconciles with the
identical name; it is a no-op unless the two ever disagree.

WHY THIS GATE STUBS send() TO A BLACK HOLE. The real server (test_input_
pipeline's fixture app) holds no layout matching the fixture's index 0 — its
LayoutRegistry starts empty — so letting `layout_rename` actually round-trip
would get back a `layout_state` with `layouts: []` and silently wipe the
staged fixture, proving nothing about THIS bug. More importantly: a gate that
let the real reply do the work would only prove the rename is fast on
localhost, and the owner's phone is not always on a hard-wired LAN — it is
Tailscale, sometimes a relay, sometimes a busy Wi-Fi. So `send()` is replaced
with a function that only records what it was asked to send and NEVER
answers, and the assertions below still have to pass — proving the fix is
optimistic, not merely quick.

Run:  .venv\\Scripts\\python tests/test_layout_rename_live.py
Requires: pip install playwright && playwright install chromium
"""

import socket
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(PROJECT / "server"))

from _audit_panels import LAYOUT_LIST_STAGE_JS, _LONG_TITLE  # noqa: E402

NEW_NAME = "Renamed while offline"

# `send()` recording nothing but a black hole — see the module docstring for
# why the real server's reply must never be what makes this pass. Installed
# BEFORE the fixture layouts are staged so nothing sent during staging itself
# (there is none — LAYOUT_LIST_STAGE_JS only assigns `layouts` and calls
# openLayoutPicker()) can slip past it either.
# Wrapped in a no-argument function (the CONTRAST_JS precedent, tests/
# test_layout_audit.py): Playwright treats a bare string containing an arrow
# function as one to CALL, not install — the unwrapped form here invoked
# `window.send` with no argument the instant it was installed, instead of
# only defining it.
STUB_SEND_JS = ("() => { window.__sent = []; "
                "window.send = (m) => window.__sent.push(m); }")


def _boot():
    """Start the real client + server app (input faked, everything else
    real) that tests/test_input_pipeline.py already stands up — reused
    rather than a second server, so this gate can never disagree with that
    one about what a real connection looks like."""
    import test_input_pipeline as gate
    threading.Thread(target=gate.run_server, daemon=True).start()
    gate.server_ready.wait(15)
    deadline = time.time() + 10
    while time.time() < deadline:
        if gate.server_error:
            raise gate.server_error[0]
        try:
            with socket.create_connection(("127.0.0.1", gate.PORT), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("audit server never started")
    return gate


def _drive_rename(page) -> dict:
    """Stage the layout list (the audit's own fixture — three layouts, index 0
    the active one), open its ⚙ sheet, open Rename, retype the name and tap
    Save — as real taps on the real DOM, not as direct function calls, since
    the bug is about what ends up ON SCREEN after a real interaction. Returns
    everything the checks need from ONE drive, so the panel is only ever
    opened and renamed once — a second rename would hide exactly the bug
    being gated."""
    page.evaluate(STUB_SEND_JS)
    page.evaluate(LAYOUT_LIST_STAGE_JS)
    # The fixture only assigns `layouts`/`layoutActive` and opens the list —
    # exactly what every OTHER panel-audit fixture does, because they only
    # ever check the panel just opened. A real connection always pairs that
    # assignment with `updateLayoutBar()` (connection.js's `layout_state`
    # handler runs both together), so this one extra call is what puts the
    # fixture's layout on the bar first — establishing the honest BEFORE this
    # gate's whole point rests on: proof Save is changing something real, not
    # passing because nothing was ever displayed to begin with.
    page.evaluate("updateLayoutBar()")
    before_bar = page.evaluate("document.getElementById('lay-name').textContent")
    # Row 0 of the list is the fixed "Desktop" row (no ⚙); the first REAL
    # layout — the long-titled, active one `layoutActive = 0` points at — is
    # the first row with a gear.
    page.locator("#layout-panel .lay-gear").first.click()
    page.locator("#layout-panel").get_by_text("Rename", exact=True).click()
    field = page.locator(".lay-name-in")
    field.fill(NEW_NAME)
    page.locator("#layout-panel").get_by_text("Save", exact=True).click()

    # Reopen the list AND the sheet AFTER reading the bar/state, in the SAME
    # trip — proving both without a second rename, exactly the workaround the
    # owner reported using.
    after_save = page.evaluate("""() => ({
      barText: document.getElementById('lay-name').textContent,
      panelHidden: document.getElementById('layout-panel').hidden,
      stateName: layouts[0].name,
      sent: window.__sent,
    })""")
    page.evaluate("openLayoutPicker()")
    row_text = page.evaluate(
        "document.querySelectorAll('#layout-panel .lay-item')[1]"
        ".querySelector('.lay-item-main span').textContent")
    page.evaluate("openLayoutSettings(0)")
    sheet_text = page.evaluate(
        "document.querySelector('#layout-panel .lay-name-line').textContent")
    return {**after_save, "before_bar": before_bar, "row_text": row_text,
            "sheet_text": sheet_text}


def main() -> int:
    print("\n=== LAYOUT RENAME LIVE GATE ===")
    gate = _boot()
    from playwright.sync_api import sync_playwright

    failed = 0

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failed
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not ok and detail:
            print(f"        DETAIL {detail}")
        failed += 0 if ok else 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 412, "height": 915}, has_touch=True, is_mobile=True,
            user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36 VibeCoderApp"),
        )
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
        page.wait_for_selector("#group-left button", timeout=8000)
        page.wait_for_function(
            "document.getElementById('status').textContent.includes('Connected')",
            timeout=8000)

        got = _drive_rename(page)
        browser.close()
        # The server's own disconnect handling (presence.leave_session) keeps
        # running in the fixture's daemon thread after the socket closes; a
        # script that exits within microseconds of `browser.close()` (this
        # one prints a handful of already-computed checks and returns) races
        # ahead of it and Python's interpreter shutdown then finds the thread
        # pool executor gone mid-submit — cosmetic only (the exit code is
        # already decided), but a `RuntimeError` traceback dropped into a
        # gate's own PASS/FAIL evidence is exactly the kind of noise that
        # makes a real failure easy to miss on a later read.
        time.sleep(1.5)

    if errors:
        check("no JS exceptions while renaming", False, "; ".join(errors))
    else:
        check("no JS exceptions while renaming", True)

    check("the fixture's original long title was on the bar before Save",
          got["before_bar"] == _LONG_TITLE,
          f"bar text before Save was {got['before_bar']!r} — the drive is not "
          "changing what it thinks it is changing")

    # THE REPORTED BUG, DIRECTLY: the bar must already read the new name the
    # instant Save closes the panel — no reopen, no server reply (send() is a
    # black hole for this whole drive).
    check("the layout bar shows the new name immediately after Save",
          got["barText"] == NEW_NAME,
          f"bar text is {got['barText']!r}, expected {NEW_NAME!r} — this is "
          f"the exact regression: he had to re-open Rename to see it")

    check("Save closes the panel (no lingering sheet)", got["panelHidden"] is True,
          f"layPanel.hidden is {got['panelHidden']!r}")

    # The single source of truth every surface reads from — mutated, not
    # merely displayed once and forgotten.
    check("layouts[0].name is updated in place (optimistic, not display-only)",
          got["stateName"] == NEW_NAME,
          f"layouts[0].name is {got['stateName']!r}")

    # Reopening the LIST (not Rename a second time) must show it too — the
    # owner's actual workaround was reopening Rename, but the list is what he
    # is normally looking at.
    check("the list row shows the new name on a fresh open — no second rename",
          got["row_text"] == NEW_NAME,
          f"list row reads {got['row_text']!r}")

    check("the ⚙ sheet's own header shows the new name on a fresh open",
          got["sheet_text"] == NEW_NAME,
          f"sheet header reads {got['sheet_text']!r}")

    # The optimistic update must be IN ADDITION to telling the server, never a
    # replacement for it — a phone that only lies to itself is worse than one
    # that is merely slow.
    renames = [m for m in got["sent"] if m.get("type") == "layout_rename"]
    check("layout_rename was still sent to the server exactly once",
          len(renames) == 1 and renames[0].get("index") == 0
          and renames[0].get("name") == NEW_NAME,
          f"sent messages: {got['sent']!r}")

    print()
    if failed:
        print(f"LAYOUT RENAME LIVE GATE FAILED — {failed} check(s).")
        return 1
    print("LAYOUT RENAME LIVE GATE PASSED — a rename shows up without a "
          "second trip through Rename, even with the server's reply "
          "withheld entirely.")
    return 0


def test_layout_rename_live():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
