# `design_lab.py` + `design_lab.js` — the bench

One tool, two halves, one doc (the `theme.css` / `theme.js` arrangement):
the **server** reads and writes the real source files, the **page** turns the
registry into knobs and shows what each one does to eight renderings at once.

Built **2026-08-19**, at the owner's request — his own words, kept verbatim
because they name the deliverable:

<!-- lang-ok-begin: the owner's own request, quoted as evidence -->
> "napravi html u kojem sve ove različite situacije za ui ovih kontrola …
> da mogu da radim fine tune … i kada dole kliknem Save da se to primeni na
> kod."
<!-- lang-ok-end -->

## Why it exists

Every look this page shows was settled, until now, by rendering a ballot,
looking at it, and editing a CSS file by hand. Three things went wrong that way
often enough to name:

- a number tuned against **the one look that happened to be open** — the ON
  state's round one is the case study: an accent ring, an accent wash and an
  accent glow, all three of them correct in the plain dark look and two of them
  outranked by the per-set rules in the coloured ones;
- a value tuned against **no backdrop at all**, when a control floats over the
  PC's own screen and that screen can be any colour (the whole reason an icon
  carries a shadow);
- a value that lives in **two files** — the shadow alphas are a CSS token and a
  JS constant — moved in only one of them.

The lab answers all three: eight frames side by side, a backdrop you pick, and
one knob that writes to every place its value lives.

## What is true of it by construction

**It holds no defaults.** Every value on the page arrived from `/tokens`, which
parsed the real file a moment ago; every value it sends back goes into that
same declaration. There is no third copy to go stale.

**What you see is the product.** The specimens live in an iframe that loads
`client/theme.css`, `client/style.css`, `client/panels.css`,
`client/ledger-panel.css` and `client/theme.js` — the real cascade and the real
per-set ink arithmetic. See [preview.md](preview.md).

**Live is an override; Save is a write.** Dragging a slider posts a message to
the frames, which set the token inline. Nothing on disk moves until Save, so a
tuning session that ends in **Revert** leaves the tree byte-identical.

**A save is a value, never a rule.** The writer matches `--name: <value>;` by
name inside one named block, and only for tokens the registry offers. It cannot
reach a selector, a rule or a comment even if the page asks it to — which is
what makes it safe to run against files whose comments are the project's
memory. See [design_tokens.md](design_tokens.md).

## The routes

| Route | Answer |
|-------|--------|
| `GET /` | the page (`design_lab.html`) |
| `GET /preview` | one specimen board, loaded eight times |
| `GET /tokens` | the registry, the values as they are on disk, and which gate pins what |
| `POST /save` | writes, and answers with every line it changed plus the gates that now have an opinion |
| `GET /<path>` | files under `tools/` and `client/` only — the allowlist is the whole answer to what a browser on this machine may read through it |

## What the page does with a save

It reports every changed line as the server described it — file, token, old
value, new value — and then, separately, the **pins**: values the owner settled
on a ballot and a test guards by date. The lab writes them like any other and
says which gate will now fail. That is deliberate. Re-opening his verdict is
his to do; refusing would just send him back to the editor, and doing it
silently would let a decreed number drift with nobody noticing.

After a save the page **re-reads from disk** rather than trusting what it sent:
the file is the truth about what is in the file.

## What it does NOT do live

The **coloured** looks compute their shadow strength in `client/theme.js` from
a constant read once at load. Dragging the shadow-strength knob therefore moves
the plain looks immediately and the coloured ones only after Save and a reload
— and the row says so on the page, rather than looking like it worked.

## Gate

[tests/test_design_lab.py](../../tests/test_design_lab.py) — every offered knob
exists in the source it names and is really drawn with; a round trip leaves the
file byte-identical; three kinds of bad write are refused; nothing shipped
imports this folder.

Up: [tools/___tools.md](../___tools.md)
