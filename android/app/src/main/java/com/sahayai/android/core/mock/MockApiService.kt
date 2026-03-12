package com.sahayai.android.core.mock

import com.sahayai.android.core.network.SahayAIApiService
import com.sahayai.android.domain.model.AcknowledgeRequest
import com.sahayai.android.domain.model.Alert
import com.sahayai.android.domain.model.CaregiverSummary
import com.sahayai.android.domain.model.CognitiveTrendPoint
import com.sahayai.android.domain.model.ConversationRequest
import com.sahayai.android.domain.model.ConversationResponse
import com.sahayai.android.domain.model.Reminder
import com.sahayai.android.domain.model.SceneResponse
import com.sahayai.android.domain.model.StatusRequest
import com.sahayai.android.domain.model.StatusResponse
import kotlinx.coroutines.delay
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response

class MockApiService : SahayAIApiService {

    private suspend fun mockDelay() = delay((300L..600L).random())

    override suspend fun sendConversation(request: ConversationRequest): Response<ConversationResponse> {
        mockDelay()
        return Response.success(MockData.conversationResponse(request.message))
    }

    override suspend fun analyzeScene(
        userId: RequestBody,
        image: MultipartBody.Part
    ): Response<SceneResponse> {
        delay(800) // Simulate image analysis latency
        return Response.success(MockData.sceneResponse)
    }

    override suspend fun checkStatus(request: StatusRequest): Response<StatusResponse> {
        mockDelay()
        return Response.success(MockData.statusResponse)
    }

    override suspend fun getCaregiverAlerts(patientId: String): Response<List<Alert>> {
        mockDelay()
        return Response.success(MockData.alerts)
    }

    override suspend fun getCaregiverSummary(patientId: String): Response<CaregiverSummary> {
        mockDelay()
        return Response.success(MockData.summary)
    }

    override suspend fun acknowledgeAlert(
        alertId: String,
        body: AcknowledgeRequest
    ): Response<Unit> {
        mockDelay()
        return Response.success(Unit)
    }

    override suspend fun getReminders(userId: String): Response<List<Reminder>> {
        mockDelay()
        return Response.success(MockData.reminders)
    }

    override suspend fun confirmReminder(reminderId: String): Response<Unit> {
        mockDelay()
        return Response.success(Unit)
    }

    override suspend fun getCognitiveTrends(patientId: String): Response<List<CognitiveTrendPoint>> {
        mockDelay()
        return Response.success(MockData.cctTrend)
    }
}
