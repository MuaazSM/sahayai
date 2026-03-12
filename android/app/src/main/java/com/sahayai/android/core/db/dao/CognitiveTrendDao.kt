package com.sahayai.android.core.db.dao

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert
import com.sahayai.android.core.db.entity.CognitiveTrendEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface CognitiveTrendDao {
    @Query("SELECT * FROM cognitive_trends ORDER BY date DESC LIMIT :limit")
    fun getRecentTrends(limit: Int = 14): Flow<List<CognitiveTrendEntity>>

    @Upsert
    suspend fun upsertAll(trends: List<CognitiveTrendEntity>)

    @Query("DELETE FROM cognitive_trends")
    suspend fun deleteAll()
}
