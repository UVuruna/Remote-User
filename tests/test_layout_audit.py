"""Layout audit for the GUI surfaces this project ships on the PHONE — the
overlay panels (Sets picker, Quality panel, Aspect panel + Move handle).
Proof source for .claude/layout-proof.md (THE SPACE & LEGIBILITY LAW,
rules/GUI.md): the REAL page is opened in a REAL headless Chromium at phone
sizes, each panel is opened, and geometry is checked — nothing clipped, no
horizontal overflow anywhere, every panel card fully inside the viewport.

Also audits the server-side region placement math (`_fit_rect` with the
2026-08-05 `pos` fraction): the placed rect must stay inside its box for
every position, or the phone would frame pixels outside the monitor.

Run:  .venv\\Scripts\\python tests/test_layout_audit.py
Requires the same toolchain as the input gate (playwright + chromium).
"""

import json
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

SIZES = [("portrait 412x915", 412, 915), ("landscape 915x412", 915, 412)]


def _grid_audit() -> bool:
    """Every grid of the owner's sheet tiles its region EXACTLY: no gap, no
    overlap, no sliver. Pure numbers, so it is checked here rather than by
    looking at a screenshot of two windows."""
    from grids import GRID_CELLS, _cells
    region = (0, 0, 1200, 800)
    for grid, count in GRID_CELLS.items():
        for orient in ("landscape", "portrait"):
            cells = _cells(region, grid, orient)
            if len(cells) != count:
                return False
            area = sum(w * h for _, _, w, h in cells)
            if area != region[2] * region[3]:
                return False          # a gap or an overlap
            for x, y, w, h in cells:
                if w < 100 or h < 100:
                    return False      # a sliver nobody could use
                if x < 0 or y < 0 or x + w > region[2] or y + h > region[3]:
                    return False      # outside the region
    return True


def _fit_rect_audit() -> bool:
    """Pure-math check: the region never leaves its box, at any pos/aspect."""
    from grids import _fit_rect   # the geometry moved out of window_manager (2026-08-07)
    box = (100, 50, 1000, 600)
    for aspect in (0.4, 1.0, 16 / 9, 3.2):
        for pos in (0.0, 0.25, 0.5, 0.75, 1.0):
            x, y, w, h = _fit_rect(box, aspect, pos)
            if not (box[0] <= x and box[1] <= y and
                    x + w <= box[0] + box[2] and y + h <= box[1] + box[3]):
                return False
            if w <= 0 or h <= 0:
                return False
    return True


SHOT_DIR = PROJECT / ".claude" / "shots"


def _shot_name(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_") + ".png"


def _check_panel(page, name, open_js, close_js, card_sel, shot=False):
    """Opens one overlay panel and verifies: the card sits fully inside the
    viewport, the page gained no horizontal overflow, and no element inside
    the card is clipped horizontally."""
    page.evaluate(open_js)
    page.wait_for_selector(card_sel, state="visible", timeout=4000)
    ok = page.evaluate(
        """(sel) => {
          const card = document.querySelector(sel);
          const r = card.getBoundingClientRect();
          const inView = r.left >= 0 && r.top >= 0 &&
                         r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1;
          const noPageScroll =
            document.scrollingElement.scrollWidth <= innerWidth + 1;
          let noClip = card.scrollWidth <= card.clientWidth + 1;
          for (const el of card.querySelectorAll('button, .q-row, .sets-row, input')) {
            if (el.scrollWidth > el.clientWidth + 2) noClip = false;
          }

          // CONTRAST - the check that was missing (owner screenshot
          // 2026-08-06: six white bars with near-white labels on them, and
          // every geometric check green). Text that cannot be read is not a
          // style opinion, it is unreadable content, and the law's whole
          // subject is content the user must read. A <button> with no
          // background of its own inherits the WebView's light default while
          // the theme keeps its light text - which is exactly how it happened.
          // ALPHA IS COMPOSITED, never ignored: this project's own selected
          // states are translucent accent over a card (rgb(56 189 248 /
          // 0.08)), and reading that as solid accent under accent text
          // reports 1.00:1 on a button that is perfectly readable. A guard
          // that cries wolf gets switched off, so it measures what the eye
          // gets: every layer painted over the one below it.
          const parse = (c) => {
            const m = (c || '').match(/[\\d.]+/g);
            if (!m || m.length < 3) return null;
            return [+m[0], +m[1], +m[2], m.length > 3 ? +m[3] : 1];
          };
          const over = (top, bottom) =>
            [0, 1, 2].map((i) => top[i] * top[3] + bottom[i] * (1 - top[3]));
          const PAGE = [15, 23, 42];            // --surface-0, the floor
          const bgOf = (el) => {
            const layers = [];
            for (let n = el; n; n = n.parentElement) {
              const c = parse(getComputedStyle(n).backgroundColor);
              if (!c || c[3] === 0) continue;
              layers.push(c);
              if (c[3] === 1) break;
            }
            let base = PAGE;
            for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
            return base;
          };
          const lumOf = (rgb) => {
            const [r, g, b] = rgb.map((v) => {
              const s = v / 255;
              return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
            });
            return 0.2126 * r + 0.7152 * g + 0.0722 * b;
          };
          let contrast = [];
          for (const el of card.querySelectorAll('*')) {
            const text = (el.textContent || '').trim();
            if (!text || el.children.length) continue;   // leaf text only
            const style = getComputedStyle(el);
            if (style.visibility === 'hidden' || style.display === 'none') continue;
            if (parseFloat(style.opacity) < 0.5) continue;  // deliberately inert
            const ink = parse(style.color);
            if (!ink || ink[3] === 0) continue;
            const bgRgb = bgOf(el);
            const fg = lumOf(over(ink, bgRgb));
            const bg = lumOf(bgRgb);
            const ratio = (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
            if (ratio < 3.0) {   // WCAG AA for large/bold UI text; below this
                                 // the owner cannot read his own buttons
              contrast.push(text.slice(0, 20) + ' [' + el.tagName.toLowerCase() +
                            '.' + (el.className || '-') + '] ' +
                            style.color + ' on ' + ratio.toFixed(2) + ':1');
            }
          }
          return { inView, noPageScroll, noClip, contrast };
        }""",
        card_sel,
    )
    if shot:
        # The layout gate grades a PICTURE, and a picture of the phone's own
        # panels is the only thing that can carry a colour verdict — the very
        # thing the owner had to report by eye on 2026-08-06. Written by the
        # audit itself, so it can never be of a different build than the one
        # just measured.
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT_DIR / _shot_name(name)))
    page.evaluate(close_js)
    passed = (ok["inView"] and ok["noPageScroll"] and ok["noClip"]
              and not ok["contrast"])
    return passed, ok


def main() -> int:
    import test_input_pipeline as gate

    threading.Thread(target=gate.run_server, daemon=True).start()
    gate.server_ready.wait(15)
    deadline = time.time() + 10
    import socket
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

    from playwright.sync_api import sync_playwright

    results = {"region math: _fit_rect stays inside its box for every pos":
               _fit_rect_audit(),
               "grid math: every shape tiles its region exactly": _grid_audit()}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for label, w, h in SIZES:
            ctx = browser.new_context(
                viewport={"width": w, "height": h}, has_touch=True, is_mobile=True,
                # 2x, so the written shots are a real phone's pixels (824x1830,
                # not 412x915). The proof is GRADED BY EYE against DESIGN.md —
                # THE VISUAL PROOF (rules/GUI.md) will not accept an image
                # under 700 px on its short side, and it is right not to: a
                # 412 px thumbnail cannot show whether text is crowded.
                device_scale_factor=2,
                user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 "
                            "Mobile Safari/537.36 RemoteUserApp"),
            )
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
            page.wait_for_selector("#group-left button", timeout=8000)
            # The REAL app sets, from the shipped actions.json — the panels
            # that list them must be measured with the names the owner will
            # actually see, not with invented short ones.
            page.evaluate("(sets) => { window.APP_SETS = sets; }",
                          json.loads((PROJECT / "actions.json")
                                     .read_text(encoding="utf-8"))["app_sets"])

            for name, open_js, close_js, sel in (
                # FULLEST state (owner 2026-08-05): the panel states the PC's
                # own settings and strikes out the fps steps that PC puts out
                # of reach. A base must therefore be set before opening —
                # without it the header is the short "Waiting for the PC's own
                # settings…" and the audit would measure the empty case. 4K +
                # a 10 fps PC is the longest header AND the most struck-out
                # steps this panel can show.
                ("Quality panel",
                 "setStreamBase({fps:10, width:3840, height:2160,"
                 " bitrate:'6M', bitrate_mid:'2400k', bitrate_low:'600k'});"
                 "openQualityPanel()",
                 "closeQualityPanel()", "#quality-panel .sets-card"),
                # FULLEST state (owner 2026-08-06): every app set listed AND
                # two of them wearing the live badge, which is the widest a
                # row in this card can get — checkbox + icon + the longest set
                # name + "ON THE WHEEL NOW". The badge exists because he asked
                # to SEE which app set is actually riding, so it is exactly
                # the thing that must not be cut off.
                ("Sets picker",
                 "appSets = APP_SETS;"
                 "layouts = [{name:'Claude', process:'code.exe',"
                 " title:'Ispravka UI dizajna meni…', orient:'portrait',"
                 " icon:null, app_sets:['VSCode','Claude'], ratio:null, pos:0.5}];"
                 "layoutActive = 0; openSetsPanel()",
                 "layoutActive = null; layouts = []; closeSetsPanel()",
                 "#sets-panel .sets-card"),
                ("Dictation card",
                 "window.Android = {"
                 " voiceLangs: () => JSON.stringify(["
                 "  {tag:'sr-RS', name:'Srpski (Srbija)', status:'download'},"
                 "  {tag:'en-US', name:'English (United States)', status:'ready'},"
                 "  {tag:'de-DE', name:'Deutsch (Deutschland)', status:'online'},"
                 "  {tag:'pt-BR', name:'Português (Brasil)', status:'download', extra:true},"
                 "  {tag:'ja-JP', name:'日本語 (日本)', status:'online', extra:true}]),"
                 " voiceMuteBeeps: () => true, voiceSetMuteBeeps: () => {},"
                 " voiceChosen: () => 'sr-RS', voiceSetLang: () => {},"
                 " voiceState: () => '' };"
                 "renderDictationCard()",
                 "closeDictationPanel()", "#dictation-panel .sets-card"),
                # The Region grab (owner 2026-08-05). Its bar is the part that
                # can starve: hint + Send + ✕ on one line above the keyboard
                # inset, on a 412 px phone. Opened with the frame pushed into
                # the corner, which is where a bar overlap would show first.
                ("Region grab",
                 "openRegionPanel();"
                 "rgBox.x = 4; rgBox.y = 4; rgBox.w = 60; rgBox.h = 60; rgApply()",
                 "closeRegionPanel()", "#region-panel .rg-bar"),
                # The command chooser (owner idea 2026-08-05): the longest
                # real case is the Claude Thinking button's six levels.
                ("Command chooser",
                 "openChoicePanel({label:'Thinking', text:'/effort',"
                 " options:['low','medium','high','xhigh','max','auto']})",
                 "closeChoicePanel()", "#choice-panel .sets-card"),
                ("Aspect panel + Move handle",
                 "layouts = [{name:'Audit', process:'x', orient:'portrait',"
                 " icon:null, ratio:[600,1000], pos:0.5}]; openAspectPanel(0)",
                 "closeLayoutPanel()", "#layout-panel .lay-card"),
                # The layout list carries a rename button per row (owner
                # 2026-08-05) — a long window title must not push the row's
                # buttons off the card.
                ("Layout list with rename",
                 "layouts = [{name:'Claude Code - Remote User - Visual Studio "
                 "Code [Administrator]', process:'x', orient:'portrait',"
                 " icon:null, ratio:[600,1000], pos:0.5}]; openLayoutPicker()",
                 "closeLayoutPanel()", "#layout-panel .lay-card"),
                # The rename card also carries the per-layout app-shortcut
                # ticks (owner 2026-08-06) — the long title AND four chips.
                ("Rename card",
                 "appSets = APP_SETS;"
                 "layouts = [{name:'Claude Code - Remote User - Visual Studio "
                 "Code [Administrator]', process:'code.exe', orient:'portrait',"
                 " icon:null, app_sets:['VSCode','Claude'], ratio:null, pos:0.5}];"
                 "openRenamePanel(0)",
                 "closeLayoutPanel()", "#layout-panel .lay-card"),
                # Creation panel: the Name field is prefilled with the chosen
                # window's (long) title and must fit the card.
                # The grid catalogue he drew (owner 2026-08-07) — the THREE
                # state, where four arrangement SKETCHES sit under the count
                # chips. Its own case because it is the tallest the creation
                # panel ever gets, and because a drawing nobody looked at is
                # not a proof.
                ("Grid arrangement choice",
                 "creating = newCreation('list');"
                 "creating.slots = [{hwnd:1, title:'Chrome', process:'chrome.exe',"
                 " icon:null, tab:null, x:0.5, y:0.5},"
                 " {hwnd:2, title:'Explorer', process:'explorer.exe',"
                 " icon:null, tab:null, x:0.5, y:0.5},"
                 " {hwnd:3, title:'Claude Code - Remote User - Visual Studio"
                 " Code [Administrator]', process:'code.exe', icon:null,"
                 " tab:null, x:0.5, y:0.5}];"
                 "creating.mode = 'grid'; creating.grid = '3-left';"
                 "renderCreationPanel()",
                 "cancelCreation(true)", "#layout-panel .lay-card"),
                ("Creation panel + Name field",
                 "appSets = APP_SETS;"
                 "creating = newCreation('tap');"
                 "creating.slots = [{hwnd:1, title:'Claude Code - Remote User"
                 " - Visual Studio Code [Administrator]', process:'code.exe',"
                 " icon:null, tab:null, x:0.5, y:0.5}];"
                 "renderCreationPanel()",
                 "creating = null; closeLayoutPanel()",
                 "#layout-panel .lay-card"),
            ):
                passed, detail = _check_panel(page, name, open_js, close_js, sel,
                                              shot=(label == "portrait 412x915"))
                results[f"{name} @ {label}"] = passed
                if not passed:
                    print(f"  DETAIL {name} @ {label}: {detail}")

            # D-pad labels: a set's POOL may hold reserve commands with longer
            # names than the shipped four ("Copy path", "Go to file"), and the
            # law forbids eliding them — they wrap instead (owner 2026-08-05).
            # The wrapped label must still stay INSIDE its 58 px button.
            page.evaluate(
                "categories.push({name:'Audit', icon:'grid', required:true,"
                " buttons:[{label:'Copy path', chord:'ctrl+shift+c'},"
                "          {label:'Go to file', chord:'ctrl+p'},"
                "          {label:'Paste plain', chord:'ctrl+shift+v'},"
                "          {label:'Find next', chord:'f3'}]});"
                "groups.left = allCats().length - 1; renderGroup('left');")
            results[f"D-pad labels inside their buttons @ {label}"] = page.evaluate(
                """() => {
                  const btns = document.querySelectorAll('#group-left .ctl');
                  let ok = btns.length > 0;
                  for (const b of btns) {
                    const l = b.querySelector('.lbl');
                    if (!l) continue;
                    const br = b.getBoundingClientRect();
                    const lr = l.getBoundingClientRect();
                    if (lr.top < br.top - 1 || lr.bottom > br.bottom + 1 ||
                        lr.left < br.left - 1 || lr.right > br.right + 1) ok = false;
                    if (l.scrollWidth > l.clientWidth + 1) ok = false;  // no cut
                  }
                  return ok;
                }""")
            page.evaluate("categories.pop(); groups.left = 0; refreshCategories();")

            # The Move handle must be visible and inside the panel card.
            page.evaluate(
                "layouts = [{name:'Audit', process:'x', orient:'portrait',"
                " icon:null, ratio:[600,1000], pos:0.5}]; openAspectPanel(0)")
            page.wait_for_selector(".asp-move", state="visible", timeout=4000)
            results[f"Move handle visible inside the card @ {label}"] = page.evaluate(
                """() => {
                  const m = document.querySelector('.asp-move').getBoundingClientRect();
                  const c = document.querySelector('.lay-card').getBoundingClientRect();
                  return m.width >= 40 && m.left >= c.left && m.right <= c.right &&
                         m.top >= c.top && m.bottom <= c.bottom;
                }""")
            # A SECOND TOUCH IS NOT A DOUBLE TAP (owner 2026-08-07: he shrank
            # a layout, pulled the Move handle down, "ali on je i dalje na
            # sredini"). The handle treated ANY contact within 350 ms of the
            # previous one as the double-tap that re-centres — including the
            # press that begins a drag right after a first touch. That press
            # then returned without capturing the pointer, so the drag was
            # dead AND the region had just been put back in the middle: his
            # exact words. A double tap is two SHORT taps; this drives the
            # real handlers and asserts the region actually moved.
            # A ROW'S BADGE IS A BADGE (owner's law, found 2026-08-07 by
            # OPENING this panel's own screenshot). `.lay-item-main img` sized
            # the app icon; the Desktop row draws an inline <svg>, which the
            # rule never named — so it had no size, took the whole flex line,
            # and squeezed "Desktop" into "Deskt/op" beside a monitor the
            # height of the card. Every geometric check stayed green: nothing
            # was clipped, it was merely unreadable. So the icon is measured.
            page.evaluate(
                "layouts = [{name:'Audit', process:'x', orient:'portrait',"
                " icon:null, ratio:null, pos:0.5}]; openLayoutPicker()")
            page.wait_for_selector("#layout-panel .lay-card", state="visible", timeout=4000)
            results[f"a layout row's icon stays a badge @ {label}"] = page.evaluate(
                """() => [...document.querySelectorAll('.lay-item-main img, .lay-item-main svg')]
                     .every((el) => {
                       const r = el.getBoundingClientRect();
                       return r.width <= 40 && r.height <= 40;
                     })""")
            page.evaluate("closeLayoutPanel()")
            page.evaluate(
                "layouts = [{name:'Audit', process:'x', orient:'portrait',"
                " icon:null, ratio:[600,1000], pos:0.5}]; openAspectPanel(0)")
            page.wait_for_selector(".asp-move", state="visible", timeout=4000)
            results[f"a press after a tap is not a re-centre @ {label}"] = page.evaluate(
                """() => {
                  const h = document.querySelector('.asp-move');
                  const r = document.querySelector('.asp-screen').getBoundingClientRect();
                  const put = (t) => h.dispatchEvent(new PointerEvent(t, {
                    pointerId: 7, bubbles: true, cancelable: true,
                    clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 }));
                  // A synthetic pointer id owns no real capture — stubbing
                  // keeps the DOM from throwing; nothing below depends on it.
                  h.setPointerCapture = () => {};
                  h.hasPointerCapture = () => false;
                  aspecting.pos = 0.9; updateAspectPreview();
                  put('pointerdown'); put('pointerup');   // one tap
                  put('pointerdown');                     // …then a real press
                  return aspecting.pos === 0.9;
                }""")
            page.evaluate("closeLayoutPanel()")
            results[f"no page errors @ {label}"] = not errors
            ctx.close()
        browser.close()

    print("\n=== LAYOUT AUDIT ===")
    failed = 0
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"LAYOUT AUDIT FAILED — {failed} check(s).")
        return 1
    print("LAYOUT AUDIT PASSED — panels fit, nothing clipped, region math bounded.")
    return 0


def test_layout_audit():
    """pytest entry — skipped where the browser toolchain is absent."""
    import pytest
    pytest.importorskip("playwright.sync_api")
    pytest.importorskip("uvicorn")
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
