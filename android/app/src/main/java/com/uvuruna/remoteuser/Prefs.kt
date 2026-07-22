package com.uvuruna.remoteuser

import android.content.Context

/** One stored value: the pairing URL (with token). The WebView keeps it
 *  fresh — when the in-page wizard hands the phone the works-anywhere link,
 *  the shell persists that as the new home. */
object Prefs {
    private const val FILE = "remoteuser"
    private const val KEY_URL = "pairing_url"

    fun url(context: Context): String? =
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(KEY_URL, null)

    fun setUrl(context: Context, url: String?) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .edit().putString(KEY_URL, url).apply()
    }
}
