# Freeze Offer

**Script:** [freeze_offer.py](../freeze_offer.py)

## Purpose

The ONE-TIME 4K@60 freeze offer (task 226, owner ballot verdict). Split into
its own module the day it was written — folding it into `main_window.py`
pushed that file past THE STRUCTURE LAW's 1000-line guard.

`build_freeze_offer_banner(window)` returns a dismissible in-window bar (never
a modal dialog — the owner's standing rule for in-app guidance) when, at
construction time, `SETTINGS.h264_max_width >= 3840` and
`SETTINGS.target_fps >= 60` — the freeze recipe named in
`config.h264_max_width`'s own docstring (task 151): a saved capture width of
3840 at 60 fps floods the pipeline with 0.75 GB/s of raw pixels per client.
Returns `None` once `SETTINGS.offered_2560` is set, or when the recipe is not
both true right now.

Either answer sets `offered_2560 = True` through the same `save_user_settings`
path every other setting in this app persists through — the offer never
repeats, on either answer. "Switch" additionally sets `h264_max_width = 2560`
(never a hand-edited json) and calls `window.restart_server()` — the exact
worker the Settings window's own Apply & restart uses, since this reshapes
the encoder the same way.

## Connections

### Uses
- [Config](../../__about/config.md) — `SETTINGS`, `save_user_settings`

### Used by
- [Main Window](main_window.md) — mounted at the top of the window's column,
  before the header, in `MainWindow.__init__`

## Design Decisions

- **A bar, not a dialog.** The owner's guidance principle is that a step the
  user must take is explained IN the window, never in a blocking prompt.
- **The flag is set on EITHER answer.** The ask is "may we say this once", not
  "did you take our advice" — a "Keep 4K" that left the flag unset would ask
  again on the next start, which is the nagging he has banned everywhere else
  in this product.
- **Never a hand-edited json.** `Switch` goes through `save_user_settings`,
  the identical path the Settings window's Stream card Apply button uses.
