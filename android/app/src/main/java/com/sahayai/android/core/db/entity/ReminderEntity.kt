package com.sahayai.android.core.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.sahayai.android.domain.model.Reminder

@Entity(tableName = "reminders")
data class ReminderEntity(
    @PrimaryKey val id: String,
    val userId: String,
    val title: String,
    val description: String,
    val reminderType: String,
    val scheduledTime: String,
    val isConfirmed: Boolean,
    val createdAt: String,
    val cachedAt: Long = System.currentTimeMillis()
)

fun ReminderEntity.toDomain() = Reminder(
    id = id,
    userId = userId,
    title = title,
    description = description,
    reminderType = reminderType,
    scheduledTime = scheduledTime,
    isConfirmed = isConfirmed,
    createdAt = createdAt
)

fun Reminder.toEntity() = ReminderEntity(
    id = id,
    userId = userId,
    title = title,
    description = description,
    reminderType = reminderType,
    scheduledTime = scheduledTime,
    isConfirmed = isConfirmed,
    createdAt = createdAt
)
