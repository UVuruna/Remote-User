# tests/manual — the things only a person can run

Everything else under `tests/` is a GATE: it runs unattended, it fails the
build, and it is proven by planting its own defect. **Nothing in this folder is
a gate.** These are instruments the owner or an agent runs BY HAND, on a real
desktop, to answer a question no automated check can answer — because the
question is about another application's behaviour, or about what a real device
does, and inventing a fake for it would only prove the fake.

They are kept in the repo rather than the scratchpad for one reason: each one
was written because a round was lost to guessing, and the next round should
find the instrument instead of guessing again.

| File | The question it answers |
|------|-------------------------|
| [`catch_popup.py`](catch_popup.py) | **What IS that popup?** Watches the live desktop and prints every window that appears, disappears, moves, or changes its enabled state — with its owner chain, class, process and rect. |
| [`popup_test.html`](popup_test.html) | **Makes the four kinds of window this project keeps arguing about**, on demand, so the server can be watched while it decides what to do with each. |
| `popup_test_image.png` | The picture `popup_test.html` opens and saves. Generated, not photographed; it has no content on purpose. |
| [`open_default.py`](open_default.py) | **Which program does his machine really use for this file?** Opens five kinds of file through their OWN default handler, the way a double click in Explorer does — printing the handler read from the shell's own `assoc`/`ftype` first. Its five files live in [`assets/`](assets/___assets.md). |

---

## `catch_popup.py` — what is that popup?

    .venv\Scripts\python.exe tests\manual\catch_popup.py

Run it, then make the popup happen. Ctrl+C prints a summary.

**Why it exists.** The owner reported for several rounds that a popup ends up
somewhere he cannot reach, and three rounds measured the wrong thing because
nobody had established what the popup IS. Two completely different things look
identical on screen:

- **a real top-level Windows window** — owned by an application or by nothing.
  Our code can see it, attribute it and place it.
- **an overlay the application draws INSIDE ITSELF** — no `hwnd`, no owner,
  nothing to move. If it is this, no amount of work in `server/layout_popup.py`
  can ever touch it, and saying otherwise would be a lie.

So the script reports the difference instead of assuming it. **If nothing new
appears while a popup is plainly visible on screen, that is the answer** — the
app drew it itself — and the summary says so in those words.

## `popup_test.html` — make the windows happen

Open it in a browser inside a layout member window, then press its buttons from
the phone. Watch two things each time: does the new window land inside the
streamed picture, and can the layout still be raised afterwards.

The five buttons are not interchangeable; each is a different Windows
relationship, and the project's rules treat them differently:

1. **A separate browser window** — top-level, owned by nothing. This is the
   case the "a layout with it?" chip is meant to notice.
2. **The print dialog** — a real **owned modal**. While it stands, its owner is
   *disabled*, and Windows *hides* the dialog if the owner is minimized. That
   pair is what once nailed a layout down; see constraint 23 in the project
   [CLAUDE.md](../../CLAUDE.md).
3. **The file picker** — the same shape from a different Windows subsystem. If
   one behaves and the other does not, the cause is not the ownership rule.
4. **An image in its own window** — for checking the chip after a plain single
   click rather than a double click.
5. **The image in the Photos app** — a new window of a *different* process,
   the cleanest case, and a double click is what the birth offer waits for.

**Known limit, measured 2026-08-13 and worth knowing before using this file:**
a link handed to the OS URL handler often opens as a **TAB in an existing
browser window** and creates no new window at all. When that happens, none of
this project's detection can see it — there is no new `hwnd` to attribute.
`catch_popup.py` is what shows you which of the two just happened.

---

Related: [`tests/___tests.md`](../___tests.md) for the real gates, and the
project [CLAUDE.md](../../CLAUDE.md) constraints 17, 18, 19 and 23 for the
rules these instruments were written to check.
