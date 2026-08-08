# Caret — Flow

**About:** [description](../__about/caret.md)

## Where the numbers come from

```
🖥  PC                                      📱 phone
   focus_guard knows WHICH window is           visualViewport → keyboard height
   being typed into
   GetGUIThreadInfo / UI Automation
        └─ caret rect, monitor-normalized
                 │
                 ▼  server → client, only when it CHANGES
        caret {x, y, w, h}   or   nothing at all
                 │
                 └────────────────►  caretLift({caret, view, canvasHeight,
                                                keyboardHeight, unknownMode})
                                              │
                                              ▼
                                     canvas pixels added to view.ty
                                     (the picture rises; the canvas does not)
```

## The decision, in order

```
keyboardHeight = 0 ?  ─────────────────────────────► 0
        │ no                        (nothing can be covered by nothing —
        ▼                            checked first so a stale caret can
caret == null ?                      never move a picture nobody types on)
        │ yes ──► unknownMode "lift" ? ──► lift what is covered, capped
        │                    else ──────► 0        (never guess a position)
        │ no
        ▼
caretBottom = (caret.y + caret.h) * view.scale + view.ty
keyboardTop = canvasHeight - keyboardHeight
shortfall   = caretBottom + LIFT_MARGIN - keyboardTop
        │
        ├─ shortfall <= 0 ────────────────────────► 0     ← the ordinary case
        │
        └─ headroom = caretTop - TOP_MARGIN
           lift = min(shortfall, headroom)
                    │          │
                    │          └─ the strip above the keyboard is too short:
                    │             lift all it can take, leave the rest covered
                    └─ pay exactly what is missing, never the keyboard's height
```

## Why the view and not the monitor

`view.scale` and `view.ty` are read live, so the same PC caret gives a
different answer after he pans or pinch-zooms — which is correct, because the
question is where the row is on **his screen right now**, not where it is on
the PC. The gate proves this by panning the same caret under the keyboard and
requiring a lift.

## What this file does NOT do

It does not send, receive, draw, or remember anything. `render.js` owns the
transform and applies the number; `focus_guard` on the PC owns finding the
caret. Keeping this file pure is what lets
[the gate](../../tests/test_caret_lift.py) execute the rule itself instead of
inspecting it.
