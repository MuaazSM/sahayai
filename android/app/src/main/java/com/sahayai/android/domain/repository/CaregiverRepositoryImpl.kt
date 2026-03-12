package com.sahayai.android.domain.repository

import com.sahayai.android.core.db.dao.AlertDao
import com.sahayai.android.core.db.dao.CognitiveTrendDao
import com.sahayai.android.core.db.entity.toDomain
import com.sahayai.android.core.db.entity.toEntity
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.core.network.SahayAIApiService
import com.sahayai.android.core.network.safeApiCall
import com.sahayai.android.domain.model.AcknowledgeRequest
import com.sahayai.android.domain.model.Alert
import com.sahayai.android.domain.model.CaregiverSummary
import com.sahayai.android.domain.model.CognitiveTrendPoint
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Instant
import javax.inject.Inject

class CaregiverRepositoryImpl @Inject constructor(
    private val api: SahayAIApiService,
    private val alertDao: AlertDao,
    private val trendDao: CognitiveTrendDao
) : CaregiverRepository {

    override fun getAlerts(patientId: String): Flow<NetworkResult<List<Alert>>> {
        return alertDao.getAlertsForPatient(patientId).map { entities ->
            NetworkResult.Success(entities.map { it.toDomain() })
        }
    }

    override suspend fun refreshAlerts(patientId: String) {
        val result = safeApiCall { api.getCaregiverAlerts(patientId) }
        if (result is NetworkResult.Success) {
            alertDao.upsertAll(result.data.map { it.toEntity() })
        }
    }

    override suspend fun acknowledgeAlert(alertId: String, acknowledgedBy: String): NetworkResult<Unit> {
        val result = safeApiCall {
            api.acknowledgeAlert(alertId, AcknowledgeRequest(acknowledgedBy = acknowledgedBy))
        }
        if (result is NetworkResult.Success) {
            alertDao.acknowledgeAlert(alertId, acknowledgedBy, Instant.now().toString())
        }
        return result
    }

    override suspend fun getSummary(patientId: String): NetworkResult<CaregiverSummary> {
        return safeApiCall { api.getCaregiverSummary(patientId) }
    }

    override fun getCognitiveTrends(patientId: String): Flow<NetworkResult<List<CognitiveTrendPoint>>> {
        return trendDao.getRecentTrends(14).map { entities ->
            NetworkResult.Success(entities.map { it.toDomain() })
        }
    }

    override suspend fun refreshTrends(patientId: String) {
        val result = safeApiCall { api.getCognitiveTrends(patientId) }
        if (result is NetworkResult.Success) {
            trendDao.upsertAll(result.data.map { it.toEntity() })
        }
    }
}
