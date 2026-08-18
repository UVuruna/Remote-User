package com.uvuruna.vibecoder

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities

/**
 * WHAT NETWORK THE PHONE IS ON, AND WHEN THAT CHANGES.
 *
 * Split out of MainActivity.kt on 2026-08-18 (THE STRUCTURE LAW, VC-R7), on
 * the seam NoticeService / Notifier / Updater / ScreenAwake / Insets were all
 * cut on before it: MainActivity is about WHICH page to load and how to
 * survive losing it, and this is one job with one dependency — the system's
 * ConnectivityManager.
 *
 * It is a CLASS taking the activity, exactly like Updater, and not an
 * `object`: a NetworkCallback is registered against a live host and must be
 * unregistered with it, so an instance whose lifetime IS the activity's is
 * the honest shape. `watch()` from onCreate, `release()` from onDestroy —
 * never leak the callback, the same discipline Updater.release() keeps.
 *
 * WHAT IT DELIBERATELY DOES NOT OWN: `onWifi`, `onCellular`,
 * `warnedForeignWifi` and `connectivity` stay fields of MainActivity. They are
 * read from two other files (Bridge.kt asks which transport the page is on,
 * ConnectionError.kt asks for the live capabilities and flips the foreign-WiFi
 * flag), and moving the STATE as well as the WATCHING would have been a second
 * change riding on a structural one. This class is the thing that notices; the
 * activity remains the thing that knows.
 */
class ConnectivityWatcher(private val host: MainActivity) {

    /** Reconnect the moment the phone actually has a network again. Foreign
     *  Wi-Fi drops and re-grants connectivity constantly (AP kicks, power
     *  save, captive re-auth) — leaving recovery to a finger on "Try again"
     *  is what made the error card feel dead. Also tracks whether the default
     *  network is Wi-Fi at all: the foreign-Wi-Fi notice needs the transport,
     *  and a VPN network (Tailscale) lists its underlying transports in its
     *  capabilities. */
    private val callback = object : ConnectivityManager.NetworkCallback() {
        /** A NEW default network. This is the moment the loaded address may
         *  have stopped being the right one — home Wi-Fi to mobile data, a
         *  tunnel coming up, a foreign AP re-granting connectivity.
         *
         *  It used to re-resolve only `if (errorView.visibility == VISIBLE)`,
         *  and THAT is the owner's 2026-08-07 report. The error card is a
         *  cold-start state: it means no address answered before a page ever
         *  loaded. The state he is actually in is the opposite one — a page
         *  that loaded perfectly on the home Wi-Fi and is now retrying a
         *  192.168 host from a mobile network. In that state nothing here ran,
         *  nothing in the page could move it (its socket can only reach
         *  `location.host`), and the only code path that re-probes both
         *  addresses was a fresh process. So he killed the app, and it worked,
         *  every time — which is what made "Try again" look broken.
         *
         *  Resolving with a live page is safe by construction: `sessionHealthy`
         *  keeps a document whose own address still answers. */
        override fun onAvailable(network: Network) {
            host.runOnUiThread {
                if (host.isFinishing || host.isDestroyed) return@runOnUiThread
                host.resolveAndLoad(silent = true)
            }
        }

        override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) {
            val wifi = caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
            host.onCellular = caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)
            host.runOnUiThread {
                if (wifi != host.onWifi) {
                    host.onWifi = wifi
                    if (!wifi) host.warnedForeignWifi = false // the next foreign Wi-Fi warns again
                }
            }
        }
    }

    /** Start watching the DEFAULT network. The manager is handed to the
     *  activity as well, because ConnectionError.kt reads the live
     *  capabilities off it (`activeCaps()`) — one manager, one owner of the
     *  callback. */
    fun watch() {
        host.connectivity =
            (host.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager)
                .also { it.registerDefaultNetworkCallback(callback) }
    }

    /** Never leak the callback — the same rule Updater.release() keeps for its
     *  receiver and its install session. Safe to call twice. */
    fun release() {
        host.connectivity?.unregisterNetworkCallback(callback)
        host.connectivity = null
    }
}
