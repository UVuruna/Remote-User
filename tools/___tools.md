# `tools/` — the workshop

Programs the **PC** runs while the product is being built. Nothing here ships,
nothing here is imported by `client/`, `server/`, `android/` or `setup/`, and
nothing on the phone knows this folder exists — the same boundary the project
already draws around the owner's hooks and rules (root `CLAUDE.md`: *we build
for OTHERS, never for his machine*). The gate that keeps it that way is
[tests/test_design_lab.py](../tests/test_design_lab.py).

## The design lab

    python tools/design_lab.py               the page, on 127.0.0.1:8781
    python tools/design_lab.py --print       the tunables and their values, no browser
    python tools/design_lab.py --no-browser  serve only

One page showing **all eight renderings of every control at once** (dark/light
× plain/coloured × outlined/filled), over a PC screen of your choosing, with
every value they are made of as a knob on the left. **Save writes the knob back
into the file it came from** — `client/theme.css`, `client/style.css`,
`client/theme.js` or `server/config.py` — as a value, in place, with every
comment around it untouched.

| File | Role | Doc |
|------|------|-----|
| [design_tokens.py](design_tokens.py) | the registry: which value is tunable, which group, which file — and the reader/writer | [__about/design_tokens.md](__about/design_tokens.md) |
| [design_lab.py](design_lab.py) | the local server: `/tokens`, `/save`, the two folders it will serve | [__about/design_lab.md](__about/design_lab.md) |
| [design_lab.js](design_lab.js) | the page: builds the knobs, pushes every turn into the frames, posts the save | [__about/design_lab.md](__about/design_lab.md) |
| [design_lab.html](design_lab.html) | the scaffold the script fills | — |
| [design_lab.css](design_lab.css) | the workshop's own chrome — never a specimen's | — |
| [preview.html](preview.html) | the specimen board, drawn with the product's own files | [__about/preview.md](__about/preview.md) |

Back to [the project README](../README.md) · the colours it tunes:
[client/__about/theme.md](../client/__about/theme.md)
