package com.sahayai.android.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class SceneResponse(
    @SerialName("description") val description: String,
    @SerialName("objects_detected") val objectsDetected: List<String> = emptyList(),
    @SerialName("safety_concerns") val safetyConcerns: List<String> = emptyList(),
    @SerialName("confidence") val confidence: Float = 1.0f
)
