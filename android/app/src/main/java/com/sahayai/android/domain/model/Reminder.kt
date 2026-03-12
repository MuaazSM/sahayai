package com.sahayai.android.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

enum class ReminderType { MEDICATION, EXERCISE, APPOINTMENT, HYDRATION, OTHER }

@Serializable
data class Reminder(
    @SerialName("id") val id: String,
    @SerialName("user_id") val userId: String,
    @SerialName("title") val title: String,
    @SerialName("description") val description: String = "",
    @SerialName("reminder_type") val reminderType: String = "OTHER",
    @SerialName("scheduled_time") val scheduledTime: String,
    @SerialName("is_confirmed") val isConfirmed: Boolean = false,
    @SerialName("created_at") val createdAt: String = ""
)

@Serializable
data class AcknowledgeRequest(
    @SerialName("acknowledged_by") val acknowledgedBy: String,
    @SerialName("note") val note: String = ""
)
