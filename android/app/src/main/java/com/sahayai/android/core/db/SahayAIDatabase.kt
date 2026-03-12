package com.sahayai.android.core.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.sahayai.android.core.db.dao.AlertDao
import com.sahayai.android.core.db.dao.CognitiveTrendDao
import com.sahayai.android.core.db.dao.ReminderDao
import com.sahayai.android.core.db.entity.AlertEntity
import com.sahayai.android.core.db.entity.CognitiveTrendEntity
import com.sahayai.android.core.db.entity.ReminderEntity

@Database(
    entities = [ReminderEntity::class, AlertEntity::class, CognitiveTrendEntity::class],
    version = 1,
    exportSchema = false
)
abstract class SahayAIDatabase : RoomDatabase() {
    abstract fun reminderDao(): ReminderDao
    abstract fun alertDao(): AlertDao
    abstract fun cognitiveTrendDao(): CognitiveTrendDao
}
