package com.myopenweb.app

import android.content.pm.PackageManager
import android.os.Bundle
import android.view.WindowManager
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import com.myopenweb.app.databinding.BocoActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var binding: BocoActivityMainBinding
    private lateinit var webViewContainer: WebViewContainer

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS)

        binding = BocoActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        webViewContainer = WebViewContainer(this, binding.bocoWebview)
        webViewContainer.init()
        webViewContainer.loadPage()
    }

    override fun onResume() {
        super.onResume()
        webViewContainer.onResume()
    }

    override fun onPause() {
        super.onPause()
        webViewContainer.onPause()
    }

    override fun onDestroy() {
        webViewContainer.onDestroy()
        super.onDestroy()
    }

    @Deprecated("This callback is required for bridge permission flow")
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
        webViewContainer.getBridge().nativeSTT.onPermissionResult(granted)
    }

    @Deprecated("Use onBackPressedDispatcher")
    override fun onBackPressed() {
        if (!webViewContainer.handleBack()) {
            super.onBackPressed()
        }
    }

    fun getWebViewContainer(): WebViewContainer = webViewContainer
}
