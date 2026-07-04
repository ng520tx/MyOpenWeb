package com.myopenweb.app.native_

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Base64
import android.util.Log
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import com.myopenweb.app.MainActivity
import com.myopenweb.app.bridge.MoaBridge
import com.myopenweb.app.util.JsonUtil
import java.io.BufferedReader
import java.io.InputStreamReader

class NativeFilePicker(
    private val activity: MainActivity,
    private val bridge: MoaBridge
) {

    companion object {
        private const val TAG = "NativeFilePicker"
        private const val MAX_TEXT_SIZE = 10 * 1024 * 1024 // 10MB
    }

    private var pendingCbFuncName: String = ""

    private val launcher: ActivityResultLauncher<Intent> =
        activity.registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == Activity.RESULT_OK && result.data?.data != null) {
                handleUri(result.data!!.data!!, pendingCbFuncName)
            } else {
                bridge.invokeCallback(pendingCbFuncName, JsonUtil.error("File selection cancelled"))
            }
            pendingCbFuncName = ""
        }

    fun pick(accept: String, cbFuncName: String) {
        pendingCbFuncName = cbFuncName
        val intent = Intent(Intent.ACTION_GET_CONTENT).apply {
            type = if (accept == "*/*" || accept.isBlank()) "*/*" else accept
            addCategory(Intent.CATEGORY_OPENABLE)
        }
        try {
            launcher.launch(Intent.createChooser(intent, "选择文件"))
        } catch (e: Exception) {
            Log.e(TAG, "Failed to launch file picker", e)
            bridge.invokeCallback(cbFuncName, JsonUtil.error(e.message ?: "Cannot open file picker"))
        }
    }

    private fun handleUri(uri: Uri, cbFuncName: String) {
        try {
            val mimeType = activity.contentResolver.getType(uri) ?: "application/octet-stream"
            val name = getFileName(uri) ?: "unknown"
            val isImage = mimeType.startsWith("image/")

            if (isImage) {
                val bytes = activity.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                if (bytes == null) {
                    bridge.invokeCallback(cbFuncName, JsonUtil.error("Cannot read file"))
                    return
                }
                val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
                val dataUrl = "data:$mimeType;base64,$b64"
                bridge.invokeCallback(
                    cbFuncName,
                    JsonUtil.success(
                        "uri" to uri.toString(),
                        "name" to name,
                        "mimeType" to mimeType,
                        "isImage" to true,
                        "dataUrl" to dataUrl
                    )
                )
            } else {
                val content = activity.contentResolver.openInputStream(uri)?.use { stream ->
                    val reader = BufferedReader(InputStreamReader(stream, "UTF-8"))
                    val sb = StringBuilder()
                    val buf = CharArray(8192)
                    var total = 0
                    var len: Int
                    while (reader.read(buf).also { len = it } != -1 && total < MAX_TEXT_SIZE) {
                        sb.append(buf, 0, len)
                        total += len
                    }
                    sb.toString()
                }
                if (content == null) {
                    bridge.invokeCallback(cbFuncName, JsonUtil.error("Cannot read file"))
                    return
                }
                bridge.invokeCallback(
                    cbFuncName,
                    JsonUtil.success(
                        "uri" to uri.toString(),
                        "name" to name,
                        "mimeType" to mimeType,
                        "content" to content
                    )
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error reading file", e)
            bridge.invokeCallback(cbFuncName, JsonUtil.error(e.message ?: "Read error"))
        }
    }

    private fun getFileName(uri: Uri): String? {
        var name: String? = null
        activity.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            val idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (idx >= 0 && cursor.moveToFirst()) {
                name = cursor.getString(idx)
            }
        }
        return name ?: uri.lastPathSegment
    }
}
