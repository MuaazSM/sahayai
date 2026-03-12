package com.sahayai.android.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ConversationRequest(
    @SerialName("user_id") val userId: String,
    @SerialName("message") val message: String,
    @SerialName("role") val role: String = "patient"
)

@Serializable
data class ConversationResponse(
    @SerialName("response_text") val responseText: String,
    @SerialName("aac_score") val aacScore: Float,
    @SerialName("cct_score") val cctScore: Float? = null,
    @SerialName("emr_triggered") val emrTriggered: Boolean = false,
    @SerialName("emr_memory") val emrMemory: String? = null
)
