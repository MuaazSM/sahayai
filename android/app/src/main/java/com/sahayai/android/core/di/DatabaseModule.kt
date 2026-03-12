package com.sahayai.android.core.di

import android.content.Context
import androidx.room.Room
import com.sahayai.android.core.db.SahayAIDatabase
import com.sahayai.android.core.db.dao.AlertDao
import com.sahayai.android.core.db.dao.CognitiveTrendDao
import com.sahayai.android.core.db.dao.ReminderDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): SahayAIDatabase {
        return Room.databaseBuilder(
            context,
            SahayAIDatabase::class.java,
            "sahayai_db"
        ).build()
    }

    @Provides
    fun provideReminderDao(db: SahayAIDatabase): ReminderDao = db.reminderDao()

    @Provides
    fun provideAlertDao(db: SahayAIDatabase): AlertDao = db.alertDao()

    @Provides
    fun provideCognitiveTrendDao(db: SahayAIDatabase): CognitiveTrendDao = db.cognitiveTrendDao()
}
