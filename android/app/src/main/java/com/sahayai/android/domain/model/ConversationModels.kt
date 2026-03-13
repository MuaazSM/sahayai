package com.sahayai.android.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class EMRMemory(
    @SerialName("text") val text: String,
    @SerialName("emotion_tag") val emotionTag: String
)

@Serializable
data class ConversationRequest(
    @SerialName("user_id") val userId: String,
    @SerialName("message") val message: String,
    @SerialName("role") val role: String = "patient",
    @SerialName("conversation_id") val conversationId: String? = null
)

@Serializable
data class ConversationResponse(
    @SerialName("response_text") val responseText: String,
    @SerialName("conversation_id") val conversationId: String = "",
    @SerialName("aac_score") val aacScore: Float = 0f,
    @SerialName("cct_score") val cctScore: Float? = null,
    @SerialName("emr_triggered") val emrTriggered: Boolean = false,
    @SerialName("emr_memory") val emrMemory: EMRMemory? = null,
    @SerialName("audio_base64") val audioBase64: String? = null,
    @SerialName("audio_provider") val audioProvider: String? = null
)
