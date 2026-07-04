package com.myopenweb.app.native_

import android.speech.tts.TextToSpeech
import android.util.Log
import com.myopenweb.app.MainActivity
import java.util.Locale

class NativeTTS(
    private val activity: MainActivity
) : TextToSpeech.OnInitListener {

    companion object {
        private const val TAG = "NativeTTS"
    }

    private var tts: TextToSpeech? = null
    private var isReady = false

    init {
        tts = TextToSpeech(activity, this)
    }

    override fun onInit(status: Int) {
        isReady = status == TextToSpeech.SUCCESS
        if (!isReady) {
            Log.e(TAG, "TTS init failed with status: $status")
        }
    }

    fun play(text: String, lang: String, rate: Float) {
        if (!isReady || text.isBlank()) return

        val locale = when {
            lang.startsWith("zh") -> Locale.CHINA
            lang.startsWith("en") -> Locale.US
            lang.startsWith("ja") -> Locale.JAPAN
            else -> Locale.forLanguageTag(lang)
        }
        tts?.language = locale
        tts?.setSpeechRate(rate)
        tts?.speak(text, TextToSpeech.QUEUE_ADD, null, "mow_tts_${System.currentTimeMillis()}")
    }

    fun stop() {
        tts?.stop()
    }

    fun destroy() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        isReady = false
    }
}
