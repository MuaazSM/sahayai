package com.sahayai.android.domain.repository

import com.sahayai.android.BuildConfig
import com.sahayai.android.core.network.AlertWebSocketClient
import com.sahayai.android.domain.model.WsAlertMessage
import kotlinx.coroutines.flow.SharedFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AlertWebSocketRepository @Inject constructor(
    private val client: AlertWebSocketClient
) {
    val messages: SharedFlow<WsAlertMessage> = client.messages

    fun connect(caregiverId: String) {
        client.connect(caregiverId, BuildConfig.BASE_URL)
    }

    fun disconnect() {
        client.disconnect()
    }
}
