package com.sahayai.android.ui.caregiver.summary

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.model.CaregiverSummary
import com.sahayai.android.domain.model.CognitiveTrendPoint
import com.sahayai.android.domain.repository.CaregiverRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DailySummaryUiState(
    val summary: CaregiverSummary? = null,
    val recentTrends: List<CognitiveTrendPoint> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class DailySummaryViewModel @Inject constructor(
    private val caregiverRepository: CaregiverRepository,
    private val prefsRepository: UserPreferencesRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(DailySummaryUiState())
    val uiState: StateFlow<DailySummaryUiState> = _uiState

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            val prefs = runCatching { prefsRepository.userPreferences.first() }.getOrNull()
            val patientId = prefs?.patientId?.takeIf { it.isNotBlank() } ?: run {
                _uiState.update { it.copy(isLoading = false, error = "Patient ID not configured.") }
                return@launch
            }

            // Load summary
            when (val summaryResult = caregiverRepository.getSummary(patientId)) {
                is NetworkResult.Success -> {
                    _uiState.update { it.copy(summary = summaryResult.data) }
                }
                is NetworkResult.Error -> {
                    _uiState.update { it.copy(error = summaryResult.message) }
                }
                NetworkResult.Loading -> Unit
            }

            // Load last 7 trend points
            caregiverRepository.getCognitiveTrends(patientId).first { result ->
                when (result) {
                    is NetworkResult.Success -> {
                        _uiState.update { state ->
                            state.copy(
                                recentTrends = result.data.takeLast(7),
                                isLoading = false
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
}
