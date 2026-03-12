package com.sahayai.android.domain.repository

import app.cash.turbine.test
import com.sahayai.android.core.db.dao.AlertDao
import com.sahayai.android.core.db.dao.CognitiveTrendDao
import com.sahayai.android.core.db.entity.AlertEntity
import com.sahayai.android.core.db.entity.CognitiveTrendEntity
import com.sahayai.android.core.mock.MockApiService
import com.sahayai.android.core.network.NetworkResult
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class CaregiverRepositoryTest {

    private lateinit var repository: CaregiverRepositoryImpl
    private val mockAlertDao = mockk<AlertDao>(relaxed = true)
    private val mockTrendDao = mockk<CognitiveTrendDao>(relaxed = true)

    @Before
    fun setup() {
        every { mockAlertDao.getAlertsForPatient(any()) } returns flowOf(emptyList())
        every { mockTrendDao.getRecentTrends(any()) } returns flowOf(emptyList())
        repository = CaregiverRepositoryImpl(
            api = MockApiService(),
            alertDao = mockAlertDao,
            trendDao = mockTrendDao
        )
    }

    @Test
    fun `getSummary returns Success with patient data`() = runTest {
        val result = repository.getSummary("ramesh_demo_001")
        assertTrue(result is NetworkResult.Success)
        val summary = (result as NetworkResult.Success).data
        assertTrue(summary.stepsToday >= 0)
    }

    @Test
    fun `refreshAlerts upserts to database`() = runTest {
        repository.refreshAlerts("ramesh_demo_001")
        coVerify { mockAlertDao.upsertAll(any()) }
    }

    @Test
    fun `getAlerts returns Success even when cache empty`() = runTest {
        repository.getAlerts("patient").test {
            val item = awaitItem()
            assertTrue(item is NetworkResult.Success && (item as NetworkResult.Success).data.isEmpty())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun `refreshTrends upserts to database`() = runTest {
        repository.refreshTrends("ramesh_demo_001")
        coVerify { mockTrendDao.upsertAll(any()) }
    }

    @Test
    fun `getCognitiveTrends returns Success even when cache empty`() = runTest {
        repository.getCognitiveTrends("patient").test {
            val item = awaitItem()
            assertTrue(item is NetworkResult.Success && (item as NetworkResult.Success).data.isEmpty())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun `acknowledgeAlert returns Success and updates DB`() = runTest {
        val result = repository.acknowledgeAlert("alert_001", "caregiver_priya_001")
        assertTrue(result is NetworkResult.Success)
        coVerify { mockAlertDao.acknowledgeAlert("alert_001", "caregiver_priya_001", any()) }
    }
}
