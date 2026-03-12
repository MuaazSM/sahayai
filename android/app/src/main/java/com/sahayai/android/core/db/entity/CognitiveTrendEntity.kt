package com.sahayai.android.core.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.sahayai.android.domain.model.CognitiveTrendPoint

@Entity(tableName = "cognitive_trends")
data class CognitiveTrendEntity(
    @PrimaryKey val date: String,
    val cctScore: Float,
    val aacScore: Float?,
    val conversationCount: Int,
    val cachedAt: Long = System.currentTimeMillis()
)

fun CognitiveTrendEntity.toDomain() = CognitiveTrendPoint(
    date = date,
    cctScore = cctScore,
    aacScore = aacScore,
    conversationCount = conversationCount
)

fun CognitiveTrendPoint.toEntity() = CognitiveTrendEntity(
    date = date,
    cctScore = cctScore,
    aacScore = aacScore,
    conversationCount = conversationCount
)
