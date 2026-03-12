package com.sahayai.android.core.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.sahayai.android.domain.model.Alert

@Entity(tableName = "alerts")
data class AlertEntity(
    @PrimaryKey val id: String,
    val patientId: String,
    val alertType: String,
    val priority: String,
    val title: String,
    val description: String,
    val createdAt: String,
    val isAcknowledged: Boolean,
    val acknowledgedBy: String?,
    val acknowledgedAt: String?,
    val cachedAt: Long = System.currentTimeMillis()
)

fun AlertEntity.toDomain() = Alert(
    id = id,
    patientId = patientId,
    alertType = alertType,
    priority = priority,
    title = title,
    description = description,
    createdAt = createdAt,
    isAcknowledged = isAcknowledged,
    acknowledgedBy = acknowledgedBy,
    acknowledgedAt = acknowledgedAt
)

fun Alert.toEntity() = AlertEntity(
    id = id,
    patientId = patientId,
    alertType = alertType,
    priority = priority,
    title = title,
    description = description,
    createdAt = createdAt,
    isAcknowledged = isAcknowledged,
    acknowledgedBy = acknowledgedBy,
    acknowledgedAt = acknowledgedAt
)
