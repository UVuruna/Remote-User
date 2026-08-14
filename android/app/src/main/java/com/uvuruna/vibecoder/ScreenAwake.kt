package com.uvuruna.vibecoder

import android.view.View
import android.view.WindowManager

/**
 * WHAT IS ON SCREEN, AND WHETHER THE SCREEN STAYS LIT.
 *
 * Split out of MainActivity.kt on 2026-08-14 (THE STRUCTURE LAW, the same
 * seam Insets.kt was cut on): MainActivity is about WHICH page to load and how
 * to survive losing it; this is one job with one dependency — the window — and
 * the two questions are the same question. Which layer is showing (error card,
 * loader, or the live page) is exactly what decides whether the phone may burn
 * its screen, so they belong in one place instead of being kept in step by
 * hand at eight call sites.
 *
 * T80a — WHO OWNS FLAG_KEEP_SCREEN_ON. The flag used to be added once in
 * `onCreate` and cleared by exactly one thing: the PAGE, through
 * `Bridge.keepAwake(false)`. That is a single owner who is not always alive.
 * Whenever the native error card is up — no network, PC unreachable, Tailscale
 * off — there IS no page, so nothing could ever clear it and the phone held
 * its screen on over a card saying the session was dead. The screen is by far
 * the biggest battery consumer on the device.
 *
 * Ownership is therefore inverted. The SHELL owns the flag, because only the
 * shell knows whether a live session is on screen at all; the page owns one
 * INPUT to it, and keeps exactly the power it had — releasing the screen
 * during a session, which is the presence signal the whole layout design rests
 * on. It simply can no longer FAIL to release it, because it is no longer the
 * only thing that can.
 */
object ScreenAwake {

    /** The page's own last word (`Bridge.keepAwake`). True until it says
     *  otherwise, so a session that never calls the bridge behaves exactly as
     *  it did before this round. */
    private var pageWants = true

    /** Was a live page the last thing we saw? A document that goes away and
     *  comes back is a NEW page which has not called `keepAwake` yet, and its
     *  predecessor's release must not outlive it — otherwise a page that let
     *  the screen go and was then reloaded could never take it back. */
    private var sawLivePage = false

    /** The page asked. Recorded, then weighed with everything else. */
    fun pageAsked(host: MainActivity, on: Boolean) {
        pageWants = on
        apply(host)
    }

    /** The ONE writer of FLAG_KEEP_SCREEN_ON in this shell. Held only while
     *  ALL of these are true at once: there is a window on screen, a document
     *  really loaded (a failed load is not one), neither the error card nor
     *  the loader is showing, and the page has not asked us to let go.
     *  Idempotent — add/clearFlags are, and a call that changes nothing costs
     *  nothing, which is what lets every state change simply call it. */
    fun apply(host: MainActivity) {
        // `viewsReady`, not `isInitialized`: Kotlin allows that check only on a
        // property declared in the same type or file, and the repair path
        // leaves onCreate before the two layers exist at all.
        if (!host.viewsReady) return
        val shown = host.started && host.pageAlive &&
            host.errorView.visibility != View.VISIBLE &&
            host.loadingView.visibility != View.VISIBLE
        if (shown && !sawLivePage) pageWants = true   // a fresh document
        sawLivePage = shown
        if (shown && pageWants) {
            host.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            host.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }
}

/** WHICH LAYER IS ON SCREEN — the error card, the loader, or the page itself.
 *  One funnel, because the answer also decides whether the screen may stay
 *  lit; an argument left out is left exactly as it stands. */
internal fun MainActivity.showLayer(error: Boolean? = null, loading: Boolean? = null) {
    error?.let { errorView.visibility = if (it) View.VISIBLE else View.GONE }
    loading?.let { loadingView.visibility = if (it) View.VISIBLE else View.GONE }
    ScreenAwake.apply(this)
}
