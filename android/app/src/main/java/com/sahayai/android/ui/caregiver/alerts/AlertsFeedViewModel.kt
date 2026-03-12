package com.sahayai.android.ui.caregiver.alerts

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

enum class AlertFilter { ALL, CRITICAL, HIGH, MEDIUM, ACKNOWLEDGED }

data class AlertsFeedUiState(
    val alerts: List<Alert> = emptyList(),
    val filteredAlerts: List<Alert> = emptyList(),
    val selectedFilter: AlertFilter = AlertFilter.ALL,
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class AlertsFeedViewModel @Inject constructor(
    private val caregiverRepository: CaregiverRepository,
    private val prefsRepository: UserPreferencesRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AlertsFeedUiState())
    val uiState: StateFlow<AlertsFeedUiState> = _uiState

    init {
        refreshAlerts()
    }

    fun refreshAlerts() {
        viewModelScope.launch {
            val prefs = runCatching { prefsRepository.userPreferences.first() }.getOrNull()
            val patientId = prefs?.patientId?.takeIf { it.isNotBlank() } ?: return@launch

            _uiState.update { it.copy(isLoading = true, error = null) }

            caregiverRepository.getAlerts(patientId).collect { result ->
                when (result) {
                    is NetworkResult.Success -> {
                        val allAlerts = result.data
                        _uiState.update { state ->
                            state.copy(
                                alerts = allAlerts,
                                filteredAlerts = applyFilter(allAlerts, state.selectedFilter),
                                isLoading = false,
                                error = null
                            )
                        }
                    }
                    is NetworkResult.Error -> {
                        _uiState.update {
                            it.copy(isLoading = false, error = result.message)
                        }
                    }
                    NetworkResult.Loading -> {
                        _uiState.update { it.copy(isLoading = true) }
                    }
                }
            }
        }
    }

    fun setFilter(filter: AlertFilter) {
        _uiState.update { state ->
            state.copy(
                selectedFilter = filter,
                filteredAlerts = applyFilter(state.alerts, filter)
            )
        }
    }

    private fun applyFilter(alerts: List<Alert>, filter: AlertFilter): List<Alert> =
        when (filter) {
            AlertFilter.ALL -> alerts
            AlertFilter.CRITICAL -> alerts.filter { it.priority.uppercase() == "CRITICAL" }
            AlertFilter.HIGH -> alerts.filter { it.priority.uppercase() == "HIGH" }
            AlertFilter.MEDIUM -> alerts.filter { it.priority.uppercase() == "MEDIUM" }
            AlertFilter.ACKNOWLEDGED -> alerts.filter { it.isAcknowledged }
        }
}
