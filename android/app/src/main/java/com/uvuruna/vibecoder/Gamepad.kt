package com.uvuruna.vibecoder

import android.view.InputDevice
import android.view.InputEvent
import android.view.KeyEvent
import android.view.MotionEvent
import kotlin.math.abs

/** The Bluetooth game controller, forwarded to the page (build round G1,
 *  owner spec 2026-08-07).
 *
 *  WHY THIS EXISTS AT ALL: the pad pairs with the PHONE, and the WebView does
 *  not reliably expose the Gamepad API — but this shell sees every button as a
 *  `KeyEvent` and both sticks as a `MotionEvent`. So the shell captures and
 *  forwards, which is exactly the house rule: the shell adds only what a
 *  browser cannot.
 *
 *  WHAT THIS IS NOT: the mapping. Which button presses which on-screen control,
 *  how far a stick has to tilt, what the cursor does with it — all of that is
 *  the page's (`client/gamepad.js`), on the existing protocol, so the PC needs
 *  nothing new and a mapping change ships with the PC's page instead of with a
 *  new APK. This file is an ADAPTER: platform events in, three page callbacks
 *  out, no policy of its own.
 *
 *  It names buttons by POSITION, never by a vendor's letter: Android reports
 *  △ ◻ ○ ✕ on a PlayStation pad as the same BUTTON_Y/X/B/A an Xbox pad sends,
 *  and those four sit in the same four places on both — so `f_up` is the top
 *  face button either way and the page never learns which brand is in hand.
 *
 *  Three sources can report the SAME press (a D-pad as keys AND as a hat, a
 *  trigger as a key AND as an axis), so every name goes through `set()`, which
 *  emits only on a real change. Key auto-repeat is swallowed by the same gate.
 */
class Gamepad(private val eval: (String) -> Unit) {

    private val down = HashMap<String, Boolean>()
    private var lx = 0f
    private var ly = 0f
    private var rx = 0f
    private var ry = 0f
    private var announced = -1

    /** A key from a pad. Returns true when it was ours — the caller then keeps
     *  it away from the WebView, whose own D-pad focus handling would otherwise
     *  fight the mapping for every arrow. */
    fun key(event: KeyEvent): Boolean {
        if (!fromPad(event)) return false
        val name = KEYS[event.keyCode] ?: run {
            // An unknown keycode is the one thing this table cannot guess for a
            // controller nobody here has held. Say so ONCE, into the PC's log.
            if (event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0) {
                info("unmapped keycode ${event.keyCode} (${KeyEvent.keyCodeToString(event.keyCode)})")
            }
            return false
        }
        when (event.action) {
            KeyEvent.ACTION_DOWN -> set(name, true)
            KeyEvent.ACTION_UP -> set(name, false)
            else -> return false
        }
        return true
    }

    /** Both sticks, the hat and the analog triggers, from one motion event. */
    fun motion(event: MotionEvent): Boolean {
        if (event.action != MotionEvent.ACTION_MOVE || !fromPad(event)) return false
        announce(event)
        val device = event.device
        val nlx = axis(event, device, MotionEvent.AXIS_X)
        val nly = axis(event, device, MotionEvent.AXIS_Y)
        // The right stick is Z/RZ on most modern pads and RX/RY on some older
        // ones; whichever the device actually declares is the one to read.
        val nrx = axis(event, device, MotionEvent.AXIS_Z, MotionEvent.AXIS_RX)
        val nry = axis(event, device, MotionEvent.AXIS_RZ, MotionEvent.AXIS_RY)
        if (nlx != lx || nly != ly || nrx != rx || nry != ry) {
            lx = nlx; ly = nly; rx = nrx; ry = nry
            eval("window.__padAxis && __padAxis($lx,$ly,$rx,$ry)")
        }
        // A D-pad that reports as a HAT rather than as keys — deduped by set().
        val hx = axis(event, device, MotionEvent.AXIS_HAT_X)
        val hy = axis(event, device, MotionEvent.AXIS_HAT_Y)
        set("d_left", hx < -HAT_ON)
        set("d_right", hx > HAT_ON)
        set("d_up", hy < -HAT_ON)
        set("d_down", hy > HAT_ON)
        // Analog triggers — a DualShock reports L2/R2 only as these.
        set("l2", axis(event, device, MotionEvent.AXIS_LTRIGGER, MotionEvent.AXIS_BRAKE) > TRIGGER_ON)
        set("r2", axis(event, device, MotionEvent.AXIS_RTRIGGER, MotionEvent.AXIS_GAS) > TRIGGER_ON)
        return true
    }

    /** Everything the pad is holding goes UP. Called when the app leaves the
     *  foreground: a PC mouse button held by a pad button whose release this
     *  shell never saw would stay down for the rest of the session. */
    fun releaseAll() {
        for (name in down.keys.filter { down[it] == true }) set(name, false)
        if (lx != 0f || ly != 0f || rx != 0f || ry != 0f) {
            lx = 0f; ly = 0f; rx = 0f; ry = 0f
            eval("window.__padAxis && __padAxis(0,0,0,0)")
        }
    }

    /** Emits only on a real change — the same press can arrive as a key AND as
     *  an axis, and holding a button repeats it forever. */
    private fun set(name: String, isDown: Boolean) {
        if (down[name] == isDown) return
        down[name] = isDown
        eval("window.__padButton && __padButton('$name',$isDown)")
    }

    private fun info(text: String) {
        eval("window.__padInfo && __padInfo('${text.replace("'", "")}')")
    }

    /** One line per controller, the first time it sends anything: which pad,
     *  and what it calls its axes. It is the only way to diagnose an unknown
     *  controller on the owner's own phone without putting a panel in his face. */
    private fun announce(event: MotionEvent) {
        val device = event.device ?: return
        if (device.id == announced) return
        announced = device.id
        val axes = device.motionRanges.joinToString(",") { MotionEvent.axisToString(it.axis) }
        info("connected: ${device.name} [$axes]")
    }

    /** The device's own resting slop, then the page's deadzone on top of it. */
    private fun axis(event: MotionEvent, device: InputDevice?, vararg which: Int): Float {
        for (axis in which) {
            val range = device?.getMotionRange(axis, event.source) ?: continue
            val value = event.getAxisValue(axis)
            return if (abs(value) <= range.flat) 0f else value
        }
        return 0f
    }

    private fun fromPad(event: InputEvent): Boolean {
        val source = event.source
        return source and InputDevice.SOURCE_GAMEPAD == InputDevice.SOURCE_GAMEPAD ||
            source and InputDevice.SOURCE_JOYSTICK == InputDevice.SOURCE_JOYSTICK
    }

    private companion object {
        const val HAT_ON = 0.5f
        const val TRIGGER_ON = 0.5f

        /** Position names, not vendor letters — see the class doc. */
        val KEYS = mapOf(
            KeyEvent.KEYCODE_DPAD_UP to "d_up",
            KeyEvent.KEYCODE_DPAD_DOWN to "d_down",
            KeyEvent.KEYCODE_DPAD_LEFT to "d_left",
            KeyEvent.KEYCODE_DPAD_RIGHT to "d_right",
            KeyEvent.KEYCODE_BUTTON_Y to "f_up",      // triangle
            KeyEvent.KEYCODE_BUTTON_X to "f_left",    // square
            KeyEvent.KEYCODE_BUTTON_B to "f_right",   // circle
            KeyEvent.KEYCODE_BUTTON_A to "f_down",    // cross
            KeyEvent.KEYCODE_BUTTON_L1 to "l1",
            KeyEvent.KEYCODE_BUTTON_R1 to "r1",
            KeyEvent.KEYCODE_BUTTON_L2 to "l2",
            KeyEvent.KEYCODE_BUTTON_R2 to "r2",
            KeyEvent.KEYCODE_BUTTON_THUMBL to "l3",
            KeyEvent.KEYCODE_BUTTON_THUMBR to "r3",
            KeyEvent.KEYCODE_BUTTON_START to "start",
            KeyEvent.KEYCODE_BUTTON_SELECT to "select",
        )
    }
}
