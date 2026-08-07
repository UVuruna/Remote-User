package com.uvuruna.remoteuser

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import org.json.JSONArray
import org.json.JSONObject

/** Dictation subsystem — split from MainActivity 2026-08-05 (THE STRUCTURE
 *  LAW). The page cannot listen itself (WebView has no Speech API), so this
 *  class runs the SpeechRecognizer and talks back through `js` callbacks:
 *  `__voiceHeard(text, isFinal)` per round — the PREFERRED callback since
 *  2026-08-08 (owner design, REPEAT of task 75: round-boundary duplication
 *  survived the 0.0.293 fix because the trim lived here, untestable — this
 *  repo has no JVM test runner. The de-duplication rule now lives on the
 *  page, `client/controls.js` `voiceDedup`, proven by a fail-closed gate;
 *  see `deliver()` below) — `__voiceResult(text)` as the LEGACY fallback for
 *  a page that predates `__voiceHeard` (CLAUDE.md constraint 12: neither
 *  side may assume the other's version), `__voiceEnd(reason)` per round,
 *  `__voiceState(state)` for the Mic button's look, `__voiceInfo(text)` for
 *  SILENT diagnostics the page forwards to the PC's server log (owner round
 *  2, angrily: diagnostics are evidence for the developer, never a panel
 *  flashed at the user).
 *
 *  THE LANGUAGE IS A USER CHOICE (owner round 2): pinning to the phone's
 *  first system locale transcribed the owner's Serbian as English garbage —
 *  his phone lists English first. The page's setup card offers
 *  `candidates()` (system locales + keyboard languages, nothing hardcoded)
 *  and stores exactly one `chosenTag()`; everything below runs on THAT
 *  language: on-device when its model is installed, otherwise the Google
 *  online service pinned to it, with the model download triggered
 *  automatically and a silent switch to on-device once it lands. */
class VoiceInput(private val activity: Activity, private val js: (String) -> Unit) {

    private var recognizer: SpeechRecognizer? = null
    private var onDevice = false        // current recognizer is the on-device one
    private var supportChecked = false  // checkRecognitionSupport ran this run
    private var installed: List<String> = emptyList()
    private var supported: List<String> = emptyList()
    private var downloadTriggered = false

    /** True while the chosen language's on-device model is (probably) still
     *  downloading — the page styles the Mic button (owner: an alternate
     *  icon look, dictation keeps working online meanwhile). */
    private var downloading = false

    /** True while the app is not on screen (owner round 4, 2026-08-05: the
     *  LOCK button must stop everything — rounds kept cycling and beeping
     *  under a locked screen). Set from the activity's onPause/onResume;
     *  while true no round may start and any running one is cancelled. */
    private var background = false

    /** What has been recognized SO FAR in the running round (owner 2026-08-06,
     *  shouting: "izgovorim 10 rečenica, mikrofon nije ništa upisao... neki
     *  program preseče i obriše sve što sam pričao"). A round delivers its
     *  text only at the END, so a round that dies — ERROR_CLIENT when
     *  something else takes over, a network drop, a service restart — used to
     *  take every spoken word with it. The partial hypothesis is kept here and
     *  typed out when a round dies without a final, so speech is never simply
     *  deleted. Cleared by a final result, which always wins over it. */
    private var partial = ""

    /** FALLBACK-ONLY since 2026-08-08 (see the class doc). This is the OLD
     *  trim from the 0.0.293 fix — it only catches a PREFIX continuation of
     *  the SAME round's cumulative partial, never an overlap between two
     *  INDEPENDENT rounds' transcripts, which is exactly the shape task 75
     *  came back as (his morning message: "Da li mogu Da li mogu da ih" — a
     *  1-4 word fragment repeated once, at a round boundary). It is kept only
     *  for a page that predates `__voiceHeard` and never receives the real
     *  fix; `deliver()` no longer relies on it for a page that does. Cleared
     *  when an utterance genuinely ends (a final result) or when the mic goes
     *  off — the same lifecycle `voiceLastOut` on the page now owns for
     *  real. */
    private var lastOut = ""

    /** True while the beep-carrying streams are muted for a listening
     *  session (owner round 4: the round beeps irritate — mutable via the
     *  card's checkbox, default muted). */
    private var beepsMuted = false

    private val prefs
        get() = activity.getSharedPreferences("voice", Context.MODE_PRIVATE)

    private val audio
        get() = activity.getSystemService(Context.AUDIO_SERVICE)
            as android.media.AudioManager

    // ── The user's choice ────────────────────────────────────────────────

    fun chosenTag(): String = prefs.getString("lang", "") ?: ""

    /** The setup card picked a language: persist, rebuild the engine around
     *  it, and (re)check what the device holds for it. */
    fun setChosen(tag: String) {
        prefs.edit().putString("lang", tag).apply()
        recognizer?.destroy()
        recognizer = null
        supportChecked = false
        downloadTriggered = false
        downloading = false
        pushState()
        info("Dictation language chosen: $tag")
    }

    /** Candidate languages for the setup card, as JSON
     *  `[{tag, name, status, extra}]` — status: "ready" (on-device model
     *  installed) / "download" (model exists and will be fetched) /
     *  "online" (no on-device model — internet recognition only). Before
     *  the async support result lands, statuses default to "online".
     *  `extra: true` marks languages BEYOND the phone's own (owner round 4:
     *  everything downloadable or understood online rides in the card's
     *  collapsed "More languages" section). */
    fun candidates(): String {
        queryOnlineLangs()
        val arr = JSONArray()
        val base = candidateTags()
        for (tag in base) arr.put(langEntry(tag, extra = false))
        val extras = LinkedHashSet<String>()
        (supported + onlineLangs).forEach { tag ->
            if (tag.isNotBlank() && base.none { sameLang(it, tag) } &&
                extras.none { sameLang(it, tag) }
            ) extras.add(tag)
        }
        extras.sortedBy { java.util.Locale.forLanguageTag(it).getDisplayName() }
            .forEach { arr.put(langEntry(it, extra = true)) }
        return arr.toString()
    }

    private fun langEntry(tag: String, extra: Boolean): JSONObject {
        val locale = java.util.Locale.forLanguageTag(tag)
        val name = locale.getDisplayName(locale)
            .replaceFirstChar { it.uppercase(locale) }
        val status = when {
            installed.any { sameLang(it, tag) } -> "ready"
            supported.any { sameLang(it, tag) } -> "download"
            else -> "online"
        }
        return JSONObject().put("tag", tag).put("name", name)
            .put("status", status).put("extra", extra)
    }

    // Languages the ONLINE service understands — asked once from the speech
    // service (the classic details broadcast; empty when nothing answers).
    private var onlineLangs: List<String> = emptyList()
    private var onlineQueried = false

    private fun queryOnlineLangs() {
        if (onlineQueried) return
        onlineQueried = true
        try {
            activity.sendOrderedBroadcast(
                RecognizerIntent.getVoiceDetailsIntent(activity)
                    ?: Intent(RecognizerIntent.ACTION_GET_LANGUAGE_DETAILS),
                null,
                object : android.content.BroadcastReceiver() {
                    override fun onReceive(c: Context?, i: Intent?) {
                        onlineLangs = getResultExtras(true)
                            ?.getStringArrayList(RecognizerIntent.EXTRA_SUPPORTED_LANGUAGES)
                            ?: emptyList()
                    }
                },
                null, Activity.RESULT_OK, null, null
            )
        } catch (e: Exception) {
            // No service answering the details broadcast — the base list stands.
        }
    }

    fun state(): String = if (downloading) "downloading" else ""

    // ── Beeps (owner round 4, 2026-08-05) ────────────────────────────────
    // Android plays start/stop tones around every listening round, and the
    // rounds cycle on every silence. Default: muted while dictating; the
    // card's checkbox flips it. Mute covers the streams the tones ride on;
    // each is best-effort (Do-Not-Disturb policies may refuse one).

    fun muteBeepsPref(): Boolean = prefs.getBoolean("mute_beeps", true)

    fun setMuteBeepsPref(on: Boolean) {
        prefs.edit().putBoolean("mute_beeps", on).apply()
        if (!on) unmuteBeeps()
    }

    private val beepStreams = intArrayOf(
        android.media.AudioManager.STREAM_MUSIC,
        android.media.AudioManager.STREAM_SYSTEM,
        android.media.AudioManager.STREAM_NOTIFICATION,
    )

    private fun muteBeeps() {
        if (beepsMuted || !muteBeepsPref()) return
        beepsMuted = true
        for (s in beepStreams) {
            try {
                audio.adjustStreamVolume(s, android.media.AudioManager.ADJUST_MUTE, 0)
            } catch (e: Exception) {
                // DND security policy can refuse a stream — the rest still mute.
            }
        }
    }

    private fun unmuteBeeps() {
        if (!beepsMuted) return
        beepsMuted = false
        for (s in beepStreams) {
            try {
                audio.adjustStreamVolume(s, android.media.AudioManager.ADJUST_UNMUTE, 0)
            } catch (e: Exception) {
            }
        }
    }

    // ── Screen state (owner round 4: LOCK stops everything) ──────────────

    fun onBackground() {
        background = true
        recognizer?.cancel()
        partial = ""
        lastOut = ""
        unmuteBeeps()
    }

    fun onForeground() {
        background = false
    }

    // ── Listening ────────────────────────────────────────────────────────

    fun listen() {
        if (background) return // locked/hidden — nothing may listen (owner)
        if (!SpeechRecognizer.isRecognitionAvailable(activity)) {
            end("unavailable")
            return
        }
        val chosen = chosenTag()
        if (chosen.isBlank()) {
            end("nolang") // the page opens the setup card instead
            return
        }
        checkSupport(chosen)
        muteBeeps()
        val r = recognizer ?: makeRecognizer(chosen).also { rec ->
            rec.setRecognitionListener(listener)
            recognizer = rec
        }
        partial = ""
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            // ON since 2026-08-06, and not to type as he speaks: the
            // partial is the RESCUE COPY of a round that may never reach
            // its final result (see `partial`). Nothing is sent from it
            // while the round is alive.
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            // ONE language everywhere — the chosen one. (The on-device
            // language-switch extras exist, but a wanted-but-missing
            // language riding along silently heard NOTHING — the round-1
            // gap; one explicit language has no silent failure mode.)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, chosen)
        }
        // The previous session is STOPPED before a new one starts (owner
        // 2026-08-07). Without this, `startListening` on a recognizer that is
        // still running is refused with ERROR_CLIENT, the page restarts 250 ms
        // later, and it is refused again.
        //
        // UNPROVEN, investigated 2026-08-08 (task 75 REPEAT — his log shows
        // 177 ERROR_CLIENTs across one dictation session, roughly every 3 s,
        // continuously, with exactly this cancel-then-start pattern in
        // place): `cancel()` and `startListening()` both post to THIS
        // thread's message queue, so they run in order on OUR side — but the
        // recognizer SERVICE they talk to lives in a separate process, and
        // our ordering does not guarantee its unbind finished before the
        // rebind request lands. Posting the start as a SEPARATE message
        // instead of calling it synchronously right after cancel gives the
        // service one full run of the message loop to settle the cancel
        // first. This is the best evidence-shaped fix available from the
        // code alone; it can only be confirmed or refuted against the next
        // server.log with this build installed, not from this machine.
        r.cancel()
        android.os.Handler(android.os.Looper.getMainLooper()).post {
            // The round may have been superseded (locked, a newer listen()
            // call) while this was queued — never fire a stale start.
            if (!background && recognizer === r) r.startListening(intent)
        }
    }

    fun cancel() {
        recognizer?.cancel()
        partial = ""
        lastOut = ""   // the mic went off: whatever comes next is a new sentence
        unmuteBeeps()
    }

    fun deny() = end("denied")

    fun destroy() {
        recognizer?.destroy()
        recognizer = null
        unmuteBeeps()
    }

    // ── Internals ────────────────────────────────────────────────────────

    /** System locales + the keyboard's enabled languages — LANGUAGE-AGNOSTIC
     *  (owner decree 2026-08-05: nothing hardcoded, ever). */
    private fun candidateTags(): List<String> {
        val tags = LinkedHashSet<String>()
        val list = android.os.LocaleList.getAdjustedDefault()
        (0 until list.size()).forEach { tags.add(list[it].toLanguageTag()) }
        try {
            val imm = activity.getSystemService(Context.INPUT_METHOD_SERVICE)
                as android.view.inputmethod.InputMethodManager
            for (im in imm.enabledInputMethodList) {
                for (sub in imm.getEnabledInputMethodSubtypeList(im, true)) {
                    val tag = sub.languageTag.ifBlank { sub.locale.replace('_', '-') }
                    if (tag.isNotBlank()) tags.add(tag)
                }
            }
        } catch (e: Exception) {
            // The keyboard list is a bonus — locales alone still make a list.
        }
        return tags.filter { it.isNotBlank() }
    }

    /** "sr-RS" vs "sr-Latn-RS" vs "sr" all speak the same language — the
     *  model lists and the locale list write it differently. */
    private fun sameLang(a: String, b: String): Boolean =
        java.util.Locale.forLanguageTag(a).language ==
            java.util.Locale.forLanguageTag(b).language

    /** The recognizer for the CHOSEN language: on-device when its model is
     *  KNOWN installed (evidence, not hope), else Google's online service
     *  (the phone default — Samsung's — garbled dictation outright, owner
     *  2026-08-04), else the system default. */
    private fun makeRecognizer(chosen: String): SpeechRecognizer {
        onDevice = Build.VERSION.SDK_INT >= 33 &&
            SpeechRecognizer.isOnDeviceRecognitionAvailable(activity) &&
            installed.any { sameLang(it, chosen) }
        if (onDevice) {
            info("Voice engine: on-device @ $chosen")
            return SpeechRecognizer.createOnDeviceSpeechRecognizer(activity)
        }
        val services = activity.packageManager.queryIntentServices(
            Intent("android.speech.RecognitionService"), 0
        )
        val g = services.firstOrNull {
            it.serviceInfo.packageName == "com.google.android.googlequicksearchbox"
        }
        info("Voice engine: " + (if (g != null) "Google online" else "system service") +
            " @ $chosen")
        return if (g != null) {
            SpeechRecognizer.createSpeechRecognizer(
                activity,
                android.content.ComponentName(g.serviceInfo.packageName, g.serviceInfo.name)
            )
        } else SpeechRecognizer.createSpeechRecognizer(activity)
    }

    /** Asks the on-device engine what it REALLY holds (the round-1 gap: a
     *  language with no model heard nothing and no error ever fired). Runs
     *  once per app run — and again while a download is pending, so the
     *  moment the chosen model lands the engine silently switches on-device
     *  (owner round 2: silent switch approved, no popups). */
    private fun checkSupport(chosen: String) {
        if (Build.VERSION.SDK_INT < 33) return
        if (supportChecked && !downloading) return
        supportChecked = true
        if (!SpeechRecognizer.isOnDeviceRecognitionAvailable(activity)) return
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(
            RecognizerIntent.EXTRA_LANGUAGE_MODEL,
            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
        ).putExtra(RecognizerIntent.EXTRA_LANGUAGE, chosen)
        val probe = SpeechRecognizer.createOnDeviceSpeechRecognizer(activity)
        probe.checkRecognitionSupport(intent, activity.mainExecutor,
            object : android.speech.RecognitionSupportCallback {
                override fun onSupportResult(support: android.speech.RecognitionSupport) {
                    installed = support.installedOnDeviceLanguages
                    supported = support.supportedOnDeviceLanguages
                    val ready = installed.any { sameLang(it, chosen) }
                    if (ready && (downloading || !onDevice)) {
                        // The model is here — rebuild on-device, silently.
                        downloading = false
                        recognizer?.destroy()
                        recognizer = null
                        pushState()
                        info("On-device model for $chosen ready — switched")
                    } else if (!ready && supported.any { sameLang(it, chosen) } &&
                        !downloadTriggered
                    ) {
                        downloadTriggered = true
                        downloading = true
                        probe.triggerModelDownload(intent)
                        pushState()
                        info("Downloading the $chosen model — online meanwhile")
                    } else if (!ready && supported.none { sameLang(it, chosen) }) {
                        info("No on-device model exists for $chosen — online only")
                    }
                    probe.destroy()
                }

                override fun onError(error: Int) {
                    info("Voice support check failed (code $error)")
                    probe.destroy()
                }
            })
    }

    /** Hand over what this round produced. The final result wins; if there is
     *  none, the kept partial is used, because losing what he already said is
     *  the one outcome this whole subsystem may not have.
     *
     *  THE DE-DUPLICATION RULE LIVES ON THE PAGE since 2026-08-08 (owner
     *  design, REPEAT of task 75 — see the class doc). `__voiceHeard` gets
     *  the RAW text plus `isFinal` and does its own round-boundary overlap
     *  trim (`client/controls.js` `voiceDedup`), proven by
     *  `tests/test_voice_dedup.py`. `fallback` below is computed ONLY for a
     *  page too old to define `__voiceHeard` — the OLD prefix-only trim from
     *  the 0.0.293 fix, kept with its OLD known gap (misses a non-prefix
     *  overlap between two rounds, does not trim a final) because it is a
     *  compatibility path, not the fix. */
    private fun deliver(text: String?) {
        val isFinal = !text.isNullOrBlank()
        val raw = if (isFinal) text!! else partial
        partial = ""
        if (raw.isBlank()) return

        var fallback = raw
        if (isFinal) {
            lastOut = ""            // the utterance is over; the next one is new
        } else {
            if (lastOut.isNotEmpty() && raw.startsWith(lastOut)) {
                fallback = raw.substring(lastOut.length).trimStart()
            } else if (lastOut.isNotEmpty() && lastOut.startsWith(raw)) {
                fallback = ""        // nothing new was heard — say nothing
            }
            if (fallback.isNotBlank()) {
                lastOut = if (lastOut.isEmpty()) fallback else "$lastOut $fallback"
            }
        }

        val rawJs = JSONObject.quote(raw)
        val fallbackJs = JSONObject.quote(fallback)
        js(
            "if (window.__voiceHeard) { window.__voiceHeard($rawJs, $isFinal); } " +
                "else if (window.__voiceResult && $fallbackJs) { window.__voiceResult($fallbackJs); }"
        )
    }

    private val listener = object : RecognitionListener {
        override fun onResults(results: Bundle?) {
            deliver(results
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull())
            end("")
        }

        override fun onError(error: Int) {
            // The round died. Whatever was already recognized is typed out
            // instead of being thrown away with it (owner 2026-08-06) — the
            // ERROR_CLIENT lines that fill his log are exactly these rounds.
            deliver(null)
            // NO_MATCH / SPEECH_TIMEOUT are a quiet room, not failures — the
            // page starts the next round while ON. Every OTHER error goes to
            // the server log (never the screen).
            if (error != SpeechRecognizer.ERROR_NO_MATCH &&
                error != SpeechRecognizer.ERROR_SPEECH_TIMEOUT
            ) {
                info("Voice error $error (" + (if (onDevice) "on-device" else "online") + ")")
            }
            if (error == SpeechRecognizer.ERROR_CLIENT) {
                // Investigated 2026-08-08 (task 75 REPEAT, Path C(b)):
                // Android's own guidance for ERROR_CLIENT is that the
                // instance may be left unusable. Reusing a possibly wedged
                // recognizer is a second plausible source of his 177-in-one-
                // session refusal storm. Destroying costs nothing — `listen()`
                // lazily rebuilds — and can only help; unproven from this
                // machine, confirmable only against his next server.log.
                recognizer?.destroy()
                recognizer = null
            }
            end(
                if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) "denied"
                else ""
            )
        }

        override fun onReadyForSpeech(params: Bundle?) {}
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {}
        override fun onPartialResults(partialResults: Bundle?) {
            val text = partialResults
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()
            if (!text.isNullOrBlank()) partial = text   // the rescue copy, nothing sent
        }
        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    private fun end(reason: String) = js("window.__voiceEnd && __voiceEnd('$reason')")

    private fun info(text: String) =
        js("window.__voiceInfo && __voiceInfo(${JSONObject.quote(text)})")

    private fun pushState() =
        js("window.__voiceState && __voiceState(${JSONObject.quote(state())})")
}
