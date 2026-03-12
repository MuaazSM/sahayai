package com.sahayai.android.core.network

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
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path

interface SahayAIApiService {

    @POST("conversation")
    suspend fun sendConversation(@Body request: ConversationRequest): Response<ConversationResponse>

    @Multipart
    @POST("analyze-scene")
    suspend fun analyzeScene(
        @Part("user_id") userId: RequestBody,
        @Part image: MultipartBody.Part
    ): Response<SceneResponse>

    @POST("check-status")
    suspend fun checkStatus(@Body request: StatusRequest): Response<StatusResponse>

    @GET("caregiver/alerts/{patient_id}")
    suspend fun getCaregiverAlerts(@Path("patient_id") patientId: String): Response<List<Alert>>

    @GET("caregiver/summary/{patient_id}")
    suspend fun getCaregiverSummary(@Path("patient_id") patientId: String): Response<CaregiverSummary>

    @POST("caregiver/alerts/{alert_id}/acknowledge")
    suspend fun acknowledgeAlert(
        @Path("alert_id") alertId: String,
        @Body body: AcknowledgeRequest
    ): Response<Unit>

    @GET("patient/reminders/{user_id}")
    suspend fun getReminders(@Path("user_id") userId: String): Response<List<Reminder>>

    @POST("patient/reminders/{reminder_id}/confirm")
    suspend fun confirmReminder(@Path("reminder_id") reminderId: String): Response<Unit>

    @GET("caregiver/trends/{patient_id}")
    suspend fun getCognitiveTrends(@Path("patient_id") patientId: String): Response<List<CognitiveTrendPoint>>
}
