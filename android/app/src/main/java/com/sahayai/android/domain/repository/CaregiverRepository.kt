package com.sahayai.android.domain.repository

import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.model.Alert
import com.sahayai.android.domain.model.CaregiverSummary
import com.sahayai.android.domain.model.CognitiveTrendPoint
import kotlinx.coroutines.flow.Flow

interface CaregiverRepository {
    fun getAlerts(patientId: String): Flow<NetworkResult<List<Alert>>>
    suspend fun refreshAlerts(patientId: String)
    suspend fun acknowledgeAlert(alertId: String, acknowledgedBy: String): NetworkResult<Unit>
    suspend fun getSummary(patientId: String): NetworkResult<CaregiverSummary>
    fun getCognitiveTrends(patientId: String): Flow<NetworkResult<List<CognitiveTrendPoint>>>
    suspend fun refreshTrends(patientId: String)
}
