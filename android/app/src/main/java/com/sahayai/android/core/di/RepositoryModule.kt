package com.sahayai.android.core.di

import com.sahayai.android.domain.repository.CaregiverRepository
import com.sahayai.android.domain.repository.CaregiverRepositoryImpl
import com.sahayai.android.domain.repository.ConversationRepository
import com.sahayai.android.domain.repository.ConversationRepositoryImpl
import com.sahayai.android.domain.repository.ReminderRepository
import com.sahayai.android.domain.repository.ReminderRepositoryImpl
import com.sahayai.android.domain.repository.SceneRepository
import com.sahayai.android.domain.repository.SceneRepositoryImpl
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds @Singleton
    abstract fun bindConversationRepository(impl: ConversationRepositoryImpl): ConversationRepository

    @Binds @Singleton
    abstract fun bindSceneRepository(impl: SceneRepositoryImpl): SceneRepository

    @Binds @Singleton
    abstract fun bindReminderRepository(impl: ReminderRepositoryImpl): ReminderRepository

    @Binds @Singleton
    abstract fun bindCaregiverRepository(impl: CaregiverRepositoryImpl): CaregiverRepository
}
