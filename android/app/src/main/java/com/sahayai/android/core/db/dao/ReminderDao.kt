package com.sahayai.android.core.db.dao

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert
import com.sahayai.android.core.db.entity.ReminderEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ReminderDao {
    @Query("SELECT * FROM reminders WHERE userId = :userId ORDER BY scheduledTime ASC")
    fun getRemindersForUser(userId: String): Flow<List<ReminderEntity>>

    @Upsert
    suspend fun upsertAll(reminders: List<ReminderEntity>)

    @Query("UPDATE reminders SET isConfirmed = 1 WHERE id = :reminderId")
    suspend fun confirmReminder(reminderId: String)

    @Query("DELETE FROM reminders WHERE userId = :userId")
    suspend fun deleteForUser(userId: String)
}
