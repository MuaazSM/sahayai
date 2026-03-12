package com.sahayai.android.core.mock

import com.sahayai.android.domain.model.Alert
import com.sahayai.android.domain.model.CaregiverSummary
import com.sahayai.android.domain.model.CognitiveTrendPoint
import com.sahayai.android.domain.model.ConversationResponse
import com.sahayai.android.domain.model.Reminder
import com.sahayai.android.domain.model.SceneResponse
import com.sahayai.android.domain.model.StatusResponse
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlin.random.Random

object MockData {
    const val rameshUserId = "ramesh_demo_001"
    const val caregiverId = "caregiver_priya_001"
    const val rameshName = "Ramesh"

    val reminders: List<Reminder> = listOf(
        Reminder(
            id = "rem_001",
            userId = rameshUserId,
            title = "Morning Medication",
            description = "Take 2 tablets of Amlodipine with water",
            reminderType = "MEDICATION",
            scheduledTime = "08:00",
            isConfirmed = true
        ),
        Reminder(
            id = "rem_002",
            userId = rameshUserId,
            title = "Morning Walk",
            description = "30-minute walk in the garden",
            reminderType = "EXERCISE",
            scheduledTime = "09:00",
            isConfirmed = false
        ),
        Reminder(
            id = "rem_003",
            userId = rameshUserId,
            title = "Afternoon Medication",
            description = "Take 1 tablet of Metformin after lunch",
            reminderType = "MEDICATION",
            scheduledTime = "13:30",
            isConfirmed = false
        ),
        Reminder(
            id = "rem_004",
            userId = rameshUserId,
            title = "Drink Water",
            description = "Stay hydrated — 8 glasses today",
            reminderType = "HYDRATION",
            scheduledTime = "15:00",
            isConfirmed = false
        )
    )

    val alerts: List<Alert> = listOf(
        Alert(
            id = "alert_001",
            patientId = rameshUserId,
            alertType = "MISSED_MEDICATION",
            priority = "HIGH",
            title = "Missed Afternoon Medication",
            description = "Ramesh has not confirmed the 13:30 Metformin dose. This is the second miss this week.",
            createdAt = "2026-03-12T14:05:00Z",
            isAcknowledged = false
        ),
        Alert(
            id = "alert_002",
            patientId = rameshUserId,
            alertType = "LOW_CCT",
            priority = "MEDIUM",
            title = "Cognitive Score Drop",
            description = "CCT score dropped to 62 during today's conversation — below the baseline of 72. Consider a check-in call.",
            createdAt = "2026-03-12T11:30:00Z",
            isAcknowledged = false
        ),
        Alert(
            id = "alert_003",
            patientId = rameshUserId,
            alertType = "UNUSUAL_BEHAVIOR",
            priority = "LOW",
            title = "Reduced Activity",
            description = "Step count is 1,200 today compared to usual 3,500+. Ramesh may be resting.",
            createdAt = "2026-03-12T16:00:00Z",
            isAcknowledged = true,
            acknowledgedBy = caregiverId,
            acknowledgedAt = "2026-03-12T16:15:00Z"
        )
    )

    val cctTrend: List<CognitiveTrendPoint> = run {
        val formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd")
        val baseDate = LocalDate.of(2026, 3, 12)
        val baseScores = listOf(72f, 74f, 71f, 75f, 78f, 73f, 76f, 74f, 70f, 68f, 72f, 65f, 69f, 62f)
        baseScores.mapIndexed { index, score ->
            val date = baseDate.minusDays((13 - index).toLong())
            CognitiveTrendPoint(
                date = date.format(formatter),
                cctScore = score + Random.nextFloat() * 2f - 1f,
                aacScore = 70f + Random.nextFloat() * 15f,
                conversationCount = (1..4).random()
            )
        }
    }

    val summary: CaregiverSummary = CaregiverSummary(
        patientId = rameshUserId,
        date = "2026-03-12",
        stepsToday = 1200,
        remindersCompleted = 1,
        remindersTotal = 4,
        avgCctScore = 66.5f,
        riskLevel = "MODERATE",
        aacScore = 68f,
        conversationsToday = 2,
        moodSummary = "Ramesh seemed a bit withdrawn this morning but engaged well in the afternoon conversation."
    )

    fun conversationResponse(message: String): ConversationResponse {
        val responses = listOf(
            ConversationResponse(
                responseText = "Namaste, Ramesh ji! I am here with you. How are you feeling today? Did you take your morning walk?",
                aacScore = 72f,
                cctScore = 68f,
                emrTriggered = false
            ),
            ConversationResponse(
                responseText = "Your daughter Priya called this morning. She will visit on Sunday. She loves you very much.",
                aacScore = 75f,
                cctScore = 71f,
                emrTriggered = true,
                emrMemory = "Ramesh's daughter Priya"
            ),
            ConversationResponse(
                responseText = "It is time for your afternoon medication. Shall I remind you again in 15 minutes?",
                aacScore = 70f,
                cctScore = 65f,
                emrTriggered = false
            ),
            ConversationResponse(
                responseText = "The weather is pleasant today. Perhaps a short walk in the garden would be nice?",
                aacScore = 78f,
                cctScore = 74f,
                emrTriggered = false
            )
        )
        return responses.random()
    }

    val sceneResponse: SceneResponse = SceneResponse(
        description = "I can see your living room. There is a sofa on the left, a TV ahead, and a small table with a glass of water. The room looks tidy and well-lit. I notice your walking stick is near the door — good thinking for your morning walk.",
        objectsDetected = listOf("sofa", "television", "table", "glass", "walking stick"),
        safetyConcerns = emptyList(),
        confidence = 0.94f
    )

    val statusResponse: StatusResponse = StatusResponse(
        status = "SAFE",
        message = "Your location has been shared with Priya. She has been notified that you are safe.",
        alertSent = true,
        caregiverNotified = true
    )
}
