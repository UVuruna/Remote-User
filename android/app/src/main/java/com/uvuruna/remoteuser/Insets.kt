package com.uvuruna.remoteuser

import android.webkit.WebView
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/**
 * WHAT THE WINDOW'S EDGES DO: the system bars we hide, and the keyboard inset
 * only this side can measure.
 *
 * Split out of MainActivity.kt on 2026-08-09 (THE STRUCTURE LAW). It is one
 * job with one dependency — `WindowInsets` — and it is the seam where the
 * platform's idea of the window meets the page's. Everything else in
 * MainActivity is about WHICH page to load and how to survive losing it.
 */

/** Immersive: the status and navigation bars are HIDDEN while controlling
 *  the PC. targetSdk 35 draws the WebView edge-to-edge, so a visible nav
 *  bar sat ON TOP of the page's bottom controls and the system stole the
 *  touches aimed at them (owner report 2026-07-26 — "no button works").
 *  A swipe from the edge shows the bars transiently; they hide again by
 *  themselves. Re-applied on every focus gain — the system restores bars
 *  after dialogs, app switches and the keyboard. */
fun MainActivity.hideSystemBars() {
    val controller = WindowCompat.getInsetsController(window, window.decorView)
    controller.systemBarsBehavior =
        WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
    controller.hide(WindowInsetsCompat.Type.systemBars())
}


// ── HOW TALL THE KEYBOARD IS — only the SHELL can answer (2026-08-09) ──
//
// The owner has reported the same thing five or six times: the soft
// keyboard covers the row he is typing into, so he cannot even see the
// word he wants to delete. Every previous round fixed the RULE on the page
// (client/caret.js) and the rule kept returning zero, because the page was
// being handed a keyboard height of zero.
//
// Why: the page reads `window.innerHeight - visualViewport.height`. That
// works while the WINDOW is resized by the IME — which is what
// `android:windowSoftInputMode="adjustResize"` used to guarantee. It no
// longer does. This app targets SDK 35 and draws EDGE-TO-EDGE with the
// system bars hidden, and under edge-to-edge Android stops resizing the
// window for the IME: the app is expected to read the ime INSET itself.
// So `adjustResize` is in our manifest, honestly declared, and quietly
// does nothing — and the page's subtraction is a subtraction of nothing.
//
// The inset is measurable HERE and nowhere else, so the shell measures it
// and tells the page, in CSS pixels because that is what the page thinks
// in. Pushed rather than polled: the keyboard opens and closes on the
// user's timing, not on ours.
private var lastImeCss = -1

fun MainActivity.watchImeInsets() {
    ViewCompat.setOnApplyWindowInsetsListener(web) { _, insets ->
        val ime = insets.getInsets(WindowInsetsCompat.Type.ime()).bottom
        val css = (ime / resources.displayMetrics.density).toInt()
        if (css != lastImeCss) {
            lastImeCss = css
            web.evaluateJavascript("window.__imeHeight && __imeHeight($css)", null)
        }
        insets
    }
}

/** THE MEMO ABOVE OUTLIVES THE PAGE, AND THAT IS A BUG (found 2026-08-09).
 *
 *  `lastImeCss` is file-scope: it survives every WebView reload, while
 *  `window.__imeHeight` does not — a fresh document starts at zero. So a
 *  keyboard re-opened at the SAME height after a reload (a reconnect, a
 *  re-pair, any `web.reload()`) matched the memo, was skipped as "no change",
 *  and the new page never learned there was a keyboard at all. The rescue
 *  would simply not happen for the rest of that session, silently, and only
 *  after a reload — which is exactly the shape of a bug that survives testing.
 *
 *  Called from `onPageFinished`: forget what the old document was told, then
 *  ask the platform to deliver the current insets again so the new one is told
 *  the truth immediately, rather than waiting for the user to close and reopen
 *  the keyboard. Re-using the listener above is deliberate — one path to the
 *  page, so the two can never disagree. */
fun MainActivity.forgetImeInset() {
    lastImeCss = -1
    ViewCompat.requestApplyInsets(web)
}
