package com.sahayai.android.domain.repository

import com.sahayai.android.core.db.dao.ReminderDao
import com.sahayai.android.core.db.entity.toDomain
import com.sahayai.android.core.db.entity.toEntity
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.core.network.SahayAIApiService
import com.sahayai.android.core.network.safeApiCall
import com.sahayai.android.domain.model.Reminder
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject

class ReminderRepositoryImpl @Inject constructor(
    private val api: SahayAIApiService,
    private val dao: ReminderDao
) : ReminderRepository {

    override fun getReminders(userId: String): Flow<NetworkResult<List<Reminder>>> {
        return dao.getRemindersForUser(userId).map { entities ->
            NetworkResult.Success(entities.map { it.toDomain() })
        }
    }

    override suspend fun refreshReminders(userId: String) {
        val result = safeApiCall { api.getReminders(userId) }
        if (result is NetworkResult.Success) {
            dao.upsertAll(result.data.map { it.toEntity() })
        }
    }

    override suspend fun confirmReminder(reminderId: String): NetworkResult<Unit> {
        val result = safeApiCall { api.confirmReminder(reminderId) }
        if (result is NetworkResult.Success) {
            dao.confirmReminder(reminderId)
        }
        return result
    }
}
