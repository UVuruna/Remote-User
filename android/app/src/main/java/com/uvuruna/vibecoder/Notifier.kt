package com.uvuruna.vibecoder

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

/**
 * "The PC calls you" — the phone half of ROADMAP Phase H (owner 2026-08-05).
 *
 * The PC sends a notice naming the AGENT that finished, because the owner
 * runs several at once and a bare beep says nothing:
 *
 *   "nije dovoljno samo da kaže beep kad završi agent … najbolje od svega je
 *    da izbaci notifikaciju koja opisuje koji agent je završio"
 *
 * Two carriers live here, and each covers what the other cannot:
 *
 *  - a real system NOTIFICATION, which survives the app being backgrounded
 *    and the screen being off — the situation this whole feature is for. The
 *    agent's name is the notification TAG, so a second notice from the same
 *    agent replaces its own line while four agents keep four lines;
 *  - SPEECH (TextToSpeech), for when his eyes and hands are on the PC. The
 *    engine is opened lazily and kept, because the first `speak()` after a
 *    cold start otherwise lands after the sentence it was asked to say.
 *
 * The page decides which of the two to use (its own per-device switches) —
 * this class only knows how to deliver.
 *
 * HOW it speaks is the PC's decision (owner round R2, 2026-08-07). The desktop
 * Settings window offers a voice and a speaking pace, and both ride on every
 * notify frame rather than being pushed here once: nothing about the voice is
 * then stored on the phone, so no reconnect can leave it speaking in a voice
 * the desktop no longer selects. The list of voices to choose FROM can only
 * come from here — a TextToSpeech engine's voices differ per device, per
 * language pack, per Android version, and the PC cannot see any of it.
 */
/** `js` is how a page learns that a spoken sample has FINISHED. It is
 *  optional because `NoticeService` also builds a Notifier and has no page at
 *  all — a service speaking a notice into a pocket has nobody to tell. */
class Notifier(private val ctx: Context, private val js: ((String) -> Unit)? = null) {

    companion object {
        private const val TAG = "Notifier"
        private const val CHANNEL_ID = "agents"
        /** The utterance id a voice SAMPLE rides under. Only a sample is
         *  reported back to the page — a notice being spoken is not something
         *  the voice card is waiting on. */
        private const val UTT_SAMPLE = "sample"
        /** Where the tapped notice happened — `{index, name}` as JSON. */
        const val EXTRA_JUMP = "com.uvuruna.vibecoder.JUMP"
        // One id per agent name, so notifications REPLACE per agent instead of
        // stacking one line per finished turn. Hashing keeps that stable
        // across app restarts without keeping a table.
        private fun idFor(tag: String) = tag.hashCode() and 0x7fffffff
    }

    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private val pending = ArrayList<String>()
    // What the PC last asked for. `speechRate` is TextToSpeech's own scale
    // (1 = the engine's normal pace); `voiceName` is a Voice.name exactly as
    // this device reported it, and an empty one means "whatever the engine
    // thinks best for its locale".
    private var speechRate = 1f
    private var voiceName = ""

    init {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Agents on the PC",
                NotificationManager.IMPORTANCE_HIGH,   // heads-up: this is the point
            ).apply {
                description = "When a job on your PC finishes or needs you"
                enableVibration(true)
            }
            ctx.getSystemService(NotificationManager::class.java)
                ?.createNotificationChannel(channel)
        }
        // Bound at START, not at the first notice. It always had one reason —
        // the first speak() after a cold start otherwise lands after the
        // sentence it was asked to say — and round R2 gave it a second:
        // `voices()` is asked the moment the page connects, and an engine that
        // has not bound yet has nothing to report.
        ensureEngine()
    }

    /** Raises (or replaces) one agent's notification.
     *
     *  `jump` is the PC's answer to "where did this happen" — a JSON
     *  `{index, name}` naming the layout that agent's project is showing
     *  (owner 2026-08-08, task 110: *"da klikom na notifikaciju nas odvede do
     *  tog layouta"*). It travels as an intent extra and is read out by
     *  MainActivity; empty means the PC could not say, and the tap then does
     *  exactly what it always did — open the app. */
    fun post(title: String, text: String, tag: String, jump: String = "") {
        val intent = Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        if (jump.isNotBlank()) intent.putExtra(EXTRA_JUMP, jump)
        val open = PendingIntent.getActivity(
            // The request code is PER AGENT, not 0 for everyone. With one
            // shared code, FLAG_UPDATE_CURRENT rewrites the SAME PendingIntent
            // every time, so four agents' notifications would all carry the
            // extras of whichever finished last — and the tap would open the
            // wrong window while looking perfectly right.
            ctx, idFor(tag), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(title)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(Notification.CATEGORY_STATUS)
            .setDefaults(NotificationCompat.DEFAULT_ALL)   // sound + vibration
            .setAutoCancel(true)
            .setContentIntent(open)
        if (text.isNotEmpty()) {
            builder.setContentText(text)
            // A finished agent often has more to say than one line — the
            // expanded style is what keeps the whole sentence readable.
            builder.setStyle(NotificationCompat.BigTextStyle().bigText(text))
        }
        try {
            NotificationManagerCompat.from(ctx).notify(tag, idFor(tag), builder.build())
        } catch (e: SecurityException) {
            // POST_NOTIFICATIONS refused (Android 13+). Not fatal: the page
            // still speaks and toasts, and the log says why the banner is
            // missing instead of leaving a silent mystery.
            Log.w(TAG, "Notification refused — permission not granted", e)
        }
    }

    /** Says it out loud, in the voice and at the pace the PC asked for.
     *  Queues until the engine is ready, never drops. */
    fun speak(text: String, voice: String = "", rate: Float = 1f) {
        if (text.isBlank()) return
        setSpeechRate(rate)
        setVoice(voice)
        synchronized(pending) { pending.add(text) }
        if (ttsReady) drain() else ensureEngine()
    }

    /** Speaks a SAMPLE: interrupts whatever is speaking and says this
     *  instead, then tells the page when it is really finished.
     *
     *  TWO THINGS `speak` CANNOT DO, and both are his report of 2026-08-13
     *  (a second voice could not be tapped until the first finished, and the
     *  speaker button stayed lit afterwards).
     *
     *  1. IT INTERRUPTS. `speak` queues (QUEUE_ADD) because a notice must
     *     never be dropped — two agents finishing together are two things he
     *     needs to hear. A sample is the opposite: tapping voice 13 while
     *     voice 11 talks means "let me hear THIRTEEN", and queueing it would
     *     also speak it in the wrong voice, since the engine's voice is set
     *     per call but applies to the whole queue.
     *  2. IT ANSWERS. The page had to GUESS how long the sample would take
     *     from its character count — forbidden outright (root CLAUDE.md,
     *     constraint 15: we never estimate how long another program needs, we
     *     watch for the condition). The engine knows, so it says so.
     *
     *  A NEW METHOD rather than a flag on `speak`, for the reason written
     *  over `speakAs`: the page is served by the PC and this shell is
     *  installed separately, so a changed signature simply stops resolving
     *  for a page that has not been re-served yet. */
    fun speakSample(text: String, voice: String = "", rate: Float = 1f) {
        if (text.isBlank()) return
        setSpeechRate(rate)
        setVoice(voice)
        // A queued NOTICE must survive being interrupted by a sample — it is
        // the thing this app exists to deliver. Only the utterance already
        // leaving the speaker is cut off.
        if (!ttsReady) { ensureEngine(); synchronized(pending) { pending.add(text) }; return }
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, UTT_SAMPLE)
    }

    /** The engine has stopped speaking a SAMPLE — said once per sample,
     *  whether it ended, was cut off by the next one, or failed. */
    private fun sampleDone() {
        js?.invoke("window.__ttsDone && __ttsDone()")
    }

    /** Every voice this DEVICE has, as JSON the page forwards to the PC:
     *  `[{name, label, locale}, …]`. `name` is the identity the PC stores and
     *  sends back; `label` is what a person reads. Empty when the engine has
     *  not bound yet or has none — the desktop window then says so instead of
     *  pretending the phone is mute. */
    fun voices(): String {
        ensureEngine()
        val array = JSONArray()
        val engine = tts
        if (engine == null || !ttsReady) return array.toString()
        try {
            for (voice in engine.voices.orEmpty()) {
                // A voice whose data is not downloaded cannot say anything —
                // offering it on the PC would be a choice that silently fails.
                if (voice.features?.contains(
                        TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED) == true) continue
                val variant = voice.name.substringAfterLast('#')
                    .removeSuffix("-local").removeSuffix("-network")
                array.put(JSONObject()
                    .put("name", voice.name)
                    .put("label", "${voice.locale.displayLanguage} $variant".trim())
                    .put("locale", voice.locale.toLanguageTag()))
            }
        } catch (e: Exception) {
            // getVoices() is documented to work and throws on real devices
            // anyway (engines that report a null voice set). An empty list is
            // a usable answer; a crashed shell is not.
            Log.w(TAG, "Could not list the text-to-speech voices", e)
        }
        return array.toString()
    }

    private fun setSpeechRate(rate: Float) {
        speechRate = if (rate > 0f) rate else 1f
        if (ttsReady) tts?.setSpeechRate(speechRate)
    }

    private fun setVoice(name: String) {
        voiceName = name
        if (ttsReady) applyVoice()
    }

    private fun applyVoice() {
        val engine = tts ?: return
        if (voiceName.isEmpty()) return          // the engine's own choice
        // A voice this device does not have falls back to the default: the PC
        // may be remembering a phone that is no longer this one, and a missing
        // voice must never mean a silent notice.
        val match = try {
            engine.voices.orEmpty().firstOrNull { it.name == voiceName }
        } catch (e: Exception) {
            Log.w(TAG, "Could not read the voice list", e); null
        }
        if (match != null) engine.voice = match
        else Log.w(TAG, "Voice '$voiceName' is not on this device — using the default")
    }

    private fun drain() {
        val queued = synchronized(pending) {
            val copy = ArrayList(pending); pending.clear(); copy
        }
        queued.forEach { tts?.speak(it, TextToSpeech.QUEUE_ADD, null, "agent") }
    }

    private fun ensureEngine() {
        if (tts != null) return             // bound, or still binding
        tts = TextToSpeech(ctx) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            if (!ttsReady) {
                Log.w(TAG, "TextToSpeech unavailable (status $status)")
                synchronized(pending) { pending.clear() }
                return@TextToSpeech
            }
            // The default locale is the phone's, which is what the owner
            // hears best; an engine without it falls back on its own.
            tts?.language = Locale.getDefault()
            tts?.setSpeechRate(speechRate)
            // ALL THREE ENDINGS REPORT, and that is the point: a sample that
            // failed or was cut off leaves the page's speaker button lit
            // forever if only `onDone` speaks. `onStop` fires for the
            // utterance a QUEUE_FLUSH replaced, which is exactly what one tap
            // interrupting another looks like.
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(id: String?) {}
                override fun onDone(id: String?) { if (id == UTT_SAMPLE) sampleDone() }
                override fun onStop(id: String?, interrupted: Boolean) {
                    if (id == UTT_SAMPLE) sampleDone()
                }
                @Deprecated("Kept: the non-deprecated overload is API 21+ only in name — "
                            + "the base class still routes old engines through this one.")
                override fun onError(id: String?) { if (id == UTT_SAMPLE) sampleDone() }
                override fun onError(id: String?, code: Int) {
                    if (id == UTT_SAMPLE) sampleDone()
                }
            })
            applyVoice()
            drain()
        }
    }

    fun release() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        ttsReady = false
        voiceName = ""
        speechRate = 1f
    }
}
