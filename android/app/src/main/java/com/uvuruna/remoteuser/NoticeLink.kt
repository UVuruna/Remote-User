package com.uvuruna.remoteuser

import android.net.Uri
import android.util.Log
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * The waiting state, and nothing else (owner decree 2026-08-07).
 *
 *   *"samo je važno da ta komunikacija koja mora da bude u pozadini bude
 *    minimalna … android strana čeka signal, ne prima ništa od kompjutera,
 *    ali ostane u stanju čekanja signala."*
 *
 * One thread. It opens `GET /notices?token=…` on the PC and then BLOCKS in
 * `readLine()`. It sends nothing, asks for nothing, polls nothing, and holds
 * no wake lock. A blocked read costs no CPU at all: the thread is parked in
 * the kernel until a packet arrives, and an arriving packet is what wakes the
 * device — the radio's own job, which it does for every app on the phone.
 *
 * What comes back down that socket, ever:
 *   - a bare newline every 60 s, the PC's beat. One byte. It keeps the
 *     router's / carrier's NAT mapping for this connection alive, and it is
 *     how a link that died silently gets noticed — hearing nothing for
 *     `BEAT_MISS` beats means reconnect, because a socket that is quiet and a
 *     socket that is dead look identical from here.
 *   - one JSON line when an agent on the PC has something to say. That line
 *     is byte-for-byte the frame the page would have received.
 *
 * Why plain HTTP and not a WebSocket or a push service: this shell already
 * speaks `HttpURLConnection` (it probes `/ping` with it), so the waiting
 * state costs the APK no new dependency, no handshake, no library, and no
 * third party between the owner's PC and the owner's phone.
 *
 * Deliberately Android-UI-free: it knows addresses, sockets and lines. What
 * to DO with a notice belongs to NoticeService.
 */
class NoticeLink(
    private val addresses: () -> List<String>,
    private val onNotice: (JSONObject) -> Unit,
) {

    private companion object {
        const val TAG = "NoticeLink"
        const val CONNECT_TIMEOUT_MS = 8_000
        // Must outlast the PC's beat with room to spare: server/notify.py
        // beats every BEAT_S = 60 s and BEAT_MISS = 3 is the shared rule.
        // A read that times out is a link that stopped answering, not an
        // idle one — idle still delivers a byte a minute.
        const val READ_TIMEOUT_MS = 180_000
        // Reconnect backoff. It starts gentle and gives up quickly on being
        // eager: a phone with no route to the PC (out of the house, tunnel
        // off) must not retry every few seconds all night — that, not the
        // waiting itself, is what a background socket costs in battery.
        const val BACKOFF_START_MS = 5_000L
        const val BACKOFF_MAX_MS = 300_000L
    }

    @Volatile private var running = false
    @Volatile private var live: HttpURLConnection? = null
    private var thread: Thread? = null

    fun start() {
        if (running) return
        running = true
        thread = Thread({ loop() }, "notice-link").apply {
            isDaemon = true
            start()
        }
    }

    fun stop() {
        running = false
        // Yank the socket: the thread is parked inside readLine() and nothing
        // short of closing it under him will bring him back.
        try {
            live?.disconnect()
        } catch (e: Exception) {
            Log.w(TAG, "Could not close the waiting socket", e)
        }
        thread?.interrupt()
        thread = null
    }

    private fun loop() {
        var backoff = BACKOFF_START_MS
        while (running) {
            val opened = addresses().any { url -> running && wait(url) }
            if (!running) return
            // `opened` means one address let us wait for a while and then the
            // connection ended — normal (the PC restarted, the Wi-Fi moved).
            // Reconnect promptly. Nothing answering at all is the case that
            // must not spin.
            backoff = if (opened) BACKOFF_START_MS
            else (backoff * 2).coerceAtMost(BACKOFF_MAX_MS)
            try {
                Thread.sleep(backoff)
            } catch (e: InterruptedException) {
                return
            }
        }
    }

    /** One attempt at one address: connect, then read lines until it ends.
     *  Returns true if the PC actually accepted us (so the caller knows the
     *  difference between "the link dropped" and "there is no PC here"). */
    private fun wait(pageUrl: String): Boolean {
        val target = noticeUrl(pageUrl) ?: return false
        var accepted = false
        var conn: HttpURLConnection? = null
        try {
            conn = (URL(target).openConnection() as HttpURLConnection).apply {
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                instanceFollowRedirects = false
                useCaches = false
                setRequestProperty("Accept", "application/x-ndjson")
            }
            live = conn
            // Only a 200 is the PC. A captive portal answers anything with a
            // login page — the same false positive that once sent the WebView
            // to a dead address (live failure 2026-07-27) — and a 403 means
            // the token rotated and this phone must be paired again.
            if (conn.responseCode != 200) {
                Log.w(TAG, "Notice channel refused: HTTP ${conn.responseCode}")
                return false
            }
            accepted = true
            Log.i(TAG, "Waiting for notices from the PC")
            BufferedReader(InputStreamReader(conn.inputStream)).use { reader ->
                while (running) {
                    val line = reader.readLine() ?: break   // the PC ended it
                    if (line.isBlank()) continue             // the beat — not news
                    try {
                        onNotice(JSONObject(line))
                    } catch (e: Exception) {
                        // A line we cannot parse is a version drift, not a
                        // reason to drop the channel the owner is waiting on.
                        Log.w(TAG, "Unreadable notice line", e)
                    }
                }
            }
        } catch (e: Exception) {
            // Everything here is an ordinary fact of a phone's life: no
            // route, Wi-Fi handover, the PC asleep, a read that timed out
            // because the beats stopped. Logged, never surfaced — the card
            // in the page is what tells the owner anything he can act on.
            Log.i(TAG, "Notice channel ended (${e.javaClass.simpleName}: ${e.message})")
        } finally {
            live = null
            try {
                conn?.disconnect()
            } catch (e: Exception) {
                Log.w(TAG, "Could not close the waiting socket", e)
            }
        }
        return accepted
    }

    /** The stored PAIRING url carries the token in its query — the notice
     *  channel is the same host, the same port and the same token. */
    private fun noticeUrl(pageUrl: String): String? = try {
        val u = Uri.parse(pageUrl)
        val token = u.getQueryParameter("token")
        // A stored address always carries its port, but -1 (none given) would
        // build "http://host:-1/…" and fail forever with no clue why.
        val port = if (u.port > 0) u.port else 80
        if (token.isNullOrBlank() || u.host == null) null
        else "${u.scheme}://${u.host}:$port/notices?token=$token"
    } catch (e: Exception) {
        Log.w(TAG, "Stored address is not a URL: $pageUrl", e)
        null
    }
}
