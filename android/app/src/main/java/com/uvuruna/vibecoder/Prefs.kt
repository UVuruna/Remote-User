package com.uvuruna.vibecoder

import android.content.Context
import java.util.UUID

/** Two stored addresses, both tokened page URLs:
 *  - LAN: written by pairing (the QR always encodes the home address)
 *  - Tailscale: learned from the page itself — the client receives
 *    `tailscale_url` in every `config` and hands it over via the JS bridge
 *  MainActivity probes both and loads whichever is reachable, so the app
 *  works at home (LAN) and anywhere (mesh) without the user knowing why. */
object Prefs {
    private const val FILE = "vibecoder"
    private const val KEY_LAN = "pairing_url"
    private const val KEY_TS = "tailscale_url"
    private const val KEY_DEVICE = "device_id"
    private const val KEY_ORIENT = "orient_lock"

    /** Where the PAGE's own per-device preferences live (the `prefGet`/
     *  `prefSet` bridge). Named here rather than in Bridge.kt because the
     *  notice service reads one of them — the user's "speak / banner"
     *  switches — while no page exists to ask (owner 2026-08-07). */
    const val CLIENT_FILE = "client_prefs"

    /** WHEN this device listens for notices (owner 2026-08-12).
     *
     *  His complaint was that two states kept being confused: the app RUNNING
     *  in the background — behind other apps, or with the phone locked and the
     *  screen off — and the app CLOSED, swiped out of recents. A locked phone
     *  with the app alive keeps its channel whatever this answers; this is
     *  only about the swipe.
     *
     *  Written by the page's Notices card (client/notify.js) through the
     *  `prefSet` bridge, so it lands in CLIENT_FILE under the bridge's own
     *  `p_` prefix — and this is read while NO page exists, exactly like the
     *  notice voice beside it. Anything that is not the literal "always" is
     *  the shipped default: a device that never opened the card behaves
     *  exactly as 0.0.127 did, and only a deliberate tap widens it. */
    fun noticeAlways(context: Context): Boolean =
        context.getSharedPreferences(CLIENT_FILE, Context.MODE_PRIVATE)
            .getString("p_noticeWhen", "") == "always"

    /** WHETHER this device listens for notices at all (T80b, owner-approved
     *  2026-08-14). The switch beside it, `noticeAlways`, answers WHEN — and
     *  until this round that was the only choice there was: the waiting
     *  channel started unconditionally at every launch and woke the radio
     *  ~1440 times a day whether or not he wanted notices on this handset.
     *
     *  Written by the page's Notices card through the `setNoticeChannel`
     *  bridge, into the SAME per-device store the `prefGet`/`prefSet` bridge
     *  uses (CLIENT_FILE, under the bridge's own `p_` prefix), because it is
     *  read while NO page exists — MainActivity asks it before the WebView has
     *  loaded anything.
     *
     *  DEFAULT ON, and the question is an equality against the one literal the
     *  page writes for "off": an absent pref, an empty one, a store from an
     *  older version — every one of them is ON, so nothing changes for anyone
     *  who does not touch the row, and only a deliberate tap can silence a
     *  device. */
    fun noticeChannel(context: Context): Boolean =
        context.getSharedPreferences(CLIENT_FILE, Context.MODE_PRIVATE)
            .getString("p_noticeChannel", "") != "off"

    fun setNoticeChannel(context: Context, on: Boolean) {
        context.getSharedPreferences(CLIENT_FILE, Context.MODE_PRIVATE)
            .edit().putString("p_noticeChannel", if (on) "on" else "off").apply()
    }

    /** Both stored page URLs, LAN first: the notice service probes them in
     *  this order exactly as MainActivity's resolver does. */
    fun addresses(context: Context): List<String> =
        listOfNotNull(lanUrl(context), tsUrl(context)).distinct()

    /** WHICH PHONE THIS IS, to the PC's notice channel (task 209).
     *
     *  The owner runs the app on a tablet AND a phone. The PC used to keep a
     *  single waiting channel, so each device's attach kicked the other's and
     *  the two ping-ponged every few seconds all night — and a notice reached
     *  only whichever held the slot at that instant. It now keys one channel
     *  per device, and this is the key.
     *
     *  A random UUID made on first use and kept in this app's own preferences:
     *  it identifies an INSTALL, not a person and not a handset. Deliberately
     *  NOT `ANDROID_ID`, IMEI or any hardware id — those are restricted,
     *  survive an uninstall, and would be a real identifier travelling in a
     *  query string for a job a throwaway random number does perfectly. A
     *  reinstall or a cleared app-data simply mints a new one; the worst that
     *  costs is one stale channel on the PC until its socket dies. */
    fun deviceId(context: Context): String {
        val store = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        val stored = store.getString(KEY_DEVICE, null)
        if (!stored.isNullOrBlank()) return stored
        val fresh = UUID.randomUUID().toString()
        store.edit().putString(KEY_DEVICE, fresh).apply()
        return fresh
    }

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

    /** The page's last `Android.lockOrientation` mode — "portrait" /
     *  "landscape" / "" (unlocked). Task 204: `requestedOrientation` lives
     *  only on the LIVE Activity instance and Android never persists it —
     *  an excursion whose picker got the process killed for memory, or any
     *  other Activity recreation, comes back with a FRESH instance whose
     *  `requestedOrientation` is the manifest default (unlocked), even
     *  though the page's own state still believes a layout is focused and
     *  never re-sends `lockOrientation` on its own (it only sends it when
     *  the FOCUS changes). Remembering the mode here lets onCreate/onResume
     *  re-assert it before the page has even loaded, closing that window. */
    fun orientLock(context: Context): String =
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(KEY_ORIENT, "") ?: ""

    fun setOrientLock(context: Context, mode: String) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .edit().putString(KEY_ORIENT, mode).apply()
    }
}
