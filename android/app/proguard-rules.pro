# Keep MoaBridge JavascriptInterface methods
-keepclassmembers class com.myopenweb.app.bridge.MoaBridge {
    @android.webkit.JavascriptInterface <methods>;
}
