package com.sahayai.android.core.network

import android.util.Log
import com.sahayai.android.domain.model.WsAlertMessage
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AlertWebSocketClient @Inject constructor(
    private val okHttpClient: OkHttpClient
) {
    private val _messages = MutableSharedFlow<WsAlertMessage>(replay = 0, extraBufferCapacity = 32)
    val messages: SharedFlow<WsAlertMessage> = _messages

    private var webSocket: WebSocket? = null

    private val json = Json { ignoreUnknownKeys = true }

    fun connect(caregiverId: String, baseUrl: String) {
        val wsUrl = baseUrl
            .replace("https://", "wss://")
            .replace("http://", "ws://")
            .trimEnd('/') + "/ws/alerts/$caregiverId"

        val request = Request.Builder().url(wsUrl).build()
        webSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val msg = json.decodeFromString<WsAlertMessage>(text)
                    _messages.tryEmit(msg)
                } catch (e: Exception) {
                    Log.w("AlertWebSocket", "Failed to parse message: $text", e)
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("AlertWebSocket", "WebSocket failure", t)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d("AlertWebSocket", "WebSocket closed: $reason")
            }
        })
    }

    fun disconnect() {
        webSocket?.close(1000, "User disconnected")
        webSocket = null
    }
}
