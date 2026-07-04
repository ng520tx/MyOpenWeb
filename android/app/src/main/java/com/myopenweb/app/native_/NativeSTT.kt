package com.myopenweb.app.native_

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.myopenweb.app.MainActivity
import com.myopenweb.app.bridge.MoaBridge
import com.myopenweb.app.util.JsonUtil

class NativeSTT(
    private val activity: MainActivity,
    private val bridge: MoaBridge
) {

    companion object {
        private const val TAG = "NativeSTT"
        private const val PERMISSION_REQUEST_CODE = 1001
    }

    private var recognizer: SpeechRecognizer? = null
    private var pendingCbFuncName: String = ""
    private var pendingLang: String = "zh-CN"

    fun start(lang: String, cbFuncName: String) {
        if (!SpeechRecognizer.isRecognitionAvailable(activity)) {
            bridge.invokeCallback(cbFuncName, JsonUtil.error("Speech recognition not available"))
            return
        }

        if (ContextCompat.checkSelfPermission(activity, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            pendingCbFuncName = cbFuncName
            pendingLang = lang
            ActivityCompat.requestPermissions(
                activity,
                arrayOf(Manifest.permission.RECORD_AUDIO),
                PERMISSION_REQUEST_CODE
            )
            return
        }

        startRecognition(lang, cbFuncName)
    }

    fun onPermissionResult(granted: Boolean) {
        if (granted && pendingCbFuncName.isNotEmpty()) {
            startRecognition(pendingLang, pendingCbFuncName)
        } else if (pendingCbFuncName.isNotEmpty()) {
            bridge.invokeCallback(pendingCbFuncName, JsonUtil.error("Permission denied"))
        }
        pendingCbFuncName = ""
    }

    private fun startRecognition(lang: String, cbFuncName: String) {
        activity.runOnUiThread {
            try {
                stop()
                recognizer = SpeechRecognizer.createSpeechRecognizer(activity)
                recognizer?.setRecognitionListener(object : RecognitionListener {
                    override fun onResults(results: Bundle?) {
                        val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        val text = matches?.firstOrNull() ?: ""
                        bridge.invokeCallback(cbFuncName, JsonUtil.success("text" to text))
                    }

                    override fun onError(error: Int) {
                        val msg = when (error) {
                            SpeechRecognizer.ERROR_NO_MATCH -> "No speech detected"
                            SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Speech timeout"
                            SpeechRecognizer.ERROR_AUDIO -> "Audio error"
                            SpeechRecognizer.ERROR_NETWORK -> "Network error"
                            else -> "STT error: $error"
                        }
                        bridge.invokeCallback(cbFuncName, JsonUtil.error(msg))
                    }

                    override fun onReadyForSpeech(params: Bundle?) {}
                    override fun onBeginningOfSpeech() {}
                    override fun onRmsChanged(rmsdB: Float) {}
                    override fun onBufferReceived(buffer: ByteArray?) {}
                    override fun onEndOfSpeech() {}
                    override fun onPartialResults(partialResults: Bundle?) {}
                    override fun onEvent(eventType: Int, params: Bundle?) {}
                })

                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang)
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                }
                recognizer?.startListening(intent)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start STT", e)
                bridge.invokeCallback(cbFuncName, JsonUtil.error(e.message ?: "STT start failed"))
            }
        }
    }

    fun stop() {
        try {
            recognizer?.stopListening()
            recognizer?.cancel()
            recognizer?.destroy()
            recognizer = null
        } catch (_: Exception) {}
    }

    fun destroy() {
        stop()
    }
}
