package com.sahayai.android.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CognitiveTrendPoint(
    @SerialName("date") val date: String,
    @SerialName("cct_score") val cctScore: Float,
    @SerialName("aac_score") val aacScore: Float? = null,
    @SerialName("conversation_count") val conversationCount: Int = 0
)
