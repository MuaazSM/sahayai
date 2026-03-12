package com.sahayai.android.ui.patient.reminders

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.model.Reminder
import com.sahayai.android.domain.repository.ReminderRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class RemindersUiState(
    val reminders: List<Reminder> = emptyList(),
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class RemindersViewModel @Inject constructor(
    private val reminderRepository: ReminderRepository,
    private val prefsRepository: UserPreferencesRepository
) : ViewModel() {

    private var userId: String? = null
    private var remindersJob: Job? = null

    private val _uiState = MutableStateFlow(RemindersUiState())
    val uiState: StateFlow<RemindersUiState> = _uiState

    init {
        observeUser()
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(isRefreshing = true, error = null) }
            val currentUser = userId
            if (currentUser == null) {
                _uiState.update {
                    it.copy(
                        isRefreshing = false,
                        error = "User ID missing. Please redo onboarding."
                    )
                }
                return@launch
            }
            try {
                reminderRepository.refreshReminders(currentUser)
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        error = e.message ?: "Failed to refresh reminders."
                    )
                }
            } finally {
                _uiState.update { it.copy(isRefreshing = false) }
            }
        }
    }

    fun confirmReminder(id: String) {
        viewModelScope.launch {
            when (val result = reminderRepository.confirmReminder(id)) {
                is NetworkResult.Success -> {
                    // Optimistically mark the reminder confirmed in UI state.
                    _uiState.update { state ->
                        val updated = state.reminders.map { reminder ->
                            if (reminder.id == id) reminder.copy(isConfirmed = true)
                            else reminder
                        }
                        state.copy(reminders = updated)
                    }
                }

                is NetworkResult.Error -> {
                    _uiState.update { it.copy(error = result.message) }
                }

                is NetworkResult.Loading -> Unit
            }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    private fun observeUser() {
        viewModelScope.launch {
            prefsRepository.userPreferences.collect { prefs ->
                val newId = prefs.userId.takeIf { it.isNotBlank() } ?: return@collect
                if (newId != userId) {
                    userId = newId
                    loadReminders(newId)
                }
            }
        }
    }

    private fun loadReminders(userId: String) {
        remindersJob?.cancel()
        remindersJob = viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            try {
                reminderRepository.refreshReminders(userId)
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        error = e.message ?: "Failed to refresh reminders."
                    )
                }
            }
            reminderRepository.getReminders(userId).collect { result ->
                when (result) {
                    is NetworkResult.Success -> {
                        _uiState.update {
                            it.copy(
                                reminders = result.data,
                                isLoading = false,
                                isRefreshing = false,
                                error = null
                            )
                        }
                    }

                    is NetworkResult.Error -> {
                        _uiState.update {
                            it.copy(
                                isLoading = false,
                                isRefreshing = false,
                                error = result.message
                            )
                        }
                    }

                    is NetworkResult.Loading -> {
                        _uiState.update { it.copy(isLoading = true) }
                    }
                }
            }
        }
    }
}
