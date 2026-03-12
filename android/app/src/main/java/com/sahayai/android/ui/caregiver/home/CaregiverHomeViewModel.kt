package com.sahayai.android.ui.caregiver.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.model.Alert
import com.sahayai.android.domain.model.CaregiverSummary
import com.sahayai.android.domain.repository.AlertWebSocketRepository
import com.sahayai.android.domain.repository.CaregiverRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CaregiverHomeUiState(
    val patientId: String = "",
    val caregiverId: String = "",
    val alerts: List<Alert> = emptyList(),
    val summary: CaregiverSummary? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
    val liveAlertCount: Int = 0,
    val isWebSocketConnected: Boolean = false
)

@HiltViewModel
class CaregiverHomeViewModel @Inject constructor(
    private val caregiverRepository: CaregiverRepository,
    private val prefsRepository: UserPreferencesRepository,
    private val wsRepository: AlertWebSocketRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(CaregiverHomeUiState())
    val uiState: StateFlow<CaregiverHomeUiState> = _uiState

    init {
        loadPrefsAndConnect()
    }

    private fun loadPrefsAndConnect() {
        viewModelScope.launch {
            val prefs = runCatching { prefsRepository.userPreferences.first() }.getOrNull()
                ?: return@launch

            _uiState.update { state ->
                state.copy(
                    patientId = prefs.patientId,
                    caregiverId = prefs.userId
                )
            }

            if (prefs.userId.isNotBlank()) {
                wsRepository.connect(prefs.userId)
                _uiState.update { it.copy(isWebSocketConnected = true) }
                collectWebSocketMessages()
            }

            refreshAlerts()
            refreshSummary()
        }
    }

    private fun collectWebSocketMessages() {
        viewModelScope.launch {
            wsRepository.messages.collect { message ->
                val incoming = message.alert ?: return@collect
                _uiState.update { state ->
                    val updatedAlerts = (listOf(incoming) + state.alerts).take(3)
                    state.copy(
                        alerts = updatedAlerts,
                        liveAlertCount = state.liveAlertCount + 1
                    )
                }
            }
        }
    }

    private fun refreshAlerts() {
        viewModelScope.launch {
            val patientId = _uiState.value.patientId.takeIf { it.isNotBlank() } ?: return@launch
            _uiState.update { it.copy(isLoading = true) }

            caregiverRepository.getAlerts(patientId).collect { result ->
                when (result) {
                    is NetworkResult.Success -> {
                        _uiState.update { state ->
                            state.copy(
                                alerts = result.data.take(3),
                                isLoading = false,
                                error = null
                            )
                        }
                    }
                    is NetworkResult.Error -> {
                        _uiState.update { it.copy(isLoading = false, error = result.message) }
                    }
                    NetworkResult.Loading -> {
                        _uiState.update { it.copy(isLoading = true) }
                    }
                }
            }
        }
    }

    private fun refreshSummary() {
        viewModelScope.launch {
            val patientId = _uiState.value.patientId.takeIf { it.isNotBlank() } ?: return@launch

            when (val result = caregiverRepository.getSummary(patientId)) {
                is NetworkResult.Success -> {
                    _uiState.update { it.copy(summary = result.data, error = null) }
                }
                is NetworkResult.Error -> {
                    _uiState.update { it.copy(error = result.message) }
                }
                NetworkResult.Loading -> Unit
            }
        }
    }

    fun refresh() {
        _uiState.update { it.copy(error = null) }
        refreshAlerts()
        refreshSummary()
    }

    fun disconnectWebSocket() {
        wsRepository.disconnect()
        _uiState.update { it.copy(isWebSocketConnected = false) }
    }

    override fun onCleared() {
        super.onCleared()
        disconnectWebSocket()
    }
}
