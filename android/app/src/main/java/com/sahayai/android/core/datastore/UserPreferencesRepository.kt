package com.sahayai.android.core.datastore

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.sahayai.android.domain.model.UserPreferences
import com.sahayai.android.domain.model.UserRole
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UserPreferencesRepository @Inject constructor(
    private val dataStore: DataStore<Preferences>
) {
    companion object {
        private val ONBOARDING_DONE = booleanPreferencesKey("onboarding_done")
        private val USER_ROLE = stringPreferencesKey("user_role")
        private val USER_ID = stringPreferencesKey("user_id")
        private val PATIENT_ID = stringPreferencesKey("patient_id")
        private val USER_NAME = stringPreferencesKey("user_name")
    }

    val userPreferences: Flow<UserPreferences> = dataStore.data.map { prefs ->
        UserPreferences(
            onboardingDone = prefs[ONBOARDING_DONE] ?: false,
            userRole = prefs[USER_ROLE]?.let {
                runCatching { UserRole.valueOf(it) }.getOrDefault(UserRole.PATIENT)
            } ?: UserRole.PATIENT,
            userId = prefs[USER_ID] ?: "",
            patientId = prefs[PATIENT_ID] ?: "",
            userName = prefs[USER_NAME] ?: ""
        )
    }

    suspend fun saveOnboarding(
        role: UserRole,
        userId: String,
        patientId: String = "",
        userName: String = ""
    ) {
        dataStore.edit { prefs ->
            prefs[ONBOARDING_DONE] = true
            prefs[USER_ROLE] = role.name
            prefs[USER_ID] = userId
            prefs[PATIENT_ID] = patientId
            prefs[USER_NAME] = userName
        }
    }

    suspend fun clearOnboarding() {
        dataStore.edit { prefs ->
            prefs.clear()
        }
    }
}
