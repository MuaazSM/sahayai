package com.sahayai.android.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class WsAlertMessage(
    @SerialName("type") val type: String = "alert",
    @SerialName("alert") val alert: Alert? = null,
    @SerialName("message") val message: String = ""
)
