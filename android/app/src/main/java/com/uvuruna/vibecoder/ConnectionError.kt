package com.uvuruna.vibecoder

import android.content.Intent
import android.net.NetworkCapabilities
import android.net.Uri
import android.widget.Toast

/**
 * WHY THE PC CAN'T BE REACHED, AND THE ONE BUTTON THAT FIXES IT.
 *
 * Split out of MainActivity.kt on 2026-08-17 (THE STRUCTURE LAW: the in-app
 * update feature's addition pushed the file past the 1,000-line ceiling, and
 * the law says a session that must extend an over-threshold file splits it
 * first). The seam is the same one Insets.kt/ScreenAwake.kt were cut on —
 * extension functions on `MainActivity`, exactly like `showLayer()` in
 * ScreenAwake.kt, rather than a wrapper class holding a second reference to
 * the same Activity: every function below needs the window's own error-card
 * views and network state, so a `class Diagnosis(host: MainActivity)` would
 * only be one more thing to keep in step with `host` for no benefit over
 * calling `this` directly.
 *
 * MainActivity is about WHICH page to load and how to survive losing it;
 * this is about WHY none of them answered and what the error card's one
 * button should do about it. See android/__about/MainActivity.md → "Fail
 * (private enum)" for the owner history behind the five states.
 */

/** Why the connection failed, as far as the phone can honestly tell. Order
 *  matters — each state is only reached once the ones above it are ruled out
 *  (owner-approved decision flow 2026-08-04). */
internal enum class ConnectionFail { NO_NET, PC_NO_TUNNEL, TS_MISSING, TS_OFF, PC_DOWN }

/** One generic message for five different causes was the whole problem
 *  (owner report 2026-08-04): every failure read "Try again", including the
 *  everyday one — phone away from the home Wi-Fi with Tailscale switched off
 *  — where tapping Try again can never work and the fix is two taps away in
 *  another app. The card now names the cause and its primary button IS the
 *  fix: install Tailscale / open Tailscale / re-probe now. Re-rendered on
 *  every failed resolve, so the card follows the phone's state live (tunnel
 *  comes up → the text moves on to the PC).
 *
 *  Nothing here replaces the self-healing: the 4 s timer and the network
 *  callback keep re-probing, so a user who flips Tailscale on and comes back
 *  finds the session already loading — no tap needed. */
internal fun MainActivity.showErrorCard() {
    when (classifyFailure()) {
        ConnectionFail.NO_NET -> renderErrorCard(
            R.string.err_nonet_title, R.string.err_nonet_body, R.string.try_again
        ) { resolveAndLoad() }
        ConnectionFail.PC_NO_TUNNEL -> renderErrorCard(
            R.string.err_pcts_title, R.string.err_pcts_body, R.string.try_again
        ) { resolveAndLoad() }
        ConnectionFail.TS_MISSING -> renderErrorCard(
            R.string.err_ts_missing_title, R.string.err_ts_missing_body,
            R.string.install_tailscale
        ) { installTailscale() }
        ConnectionFail.TS_OFF -> renderErrorCard(
            R.string.err_ts_off_title, R.string.err_ts_off_body, R.string.open_tailscale
        ) { openTailscale() }
        ConnectionFail.PC_DOWN -> renderErrorCard(
            R.string.error_title, R.string.error_body, R.string.try_again
        ) { resolveAndLoad() }
    }
    showLayer(error = true, loading = false)
}

private fun MainActivity.renderErrorCard(title: Int, body: Int, action: Int, onAction: () -> Unit) {
    errorTitle.setText(title)
    errorBody.setText(body)
    errorAction.setText(action)
    errorAction.setOnClickListener { onAction() }
}

/** The phone reads three things, all without a single extra permission: does
 *  it have a network at all, is a VPN tunnel up, is Tailscale even installed
 *  (needs the manifest `<queries>` entry on Android 11+).
 *
 *  Honest limits: Android exposes no "is Tailscale connected" API — only
 *  "some VPN is up" — and no way to tell the home Wi-Fi from a foreign one
 *  without the location permission just to read an SSID. So TS_OFF also
 *  catches "at home, Tailscale off, PC asleep"; its copy says so, and turning
 *  the tunnel on is the only move the phone has either way. */
private fun MainActivity.classifyFailure(): ConnectionFail {
    if (!hasNetwork()) return ConnectionFail.NO_NET
    // The PC never reported a Tailscale address: nothing the phone does can
    // create a way in — the missing step is on the PC.
    if (Prefs.tsUrl(this) == null) return ConnectionFail.PC_NO_TUNNEL
    if (tailscaleLauncher() == null) return ConnectionFail.TS_MISSING
    if (!tunnelUp()) return ConnectionFail.TS_OFF
    return ConnectionFail.PC_DOWN
}

private fun MainActivity.activeCaps(): NetworkCapabilities? {
    val cm = connectivity ?: return null
    return cm.getNetworkCapabilities(cm.activeNetwork ?: return null)
}

private fun MainActivity.hasNetwork(): Boolean {
    val caps = activeCaps() ?: return false
    return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
}

/** A VPN is up when the default network IS the tunnel — it carries the VPN
 *  transport and, being a VPN, lacks NOT_VPN. Either signal alone is enough;
 *  both are checked because OEM builds have been inconsistent. */
private fun MainActivity.tunnelUp(): Boolean {
    val caps = activeCaps() ?: return false
    return caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) ||
        !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)
}

private fun MainActivity.tailscaleLauncher(): Intent? =
    packageManager.getLaunchIntentForPackage(MainActivity.TAILSCALE_PKG)

/** Android gives no way to flip another app's VPN switch, so this opens
 *  Tailscale and the card's text tells the user the one thing to press.
 *  Coming back needs no tap here: the network callback fires the moment the
 *  tunnel is up and the resolver loads the session. */
internal fun MainActivity.openTailscale() {
    val launch = tailscaleLauncher()
    if (launch == null) {
        installTailscale()
        return
    }
    try {
        startActivity(launch)
    } catch (e: Exception) {
        Toast.makeText(this, R.string.tailscale_no_app, Toast.LENGTH_LONG).show()
    }
}

internal fun MainActivity.installTailscale() {
    val store = Intent(
        Intent.ACTION_VIEW, Uri.parse("market://details?id=${MainActivity.TAILSCALE_PKG}"))
    try {
        startActivity(store)
    } catch (e: Exception) {
        // No Play Store app (or it refuses the market: scheme) — the web
        // listing opens in any browser and installs from there.
        try {
            startActivity(
                Intent(
                    Intent.ACTION_VIEW,
                    Uri.parse(
                        "https://play.google.com/store/apps/details?id=" +
                            MainActivity.TAILSCALE_PKG)
                )
            )
        } catch (e2: Exception) {
            Toast.makeText(this, R.string.tailscale_no_app, Toast.LENGTH_LONG).show()
        }
    }
}

/** Owner request 2026-07-27: the app must WORK on any Wi-Fi, with a security
 *  heads-up. Reading the SSID/security type (to call out open public
 *  networks specifically) needs the location permission plus location
 *  services — too much friction for a notice, so the signal is
 *  transport-level: home LAN dead + tunnel alive while on Wi-Fi means an
 *  unfamiliar network. Warned once per stay (re-armed when Wi-Fi drops). */
internal fun MainActivity.warnIfForeignWifi() {
    if (!onWifi || warnedForeignWifi) return
    warnedForeignWifi = true
    Toast.makeText(this, R.string.foreign_wifi_warning, Toast.LENGTH_LONG).show()
}
