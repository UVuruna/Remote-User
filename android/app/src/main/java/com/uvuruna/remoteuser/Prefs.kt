package com.uvuruna.remoteuser

import android.content.Context

/** Two stored addresses, both tokened page URLs:
 *  - LAN: written by pairing (the QR always encodes the home address)
 *  - Tailscale: learned from the page itself — the client receives
 *    `tailscale_url` in every `config` and hands it over via the JS bridge
 *  MainActivity probes both and loads whichever is reachable, so the app
 *  works at home (LAN) and anywhere (mesh) without the user knowing why. */
object Prefs {
    private const val FILE = "remoteuser"
    private const val KEY_LAN = "pairing_url"
    private const val KEY_TS = "tailscale_url"

    /** Where the PAGE's own per-device preferences live (the `prefGet`/
     *  `prefSet` bridge). Named here rather than in Bridge.kt because the
     *  notice service reads one of them — the user's "speak / banner"
     *  switches — while no page exists to ask (owner 2026-08-07). */
    const val CLIENT_FILE = "client_prefs"

    /** Both stored page URLs, LAN first: the notice service probes them in
     *  this order exactly as MainActivity's resolver does. */
    fun addresses(context: Context): List<String> =
        listOfNotNull(lanUrl(context), tsUrl(context)).distinct()

    fun lanUrl(context: Context): String? =
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(KEY_LAN, null)

    fun setLanUrl(context: Context, url: String?) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .edit().putString(KEY_LAN, url).apply()
    }

    fun tsUrl(context: Context): String? =
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(KEY_TS, null)

    fun setTsUrl(context: Context, url: String?) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .edit().putString(KEY_TS, url).apply()
    }
}
