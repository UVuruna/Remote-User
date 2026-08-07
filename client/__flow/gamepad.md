# Flow — the game controller

```
Android shell (Gamepad.kt)                     page (gamepad.js)
──────────────────────────                     ─────────────────
KeyEvent  from a GAMEPAD/JOYSTICK source
  keycode -> position name, transitions only   __padButton(name, down)
MotionEvent (ACTION_MOVE)
  X/Y, Z|RX / RZ|RY, device flat applied       __padAxis(lx, ly, rx, ry)
  HAT_X/Y  -> d_up/d_down/d_left/d_right       (deduped by the same gate)
  triggers -> l2 / r2
onPause -> releaseAll()                        every held name goes UP, axes 0
```

## A button press

```
__padButton(name, down):
    m = PAD_MAP[name]                      # unknown pad button -> ignored
    IF m.shoulder:  padShoulderPress(m, down)          # see below
    ELSE IF a wheel is open: ignored        # only its own shoulder is heard
    ELSE IF m.group:  el = groupButton(side, slot)     # by GRID AREA, not index
                      buttonPress(el, down)            # <- the finger's own path
                      remember el while down
    ELSE IF m.corner: buttonPress(#btn-newlay | #btn-hide, down)
    ELSE IF m.act AND down: run it                     # pad-only: L3 R3 Start Select

buttonPress(el, down)  [controls.js]:
    a = ACTIVATORS.get(el)                  # registered by keepFocus / holdButton
    IF a.hold:  a.hold(down)                #  press {button, down}  — HOLDS
    ELSE:       el.classList.toggle("held", down)      # G2: the screen shows it
                IF !down: a.tap()           # acts on RELEASE, like pointerup
```

The release always goes to the element the press STARTED on — a category
switch can re-render the group under a held arrow, and a PC mouse button must
never be left down.

## A shoulder — one button, two meanings

```
L1/R1 down:
    release everything held, stop the stick loop
    padWheel = {side, step, at: now, index: null}
    openWheel(side)                         # the ring the finger already uses

stick moves while padWheel:
    padAimWheel():
        pick the stick furthest from centre (either thumb may point)
        |stick| < PAD_POINT_MIN  ->  index = null
        else  index = round((atan2(y,x) + PI/2) / (2PI/n))  mod n
              # openWheel puts item i at -PI/2 + i*2PI/n: i=0 up, i grows clockwise
        move the ".current" frame onto index (or back to the group's real set)

L1/R1 up:
    close the wheel
    index != null           ->  groups[side] = index; renderGroup(side)
    else IF now - at < PAD_TAP_MS  ->  layoutStep(±1)      # the ‹ › bar
    else                    ->  nothing
    restart the stick loop
```

## The sticks

```
__padAxis(lx, ly, rx, ry):
    store them
    a wheel is open -> padAimWheel()  and nothing else
    else            -> padStartLoop()

padStartLoop:  arm rAF only while some axis is past the deadzone

padTick(now):
    dt = min(PAD_MAX_DT, now - last)        # a missed frame may not teleport
    padCursorStep(dt)
    padScrollStep(dt)
    re-arm while a stick is still live

padCursorStep(dt):                          # LEFT stick
    dx, dy = padCurve(lx), padCurve(ly)
    from = cursorPos or centre
    scale by the layout region when the view is locked
    sendCursor(clampRemote(from + d * PAD_CURSOR_SPEED * dt/1000 * region))

padScrollStep(dt):                          # RIGHT stick, vertical + horizontal
    acc  += padCurve(ry) * PAD_SCROLL_TICKS * dt/1000
    accH += padCurve(rx) * PAD_SCROLL_TICKS * dt/1000
    whole ticks leave each accumulator, the fraction carries to the next frame
    msg = { at the cursor, ticks: -whole }      # stick up = wheel up (Y is inverted, negate)
    IF wholeH: msg.hticks = wholeH              # stick right = wheel right (X is not, no negate)
    send scroll msg

padCurve(v):
    |v| <= PAD_DEADZONE -> 0
    sign(v) * ((|v| - PAD_DEADZONE) / (1 - PAD_DEADZONE)) ^ PAD_CURVE
```

`padCursorStep` and `padScrollStep` take an explicit `dt` for one reason
beyond tidiness: it is what lets the input gate drive an exact tenth of a
second through the REAL mapping and assert an exact coordinate, instead of
racing a frame clock and asserting something vague.
