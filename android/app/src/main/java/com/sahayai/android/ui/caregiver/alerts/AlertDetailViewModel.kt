package com.sahayai.android.ui.caregiver.alerts

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.model.Alert
import com.sahayai.android.domain.repository.CaregiverRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AlertDetailUiState(
    val alert: Alert? = null,
    val isLoading: Boolean = false,
    val isAcknowledged: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class AlertDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val caregiverRepository: CaregiverRepository,
    private val prefsRepository: UserPreferencesRepository
) : ViewModel() {

    private val alertId: String = checkNotNull(savedStateHandle["alertId"]) {
        "alertId is required as a navigation argument"
    }

    private val _uiState = MutableStateFlow(AlertDetailUiState())
    val uiState: StateFlow<AlertDetailUiState> = _uiState

    init {
        loadAlert()
    }

    private fun loadAlert() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            val prefs = runCatching { prefsRepository.userPreferences.first() }.getOrNull()
            val patientId = prefs?.patientId?.takeIf { it.isNotBlank() } ?: run {
                _uiState.update { it.copy(isLoading = false, error = "Patient ID not configured.") }
                return@launch
            }

            // Fetch the latest alerts for the patient and find our alertId
            caregiverRepository.getAlerts(patientId).first { result ->
                when (result) {
                    is NetworkResult.Success -> {
                        val found = result.data.find { it.id == alertId }
                        _uiState.update { state ->
                            state.copy(
                                alert = found,
                                isAcknowledged = found?.isAcknowledged ?: false,
                                isLoading = false,
                                error = if (found == null) "Alert not found." else null
                            )
                        }
                        true
                    }
                    is NetworkResult.Error -> {
                        _uiState.update { it.copy(isLoading = false, error = result.message) }
                        true
                    }
                    NetworkResult.Loading -> false
                }
            }
        }
    }

    fun acknowledgeAlert() {
        val alert = _uiState.value.alert ?: return
        if (_uiState.value.isAcknowledged) return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            val prefs = runCatching { prefsRepository.userPreferences.first() }.getOrNull()
            val caregiverId = prefs?.userId?.takeIf { it.isNotBlank() } ?: "unknown"

            when (val result = caregiverRepository.acknowledgeAlert(alert.id, caregiverId)) {
                is NetworkResult.Success -> {
                    _uiState.update { state ->
                        state.copy(
                            isLoading = false,
                            isAcknowledged = true,
                            alert = state.alert?.copy(isAcknowledged = true)
                        )
                    }
                }
                is NetworkResult.Error -> {
                    _uiState.update { it.copy(isLoading = false, error = result.message) }
                }
                NetworkResult.Loading -> Unit
            }
        }
    }

    fun dismissError() {
        _uiState.update { it.copy(error = null) }
    }
}
