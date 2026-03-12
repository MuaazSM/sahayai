package com.sahayai.android.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CaregiverSummary(
    @SerialName("patient_id") val patientId: String,
    @SerialName("date") val date: String,
    @SerialName("steps_today") val stepsToday: Int = 0,
    @SerialName("reminders_completed") val remindersCompleted: Int = 0,
    @SerialName("reminders_total") val remindersTotal: Int = 0,
    @SerialName("avg_cct_score") val avgCctScore: Float = 0f,
    @SerialName("risk_level") val riskLevel: String = "LOW",
    @SerialName("aac_score") val aacScore: Float = 75f,
    @SerialName("conversations_today") val conversationsToday: Int = 0,
    @SerialName("mood_summary") val moodSummary: String = ""
)
