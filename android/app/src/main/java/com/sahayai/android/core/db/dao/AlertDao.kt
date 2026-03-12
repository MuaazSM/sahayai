package com.sahayai.android.core.db.dao

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert
import com.sahayai.android.core.db.entity.AlertEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface AlertDao {
    @Query("SELECT * FROM alerts WHERE patientId = :patientId ORDER BY createdAt DESC")
    fun getAlertsForPatient(patientId: String): Flow<List<AlertEntity>>

    @Query("SELECT * FROM alerts WHERE id = :alertId")
    suspend fun getAlertById(alertId: String): AlertEntity?

    @Upsert
    suspend fun upsertAll(alerts: List<AlertEntity>)

    @Query("UPDATE alerts SET isAcknowledged = 1, acknowledgedBy = :by, acknowledgedAt = :at WHERE id = :alertId")
    suspend fun acknowledgeAlert(alertId: String, by: String, at: String)

    @Query("DELETE FROM alerts WHERE patientId = :patientId")
    suspend fun deleteForPatient(patientId: String)
}
