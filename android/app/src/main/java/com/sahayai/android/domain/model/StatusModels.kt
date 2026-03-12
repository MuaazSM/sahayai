package com.sahayai.android.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class StatusRequest(
    @SerialName("user_id") val userId: String,
    @SerialName("location_lat") val locationLat: Double? = null,
    @SerialName("location_lng") val locationLng: Double? = null
)

@Serializable
data class StatusResponse(
    @SerialName("status") val status: String,
    @SerialName("message") val message: String,
    @SerialName("alert_sent") val alertSent: Boolean = false,
    @SerialName("caregiver_notified") val caregiverNotified: Boolean = false
)
