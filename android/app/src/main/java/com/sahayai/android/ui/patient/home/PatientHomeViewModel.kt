package com.sahayai.android.ui.patient.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.model.Reminder
import com.sahayai.android.domain.repository.ReminderRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PatientHomeUiState(
    val userName: String = "",
    val userId: String = "",
    val reminders: List<Reminder> = emptyList(),
    val pendingReminderCount: Int = 0,
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class PatientHomeViewModel @Inject constructor(
    private val prefsRepository: UserPreferencesRepository,
    private val reminderRepository: ReminderRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(PatientHomeUiState())
    val uiState: StateFlow<PatientHomeUiState> = _uiState

    init {
        viewModelScope.launch {
            prefsRepository.userPreferences.collectLatest { prefs ->
                _uiState.value = _uiState.value.copy(
                    userName = prefs.userName.ifEmpty { "Friend" },
                    userId = prefs.userId
                )
                if (prefs.userId.isNotEmpty()) {
                    loadReminders(prefs.userId)
                }
            }
        }
    }

    private fun loadReminders(userId: String) {
        viewModelScope.launch {
            reminderRepository.refreshReminders(userId)
            reminderRepository.getReminders(userId).collectLatest { result ->
                when (result) {
                    is NetworkResult.Success -> _uiState.value = _uiState.value.copy(
                        reminders = result.data,
                        pendingReminderCount = result.data.count { !it.isConfirmed },
                        isLoading = false,
                        error = null
                    )
                    is NetworkResult.Loading -> _uiState.value = _uiState.value.copy(
                        isLoading = true
                    )
                    is NetworkResult.Error -> _uiState.value = _uiState.value.copy(
                        error = result.message,
                        isLoading = false
                    )
                }
            }
        }
    }
}
