package com.sahayai.android.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

enum class AlertType { MISSED_MEDICATION, LOW_CCT, FALL_DETECTED, EMERGENCY_SOS, UNUSUAL_BEHAVIOR, OTHER }
enum class AlertPriority { CRITICAL, HIGH, MEDIUM, LOW }

@Serializable
data class Alert(
    @SerialName("id") val id: String,
    @SerialName("patient_id") val patientId: String,
    @SerialName("alert_type") val alertType: String,
    @SerialName("priority") val priority: String,
    @SerialName("title") val title: String,
    @SerialName("description") val description: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("is_acknowledged") val isAcknowledged: Boolean = false,
    @SerialName("acknowledged_by") val acknowledgedBy: String? = null,
    @SerialName("acknowledged_at") val acknowledgedAt: String? = null
)
