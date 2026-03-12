package com.sahayai.android.ui.patient.emergency

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.core.network.SahayAIApiService
import com.sahayai.android.domain.model.StatusRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

data class EmergencyUiState(
    val isSending: Boolean = false,
    val statusMessage: String = "",
    val alertSent: Boolean = false,
    val caregiverNotified: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class EmergencyViewModel @Inject constructor(
    private val prefsRepository: UserPreferencesRepository,
    private val apiService: SahayAIApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(EmergencyUiState())
    val uiState: StateFlow<EmergencyUiState> = _uiState

    fun onSosPressed() {
        if (_uiState.value.isSending || _uiState.value.alertSent) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isSending = true,
                error = null,
                statusMessage = "Sending emergency alert…"
            )

            val prefs = runCatching { prefsRepository.userPreferences.first() }.getOrNull()
            val userId = prefs?.userId?.takeIf { it.isNotBlank() } ?: "unknown"

            val result = runCatching {
                apiService.checkStatus(StatusRequest(userId = userId))
            }.fold(
                onSuccess = { response ->
                    if (response.isSuccessful) {
                        val body = response.body()
                        if (body != null) {
                            NetworkResult.Success(body)
                        } else {
                            NetworkResult.Error("Empty response from server")
                        }
                    } else {
                        NetworkResult.Error("Server error: ${response.code()}", response.code())
                    }
                },
                onFailure = { throwable ->
                    NetworkResult.Error(throwable.message ?: "Network error. Please try again.")
                }
            )

            when (result) {
                is NetworkResult.Success -> {
                    val data = result.data
                    _uiState.value = _uiState.value.copy(
                        isSending = false,
                        alertSent = data.alertSent,
                        caregiverNotified = data.caregiverNotified,
                        statusMessage = if (data.caregiverNotified)
                            "Your caregiver has been notified and is on their way."
                        else
                            data.message.ifBlank { "Alert sent successfully." },
                        error = null
                    )
                }

                is NetworkResult.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isSending = false,
                        error = result.message,
                        statusMessage = ""
                    )
                }

                NetworkResult.Loading -> Unit
            }
        }
    }

    fun dismissError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
