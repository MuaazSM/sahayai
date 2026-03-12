package com.sahayai.android.domain.repository

import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.model.Reminder
import kotlinx.coroutines.flow.Flow

interface ReminderRepository {
    fun getReminders(userId: String): Flow<NetworkResult<List<Reminder>>>
    suspend fun confirmReminder(reminderId: String): NetworkResult<Unit>
    suspend fun refreshReminders(userId: String)
}
