package com.myopenweb.app

import android.annotation.SuppressLint
import android.util.Log
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import com.myopenweb.app.bridge.MoaBridge

class WebViewContainer(
    private val activity: MainActivity,
    private val webView: WebView
) {

    companion object {
        private const val TAG = "MyOpenWeb"
        private const val ASSETS_URL = "file:///android_asset/web/index.html"
    }

    private lateinit var bridge: MoaBridge

    @SuppressLint("SetJavaScriptEnabled")
    fun init() {
        bridge = MoaBridge(activity, webView)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = true
            allowContentAccess = true
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            mediaPlaybackRequiresUserGesture = false
            useWideViewPort = true
            loadWithOverviewMode = true
            setSupportZoom(false)
            builtInZoomControls = false
            displayZoomControls = false
            databaseEnabled = true
            textZoom = 100
        }

        webView.addJavascriptInterface(bridge, "moaBridge")

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?
            ): Boolean {
                return false
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                bridge.safeAreaHelper.injectCssVariables()
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(msg: ConsoleMessage?): Boolean {
                msg?.let {
                    Log.d(TAG, "[${it.messageLevel()}] ${it.message()} (${it.sourceId()}:${it.lineNumber()})")
                }
                return true
            }
        }
    }

    fun loadPage() {
        val url = if (BuildConfig.DEBUG) {
            BuildConfig.DEV_SERVER_URL
        } else {
            ASSETS_URL
        }
        Log.d(TAG, "Loading: $url")
        webView.loadUrl(url)
    }

    fun handleBack(): Boolean {
        if (webView.canGoBack()) {
            webView.goBack()
            return true
        }
        return false
    }

    fun onResume() {
        webView.onResume()
    }

    fun onPause() {
        webView.onPause()
    }

    fun onDestroy() {
        bridge.destroy()
        webView.destroy()
    }

    fun getBridge(): MoaBridge = bridge

    fun evaluateJs(script: String) {
        activity.runOnUiThread {
            webView.evaluateJavascript(script, null)
        }
    }
}
