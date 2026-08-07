# Flow — grids

```
layout_region(work_area, aspect, ratio, pos)
   │
   ├─ box   = _fit_rect(work_area, aspect)        # phone-shaped, centred
   └─ IF ratio: return _fit_rect(box, ratio, pos) # smaller, slid along the free axis
      ELSE:     return box

_cells(region, grid, orient)
   │
   ├─ grid "4"  → four quarters
   ├─ grid "2"  → _split(region, 2, vertical = orient != portrait)
   └─ grid "3-<side>"
         vertical = side in (left, right)          # which way the bar runs
         first, second = _split(region, 2, vertical)
         bar, rest     = (first, second) if side in (top, left) else (second, first)
         pair          = _split(rest, 2, NOT vertical)   # split ACROSS the bar
         return [bar, *pair]  or  [*pair, bar]
```

Member order is the return order: cell 1 first. A merge keeps cell 1 as the
target layout's own window, which is why the order is part of the contract and
not an implementation detail.
