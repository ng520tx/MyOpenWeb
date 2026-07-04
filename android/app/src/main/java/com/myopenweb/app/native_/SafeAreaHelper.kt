package com.myopenweb.app.native_

import android.os.Build
import android.view.WindowInsets
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.myopenweb.app.MainActivity
import com.myopenweb.app.util.JsonUtil

class SafeAreaHelper(
    private val activity: MainActivity
) {

    fun getSafeArea(): String {
        val topPx: Int
        val bottomPx: Int

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val insets = activity.window.decorView.rootWindowInsets
            if (insets != null) {
                val systemBars = insets.getInsets(WindowInsets.Type.systemBars())
                topPx = systemBars.top
                bottomPx = systemBars.bottom
            } else {
                topPx = getStatusBarHeight()
                bottomPx = getNavigationBarHeight()
            }
        } else {
            val rootView = activity.window.decorView
            val insetsCompat = ViewCompat.getRootWindowInsets(rootView)
            if (insetsCompat != null) {
                val systemBars = insetsCompat.getInsets(WindowInsetsCompat.Type.systemBars())
                topPx = systemBars.top
                bottomPx = systemBars.bottom
            } else {
                topPx = getStatusBarHeight()
                bottomPx = getNavigationBarHeight()
            }
        }

        val density = activity.resources.displayMetrics.density
        val topDp = (topPx / density).toInt()
        val bottomDp = (bottomPx / density).toInt()

        return JsonUtil.success(
            "top" to topDp,
            "bottom" to bottomDp,
            "topPx" to topPx,
            "bottomPx" to bottomPx
        )
    }

    fun injectCssVariables() {
        val result = getSafeArea()
        val json = org.json.JSONObject(result)
        val topPx = json.optInt("topPx", 0)
        val bottomPx = json.optInt("bottomPx", 0)

        val script = """
            (function(){
                document.documentElement.style.setProperty('--safe-area-top', '${topPx}px');
                document.documentElement.style.setProperty('--safe-area-bottom', '${bottomPx}px');
            })();
        """.trimIndent()

        activity.getWebViewContainer().evaluateJs(script)
    }

    private fun getStatusBarHeight(): Int {
        val resId = activity.resources.getIdentifier("status_bar_height", "dimen", "android")
        return if (resId > 0) activity.resources.getDimensionPixelSize(resId) else 0
    }

    private fun getNavigationBarHeight(): Int {
        val resId = activity.resources.getIdentifier("navigation_bar_height", "dimen", "android")
        return if (resId > 0) activity.resources.getDimensionPixelSize(resId) else 0
    }
}
