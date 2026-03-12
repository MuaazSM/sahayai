package com.sahayai.android.core.mock

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class MockApiServiceTest {

    private lateinit var service: MockApiService

    @Before
    fun setup() {
        service = MockApiService()
    }

    @Test
    fun `getReminders returns Ramesh demo reminders`() = runTest {
        val response = service.getReminders(MockData.rameshUserId)
        assertTrue(response.isSuccessful)
        val reminders = response.body()
        assertNotNull(reminders)
        assertTrue(reminders!!.isNotEmpty())
        assertTrue(reminders.any { it.reminderType == "MEDICATION" })
    }

    @Test
    fun `getCaregiverAlerts returns demo alerts`() = runTest {
        val response = service.getCaregiverAlerts(MockData.rameshUserId)
        assertTrue(response.isSuccessful)
        val alerts = response.body()
        assertNotNull(alerts)
        assertTrue(alerts!!.isNotEmpty())
        assertTrue(alerts.any { it.priority == "HIGH" })
    }

    @Test
    fun `getCaregiverSummary returns Ramesh summary`() = runTest {
        val response = service.getCaregiverSummary(MockData.rameshUserId)
        assertTrue(response.isSuccessful)
        val summary = response.body()
        assertNotNull(summary)
        assertEquals(MockData.rameshUserId, summary!!.patientId)
        assertEquals("MODERATE", summary.riskLevel)
    }

    @Test
    fun `getCognitiveTrends returns 14 data points`() = runTest {
        val response = service.getCognitiveTrends(MockData.rameshUserId)
        assertTrue(response.isSuccessful)
        val trends = response.body()
        assertNotNull(trends)
        assertEquals(14, trends!!.size)
        assertTrue(trends.all { it.cctScore in 50f..100f })
    }

    @Test
    fun `sendConversation returns response with valid scores`() = runTest {
        val request = com.sahayai.android.domain.model.ConversationRequest(
            userId = MockData.rameshUserId,
            message = "Hello SahayAI"
        )
        val response = service.sendConversation(request)
        assertTrue(response.isSuccessful)
        val body = response.body()
        assertNotNull(body)
        assertTrue(body!!.responseText.isNotEmpty())
        assertTrue(body.aacScore > 0f)
    }

    @Test
    fun `confirmReminder returns success`() = runTest {
        val response = service.confirmReminder("rem_001")
        assertTrue(response.isSuccessful)
    }

    @Test
    fun `acknowledgeAlert returns success`() = runTest {
        val body = com.sahayai.android.domain.model.AcknowledgeRequest(
            acknowledgedBy = MockData.caregiverId
        )
        val response = service.acknowledgeAlert("alert_001", body)
        assertTrue(response.isSuccessful)
    }
}
