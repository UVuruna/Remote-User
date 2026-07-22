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
