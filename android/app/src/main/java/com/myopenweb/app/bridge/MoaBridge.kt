package com.myopenweb.app.bridge

import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import com.myopenweb.app.MainActivity
import com.myopenweb.app.native_.NativeFilePicker
import com.myopenweb.app.native_.NativeSTT
import com.myopenweb.app.native_.NativeTTS
import com.myopenweb.app.native_.SafeAreaHelper
import com.myopenweb.app.util.JsonUtil

class MoaBridge(
    private val activity: MainActivity,
    private val webView: WebView
) {

    companion object {
        private const val TAG = "MoaBridge"
    }

    val nativeSTT = NativeSTT(activity, this)
    val nativeTTS = NativeTTS(activity)
    val nativeFilePicker = NativeFilePicker(activity, this)
    val safeAreaHelper = SafeAreaHelper(activity)

    @JavascriptInterface
    fun callNative(method: String, paramsJson: String?) {
        Log.d(TAG, "callNative: $method, params: $paramsJson")

        val params = JsonUtil.parse(paramsJson)
        val cbFuncName = params.optString("cbFuncName", "")

        try {
            when (method) {
                "startSTT" -> {
                    val lang = params.optString("lang", "zh-CN")
                    nativeSTT.start(lang, cbFuncName)
                }
                "stopSTT" -> nativeSTT.stop()

                "playTTS" -> {
                    val text = params.optString("text", "")
                    val lang = params.optString("lang", "zh-CN")
                    val rate = params.optDouble("rate", 1.0).toFloat()
                    nativeTTS.play(text, lang, rate)
                }
                "stopTTS" -> nativeTTS.stop()

                "pickFile" -> {
                    val accept = params.optString("accept", "*/*")
                    nativeFilePicker.pick(accept, cbFuncName)
                }

                "goBack" -> activity.runOnUiThread {
                    @Suppress("DEPRECATION")
                    activity.onBackPressed()
                }

                "setTitle" -> {
                    val title = params.optString("title", "")
                    activity.runOnUiThread { activity.title = title }
                }

                "getSafeArea" -> {
                    val result = safeAreaHelper.getSafeArea()
                    invokeCallback(cbFuncName, result)
                }

                else -> Log.w(TAG, "Unknown method: $method")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error in callNative($method)", e)
            if (cbFuncName.isNotEmpty()) {
                invokeCallback(cbFuncName, JsonUtil.error(e.message ?: "Unknown error"))
            }
        }
    }

    fun invokeCallback(cbFuncName: String, jsonData: String) {
        if (cbFuncName.isEmpty()) return
        val escaped = jsonData.replace("\\", "\\\\").replace("'", "\\'")
        val script = "if(window['$cbFuncName']){window['$cbFuncName']('$escaped')}"
        activity.runOnUiThread {
            webView.evaluateJavascript(script, null)
        }
    }

    fun destroy() {
        nativeSTT.destroy()
        nativeTTS.destroy()
    }
}
