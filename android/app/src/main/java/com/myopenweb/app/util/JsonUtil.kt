package com.myopenweb.app.util

import org.json.JSONObject

object JsonUtil {

    fun parse(json: String?): JSONObject {
        if (json.isNullOrBlank()) return JSONObject()
        return try {
            JSONObject(json)
        } catch (_: Exception) {
            JSONObject()
        }
    }

    fun success(vararg pairs: Pair<String, Any?>): String {
        val obj = JSONObject()
        obj.put("success", true)
        for ((k, v) in pairs) obj.put(k, v)
        return obj.toString()
    }

    fun error(message: String): String {
        val obj = JSONObject()
        obj.put("success", false)
        obj.put("message", message)
        return obj.toString()
    }
}
