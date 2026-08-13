# tests/manual/assets — the five files the default-handler test opens

Entry point: [`tests/manual/___manual.md`](../___manual.md), which explains why
nothing under `tests/manual/` is a gate.

These exist for one instrument, [`open_default.py`](../open_default.py): the
owner's repeated request to open a file through **its own default program**,
the way a double click in Explorer does — never as another tab inside VS Code.
The instrument prints which handler his machine will really use (read from the
shell's own `assoc`/`ftype`) before it opens anything.

Each file is present for a MEASURED reason rather than for variety — together
they cover every way a launched program can behave towards this project's
window machinery:

| File | The case it produces |
|------|----------------------|
| `sample.txt` | An instant start in a foreign process (Notepad) — a new top-level window appears at once. |
| `sample.png` | The image viewer: a cold start slow enough that a poll on "a window appeared" really has to wait. |
| `sample.svg` | Browser REUSE — the commonest case, and the one that produces **no new window at all**: with Chrome already running, the file lands as a TAB and only the existing window's title changes. |
| `sample.html` | The same reuse from the OTHER direction — the page an agent's report opens, which is the chain the owner has been pointing at. |
| `sample.csv` | A heavyweight cold start (Excel, when installed) — the honest upper bound on how long a launch can take. |

**They are generated, never photographed or copied from his work.** The picture
has no content on purpose: an instrument that opens a file on his desk must not
also put anything of his on screen.
